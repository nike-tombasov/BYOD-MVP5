import asyncio
import time
import numpy as np
import sounddevice as sd
from collections import OrderedDict
from livekit import rtc

# ================== SETTINGS ==================

LIVEKIT_URL = "ws://91.197.99.193:7880"
TOKEN = "PASTE_PUBLISHER_TOKEN_HERE"

LANGUAGES = ["ru", "en", "de"]

SAMPLE_RATE = 48000
CHANNELS = 2
FRAME_SIZE = 960
RMS_THRESHOLD = 0.001

# ================== DEVICE SCAN ==================

raw_devices = sd.query_devices()

unique_inputs = OrderedDict()
for idx, dev in enumerate(raw_devices):
    if dev["max_input_channels"] > 0:
        name = dev["name"]
        if name not in unique_inputs:
            unique_inputs[name] = idx

print("\n=== Available input devices ===")
devices = list(unique_inputs.items())
for i, (name, idx) in enumerate(devices):
    print(f"[{i}] {name} (sd index {idx})")

# ================== LANGUAGE → DEVICE ==================

lang_to_device = {}

for lang in LANGUAGES:
    while True:
        try:
            choice = int(input(f"\nSelect device number for language '{lang}': "))
            if 0 <= choice < len(devices):
                lang_to_device[lang] = devices[choice][1]
                break
            else:
                print("Invalid selection")
        except ValueError:
            print("Enter a valid number")

# ================== AUDIO WORKER ==================

class AudioWorker:
    def __init__(self, device_index, audio_source, loop):
        self.device_index = device_index
        self.audio_source = audio_source
        self.loop = loop
        self.audio_detected = False

    def callback(self, indata, frames, time_info, status):
        rms = np.sqrt(np.mean(indata ** 2))
        if rms > RMS_THRESHOLD:
            self.audio_detected = True

        pcm = (indata * 32767).astype(np.int16)
        pcm_bytes = pcm.tobytes()

        frame = rtc.AudioFrame(
            data=pcm_bytes,
            sample_rate=SAMPLE_RATE,
            num_channels=CHANNELS,
            samples_per_channel=frames,
        )

        asyncio.run_coroutine_threadsafe(
            self.audio_source.capture_frame(frame),
            self.loop,
        )

    def run(self):
        with sd.InputStream(
            device=self.device_index,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=FRAME_SIZE,
            dtype="float32",
            callback=self.callback,
        ):
            while True:
                time.sleep(1)

# ================== MAIN ==================

async def main():
    loop = asyncio.get_running_loop()

    room = rtc.Room()

    @room.on("connection_state_changed")
    def on_state(state):
        print(f"[LiveKit] State: {state}")

    @room.on("disconnected")
    def on_disconnected(reason):
        print(f"[LiveKit] Disconnected: {reason}")

    print("[LiveKit] Connecting...")
    await room.connect(LIVEKIT_URL, token=TOKEN)
    print("[LiveKit] Connected")

    workers = []

    for lang in LANGUAGES:
        source = rtc.AudioSource(
            sample_rate=SAMPLE_RATE,
            num_channels=CHANNELS,
        )

        track = rtc.LocalAudioTrack.create_audio_track(
            name=lang,
            source=source,
        )

        await room.local_participant.publish_track(track)
        print(f"[OK] Published track '{lang}'")

        worker = AudioWorker(
            device_index=lang_to_device[lang],
            audio_source=source,
            loop=loop,
        )

        workers.append(worker)
        asyncio.create_task(asyncio.to_thread(worker.run))

    all_confirmed = set()

    while len(all_confirmed) < len(LANGUAGES):
        for lang, worker in zip(LANGUAGES, workers):
            if worker.audio_detected and lang not in all_confirmed:
                print(f"[OK] Audio detected for '{lang}'")
                all_confirmed.add(lang)
        await asyncio.sleep(1)

    print("[OK] All tracks confirmed. Publishing continues silently.")

# ================== RUN ==================

if __name__ == "__main__":
    asyncio.run(main())