"""Wake-word detection using openWakeWord, running fully locally/offline.

Uses openWakeWord's pretrained "hey jarvis" model. The first run downloads
the (small) model files automatically; after that it works offline.
"""

from __future__ import annotations

import numpy as np
from openwakeword.model import Model

DEFAULT_MODEL = "hey_jarvis_v0.1"
DEFAULT_THRESHOLD = 0.5
CHUNK_SAMPLES = 1280  # openWakeWord expects ~80ms chunks at 16kHz


class WakeWordDetector:
    def __init__(self, model_name: str = DEFAULT_MODEL, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self._model = Model(wakeword_models=[model_name])

    def process_chunk(self, chunk: np.ndarray) -> bool:
        """Feed one int16 PCM chunk (ideally CHUNK_SAMPLES long, 16kHz mono).

        Returns True the moment the wake word score crosses the threshold.
        """
        predictions = self._model.predict(chunk)
        score = predictions.get(self.model_name, 0.0)
        return score >= self.threshold
