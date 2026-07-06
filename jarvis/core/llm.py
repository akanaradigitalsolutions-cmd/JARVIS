"""Wraps the `claude` CLI (Claude Code) in headless mode as JARVIS's brain.

Deliberately does NOT call the Anthropic API directly with a metered key.
Instead it shells out to the `claude` binary; when you're logged in via
`claude login` against a Claude Pro/Max subscription (and ANTHROPIC_API_KEY
is not set), usage draws on the subscription's included usage instead of
pay-per-token API billing.

Claude Code also runs its own internal agentic tool-use loop, so unlike a
raw API integration we don't reimplement a tool-dispatch loop here — we
just hand it a whitelisted set of MCP tools (our skills, served by
jarvis/mcp_server.py) via --mcp-config, and a single `claude -p` call
resolves everything, including any multi-step tool use.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any

from jarvis.core.config import settings
from jarvis.core.logging_config import get_logger
from jarvis.skills import base as skills

logger = get_logger("llm")

MCP_SERVER_MODULE = "jarvis.mcp_server"

# Built-in Claude Code tools we explicitly deny so JARVIS can only touch the
# machine through our own sandboxed skills. NOTE: we deny by name here
# rather than using `--tools ""` — that flag turns out to also suppress the
# MCP tool definitions from being shown to the model at all (verified
# against Claude Code 2.1.198), which silently breaks every skill. An
# explicit --disallowedTools list coexists correctly with --mcp-config.
BUILTIN_TOOLS_TO_DENY = [
    "Bash", "BashOutput", "KillShell", "PowerShell",
    "Read", "Write", "Edit", "NotebookEdit",
    "Glob", "Grep", "WebFetch", "WebSearch", "Task",
]


class ClaudeCLINotAvailableError(RuntimeError):
    pass


class ClaudeCLIClient:
    def __init__(self, claude_bin: str | None = None) -> None:
        self.claude_bin = claude_bin or settings.claude_bin
        if shutil.which(self.claude_bin) is None:
            raise ClaudeCLINotAvailableError(
                f"Couldn't find the '{self.claude_bin}' command. Install Claude Code "
                "(npm install -g @anthropic-ai/claude-code) and run 'claude login' "
                "with your Claude subscription first."
            )
        if os.getenv("ANTHROPIC_API_KEY"):
            print(
                "Warning: ANTHROPIC_API_KEY is set in your environment. The claude CLI "
                "will use it and bill against pay-as-you-go API usage instead of your "
                "Pro/Max subscription. Remove it from .env to use your subscription.",
                file=sys.stderr,
            )

    @staticmethod
    def _mcp_config() -> str:
        return json.dumps(
            {
                "mcpServers": {
                    "jarvis": {
                        "type": "stdio",
                        "command": sys.executable,
                        "args": ["-m", MCP_SERVER_MODULE],
                    }
                }
            }
        )

    @staticmethod
    def _allowed_tools() -> str:
        return ",".join(f"mcp__jarvis__{s.name}" for s in skills.all_skills())

    def build_args(self, prompt: str, system_prompt: str, session_id: str | None) -> list[str]:
        args = [
            self.claude_bin,
            "-p", prompt,
            "--output-format", "json",
            "--permission-mode", "dontAsk",
            "--mcp-config", self._mcp_config(),
            "--strict-mcp-config",
            "--allowedTools", self._allowed_tools(),
            "--disallowedTools", ",".join(BUILTIN_TOOLS_TO_DENY),
            "--system-prompt", system_prompt,
            "--model", settings.model,
        ]
        if session_id:
            args += ["--resume", session_id]
        return args

    def send(self, prompt: str, system_prompt: str, session_id: str | None) -> dict[str, Any]:
        args = self.build_args(prompt, system_prompt, session_id)
        last_error: Exception | None = None

        # One retry on any transient-looking failure (timeout, nonzero exit,
        # unparseable output) before giving up — a single flaky invocation
        # of the CLI shouldn't surface as a hard failure to the user. Both
        # attempts use --resume the same session_id, so a retry after a
        # partial tool-use failure just continues the same conversation
        # rather than losing context or duplicating work.
        for attempt in (1, 2):
            start = time.monotonic()
            try:
                proc = subprocess.run(
                    args, capture_output=True, text=True, cwd=str(settings.jarvis_home),
                    timeout=settings.claude_timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                last_error = exc
                logger.warning("claude CLI timed out after %.1fs (attempt %d/2)", settings.claude_timeout_seconds, attempt)
                continue

            duration = time.monotonic() - start
            if proc.returncode != 0:
                last_error = RuntimeError(f"claude CLI exited with code {proc.returncode}: {proc.stderr.strip()}")
                logger.warning(
                    "claude CLI exited with code %d after %.1fs (attempt %d/2): %s",
                    proc.returncode, duration, attempt, proc.stderr.strip()[:300],
                )
                continue

            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                last_error = RuntimeError(f"Couldn't parse claude CLI output: {proc.stdout[:500]!r}")
                logger.warning("claude CLI returned unparseable output (attempt %d/2): %s", attempt, exc)
                continue

            logger.info("claude CLI call succeeded in %.1fs (attempt %d/2)", duration, attempt)
            return result

        logger.error("claude CLI failed after 2 attempts: %s", last_error)
        if isinstance(last_error, subprocess.TimeoutExpired):
            raise RuntimeError(
                f"Claude didn't respond within {settings.claude_timeout_seconds}s, even after a retry. "
                "This can happen on a very long or complex task — try breaking the request into smaller "
                "steps, or raise JARVIS_CLAUDE_TIMEOUT_SECONDS in .env."
            ) from last_error
        raise last_error
