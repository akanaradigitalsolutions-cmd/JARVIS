"""Thin wrapper around the Anthropic client.

Kept separate from orchestrator.py so the LLM provider can be swapped out
later (e.g. multi-provider support) without touching the agent loop logic.
"""

from __future__ import annotations

from typing import Any

import anthropic

from jarvis.core.config import settings


class MissingApiKeyError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        if not settings.anthropic_api_key:
            raise MissingApiKeyError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
                "add your key from https://console.anthropic.com/"
            )
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.model

    def send(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 4096,
    ) -> anthropic.types.Message:
        return self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools or anthropic.NOT_GIVEN,
        )
