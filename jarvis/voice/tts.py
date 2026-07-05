"""Text-to-speech using pyttsx3 — offline, and uses each OS's native voices
(SAPI5 on Windows, NSSpeechSynthesizer on macOS).

There's no free way to get a truly cinematic "movie JARVIS" voice offline —
that needs a paid cloud TTS service (e.g. ElevenLabs). Instead, we pick the
closest free option: a British-accented system voice, which is the biggest
lever available for free/offline TTS to *sound* more like JARVIS.
"""

from __future__ import annotations

import random

import pyttsx3

from jarvis.core.config import settings

# Said the instant the wake word fires, before the command is even recorded —
# a quick in-character acknowledgment rather than a flat "Yes?".
_WAKE_ACKNOWLEDGEMENTS = [
    "Yes, boss?",
    "At your service.",
    "Go ahead, I'm listening.",
    "Yes, boss, what can I do for you?",
]

# Ordered by preference: macOS ships "Daniel" (en-GB) on most systems, and
# Windows/other platforms may have similarly-named British voices installed.
# JARVIS_TTS_VOICE (in .env) overrides this — set it to any substring of a
# voice name/id from `python -m jarvis.voice.tts --list-voices`.
_PREFERRED_VOICE_KEYWORDS = [
    "daniel", "arthur", "oliver", "en_gb", "en-gb", "british", "great britain",
]

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


def speak(text: str) -> None:
    if not text:
        return
    # A fresh engine per call, not a cached singleton: pyttsx3's macOS driver
    # (NSSpeechSynthesizer) is known to hang on a second runAndWait() call
    # against the same engine instance, which silently froze the wake-word
    # loop as soon as we added a second speak() call per exchange (the wake
    # acknowledgement, followed later by the spoken reply).
    engine = pyttsx3.init()
    engine.setProperty("rate", settings.tts_rate)
    _pick_voice(engine)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def speak_wake_acknowledgement() -> None:
    speak(random.choice(_WAKE_ACKNOWLEDGEMENTS))


if __name__ == "__main__":
    import sys

    if "--list-voices" in sys.argv:
        for voice_id, name in list_voices():
            print(f"{name}\t{voice_id}")
    else:
        speak("This is JARVIS, your personal assistant, online and ready.")
