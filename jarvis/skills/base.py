"""Skill registry: every capability Jarvis has is a "skill" — a plain
Python function registered here with a JSON schema describing its
arguments. The orchestrator exposes the registry to Claude as tools and
dispatches tool_use calls back into these functions.

Adding a new capability (e.g. a Google Ads report) is just: write a
function, decorate it with @skill(...), and import the module once from
jarvis/skills/__init__.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

SkillFunc = Callable[..., Any]


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    input_schema: dict[str, Any]
    func: SkillFunc


_REGISTRY: dict[str, Skill] = {}


def skill(name: str, description: str, input_schema: dict[str, Any]) -> Callable[[SkillFunc], SkillFunc]:
    def decorator(func: SkillFunc) -> SkillFunc:
        if name in _REGISTRY:
            raise ValueError(f"Skill '{name}' is already registered")
        _REGISTRY[name] = Skill(name=name, description=description, input_schema=input_schema, func=func)
        return func

    return decorator


def all_skills() -> list[Skill]:
    return list(_REGISTRY.values())


def get_skill(name: str) -> Skill | None:
    return _REGISTRY.get(name)


def as_anthropic_tools() -> list[dict[str, Any]]:
    return [
        {"name": s.name, "description": s.description, "input_schema": s.input_schema}
        for s in all_skills()
    ]


def reset_registry() -> None:
    """Test helper: clears the registry."""
    _REGISTRY.clear()
