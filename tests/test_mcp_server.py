import asyncio
import json

from jarvis.mcp_server import call_tool, list_tools
from jarvis.skills import base as skills
from jarvis.skills.filesystem import write_text_file


def test_list_tools_matches_skill_registry():
    tools = asyncio.run(list_tools())
    assert {t.name for t in tools} == {s.name for s in skills.all_skills()}
    assert all(t.inputSchema for t in tools)


def test_call_tool_dispatches_to_real_skill():
    write_text_file("mcp_roundtrip.txt", "hello from mcp", overwrite=True)
    result = asyncio.run(call_tool("read_text_file", {"path": "mcp_roundtrip.txt"}))
    payload = json.loads(result[0].text)
    assert payload["content"] == "hello from mcp"


def test_call_tool_unknown_name_reports_error_without_raising():
    result = asyncio.run(call_tool("not_a_real_tool", {}))
    assert "Unknown tool" in result[0].text


def test_call_tool_skill_exception_is_captured_as_text():
    result = asyncio.run(call_tool("read_text_file", {"path": "../../etc/passwd"}))
    assert "Error running" in result[0].text
