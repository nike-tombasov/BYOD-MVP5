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
from PySide6.QtCore import QObject, QEvent, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
PIN_LENGTH = 6

COLORS = {
    "green": "#8FB996",
    "yellow": "#C9B26A",
    "red": "#B97A7A",
    "blue": "#7B8FB8",
    "text": "#D6D6D6",
    "line": "#626262",
    "bg": "#2E2E2E",
    "btn_disabled": "#4A4A4A",
    "btn_active": "#6A6A6A",
    "btn_hover": "#8A8A8A",
}


def status_html(text: str, color: str) -> str:
    return f"<span style='color:{color}'>■</span> {text}"


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
    last_actual_status: str = "FREE"


class UISignals(QObject):
    set_connect_status = Signal(str, str)
    set_room_info = Signal(str, str)
    set_room_status = Signal(str)
    set_channel_status = Signal(str, str, str, bool)
    set_channel_sound = Signal(str, str)
    set_button_state = Signal(str, str, bool, str)
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
        self.signals.set_room_status.connect(self._ui_set_room_status)
        self.signals.set_channel_status.connect(self._ui_set_channel_status)
        self.signals.set_channel_sound.connect(self._ui_set_channel_sound)
        self.signals.set_button_state.connect(self._ui_set_button_state)
        self.signals.show_error.connect(self._ui_show_error)
        self.signals.set_channel_label.connect(self._ui_set_channel_label)
        self.signals.set_device_enabled.connect(self._ui_set_device_enabled)
        self.signals.set_row_visible.connect(self._ui_set_row_visible)

        self.setWindowTitle("BYOD Publisher UI v0.3")
        self.resize(600, 560)

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
        self.setStyleSheet(
            f"""
            QWidget {{ background-color: {COLORS['bg']}; color: {COLORS['text']}; }}
            QPushButton {{
                background-color: {COLORS['btn_active']};
                color: {COLORS['text']};
                border: 1px solid #5A5A5A;
                border-radius: 4px;
                padding: 4px 10px;
                text-align: center;
            }}
            QPushButton:hover:!disabled {{ background-color: {COLORS['btn_hover']}; }}
            QPushButton:disabled {{ background-color: {COLORS['btn_disabled']}; color: #A8A8A8; }}
            QLineEdit, QComboBox {{
                background-color: #3A3A3A;
                color: {COLORS['text']};
                border: 1px solid #555;
                padding: 3px;
            }}
            """
        )

        base_font = QFont("Segoe UI", 10)
        self.setFont(base_font)

        root = QVBoxLayout()
        root.setSpacing(8)

        conn_row = QHBoxLayout()
        conn_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.ip_label = QLabel("Server IP:")
        self.ip_input = QLineEdit(self.backend_ws_url)
        self.ip_input.setFixedWidth(250)

        self.pin_label = QLabel("PIN:")
        self.pin_input = QLineEdit(self.default_pin)
        self.pin_input.setMaxLength(PIN_LENGTH)
        self.pin_input.setFixedWidth(90)

        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.connect_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        conn_row.addWidget(self.ip_label)
        conn_row.addWidget(self.ip_input)
        conn_row.addSpacing(16)
        conn_row.addWidget(self.pin_label)
        conn_row.addWidget(self.pin_input)
        conn_row.addStretch(1)
        conn_row.addWidget(self.connect_btn)
        root.addLayout(conn_row)

        self.connect_status = QLabel(status_html("IDLE", COLORS["blue"]))
        self.connect_status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.connect_status)

        root.addWidget(self._line())

        self.room_name_label = QLabel("")
        self.room_name_label.setWordWrap(True)
        self.room_status_label = QLabel("")
        self.room_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.room_name_label)
        root.addWidget(self.room_status_label)

        root.addWidget(self._line())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        channels_widget = QWidget()
        channels_layout = QVBoxLayout()
        channels_layout.setSpacing(6)

        for channel_id in CHANNEL_IDS:
            row = self._build_channel_row(channel_id)
            self.channel_rows[channel_id] = row
            self.channels[channel_id] = ChannelRuntime(channel_id=channel_id, label="N/A", listen=True, owner=None)
            channels_layout.addLayout(row["line1"])
            channels_layout.addLayout(row["line2"])
            channels_layout.addWidget(self._line())

        channels_widget.setLayout(channels_layout)
        scroll.setWidget(channels_widget)
        root.addWidget(scroll)

        self.setLayout(root)

    def _line(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {COLORS['line']};")
        line.setFixedHeight(1)
        return line

    def _build_channel_row(self, channel_id: str) -> dict:
        line1 = QHBoxLayout()
        title = QLabel(f"{channel_id.replace('channel_', '')} - N/A")
        status = QLabel(status_html("FREE", COLORS["green"]))
        line1.addWidget(title)
        line1.addStretch(1)
        line1.addWidget(status)

        line2 = QHBoxLayout()
        device_box = NoWheelComboBox()
        device_box.addItem("NONE", None)
        device_box.currentIndexChanged.connect(lambda _, cid=channel_id: self._on_device_changed(cid))

        onair_btn = QPushButton("ON AIR")
        onair_btn.clicked.connect(lambda: self._on_onair_click(channel_id))
        onair_btn.installEventFilter(self)

        rms = QLabel("NO SOUND")
        rms.setFixedWidth(88)
        rms.setAlignment(Qt.AlignmentFlag.AlignCenter)

        line2.addWidget(device_box)
        line2.addWidget(onair_btn)
        line2.addWidget(rms)

        return {
            "title": title,
            "status": status,
            "device_box": device_box,
            "button": onair_btn,
            "rms": rms,
            "line1": line1,
            "line2": line2,
        }

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            for channel_id, row in self.channel_rows.items():
                if row["button"] is obj:
                    dev_data = row["device_box"].currentData()
                    if dev_data is None and not row["button"].isEnabled():
                        self.signals.set_channel_status.emit(channel_id, "NO DEVICE", "red", True)
        if event.type() == QEvent.Type.Leave:
            for channel_id, row in self.channel_rows.items():
                if row["button"] is obj:
                    last_status = self.channels[channel_id].last_actual_status
                    self._set_actual_channel_status(channel_id, last_status)
        return super().eventFilter(obj, event)

    def _set_preconnect_state(self) -> None:
        self.signals.set_room_info.emit("", "")
        self.signals.set_room_status.emit("")
        for channel_id in CHANNEL_IDS:
            self.signals.set_channel_label.emit(channel_id, "N/A")
            self.signals.set_button_state.emit(channel_id, "ON AIR", False, "disabled")
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
    def _ui_set_connect_status(self, text: str, color: str) -> None:
        self.connect_status.setText(status_html(text, COLORS[color]))

    def _ui_set_room_info(self, room_name: str, room_status: str) -> None:
        self.room_name_label.setText(room_name)
        if room_status:
            color = "green" if room_status == "OPENED" else ("yellow" if room_status == "BLOCKED" else "red")
            self.room_status_label.setText(status_html(room_status, COLORS[color]))
        else:
            self.room_status_label.setText("")

    def _ui_set_room_status(self, room_status: str) -> None:
        if not room_status:
            self.room_status_label.setText("")

    def _ui_set_channel_status(self, channel_id: str, text: str, color: str, temporary: bool) -> None:
        self.channel_rows[channel_id]["status"].setText(status_html(text, COLORS[color]))
        if not temporary:
            self.channels[channel_id].last_actual_status = text

    def _ui_set_channel_sound(self, channel_id: str, text: str) -> None:
        self.channel_rows[channel_id]["rms"].setText(text)

    def _ui_set_button_state(self, channel_id: str, text: str, enabled: bool, mode: str) -> None:
        btn: QPushButton = self.channel_rows[channel_id]["button"]
        btn.setText(text)
        btn.setEnabled(enabled)

        if mode == "streaming":
            btn.setStyleSheet("background-color: #A85A5A; color: #F0F0F0; border:1px solid #8F4747; border-radius:4px; padding:4px 10px;")
        elif mode == "pending":
            btn.setStyleSheet("background-color: #A79256; color: #F0F0F0; border:1px solid #8A7745; border-radius:4px; padding:4px 10px;")
        elif mode == "engaged":
            btn.setStyleSheet("background-color: #586B8E; color: #E8E8E8; border:1px solid #47597A; border-radius:4px; padding:4px 10px;")
        else:
            btn.setStyleSheet("")

    def _ui_set_channel_label(self, channel_id: str, text: str) -> None:
        idx = channel_id.replace("channel_", "")
        self.channel_rows[channel_id]["title"].setText(f"{idx} - {text}")

    def _ui_set_device_enabled(self, channel_id: str, enabled: bool) -> None:
        self.channel_rows[channel_id]["device_box"].setEnabled(enabled)

    def _ui_set_row_visible(self, channel_id: str, visible: bool) -> None:
        row = self.channel_rows[channel_id]
        for key in ["title", "status", "device_box", "button", "rms"]:
            row[key].setVisible(visible)

    def _ui_show_error(self, text: str) -> None:
        self._ui_set_connect_status(text, "red")
        self.connect_btn.setEnabled(True)

    # helpers
    def _set_actual_channel_status(self, channel_id: str, text: str) -> None:
        color = "green"
        if text in {"Connecting..."}:
            color = "yellow"
        elif text in {"NO DEVICE", "DEVICE ERROR", "Device error. Check system samplerate (48000 Hz only)"}:
            color = "red"
        elif text in {"ENGAGED"}:
            color = "blue"
        elif text in {"STREAMING"}:
            color = "green"
        self.signals.set_channel_status.emit(channel_id, text, color, False)

    def _refresh_channel_controls(self, channel_id: str) -> None:
        runtime = self.channels[channel_id]
        row = self.channel_rows[channel_id]
        dev_data = row["device_box"].currentData()

        if runtime.owner == self.publisher_id:
            self.signals.set_button_state.emit(channel_id, "STOP", True, "streaming" if runtime.streaming else "pending")
            self.signals.set_device_enabled.emit(channel_id, False)
            return

        if runtime.owner is not None and runtime.owner != self.publisher_id:
            self.signals.set_button_state.emit(channel_id, "ON AIR", False, "engaged")
            self.signals.set_device_enabled.emit(channel_id, True)
            return

        # owner is None
        self.signals.set_device_enabled.emit(channel_id, True)
        if dev_data is None:
            self.signals.set_button_state.emit(channel_id, "ON AIR", False, "disabled")
            return

        _, sr, _ = dev_data
        if int(sr) != SAMPLE_RATE:
            self.signals.set_button_state.emit(channel_id, "ON AIR", False, "disabled")
            return

        self.signals.set_button_state.emit(channel_id, "ON AIR", True, "default")

    # actions
    def _on_connect_clicked(self) -> None:
        self.connect_btn.setEnabled(False)
        self.signals.set_connect_status.emit("Connecting...", "yellow")
        self.backend_ws_url = self.ip_input.text().strip() or self.backend_ws_url
        pin = self.pin_input.text().strip() or self.default_pin
        asyncio.run_coroutine_threadsafe(self._run_client(pin), self.loop)

    def _on_device_changed(self, channel_id: str) -> None:
        runtime = self.channels[channel_id]
        if runtime.desired_on_air or runtime.streaming:
            return

        dev_data = self.channel_rows[channel_id]["device_box"].currentData()
        if dev_data is None:
            self._set_actual_channel_status(channel_id, "FREE")
            self._refresh_channel_controls(channel_id)
            return

        _, sr, _ = dev_data
        if int(sr) != SAMPLE_RATE:
            self._set_actual_channel_status(channel_id, "Device error. Check system samplerate (48000 Hz only)")
            self._refresh_channel_controls(channel_id)
            return

        if runtime.owner is None:
            self._set_actual_channel_status(channel_id, "FREE")
        self._refresh_channel_controls(channel_id)

    def _on_onair_click(self, channel_id: str) -> None:
        runtime = self.channels[channel_id]
        if self.backend_ws is None or self.publisher_id is None:
            self._set_actual_channel_status(channel_id, "CONNECTION ERROR")
            return

        dev_data = self.channel_rows[channel_id]["device_box"].currentData()

        if not runtime.desired_on_air:
            if dev_data is None:
                self.signals.set_channel_status.emit(channel_id, "NO DEVICE", "red", True)
                return
            _, sr, _ = dev_data
            if int(sr) != SAMPLE_RATE:
                self.signals.set_channel_status.emit(channel_id, "Device error. Check system samplerate (48000 Hz only)", "red", True)
                return

            self._set_actual_channel_status(channel_id, "Connecting...")
            self.signals.set_device_enabled.emit(channel_id, False)
            self.signals.set_button_state.emit(channel_id, "STOP", True, "pending")
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
            self.signals.show_error.emit(f"CONNECTION ERROR")
            print(f"[publisher] connection error: {exc}")

    async def _connect_backend(self, pin: str) -> None:
        self.backend_ws = await websockets.connect(self.backend_ws_url)
        await self.backend_ws.send(json.dumps({"type": "connecting", "pin": pin, "hostname": socket.gethostname()}))
        msg = json.loads(await self.backend_ws.recv())
        if msg.get("type") == "error":
            raise RuntimeError("Invalid PIN" if msg.get("code") == "INVALID_PIN" else msg.get("code", "UNKNOWN"))

        self.publisher_id = msg["publisher_id"]
        self.token = msg["token"]
        self.livekit_url = msg["livekit_url"]
        self.signals.set_connect_status.emit("CONNECTED", "green")
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
                    self._set_actual_channel_status(cid, "ENGAGED")
                    self._refresh_channel_controls(cid)
            elif msg.get("type") == "error":
                self.signals.show_error.emit("CONNECTION ERROR")

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
            runtime.label = ch.get("channel_label", "N/A")
            runtime.listen = bool(ch.get("listen", True))
            self.signals.set_channel_label.emit(channel_id, runtime.label)

            if runtime.owner == self.publisher_id:
                self._set_actual_channel_status(channel_id, "STREAMING" if runtime.streaming else "Connecting...")
                self._refresh_channel_controls(channel_id)
                asyncio.run_coroutine_threadsafe(self._ensure_streaming(channel_id), self.loop)
            elif runtime.owner is None:
                runtime.desired_on_air = False
                self._set_actual_channel_status(channel_id, "FREE")
                self._refresh_channel_controls(channel_id)
                asyncio.run_coroutine_threadsafe(self._ensure_stopped(channel_id), self.loop)
            else:
                runtime.desired_on_air = False
                self._set_actual_channel_status(channel_id, "ENGAGED")
                self._refresh_channel_controls(channel_id)
                asyncio.run_coroutine_threadsafe(self._ensure_stopped(channel_id), self.loop)

    async def _ensure_streaming(self, channel_id: str) -> None:
        rt = self.channels[channel_id]
        if rt.streaming:
            return

        dev_data = self.channel_rows[channel_id]["device_box"].currentData()
        if dev_data is None:
            self._set_actual_channel_status(channel_id, "NO DEVICE")
            rt.desired_on_air = False
            self._refresh_channel_controls(channel_id)
            return

        device_id, sr, max_channels = dev_data
        if int(sr) != SAMPLE_RATE:
            self._set_actual_channel_status(channel_id, "Device error. Check system samplerate (48000 Hz only)")
            rt.desired_on_air = False
            self._refresh_channel_controls(channel_id)
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

        rt.capture_stream = sd.InputStream(
            device=int(device_id),
            samplerate=SAMPLE_RATE,
            channels=min(max_channels, 2),
            blocksize=FRAME_SIZE,
            dtype="float32",
            callback=callback,
        )
        rt.capture_stream.start()

        rt.source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=CHANNELS)
        rt.local_track = rtc.LocalAudioTrack.create_audio_track(channel_id, rt.source)
        publication = await self.room.local_participant.publish_track(rt.local_track)
        rt.track_sid = publication.sid
        rt.streaming = True

        self._set_actual_channel_status(channel_id, "STREAMING")
        self._refresh_channel_controls(channel_id)
        rt.sender_task = asyncio.create_task(self._sender_loop(channel_id))

    async def _ensure_stopped(self, channel_id: str) -> None:
        rt = self.channels[channel_id]
        if not rt.streaming and rt.capture_stream is None and rt.sender_task is None:
            self._refresh_channel_controls(channel_id)
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
        self._refresh_channel_controls(channel_id)

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

                frame = rtc.AudioFrame(
                    data=pcm,
                    sample_rate=SAMPLE_RATE,
                    num_channels=CHANNELS,
                    samples_per_channel=FRAME_SIZE,
                )
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
