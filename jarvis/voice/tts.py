"""Text-to-speech using pyttsx3 — offline, and uses each OS's native voices
(SAPI5 on Windows, NSSpeechSynthesizer on macOS)."""

from __future__ import annotations

import pyttsx3

from jarvis.core.config import settings

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", settings.tts_rate)
    return _engine


def speak(text: str) -> None:
    if not text:
        return
    engine = _get_engine()
    engine.say(text)
    engine.runAndWait()
