"""JARVIS's entry point for turning a user message into a reply. Every
frontend (CLI, voice loop, desktop UI) calls Orchestrator.handle_message()
with plain text and gets plain text back.

Unlike a direct-API integration, there's no manual tool-dispatch loop here:
the `claude` CLI (see core/llm.py) runs its own internal agentic loop
against the MCP tools we expose, resolving multi-step tool use within a
single headless call.
"""

from __future__ import annotations

from jarvis.core.config import settings
from jarvis.core.llm import ClaudeCLIClient
from jarvis.core.memory import SessionMemory

SYSTEM_PROMPT = """You are JARVIS, a personal AI assistant in the style of Tony Stark's JARVIS: \
composed, dryly witty, unflappable, and quietly personable — never a generic corporate chatbot. \
Address the user as "boss". Greetings get a warm, in-character reply (e.g. "Yes, boss, good \
morning." rather than "Hello! How can I help you today?"). A light, understated joke or wry \
remark is welcome when it fits naturally, but never at the expense of clarity or getting the \
actual task done — you are effortlessly capable first, funny second.

You help with data analytics, digital marketing (Google Ads, social media ads), e-commerce for \
a hospitality business, web development, and general digital tasks.

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
    def __init__(self, memory: SessionMemory | None = None, client: ClaudeCLIClient | None = None) -> None:
        self.memory = memory or SessionMemory()
        self.client = client or ClaudeCLIClient()

    def handle_message(self, user_text: str) -> str:
        data = self.client.send(user_text, SYSTEM_PROMPT, self.memory.session_id)

        session_id = data.get("session_id")
        if session_id:
            self.memory.session_id = session_id

        reply = (data.get("result") or "").strip()
        self.memory.append_exchange(user_text, reply)

        if data.get("is_error"):
            raise RuntimeError(reply or "Claude returned an error.")

        return reply
