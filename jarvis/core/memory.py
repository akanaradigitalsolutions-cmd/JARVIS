"""Session bookkeeping: persists JARVIS's Claude Code session id and a
plain-text transcript (so the CLI/UI can display history) across restarts.

The actual conversation *context* Claude uses lives in Claude Code's own
on-disk session store and is resumed via --resume (see core/llm.py); this
file is only for our own display/bookkeeping.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from jarvis.core.config import settings


class SessionMemory:
    def __init__(self, local_id: str | None = None) -> None:
        self.sessions_dir = settings.jarvis_home / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.local_id = local_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.path = self.sessions_dir / f"{self.local_id}.json"

        self.session_id: str | None = None
        self.transcript: list[dict[str, Any]] = []

    @classmethod
    def latest(cls) -> "SessionMemory":
        sessions_dir = settings.jarvis_home / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(sessions_dir.glob("*.json"))
        if not files:
            return cls()
        mem = cls(local_id=files[-1].stem)
        mem.load()
        return mem

    def load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self.session_id = data.get("session_id")
            self.transcript = data.get("transcript", [])

    def append_exchange(self, user_text: str, reply_text: str) -> None:
        self.transcript.append({"role": "user", "text": user_text})
        self.transcript.append({"role": "assistant", "text": reply_text})
        self.save()

    def save(self) -> None:
        self.path.write_text(
            json.dumps({"session_id": self.session_id, "transcript": self.transcript}, indent=2)
        )

    def clear(self) -> None:
        self.session_id = None
        self.transcript = []
        self.save()
