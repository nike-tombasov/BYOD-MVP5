import argparse
import asyncio
import contextlib
import json
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
import websockets
from PySide6.QtCore import QObject, QEvent, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from livekit import rtc

SAMPLE_RATE = 48000
CHANNELS = 2
FRAME_SIZE = 960
QUEUE_MAXSIZE = 32
HEARTBEAT_SECONDS = 5
CHANNEL_IDS = [f"channel_{i}" for i in range(32)]


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


@dataclass
class ChannelRuntime:
    channel_id: str
    label: str
    listen: bool
    owner: str | None
    desired_on_air: bool = False
    streaming: bool = False
    audio_queue: queue.Queue[bytes] | None = None
    capture_stream: sd.InputStream | None = None
    source: rtc.AudioSource | None = None
    local_track: rtc.LocalAudioTrack | None = None
    track_sid: str | None = None
    sender_task: asyncio.Task | None = None


class UISignals(QObject):
    set_connect_status = Signal(str)
    set_room_info = Signal(str, str)
    set_channel_status = Signal(str, str)
    set_channel_sound = Signal(str, str)
    set_button_state = Signal(str, str, bool)
    show_error = Signal(str)
    set_channel_label = Signal(str, str)
    set_device_enabled = Signal(str, bool)
    set_row_visible = Signal(str, bool)


