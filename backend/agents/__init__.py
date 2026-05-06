"""Agent contract — FROZEN during Phase 1.

`backend-api` (which calls agents from `routers/ai_chat.py`) and `ai-agents`
(which implements the agents) both code to this interface. Changes require
lead approval and must be coordinated across both teammates.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Per-call context passed to an agent. Tenant-scoped."""

    tenant_id: str
    tenant_schema: str
    user_id: str | None = None
    company_name: str = ""
    conversation_id: str | None = None  # for multi-turn conversations via Redis
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Uniform response shape from any agent."""

    text: str
    agent_name: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens
    cached: bool = False


class BaseAgent(ABC):
    """All Claude-backed agents extend this.

    Implementations live in `backend/agents/` and are registered via the
    orchestrator. They MUST:
      - declare a stable `name`
      - provide a `system_prompt` (eligible for prompt caching)
      - declare their `tools` (Anthropic tool-use schema)
      - implement `run()` returning an AgentResponse
    """

    name: str = ""
    system_prompt: str = ""
    tools: list[dict[str, Any]] = []
    model: str | None = None  # falls back to settings.ANTHROPIC_MODEL

    @abstractmethod
    def run(self, query: str, context: AgentContext) -> AgentResponse:
        """Handle a single user query. Implementations may call tools and loop
        internally; one call to run() corresponds to one user turn.
        """
        ...

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.__abstractmethods__ and not cls.name:
            raise TypeError(f"{cls.__name__} must set a non-empty `name`")
