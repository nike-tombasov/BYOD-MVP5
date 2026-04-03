import sys
import asyncio
import threading
import numpy as np
import sounddevice as sd

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QLineEdit
)

from PySide6.QtCore import Signal, QObject

from livekit import rtc

from audio_stream import AudioStream
from rms_detector import RMSDetector


LIVEKIT_URL = "ws://localhost:7880"
TOKEN = "PASTE_PUBLISHER_TOKEN"

TRACKS = ["track_0", "track_1", "track_2"]


class UISignals(QObject):

    sound_update = Signal(str, str)


class PublisherUI(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("BYOD Publisher")
        self.resize(720, 420)

        self.signals = UISignals()
        self.signals.sound_update.connect(self.update_sound_status)

        layout = QVBoxLayout()

        # -------------------------
        # BLOCK 1 CONNECTION
        # -------------------------

        row1 = QHBoxLayout()

        self.ip_label = QLabel("Enter IP")
        self.ip_input = QLineEdit()

        self.pin_label = QLabel("Enter PIN")
        self.pin_input = QLineEdit()

        row1.addWidget(self.ip_label)
        row1.addWidget(self.ip_input)
        row1.addWidget(self.pin_label)
        row1.addWidget(self.pin_input)

        layout.addLayout(row1)

        row2 = QHBoxLayout()

        self.connect_btn = QPushButton("CONNECT")
        self.connect_status = QLabel("DISCONNECTED")

        row2.addWidget(self.connect_btn)
        row2.addWidget(self.connect_status)

        layout.addLayout(row2)

        # -------------------------
        # BLOCK 2 ROOM
        # -------------------------

        self.room_name = QLabel("test")
        self.room_name.setWordWrap(True)

        self.room_status = QLabel("room_status")

        layout.addWidget(self.room_name)
        layout.addWidget(self.room_status)

        # -------------------------
        # TRACK BLOCK
        # -------------------------

        self.track_widgets = []

        for track in TRACKS:

            # row 1
            row1 = QHBoxLayout()

            track_uid = QLabel(track)
            track_name = QLabel("test")

            row1.addWidget(track_uid)
            row1.addWidget(track_name)

            layout.addLayout(row1)

            # row 2
            row2 = QHBoxLayout()

            device = QComboBox()
            device.addItem("NONE", None)

            onair = QPushButton("ON AIR")
            onair.setStyleSheet("background-color: grey; color: white")

            row2.addWidget(device)
            row2.addWidget(onair)

            layout.addLayout(row2)

            # row 3
            row3 = QHBoxLayout()

            status = QLabel("FREE")
            detector = QLabel("NO SOUND")

            row3.addWidget(status)
            row3.addWidget(detector)

            layout.addLayout(row3)

            self.track_widgets.append({
                "track": track,
                "device": device,
                "button": onair,
                "status": status,
                "detector": detector,
                "onair": False
            })

        self.setLayout(layout)

        self.populate_devices()

        self.connect_btn.clicked.connect(self.start)

        self.loop = asyncio.new_event_loop()

        self.thread = threading.Thread(
            target=self.run_loop,
            daemon=True
        )

        self.thread.start()

        self.connected = False

        self.room = None

        self.sources = {}
        self.queues = {}

        self.streams = {}

        self.rms_streams = {}

        self.detector = RMSDetector()

    # -------------------------

    def populate_devices(self):

        devices = sd.query_devices()
        apis = sd.query_hostapis()

        inputs = []

        for i, dev in enumerate(devices):

            api = apis[dev["hostapi"]]["name"]

            if dev["max_input_channels"] <= 0:
                continue

            if "WASAPI" not in api:
                continue

            inputs.append((i, dev["name"], dev["default_samplerate"]))

        for w in self.track_widgets:

            box = w["device"]

            for i, name, sr in inputs:
                box.addItem(f"{name} ({sr})", (i, sr))

            box.currentIndexChanged.connect(
                lambda _, w=w: self.device_changed(w)
            )

    # -------------------------

    def device_changed(self, widget):

        track = widget["track"]
        data = widget["device"].currentData()

        if data is None:
            widget["status"].setText("FREE")
            return

        device_id, samplerate = data

        if samplerate != 48000:
            widget["status"].setText("DEVICE ERROR (48000 Hz only)")
            return

        if widget["onair"]:
            widget["status"].setText("STREAMING")
        else:
            widget["status"].setText("FREE")

        # restart stream if device changed during streaming

        if widget["onair"]:

            if track in self.streams:
                self.streams[track].stop()

            stream = AudioStream(
                device_id,
                track,
                self.queues[track],
                self.loop
            )

            stream.start()

            self.streams[track] = stream

    # -------------------------

    def run_loop(self):

        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    # -------------------------

    def start(self):

        if self.connected:
            return

        asyncio.run_coroutine_threadsafe(
            self.run_livekit(),
            self.loop
        )

    # -------------------------

    async def run_livekit(self):

        print("CONNECTING LIVEKIT")

        self.room = rtc.Room()

        await self.room.connect(LIVEKIT_URL, TOKEN)

        print("CONNECTED")

        self.connected = True

        self.connect_status.setText("CONNECTED")

        for track in TRACKS:

            source = rtc.AudioSource(48000, 2)

            local_track = rtc.LocalAudioTrack.create_audio_track(
                track,
                source
            )

            await self.room.local_participant.publish_track(local_track)

            self.sources[track] = source
            self.queues[track] = asyncio.Queue(maxsize=32)

            asyncio.create_task(self.audio_sender(track))

        for w in self.track_widgets:

            w["button"].clicked.connect(
                lambda _, w=w: self.toggle_onair(w)
            )

    # -------------------------

    def toggle_onair(self, widget):

        track = widget["track"]
        data = widget["device"].currentData()

        if data is None:
            widget["status"].setText("NO DEVICE")
            return

        device_id, samplerate = data

        if samplerate != 48000:
            widget["status"].setText("DEVICE ERROR (48000 Hz only)")
            return

        if not widget["onair"]:

            widget["status"].setText("CONNECTING")

            stream = AudioStream(
                device_id,
                track,
                self.queues[track],
                self.loop
            )

            stream.start()

            self.streams[track] = stream

            widget["onair"] = True

            widget["button"].setText("STOP")
            widget["button"].setStyleSheet("background-color: red; color: white")

            widget["status"].setText("STREAMING")

        else:

            widget["onair"] = False

            if track in self.streams:
                self.streams[track].stop()
                del self.streams[track]

            widget["button"].setText("ON AIR")
            widget["button"].setStyleSheet("background-color: grey; color: white")

            widget["status"].setText("FREE")

    # -------------------------

    def update_sound_status(self, track, text):

        for w in self.track_widgets:

            if w["track"] == track:
                w["detector"].setText(text)

    # -------------------------

    async def audio_sender(self, track):

        source = self.sources[track]
        queue = self.queues[track]

        while True:

            data = await queue.get()

            widget = None

            for w in self.track_widgets:
                if w["track"] == track:
                    widget = w
                    break

            if not widget or not widget["onair"]:
                continue

            pcm16 = (data * 32767).astype(np.int16)

            frame = rtc.AudioFrame(
                data=pcm16.tobytes(),
                sample_rate=48000,
                num_channels=2,
                samples_per_channel=960
            )

            try:
                await source.capture_frame(frame)
            except Exception:
                widget["status"].setText("ENGAGED")


def main():

    app = QApplication(sys.argv)

    ui = PublisherUI()
    ui.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()