class PublisherUI(QWidget):
    def __init__(self, backend_ws_url: str, pin: str) -> None:
        super().__init__()
        self.backend_ws_url = backend_ws_url
        self.default_pin = pin

        self.signals = UISignals()
        self.signals.set_connect_status.connect(self._ui_set_connect_status)
        self.signals.set_room_info.connect(self._ui_set_room_info)
        self.signals.set_channel_status.connect(self._ui_set_channel_status)
        self.signals.set_channel_sound.connect(self._ui_set_channel_sound)
        self.signals.set_button_state.connect(self._ui_set_button_state)
        self.signals.show_error.connect(self._ui_show_error)
        self.signals.set_channel_label.connect(self._ui_set_channel_label)
        self.signals.set_device_enabled.connect(self._ui_set_device_enabled)
        self.signals.set_row_visible.connect(self._ui_set_row_visible)

        self.setWindowTitle("BYOD Publisher UI v0.3")
        self.resize(860, 560)

        self.publisher_id: str | None = None
        self.token: str | None = None
        self.livekit_url: str | None = None
        self.backend_ws = None
        self.room: rtc.Room | None = None

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        self.heartbeat_task: asyncio.Task | None = None
        self.backend_task: asyncio.Task | None = None
        self.shutting_down = False

        self.channel_rows: dict[str, dict] = {}
        self.channels: dict[str, ChannelRuntime] = {}

        self._build_layout()
        self._populate_all_devices()
        self._set_preconnect_state()

    def _build_layout(self) -> None:
        root = QVBoxLayout()

        conn_row_1 = QHBoxLayout()
        self.ip_label = QLabel("Backend WS")
        self.ip_input = QLineEdit(self.backend_ws_url)
        self.ip_input.setPlaceholderText("ws://127.0.0.1:8000/ws/publisher")
        self.pin_label = QLabel("PIN")
        self.pin_input = QLineEdit(self.default_pin)
        self.pin_input.setMaxLength(16)
        conn_row_1.addWidget(self.ip_label)
        conn_row_1.addWidget(self.ip_input)
        conn_row_1.addWidget(self.pin_label)
        conn_row_1.addWidget(self.pin_input)
        root.addLayout(conn_row_1)

        conn_row_2 = QHBoxLayout()
        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.connect_status = QLabel("IDLE")
        conn_row_2.addWidget(self.connect_btn)
        conn_row_2.addWidget(self.connect_status)
        root.addLayout(conn_row_2)

        self.room_name_label = QLabel("")
        self.room_status_label = QLabel("")
        root.addWidget(self.room_name_label)
        root.addWidget(self.room_status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        channels_widget = QWidget()
        channels_layout = QVBoxLayout()

        for channel_id in CHANNEL_IDS:
            row = self._build_channel_row(channel_id)
            self.channel_rows[channel_id] = row
            self.channels[channel_id] = ChannelRuntime(channel_id=channel_id, label="N/A", listen=True, owner=None)
            channels_layout.addLayout(row["line1"])
            channels_layout.addLayout(row["line2"])
            channels_layout.addLayout(row["line3"])

        channels_widget.setLayout(channels_layout)
        scroll.setWidget(channels_widget)
        root.addWidget(scroll)

        self.setLayout(root)

    def _build_channel_row(self, channel_id: str) -> dict:
        line1 = QHBoxLayout()
        id_label = QLabel(channel_id)
        name_label = QLabel("N/A")
        line1.addWidget(id_label)
        line1.addWidget(name_label)

        line2 = QHBoxLayout()
        device_box = NoWheelComboBox()
        device_box.addItem("NONE", None)
        device_box.currentIndexChanged.connect(lambda _, cid=channel_id: self._on_device_changed(cid))
        onair_btn = QPushButton("ON AIR")
        onair_btn.clicked.connect(lambda: self._on_onair_click(channel_id))
        onair_btn.installEventFilter(self)
        line2.addWidget(device_box)
        line2.addWidget(onair_btn)

        line3 = QHBoxLayout()
        state_label = QLabel("FREE")
        sound_label = QLabel("NO SOUND")
        line3.addWidget(state_label)
        line3.addWidget(sound_label)

        return {
            "id_label": id_label,
            "name_label": name_label,
            "device_box": device_box,
            "button": onair_btn,
            "state": state_label,
            "sound": sound_label,
            "line1": line1,
            "line2": line2,
            "line3": line3,
        }

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            for channel_id, row in self.channel_rows.items():
                if row["button"] is obj and not row["button"].isEnabled():
                    dev_data = row["device_box"].currentData()
                    if dev_data is None:
                        self.signals.set_channel_status.emit(channel_id, "NO DEVICE")
        return super().eventFilter(obj, event)

    def _set_preconnect_state(self) -> None:
        for channel_id in CHANNEL_IDS:
            self.signals.set_channel_label.emit(channel_id, "N/A")
            self.signals.set_button_state.emit(channel_id, "ON AIR", False)
            self.signals.set_device_enabled.emit(channel_id, False)

    def _populate_all_devices(self) -> None:
        devices = sd.query_devices()
        apis = sd.query_hostapis()
        usable = []
        for idx, dev in enumerate(devices):
            if dev["max_input_channels"] <= 0:
                continue
            api_name = apis[dev["hostapi"]]["name"]
            if "WASAPI" not in api_name:
                continue
            usable.append((idx, dev["name"], int(dev["default_samplerate"]), int(dev["max_input_channels"])))

        for row in self.channel_rows.values():
            box: NoWheelComboBox = row["device_box"]
            for idx, name, sr, max_channels in usable:
                box.addItem(f"{name} | {sr} Hz | ch {max_channels}", (idx, sr, max_channels))

    # UI slots
    def _ui_set_connect_status(self, text: str) -> None:
        self.connect_status.setText(text)

    def _ui_set_room_info(self, room_name: str, room_status: str) -> None:
        self.room_name_label.setText(room_name)
        self.room_status_label.setText(room_status)

    def _ui_set_channel_status(self, channel_id: str, text: str) -> None:
        self.channel_rows[channel_id]["state"].setText(text)

    def _ui_set_channel_sound(self, channel_id: str, text: str) -> None:
        self.channel_rows[channel_id]["sound"].setText(text)

    def _ui_set_button_state(self, channel_id: str, text: str, enabled: bool) -> None:
        btn: QPushButton = self.channel_rows[channel_id]["button"]
        btn.setText(text)
        btn.setEnabled(enabled)

    def _ui_set_channel_label(self, channel_id: str, text: str) -> None:
        self.channel_rows[channel_id]["name_label"].setText(text)

    def _ui_set_device_enabled(self, channel_id: str, enabled: bool) -> None:
        self.channel_rows[channel_id]["device_box"].setEnabled(enabled)

    def _ui_set_row_visible(self, channel_id: str, visible: bool) -> None:
        row = self.channel_rows[channel_id]
        for key in ["id_label", "name_label", "device_box", "button", "state", "sound"]:
            row[key].setVisible(visible)

    def _ui_show_error(self, text: str) -> None:
        self.connect_status.setText(text)
        self.connect_btn.setEnabled(True)

    # actions
    def _on_connect_clicked(self) -> None:
        self.connect_btn.setEnabled(False)
        self.signals.set_connect_status.emit("Connecting...")
        self.backend_ws_url = self.ip_input.text().strip() or self.backend_ws_url
        pin = self.pin_input.text().strip() or self.default_pin
        asyncio.run_coroutine_threadsafe(self._run_client(pin), self.loop)

    def _on_device_changed(self, channel_id: str) -> None:
        runtime = self.channels[channel_id]
        row = self.channel_rows[channel_id]
        btn: QPushButton = row["button"]
        dev_data = row["device_box"].currentData()

        if runtime.desired_on_air or runtime.streaming:
            return

        if dev_data is None:
            self.signals.set_channel_status.emit(channel_id, "FREE")
            btn.setEnabled(False)
            return

        _, sr, _ = dev_data
        if int(sr) != SAMPLE_RATE:
            self.signals.set_channel_status.emit(channel_id, "Device error. Check system samplerate (48000 Hz only)")
            btn.setEnabled(False)
        else:
            if runtime.owner is None:
                self.signals.set_channel_status.emit(channel_id, "FREE")
            btn.setEnabled(runtime.owner in (None, self.publisher_id))

    def _on_onair_click(self, channel_id: str) -> None:
        runtime = self.channels[channel_id]
        if self.backend_ws is None or self.publisher_id is None:
            self.signals.set_channel_status.emit(channel_id, "CONNECTION ERROR")
            return

        row = self.channel_rows[channel_id]
        dev_data = row["device_box"].currentData()

        if not runtime.desired_on_air:
            if dev_data is None:
                self.signals.set_channel_status.emit(channel_id, "NO DEVICE")
                return
            _, sr, _ = dev_data
            if int(sr) != SAMPLE_RATE:
                self.signals.set_channel_status.emit(channel_id, "Device error. Check system samplerate (48000 Hz only)")
                return

            self.signals.set_channel_status.emit(channel_id, "Connecting...")
            self.signals.set_device_enabled.emit(channel_id, False)
            runtime.desired_on_air = True
            msg = {"type": "on_air", "publisher_id": self.publisher_id, "channel_id": channel_id, "request_on_air_ts": time.time()}
        else:
            runtime.desired_on_air = False
            msg = {"type": "stop", "publisher_id": self.publisher_id, "channel_id": channel_id, "request_off_air_ts": time.time()}

        asyncio.run_coroutine_threadsafe(self.backend_ws.send(json.dumps(msg)), self.loop)

    # async
    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _run_client(self, pin: str) -> None:
        try:
            await self._connect_backend(pin)
            await self._connect_livekit()
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.backend_task = asyncio.create_task(self._backend_loop())
            await asyncio.gather(self.heartbeat_task, self.backend_task)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.signals.show_error.emit(f"CONNECTION ERROR: {exc}")

    async def _connect_backend(self, pin: str) -> None:
        self.backend_ws = await websockets.connect(self.backend_ws_url)
        await self.backend_ws.send(json.dumps({"type": "connecting", "pin": pin, "hostname": socket.gethostname()}))
        msg = json.loads(await self.backend_ws.recv())
        if msg.get("type") == "error":
            code = msg.get("code", "UNKNOWN")
            raise RuntimeError("Invalid PIN" if code == "INVALID_PIN" else code)

        self.publisher_id = msg["publisher_id"]
        self.token = msg["token"]
        self.livekit_url = msg["livekit_url"]
        self.signals.set_connect_status.emit("CONNECTED")
        self._apply_state(msg["state"])

    async def _connect_livekit(self) -> None:
        if self.room is not None:
            return
        self.room = rtc.Room()
        await self.room.connect(self.livekit_url, self.token)

    async def _heartbeat_loop(self) -> None:
        while not self.shutting_down:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            if self.backend_ws:
                with contextlib.suppress(Exception):
                    await self.backend_ws.send(json.dumps({"type": "heartbeat", "ts": time.time()}))

    async def _backend_loop(self) -> None:
        async for raw in self.backend_ws:
            if self.shutting_down:
                return
            msg = json.loads(raw)
            if msg.get("type") == "state":
                self._apply_state(msg["state"])
            elif msg.get("type") == "on_air_rejected":
                cid = msg.get("channel_id")
                if cid in self.channels:
                    self.channels[cid].desired_on_air = False
                    self.signals.set_device_enabled.emit(cid, True)
                    self.signals.set_channel_status.emit(cid, "ENGAGED")
            elif msg.get("type") == "error":
                self.signals.show_error.emit(f"ERROR: {msg.get('code')}")

    def _apply_state(self, state: dict) -> None:
        self.signals.set_room_info.emit(state.get("room_name", ""), state.get("room_status", ""))

        known = {c["channel_id"]: c for c in state.get("channels", [])}
        for cid in CHANNEL_IDS:
            self.signals.set_row_visible.emit(cid, cid in known)

        for channel_id, ch in known.items():
            if channel_id not in self.channels:
                continue
            runtime = self.channels[channel_id]
            runtime.owner = ch.get("owner")
            runtime.label = ch.get("channel_label", channel_id)
            runtime.listen = bool(ch.get("listen", True))
            self.signals.set_channel_label.emit(channel_id, runtime.label)

            if runtime.owner == self.publisher_id:
                self.signals.set_button_state.emit(channel_id, "STOP", True)
                self.signals.set_device_enabled.emit(channel_id, False)
                self.signals.set_channel_status.emit(channel_id, "STREAMING" if runtime.streaming else "Connecting...")
                asyncio.run_coroutine_threadsafe(self._ensure_streaming(channel_id), self.loop)
            elif runtime.owner is None:
                runtime.desired_on_air = False
                self.signals.set_device_enabled.emit(channel_id, True)
                self._on_device_changed(channel_id)
                asyncio.run_coroutine_threadsafe(self._ensure_stopped(channel_id), self.loop)
            else:
                runtime.desired_on_air = False
                self.signals.set_button_state.emit(channel_id, "ON AIR", False)
                self.signals.set_device_enabled.emit(channel_id, True)
                self.signals.set_channel_status.emit(channel_id, "ENGAGED")
                asyncio.run_coroutine_threadsafe(self._ensure_stopped(channel_id), self.loop)

    async def _ensure_streaming(self, channel_id: str) -> None:
        rt = self.channels[channel_id]
        if rt.streaming:
            return

        dev_data = self.channel_rows[channel_id]["device_box"].currentData()
        if dev_data is None:
            self.signals.set_channel_status.emit(channel_id, "NO DEVICE")
            rt.desired_on_air = False
            return

        device_id, sr, max_channels = dev_data
        if int(sr) != SAMPLE_RATE:
            self.signals.set_channel_status.emit(channel_id, "Device error. Check system samplerate (48000 Hz only)")
            rt.desired_on_air = False
            return

        rt.audio_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[audio:{channel_id}] status {status}")
            audio = indata
            if audio.shape[1] == 1:
                audio = np.repeat(audio, 2, axis=1)
            elif audio.shape[1] > 2:
                audio = audio[:, :2]

            rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
            self.signals.set_channel_sound.emit(channel_id, "SOUND OK" if rms > 0.001 else "NO SOUND")

            pcm = (audio[:, :2] * 32767).astype(np.int16).tobytes()
            try:
                rt.audio_queue.put_nowait(pcm)
            except queue.Full:
                _ = rt.audio_queue.get_nowait()
                rt.audio_queue.put_nowait(pcm)

        rt.capture_stream = sd.InputStream(device=int(device_id), samplerate=SAMPLE_RATE, channels=min(max_channels, 2), blocksize=FRAME_SIZE, dtype="float32", callback=callback)
        rt.capture_stream.start()

        rt.source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=CHANNELS)
        rt.local_track = rtc.LocalAudioTrack.create_audio_track(channel_id, rt.source)
        publication = await self.room.local_participant.publish_track(rt.local_track)
        rt.track_sid = publication.sid
        rt.streaming = True
        self.signals.set_channel_status.emit(channel_id, "STREAMING")
        rt.sender_task = asyncio.create_task(self._sender_loop(channel_id))

    async def _ensure_stopped(self, channel_id: str) -> None:
        rt = self.channels[channel_id]
        if not rt.streaming and rt.capture_stream is None and rt.sender_task is None:
            return
        rt.streaming = False

        if rt.sender_task:
            rt.sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await rt.sender_task
            rt.sender_task = None

        if rt.capture_stream:
            with contextlib.suppress(Exception):
                rt.capture_stream.stop()
                rt.capture_stream.close()
            rt.capture_stream = None

        if self.room and rt.track_sid:
            with contextlib.suppress(Exception):
                await self.room.local_participant.unpublish_track(rt.track_sid)

        rt.track_sid = None
        rt.local_track = None
        rt.source = None
        rt.audio_queue = None
        self.signals.set_channel_sound.emit(channel_id, "NO SOUND")

    async def _sender_loop(self, channel_id: str) -> None:
        rt = self.channels[channel_id]
        try:
            while rt.streaming and not self.shutting_down:
                if not rt.source or not rt.audio_queue:
                    await asyncio.sleep(0.02)
                    continue
                try:
                    pcm = rt.audio_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue

                frame = rtc.AudioFrame(data=pcm, sample_rate=SAMPLE_RATE, num_channels=CHANNELS, samples_per_channel=FRAME_SIZE)
                await rt.source.capture_frame(frame)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            print(f"[sender:{channel_id}] error: {exc}")

    async def _shutdown_async(self) -> None:
        self.shutting_down = True
        for cid in CHANNEL_IDS:
            with contextlib.suppress(Exception):
                await self._ensure_stopped(cid)

        for task in [self.heartbeat_task, self.backend_task]:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        if self.backend_ws:
            with contextlib.suppress(Exception):
                await self.backend_ws.close()
        if self.room:
            with contextlib.suppress(Exception):
                await self.room.disconnect()

    def closeEvent(self, event) -> None:
        future = asyncio.run_coroutine_threadsafe(self._shutdown_async(), self.loop)
        with contextlib.suppress(Exception):
            future.result(timeout=3)
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread.is_alive():
            self.thread.join(timeout=2)
        event.accept()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="ws://127.0.0.1:8000/ws/publisher")
    parser.add_argument("--pin", default="123456")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    ui = PublisherUI(args.backend, args.pin)
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
