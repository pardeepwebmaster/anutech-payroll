"""Agent contract — FROZEN.

Every Claude-backed agent extends BaseAgent. Both the orchestrator and the
ai_chat router code to this interface.

Implementation notes:
- Uses the official `anthropic` SDK.
- Default model is `claude-opus-4-7` (latest Opus). Override per agent if
  cost-sensitive — Sonnet 4.6 / Haiku 4.5 also acceptable for narrower agents.
- Prompt caching: `system_prompt` is the cached prefix. Anything dynamic goes
  in the user message, after the breakpoint. Each call's user query and
  per-tenant context are appended after, so the prefix stays identical
  across requests for the same tenant + agent.
- Adaptive thinking is enabled by default — let Claude decide when to think.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from ..core.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Per-call context passed to an agent."""

    tenant_id: str
    tenant_schema: str
    user_id: str | None = None
    company_name: str = ""
    conversation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    text: str
    agent_name: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    cached: bool = False


_client: Anthropic | None = None


def get_anthropic_client() -> Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


class BaseAgent(ABC):
    """All Claude-backed agents extend this. Subclasses must set:
      - name: stable identifier (e.g., "hr", "payroll")
      - system_prompt: cached prefix; do not interpolate dynamic data
      - tools: list of tool schemas (Anthropic tool-use format)
      - run_tool: dispatch tool calls to your Python functions
    """

    name: str = ""
    system_prompt: str = ""
    tools: list[dict[str, Any]] = []
    model: str | None = None
    max_iterations: int = 6  # cap tool-loop iterations

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # ABCMeta sets __abstractmethods__, but on Python 3.11 the order between
        # __init_subclass__ and ABCMeta.__new__ is fragile — use getattr to be safe.
        abstract = getattr(cls, "__abstractmethods__", frozenset())
        if not abstract and not cls.name:
            raise TypeError(f"{cls.__name__} must set a non-empty `name`")

    @abstractmethod
    def run_tool(self, tool_name: str, tool_input: dict[str, Any], ctx: AgentContext) -> Any:
        """Execute a tool call and return a JSON-serializable result."""
        ...

    def run(self, query: str, ctx: AgentContext) -> AgentResponse:
        """One user turn. Loops on tool use until the model produces a final
        text answer or we hit max_iterations.
        """
        client = get_anthropic_client()
        settings = get_settings()
        model = self.model or settings.ANTHROPIC_MODEL

        # Cached prefix: system prompt with cache_control on the text block.
        system_blocks = [
            {
                "type": "text",
                "text": self._render_system(ctx),
                "cache_control": {"type": "ephemeral"},
            }
        ]

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": query},
        ]

        total_in = 0
        total_out = 0
        cache_read = 0
        tool_calls_log: list[dict[str, Any]] = []

        for iteration in range(self.max_iterations):
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_blocks,
                messages=messages,
                tools=self.tools or None,
                thinking={"type": "adaptive"},
            )
            total_in += response.usage.input_tokens
            total_out += response.usage.output_tokens
            cache_read += getattr(response.usage, "cache_read_input_tokens", 0) or 0

            if response.stop_reason == "end_turn" or not self.tools:
                text = self._extract_text(response.content)
                return AgentResponse(
                    text=text,
                    agent_name=self.name,
                    tool_calls=tool_calls_log,
                    usage={
                        "input_tokens": total_in,
                        "output_tokens": total_out,
                        "cache_read_input_tokens": cache_read,
                    },
                    cached=cache_read > 0,
                )

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results: list[dict[str, Any]] = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        tool_calls_log.append(
                            {"name": block.name, "input": block.input}
                        )
                        try:
                            result = self.run_tool(block.name, block.input, ctx)
                            content = (
                                result if isinstance(result, str) else json.dumps(result, default=str)
                            )
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": content,
                                }
                            )
                        except Exception as exc:
                            log.exception("agent %s tool %s failed", self.name, block.name)
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": f"Error: {exc}",
                                    "is_error": True,
                                }
                            )
                messages.append({"role": "user", "content": tool_results})
                continue

            log.warning(
                "agent %s unexpected stop_reason=%s; returning text",
                self.name,
                response.stop_reason,
            )
            return AgentResponse(
                text=self._extract_text(response.content),
                agent_name=self.name,
                tool_calls=tool_calls_log,
                usage={
                    "input_tokens": total_in,
                    "output_tokens": total_out,
                    "cache_read_input_tokens": cache_read,
                },
                cached=cache_read > 0,
            )

        return AgentResponse(
            text="(Agent reached max iterations without a final answer.)",
            agent_name=self.name,
            tool_calls=tool_calls_log,
            usage={
                "input_tokens": total_in,
                "output_tokens": total_out,
                "cache_read_input_tokens": cache_read,
            },
            cached=cache_read > 0,
        )

    def _render_system(self, ctx: AgentContext) -> str:
        """Render the system prompt. Override for per-tenant tweaks, but be
        aware: anything tenant-specific will live in a per-tenant cache slot,
        not a globally shared one. That's still useful (each tenant gets a
        warm cache) but lower hit rate than a frozen prompt would be.
        """
        if "{company_name}" in self.system_prompt and ctx.company_name:
            return self.system_prompt.replace("{company_name}", ctx.company_name)
        return self.system_prompt

    @staticmethod
    def _extract_text(blocks: list[Any]) -> str:
        return "\n".join(b.text for b in blocks if getattr(b, "type", None) == "text")
