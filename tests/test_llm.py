import json
import subprocess
import sys

import pytest

import jarvis.core.llm as llm_module
from jarvis.core.llm import BUILTIN_TOOLS_TO_DENY, ClaudeCLIClient, ClaudeCLINotAvailableError
from jarvis.skills import base as skills


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_raises_when_binary_missing():
    with pytest.raises(ClaudeCLINotAvailableError):
        ClaudeCLIClient(claude_bin="definitely-not-a-real-binary-xyz123")


def test_build_args_new_session_has_no_resume():
    client = ClaudeCLIClient(claude_bin=sys.executable)
    args = client.build_args("hello", "system prompt", session_id=None)
    assert args[0] == sys.executable
    assert args[args.index("-p") + 1] == "hello"
    assert "--resume" not in args
    assert args[args.index("--system-prompt") + 1] == "system prompt"


def test_build_args_resumes_existing_session():
    client = ClaudeCLIClient(claude_bin=sys.executable)
    args = client.build_args("hello again", "system prompt", session_id="abc-123")
    assert args[args.index("--resume") + 1] == "abc-123"


def test_build_args_denies_builtins_and_whitelists_skills():
    # NOTE: we deny built-ins by name via --disallowedTools rather than
    # --tools "" — that flag was verified (against Claude Code 2.1.198) to
    # also suppress MCP tool definitions from the model entirely, silently
    # breaking every skill. Don't "simplify" this back to --tools "".
    client = ClaudeCLIClient(claude_bin=sys.executable)
    args = client.build_args("hi", "sys", session_id=None)
    assert "--tools" not in args

    denied = args[args.index("--disallowedTools") + 1]
    assert set(denied.split(",")) == set(BUILTIN_TOOLS_TO_DENY)

    allowed = args[args.index("--allowedTools") + 1]
    expected = {f"mcp__jarvis__{s.name}" for s in skills.all_skills()}
    assert set(allowed.split(",")) == expected


def test_warns_but_does_not_crash_when_api_key_set(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    ClaudeCLIClient(claude_bin=sys.executable)
    captured = capsys.readouterr()
    assert "ANTHROPIC_API_KEY" in captured.err


def test_send_retries_once_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_run(args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCompletedProcess(returncode=1, stderr="temporary glitch")
        return _FakeCompletedProcess(returncode=0, stdout=json.dumps({"result": "ok", "session_id": "s1"}))

    monkeypatch.setattr(llm_module.subprocess, "run", fake_run)
    client = ClaudeCLIClient(claude_bin=sys.executable)
    result = client.send("hi", "sys", session_id=None)

    assert result == {"result": "ok", "session_id": "s1"}
    assert calls["n"] == 2


def test_send_raises_clear_error_after_two_failed_attempts(monkeypatch):
    def fake_run(args, **kwargs):
        return _FakeCompletedProcess(returncode=1, stderr="permanent failure")

    monkeypatch.setattr(llm_module.subprocess, "run", fake_run)
    client = ClaudeCLIClient(claude_bin=sys.executable)

    with pytest.raises(RuntimeError, match="permanent failure"):
        client.send("hi", "sys", session_id=None)


def test_send_raises_clear_error_after_repeated_timeout(monkeypatch):
    def fake_run(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout", 1))

    monkeypatch.setattr(llm_module.subprocess, "run", fake_run)
    client = ClaudeCLIClient(claude_bin=sys.executable)

    with pytest.raises(RuntimeError, match="didn't respond"):
        client.send("hi", "sys", session_id=None)


def test_send_recovers_from_unparseable_output_on_retry(monkeypatch):
    calls = {"n": 0}

    def fake_run(args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCompletedProcess(returncode=0, stdout="not json")
        return _FakeCompletedProcess(returncode=0, stdout=json.dumps({"result": "recovered"}))

    monkeypatch.setattr(llm_module.subprocess, "run", fake_run)
    client = ClaudeCLIClient(claude_bin=sys.executable)
    result = client.send("hi", "sys", session_id=None)

    assert result == {"result": "recovered"}
    assert calls["n"] == 2
