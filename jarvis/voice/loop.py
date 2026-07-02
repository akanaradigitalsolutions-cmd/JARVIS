"""Continuous voice loop: listens for the wake word, records your command,
transcribes it, sends it to the orchestrator, and speaks the reply back.

Run with `jarvis --voice`. Requires `pip install -e ".[voice]"` and a
working microphone/speaker — test this on your actual Mac/Windows machine,
not in a headless environment.
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd

from jarvis.core.config import settings
from jarvis.core.llm import ClaudeCLINotAvailableError
from jarvis.core.memory import SessionMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.voice.stt import transcribe, warmup as warmup_stt
from jarvis.voice.tts import speak
from jarvis.voice.wake_word import CHUNK_SAMPLES, WakeWordDetector

SAMPLE_RATE = 16000
MAX_COMMAND_SECONDS = 8
SILENCE_RMS_THRESHOLD = 0.01
SILENCE_HOLD_SECONDS = 1.2
COMMAND_BLOCK_SECONDS = 0.1


def _record_command(stream: sd.InputStream) -> np.ndarray:
    """Reads from the already-open stream until ~1.2s of silence, or the
    max duration is hit, and returns the recorded audio as float32."""
    frames: list[np.ndarray] = []
    silence_run = 0.0
    block_samples = int(SAMPLE_RATE * COMMAND_BLOCK_SECONDS)
    max_blocks = int(MAX_COMMAND_SECONDS / COMMAND_BLOCK_SECONDS)

    for _ in range(max_blocks):
        block, _overflowed = stream.read(block_samples)
        block = block.flatten()
        frames.append(block)
        rms = float(np.sqrt(np.mean(np.square(block))))
        if rms < SILENCE_RMS_THRESHOLD:
            silence_run += COMMAND_BLOCK_SECONDS
            if silence_run >= SILENCE_HOLD_SECONDS:
                break
        else:
            silence_run = 0.0

    return np.concatenate(frames) if frames else np.zeros(0, dtype=np.float32)


def run() -> None:
    print(f"JARVIS voice mode. Say \"{settings.wake_word}\" to wake me up. Ctrl+C to quit.")

    try:
        orchestrator = Orchestrator(memory=SessionMemory())
    except ClaudeCLINotAvailableError as exc:
        print(f"Setup needed: {exc}")
        return

    print("Loading wake-word model (first run downloads a few small files, may take a moment)...", flush=True)
    detector = WakeWordDetector()
    print("Wake-word model ready.", flush=True)

    warmup_stt()

    print(
        "Opening microphone (macOS may show a permission prompt now — check for a popup "
        "if this hangs, it can appear behind other windows)...",
        flush=True,
    )
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=CHUNK_SAMPLES)
    stream.start()
    print("Microphone open. Listening for the wake word.", flush=True)
    try:
        while True:
            chunk, _overflowed = stream.read(CHUNK_SAMPLES)
            chunk = chunk.flatten()
            int16_chunk = (chunk * 32767).astype(np.int16)

            if not detector.process_chunk(int16_chunk):
                continue

            speak("Yes?")
            print("(wake word detected, listening...)")
            audio = _record_command(stream)
            text = transcribe(audio)

            if not text:
                speak("Sorry, I didn't catch that.")
                continue

            print(f"you> {text}")
            reply = orchestrator.handle_message(text)
            print(f"jarvis> {reply}")
            speak(reply)
    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        stream.stop()
        stream.close()


if __name__ == "__main__":
    run()
