import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from livekit import rtc


@dataclass
class ChannelWriter:
    channel_id: str
    channel_label: str
    output_path: Path
    state: str = "IDLE"
    process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if self.process is not None:
            return
        self.state = "WAITING_TRACK"
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-f",
            "s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-i",
            "pipe:0",
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(self.output_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

    async def write_pcm(self, pcm_bytes: bytes) -> None:
        if self.process is None or self.process.stdin is None:
            return
        if self.state != "RECORDING":
            self.state = "RECORDING"
        self.process.stdin.write(pcm_bytes)
        await self.process.stdin.drain()

    async def stop(self) -> None:
        if self.process is None:
            self.state = "STOPPED"
            return
        self.state = "STOPPING"
        with contextlib.suppress(Exception):
            if self.process.stdin:
                self.process.stdin.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.process.wait(), timeout=8)
        self.process = None
        self.state = "STOPPED"


class RecorderManager:
    def __init__(
        self,
        livekit_url_getter: Callable[[], str],
        token_factory: Callable[[str], str],
        room_name_getter: Callable[[], str],
        channels_snapshot_getter: Callable[[], list[dict[str, Any]]],
        on_session_state: Callable[[bool, int | None, list[dict[str, Any]]], None],
        logger: Callable[[str], None],
    ) -> None:
        self._livekit_url_getter = livekit_url_getter
        self._token_factory = token_factory
        self._room_name_getter = room_name_getter
        self._channels_snapshot_getter = channels_snapshot_getter
        self._on_session_state = on_session_state
        self._logger = logger

        self._running = False
        self._loop_task: asyncio.Task | None = None
        self._room: rtc.Room | None = None

        self._session_active = False
        self._session_started_ts: int | None = None
        self._session_stamp: str | None = None
        self._writers: dict[str, ChannelWriter] = {}
        self._stream_tasks: dict[str, asyncio.Task] = {}

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run(), name="recorder-manager")
        self._logger("recorder started")

    async def shutdown(self) -> None:
        self._running = False
        await self.stop_session(reason="shutdown")
        if self._room:
            with contextlib.suppress(Exception):
                await self._room.disconnect()
            self._room = None
        if self._loop_task:
            self._loop_task.cancel()
            with contextlib.suppress(Exception):
                await self._loop_task

    async def _run(self) -> None:
        while self._running:
            disconnected_event = asyncio.Event()
            try:
                self._room = rtc.Room()

                @self._room.on("connected")
                def _on_connected() -> None:
                    self._logger("LiveKit connected")

                @self._room.on("disconnected")
                def _on_disconnected(reason: Any) -> None:
                    self._logger(f"LiveKit disconnected: {reason}")
                    disconnected_event.set()

                @self._room.on("track_published")
                def _on_track_published(publication: Any, participant: Any) -> None:
                    with contextlib.suppress(Exception):
                        publication.set_subscribed(True)
                    self._logger(f"track published sid={getattr(publication, 'sid', '?')} name={getattr(publication, 'name', '')}")

                @self._room.on("track_subscribed")
                def _on_track_subscribed(track: Any, publication: Any, participant: Any) -> None:
                    channel_id = str(getattr(publication, "name", ""))
                    if not channel_id:
                        return
                    self._logger(f"track subscribed channel={channel_id}")
                    task = asyncio.create_task(
                        self._consume_track(channel_id, track, getattr(publication, "sid", channel_id)),
                        name=f"recorder-track-{channel_id}",
                    )
                    self._stream_tasks[f"{channel_id}:{getattr(publication, 'sid', channel_id)}"] = task

                @self._room.on("track_unsubscribed")
                def _on_track_unsubscribed(track: Any, publication: Any, participant: Any) -> None:
                    channel_id = str(getattr(publication, "name", ""))
                    sid = str(getattr(publication, "sid", channel_id))
                    key = f"{channel_id}:{sid}"
                    task = self._stream_tasks.pop(key, None)
                    if task:
                        task.cancel()
                    self._logger(f"track unsubscribed channel={channel_id}")

                token = self._token_factory("recorder_service")
                await self._room.connect(self._livekit_url_getter(), token)

                for participant in self._room.remote_participants.values():
                    for publication in participant.track_publications.values():
                        if getattr(publication, "kind", None) == rtc.TrackKind.KIND_AUDIO:
                            with contextlib.suppress(Exception):
                                publication.set_subscribed(True)

                await disconnected_event.wait()
            except Exception as exc:
                self._logger(f"reconnect attempt due to error: {exc}")
            finally:
                for key, task in list(self._stream_tasks.items()):
                    task.cancel()
                    self._stream_tasks.pop(key, None)

            if self._running:
                await asyncio.sleep(3)

    async def _consume_track(self, channel_id: str, track: Any, publication_sid: str) -> None:
        writer = self._writers.get(channel_id)
        if writer is None:
            return
        try:
            stream = rtc.AudioStream(track=track, sample_rate=48000, num_channels=2)
            async for event in stream:
                if not self._session_active:
                    continue
                await writer.write_pcm(bytes(event.frame.data))
        except Exception as exc:
            self._logger(f"recording failure channel={channel_id} sid={publication_sid} error={exc}")

    @staticmethod
    def _safe_label(label: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label)
        return cleaned[:80] or "channel"

    async def start_session(self, reason: str) -> None:
        if self._session_active:
            return

        channels = self._channels_snapshot_getter()
        started_ts = int(datetime.now(timezone.utc).timestamp())
        stamp = datetime.fromtimestamp(started_ts, tz=timezone.utc).strftime("%Y%m%d-%H%M%S")

        writers: dict[str, ChannelWriter] = {}
        for channel in channels:
            channel_id = str(channel["channel_id"])
            label = str(channel.get("channel_label") or channel_id)
            safe_label = self._safe_label(label)
            output_path = Path("recordings") / f"{stamp}-{channel_id}-{safe_label}.mp3"
            writer = ChannelWriter(channel_id=channel_id, channel_label=label, output_path=output_path)
            try:
                await writer.start()
                self._logger(f"writer created channel={channel_id} file={output_path}")
            except Exception as exc:
                self._logger(f"ffmpeg error channel={channel_id} error={exc}")
            writers[channel_id] = writer

        self._writers = writers
        self._session_active = True
        self._session_started_ts = started_ts
        self._session_stamp = stamp
        self._publish_session_state()
        self._logger(f"session started reason={reason}")

    async def stop_session(self, reason: str) -> None:
        if not self._session_active and not self._writers:
            return
        for channel_id, writer in list(self._writers.items()):
            try:
                await writer.stop()
                self._logger(f"writer closed channel={channel_id}")
            except Exception as exc:
                self._logger(f"ffmpeg error on close channel={channel_id} error={exc}")
        self._writers.clear()
        self._session_active = False
        self._session_started_ts = None
        self._session_stamp = None
        self._publish_session_state()
        self._logger(f"session stopped reason={reason}")

    def _publish_session_state(self) -> None:
        files = [
            {
                "channel_id": writer.channel_id,
                "path": str(writer.output_path),
                "state": writer.state,
            }
            for writer in self._writers.values()
        ]
        self._on_session_state(self._session_active, self._session_started_ts, files)
