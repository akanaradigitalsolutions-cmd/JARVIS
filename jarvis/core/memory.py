"""Session memory: persists the conversation to disk so context survives
across restarts of the CLI/UI/voice loop.

This is intentionally simple (one JSON file per session) — long-term
structured memory (facts about the user/business) is planned for Phase 5.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.core.config import settings


class SessionMemory:
    def __init__(self, session_id: str | None = None) -> None:
        self.sessions_dir = settings.jarvis_home / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.path = self.sessions_dir / f"{self.session_id}.json"
        self.messages: list[dict[str, Any]] = []

    @classmethod
    def latest(cls) -> "SessionMemory":
        sessions_dir = settings.jarvis_home / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(sessions_dir.glob("*.json"))
        if not files:
            return cls()
        mem = cls(session_id=files[-1].stem)
        mem.load()
        return mem

    def load(self) -> None:
        if self.path.exists():
            self.messages = json.loads(self.path.read_text())

    def append(self, message: dict[str, Any]) -> None:
        self.messages.append(message)
        self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.messages, indent=2, default=str))

    def clear(self) -> None:
        self.messages = []
        self.save()
