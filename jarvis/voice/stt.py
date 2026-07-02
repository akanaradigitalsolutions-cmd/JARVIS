"""Speech-to-text using faster-whisper. Runs fully locally/offline — no
audio ever leaves the machine at this stage; only the transcribed text is
sent to the Claude API by the orchestrator.
"""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

# "small.en" is a good accuracy/speed tradeoff on a laptop CPU. Drop to
# "base.en" on older/slower machines, or "medium.en" if you have a GPU.
MODEL_SIZE = "small.en"

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device="auto", compute_type="int8")
    return _model


def transcribe(audio: np.ndarray) -> str:
    """Transcribe a mono float32 buffer, sampled at 16kHz, into text."""
    if audio.size == 0:
        return ""
    model = _get_model()
    segments, _info = model.transcribe(audio, language="en", vad_filter=True)
    return " ".join(segment.text.strip() for segment in segments).strip()
