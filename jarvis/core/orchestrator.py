"""The agent loop: takes a user message, talks to Claude, executes any
tool (skill) calls Claude asks for, feeds the results back, and repeats
until Claude has a final text answer. This is the one place that ties the
LLM, the skill registry, and memory together — every frontend (CLI, voice
loop, desktop UI) just calls Orchestrator.handle_message().
"""

from __future__ import annotations

import json
import logging

from jarvis.core.config import settings
from jarvis.core.llm import LLMClient
from jarvis.core.memory import SessionMemory
from jarvis.skills import base as skills

logger = logging.getLogger("jarvis.orchestrator")

SYSTEM_PROMPT = """You are JARVIS, a personal AI assistant helping your user with their work: \
data analytics, digital marketing (Google Ads, social media ads), e-commerce for a hospitality \
business, web development, and general digital tasks.

Be direct, capable, and concise, like a sharp chief-of-staff, not a chatbot. When a task needs \
a tool (reading a file, analyzing data, generating a chart, writing a PDF/PPTX/Excel file), use \
it rather than describing what you would do. Files you read or create live in the user's Jarvis \
workspace folder ({workspace}).

When asked to "compile a summary" or "create a report", prefer: analyze the data first, \
generate any needed charts, then produce the PDF/PPTX/Excel file referencing those charts. \
Tell the user the final file path when you're done.

If you don't have a tool for something yet (e.g. live Google Ads data, Shopify orders), say so \
plainly and explain what you'd need (API credentials, a data export, etc.) rather than making \
up numbers.
""".format(workspace=settings.workspace)


class Orchestrator:
    def __init__(self, memory: SessionMemory | None = None, llm: LLMClient | None = None) -> None:
        self.memory = memory or SessionMemory()
        self.llm = llm or LLMClient()
        self.tools = skills.as_anthropic_tools()

    def handle_message(self, user_text: str) -> str:
        self.memory.messages.append({"role": "user", "content": user_text})

        for _ in range(settings.max_tool_iterations):
            response = self.llm.send(
                messages=self.memory.messages,
                system=SYSTEM_PROMPT,
                tools=self.tools,
            )
            content_blocks = [block.model_dump() for block in response.content]
            self.memory.messages.append({"role": "assistant", "content": content_blocks})

            if response.stop_reason != "tool_use":
                self.memory.save()
                return self._extract_text(content_blocks)

            tool_results = [self._execute_tool(block) for block in content_blocks if block["type"] == "tool_use"]
            self.memory.messages.append({"role": "user", "content": tool_results})
            self.memory.save()

        self.memory.save()
        return "I hit my internal step limit working on that — could you break the request into smaller steps?"

    @staticmethod
    def _extract_text(content_blocks: list[dict]) -> str:
        return "\n".join(b["text"] for b in content_blocks if b["type"] == "text").strip()

    def _execute_tool(self, block: dict) -> dict:
        tool_name = block["name"]
        tool_input = block.get("input", {}) or {}
        found = skills.get_skill(tool_name)
        if found is None:
            return {
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": f"Unknown tool '{tool_name}'.",
                "is_error": True,
            }
        try:
            result = found.func(**tool_input)
            return {
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": json.dumps(result, default=str),
            }
        except Exception as exc:  # noqa: BLE001 - surface any skill failure back to Claude
            logger.exception("Skill '%s' failed", tool_name)
            return {
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": f"Error running '{tool_name}': {exc}",
                "is_error": True,
            }
