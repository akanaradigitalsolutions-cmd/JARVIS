"""Wake-word detection using openWakeWord, running fully locally/offline.

Uses openWakeWord's pretrained "Hey JARVIS" model by default. The first run
downloads the (small) model files automatically; after that it works
offline.

Want a custom phrase (e.g. "JARVIS wake up") instead? Training one needs a
GPU and isn't something that can run in a plain sandbox — see
ARCHITECTURE.md#custom-wake-word for how to train one on Google Colab
(free GPU). Once you have the trained .onnx/.tflite file, point
JARVIS_WAKE_WORD_MODEL (in .env) at it — no code changes needed, this
module picks it up automatically.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from openwakeword.model import Model
from openwakeword.utils import download_models

from jarvis.core.config import settings

DEFAULT_MODEL = "hey_jarvis_v0.1"
DEFAULT_MODEL_KEY = "hey_jarvis"  # the name download_models() expects
DEFAULT_THRESHOLD = 0.5
CHUNK_SAMPLES = 1280  # openWakeWord expects ~80ms chunks at 16kHz


class WakeWordDetector:
    def __init__(self, model_path: str | None = None, threshold: float = DEFAULT_THRESHOLD) -> None:
        custom_path = model_path or settings.wake_word_model
        target = custom_path or DEFAULT_MODEL

        if not custom_path:
            # openWakeWord does NOT auto-download pretrained models on
            # Model() init — it only resolves the local path they'd live
            # at, and fails to load if they're not there yet. This is a
            # no-op after the first successful run (it skips files that
            # already exist).
            download_models([DEFAULT_MODEL_KEY])

        # A custom model is loaded by file path; openWakeWord keys its
        # predictions dict by the file's stem in that case, rather than by
        # a name you supply — a pretrained model is keyed by its own name.
        self.model_name = Path(target).stem if custom_path else target
        self.threshold = threshold
        # Force the onnx backend explicitly. openWakeWord defaults to
        # tflite, which needs the separate `tflite-runtime` package —
        # that package has no wheels for newer Python versions (e.g. 3.13)
        # or reliable Apple Silicon support, so it silently fails to
        # install on many machines even though openwakeword lists it as a
        # dependency. onnxruntime (already a hard dependency of
        # openwakeword) works everywhere we actually need it to.
        self._model = Model(wakeword_models=[target], inference_framework="onnx")

    def process_chunk(self, chunk: np.ndarray) -> bool:
        """Feed one int16 PCM chunk (ideally CHUNK_SAMPLES long, 16kHz mono).

        Returns True the moment the wake word score crosses the threshold.
        """
        predictions = self._model.predict(chunk)
        score = predictions.get(self.model_name, 0.0)
        return score >= self.threshold
