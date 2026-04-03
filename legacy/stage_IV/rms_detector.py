import numpy as np


class RMSDetector:

    def __init__(self, threshold=0.001):
        self.threshold = threshold

    def detect(self, audio_frame):

        if len(audio_frame) == 0:
            return False

        rms = np.sqrt(np.mean(np.square(audio_frame)))

        return rms > self.threshold
