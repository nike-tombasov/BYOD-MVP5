# Publisher UI v0.3 snapshot (pre-visual v0.4 changes)
import argparse
import asyncio
import contextlib
import json
import queue
import socket
import time
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
import websockets
from livekit import rtc


SAMPLE_RATE = 48000
CHANNELS = 2
FRAME_SIZE = 960
QUEUE_MAXSIZE = 32
CHANNEL_ID = "channel_0"


@dataclass
class BackendSession:
    publisher_id: str
    token: str
    livekit_url: str


class AudioCapture:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.queue: queue.Queue[bytes] = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self.stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[audio] status: {status}")

        if indata.shape[1] == 1:
            indata = np.repeat(indata, 2, axis=1)

        pcm = (indata[:, :2] * 32767).astype(np.int16).tobytes()

        try:
            self.queue.put_nowait(pcm)
        except queue.Full:
            _ = self.queue.get_nowait()
            self.queue.put_nowait(pcm)

    def open(self, device: int | None = None) -> None:
        if self.stream is not None:
            return

        self.stream = sd.InputStream(
            device=device,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=FRAME_SIZE,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()
        print("[audio] input stream opened")

    def close(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            print("[audio] input stream closed")


class PublisherApp:
    def __init__(self, backend_ws_url: str, pin: str) -> None:
        self.backend_ws_url = backend_ws_url
        self.pin = pin
        self.session: BackendSession | None = None
        self.backend_ws = None
        self.capture = AudioCapture(asyncio.get_running_loop())
        self.room: rtc.Room | None = None
        self.track: rtc.LocalAudioTrack | None = None
        self.source: rtc.AudioSource | None = None
        self.sender_task: asyncio.Task | None = None
        self.streaming = False

    async def connect_backend(self) -> None:
        self.backend_ws = await websockets.connect(self.backend_ws_url)
        print(f"[backend] websocket connected url={self.backend_ws_url}")

        await self.backend_ws.send(
            _json(
                {
                    "type": "connecting",
                    "pin": self.pin,
                    "hostname": socket.gethostname(),
                }
            )
        )
        raw = await self.backend_ws.recv()
        msg = _from_json(raw)

        if msg.get("type") == "error":
            raise RuntimeError(f"backend error: {msg}")

        self.session = BackendSession(
            publisher_id=msg["publisher_id"], token=msg["token"], livekit_url=msg["livekit_url"]
        )
        print(f"[backend] connected as {self.session.publisher_id}")

        self.capture.open()
        print("[publisher] ready for ON AIR")

    async def connect_livekit(self) -> None:
        if self.room is not None:
            return

        assert self.session is not None
        self.room = rtc.Room()
        await self.room.connect(self.session.livekit_url, self.session.token)
        print("[livekit] connected")

    async def start_streaming(self) -> None:
        if self.streaming:
            print("[livekit] start_streaming skipped: already streaming")
            return

        await self.connect_livekit()
        self.source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=CHANNELS)
        self.track = rtc.LocalAudioTrack.create_audio_track(CHANNEL_ID, self.source)
        assert self.room is not None
        await self.room.local_participant.publish_track(self.track)
        self.sender_task = asyncio.create_task(self.sender_loop())
        self.streaming = True
        print(f"[livekit] publish started for {CHANNEL_ID}")

    async def stop_streaming(self) -> None:
        if not self.streaming:
            print("[livekit] stop_streaming skipped: already stopped")
            return

        self.streaming = False

        if self.sender_task:
            self.sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.sender_task
            self.sender_task = None

        if self.room and self.track:
            await self.room.local_participant.unpublish_track(self.track.sid)
            print(f"[livekit] unpublished {CHANNEL_ID}")
            self.track = None

    async def sender_loop(self) -> None:
        assert self.source is not None
        while True:
            pcm = await asyncio.to_thread(self.capture.queue.get)
            frame = rtc.AudioFrame(
                data=pcm,
                sample_rate=SAMPLE_RATE,
                num_channels=CHANNELS,
                samples_per_channel=FRAME_SIZE,
            )
            await self.source.capture_frame(frame)

    async def send_heartbeats(self) -> None:
        while True:
            await asyncio.sleep(5)
            if self.backend_ws is None:
                continue
            await self.backend_ws.send(_json({"type": "heartbeat", "ts": time.time()}))
            print("[backend] heartbeat sent")

    async def handle_backend_messages(self) -> None:
        assert self.backend_ws is not None
        async for raw in self.backend_ws:
            msg = _from_json(raw)
            msg_type = msg.get("type")
            if msg_type != "state":
                print(f"[backend] {msg}")
                continue

            channel = next((c for c in msg["state"]["channels"] if c["channel_id"] == CHANNEL_ID), None)
            if channel is None:
                continue

            owner = channel.get("owner")
            print(f"[backend] state channel={CHANNEL_ID} owner={owner}")
            if owner == self.session.publisher_id:
                await self.start_streaming()
            else:
                await self.stop_streaming()

    async def command_loop(self) -> None:
        assert self.backend_ws is not None
        print("[cmd] type: onair | stop | quit")
        while True:
            cmd = await asyncio.to_thread(input, "> ")
            cmd = cmd.strip().lower()
            if cmd == "onair":
                print(f"[cmd] ON AIR requested channel={CHANNEL_ID}")
                await self.backend_ws.send(
                    _json(
                        {
                            "type": "on_air",
                            "publisher_id": self.session.publisher_id,
                            "channel_id": CHANNEL_ID,
                            "request_on_air_ts": time.time(),
                        }
                    )
                )
            elif cmd == "stop":
                print(f"[cmd] STOP requested channel={CHANNEL_ID}")
                await self.stop_streaming()
                await self.backend_ws.send(
                    _json(
                        {
                            "type": "stop",
                            "publisher_id": self.session.publisher_id,
                            "channel_id": CHANNEL_ID,
                            "request_off_air_ts": time.time(),
                        }
                    )
                )
            elif cmd == "quit":
                print("[cmd] quit requested")
                await self.stop_streaming()
                break

    async def run(self) -> None:
        await self.connect_backend()
        tasks = [
            asyncio.create_task(self.send_heartbeats()),
            asyncio.create_task(self.handle_backend_messages()),
            asyncio.create_task(self.command_loop()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            if task.exception():
                raise task.exception()

        self.capture.close()
        if self.room:
            await self.room.disconnect()


def _json(payload: dict) -> str:
    return json.dumps(payload)


def _from_json(raw: str) -> dict:
    return json.loads(raw)


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="ws://127.0.0.1:8000/ws/publisher")
    parser.add_argument("--pin", default="123456")
    args = parser.parse_args()

    app = PublisherApp(args.backend, args.pin)
    await app.run()


if __name__ == "__main__":
    asyncio.run(async_main())
