"""Standalone MCP stdio server exposing every registered Jarvis skill as a
tool. The `claude` CLI spawns this as a subprocess (see the --mcp-config
built in jarvis/core/llm.py) whenever JARVIS handles a request headlessly.

Run directly with `python -m jarvis.mcp_server` for manual testing.
"""

from __future__ import annotations

import asyncio
import json

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from jarvis.skills import base as skills  # noqa: F401 - imported for its registration side effects

server = Server("jarvis")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=s.name, description=s.description, inputSchema=s.input_schema)
        for s in skills.all_skills()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    found = skills.get_skill(name)
    if found is None:
        return [types.TextContent(type="text", text=f"Unknown tool '{name}'")]
    try:
        result = found.func(**(arguments or {}))
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as exc:  # noqa: BLE001 - surface any skill failure back to Claude
        return [types.TextContent(type="text", text=f"Error running '{name}': {exc}")]


async def _run() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
