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
    anthropic_api_key: str
    model: str
    workspace: Path
    jarvis_home: Path
    wake_word: str
    tts_rate: int
    max_tool_iterations: int = 12


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=os.getenv("JARVIS_MODEL", "claude-sonnet-5"),
        workspace=_resolve_workspace(),
        jarvis_home=_resolve_home(),
        wake_word=os.getenv("JARVIS_WAKE_WORD", "jarvis").lower(),
        tts_rate=int(os.getenv("JARVIS_TTS_RATE", "175")),
    )


settings = load_settings()
