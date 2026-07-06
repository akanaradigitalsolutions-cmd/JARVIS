"""Central logging setup: a rotating file under ~/.jarvis/logs, plus
console output at DEBUG level when JARVIS_DEBUG is set (see config.py).

Deliberately never logs full prompts/replies or environment variables —
only structural info (durations, exit codes, truncated error text) — so
nothing sensitive (business data, or an accidentally-set ANTHROPIC_API_KEY)
ends up sitting in a plaintext log file.
"""

from __future__ import annotations

import logging
import logging.handlers

from jarvis.core.config import settings

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    logs_dir = settings.jarvis_home / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("jarvis")
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "jarvis.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    root.addHandler(file_handler)

    if settings.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s: %(message)s"))
        root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"jarvis.{name}")
