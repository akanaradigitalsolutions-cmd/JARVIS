"""Central configuration: env vars, workspace path, model selection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _resolve_workspace() -> Path:
    raw = os.getenv("JARVIS_WORKSPACE", "").strip()
    path = Path(raw).expanduser() if raw else Path.home() / "Jarvis" / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_home() -> Path:
    path = Path.home() / ".jarvis"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class Settings:
    claude_bin: str
    model: str
    workspace: Path
    jarvis_home: Path
    wake_word: str
    wake_word_model: str
    tts_rate: int
    tts_voice: str


def load_settings() -> Settings:
    return Settings(
        claude_bin=os.getenv("JARVIS_CLAUDE_BIN", "claude"),
        model=os.getenv("JARVIS_MODEL", "claude-sonnet-5"),
        workspace=_resolve_workspace(),
        jarvis_home=_resolve_home(),
        # The wake-word *model* is fixed to openWakeWord's pretrained
        # "hey_jarvis_v0.1" (see voice/wake_word.py) — this is just the
        # phrase shown to the user, keep them in sync.
        wake_word=os.getenv("JARVIS_WAKE_WORD", "hey jarvis").lower(),
        # Path to a custom-trained openWakeWord .onnx/.tflite model.
        # Blank = use the pretrained "Hey JARVIS" model. See
        # ARCHITECTURE.md#custom-wake-word.
        wake_word_model=os.getenv("JARVIS_WAKE_WORD_MODEL", "").strip(),
        tts_rate=int(os.getenv("JARVIS_TTS_RATE", "175")),
        tts_voice=os.getenv("JARVIS_TTS_VOICE", "").strip().lower(),
    )


settings = load_settings()
