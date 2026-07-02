"""Text-to-speech using pyttsx3 — offline, and uses each OS's native voices
(SAPI5 on Windows, NSSpeechSynthesizer on macOS).

There's no free way to get a truly cinematic "movie JARVIS" voice offline —
that needs a paid cloud TTS service (e.g. ElevenLabs). Instead, we pick the
closest free option: a British-accented system voice, which is the biggest
lever available for free/offline TTS to *sound* more like JARVIS.
"""

from __future__ import annotations

import pyttsx3

from jarvis.core.config import settings

# Ordered by preference: macOS ships "Daniel" (en-GB) on most systems, and
# Windows/other platforms may have similarly-named British voices installed.
# JARVIS_TTS_VOICE (in .env) overrides this — set it to any substring of a
# voice name/id from `python -m jarvis.voice.tts --list-voices`.
_PREFERRED_VOICE_KEYWORDS = [
    "daniel", "arthur", "oliver", "en_gb", "en-gb", "british", "great britain",
]

_engine = None


def list_voices() -> list[tuple[str, str]]:
    engine = pyttsx3.init()
    return [(v.id, v.name) for v in engine.getProperty("voices") or []]


def _pick_voice(engine) -> None:
    voices = engine.getProperty("voices") or []
    if not voices:
        return

    if settings.tts_voice:
        for v in voices:
            if settings.tts_voice in f"{v.name} {v.id}".lower():
                engine.setProperty("voice", v.id)
                return

    for keyword in _PREFERRED_VOICE_KEYWORDS:
        for v in voices:
            if keyword in f"{v.name} {v.id}".lower():
                engine.setProperty("voice", v.id)
                return
    # else: leave the OS default voice


def _get_engine():
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", settings.tts_rate)
        _pick_voice(_engine)
    return _engine


def speak(text: str) -> None:
    if not text:
        return
    engine = _get_engine()
    engine.say(text)
    engine.runAndWait()


if __name__ == "__main__":
    import sys

    if "--list-voices" in sys.argv:
        for voice_id, name in list_voices():
            print(f"{name}\t{voice_id}")
    else:
        speak("This is JARVIS, your personal assistant, online and ready.")
