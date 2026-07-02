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
from typing import Any

from jarvis.core.config import settings
from jarvis.skills import base as skills

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
        proc = subprocess.run(args, capture_output=True, text=True, cwd=str(settings.jarvis_home))
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI exited with code {proc.returncode}: {proc.stderr.strip()}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Couldn't parse claude CLI output: {proc.stdout[:500]!r}") from exc
