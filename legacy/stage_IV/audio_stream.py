import asyncio
import sounddevice as sd


class AudioStream:

    def __init__(self, device_id, track_uid, queue, loop):

        self.device_id = device_id
        self.track_uid = track_uid
        self.queue = queue
        self.loop = loop

        self.stream = None

    def start(self):

        if self.stream:
            return

        def callback(indata, frames, time, status):

            if status:
                print("AUDIO STATUS:", status)

            audio = indata.copy()

            try:
                asyncio.run_coroutine_threadsafe(
                    self.queue.put(audio),
                    self.loop
                )
            except:
                pass

        self.stream = sd.InputStream(
            device=self.device_id,
            channels=2,
            samplerate=48000,
            blocksize=960,
            callback=callback
        )

        self.stream.start()

        print("STREAM OPEN:", self.track_uid)

    def stop(self):

        if not self.stream:
            return

        try:
            self.stream.stop()
            self.stream.close()
        except:
            pass

        self.stream = None

        print("STREAM CLOSED:", self.track_uid)