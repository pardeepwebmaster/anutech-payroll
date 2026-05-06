"""Orchestrator — routes user queries to specialist agents.

Routing strategy: deterministic keyword routing first, fall back to a
lightweight Claude classification call only if keywords don't match. This
keeps the common path fast and cheap.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import text

from ..core.database import tenant_session
from . import AgentContext, AgentResponse, BaseAgent
from .compliance_agent import ComplianceAgent
from .finance_agent import FinanceAgent
from .hr_agent import HRAgent
from .payroll_agent import PayrollAgent

log = logging.getLogger(__name__)

_AGENTS: dict[str, BaseAgent] = {
    "hr": HRAgent(),
    "payroll": PayrollAgent(),
    "finance": FinanceAgent(),
    "compliance": ComplianceAgent(),
}

_KEYWORD_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(leave|leaves|vacation|sick day|absent)\b", re.I), "hr"),
    (re.compile(r"\b(employee|hire|onboard|department|joining)\b", re.I), "hr"),
    (re.compile(r"\b(salary|payslip|payroll|gross|net pay|hra|basic|tds)\b", re.I), "payroll"),
    (re.compile(r"\b(anomaly|anomalies|variance|spike|drop)\b", re.I), "payroll"),
    (re.compile(r"\b(pf|epf|esi|professional tax|compliance|filing|deadline|overdue)\b", re.I), "compliance"),
    (re.compile(r"\b(zoho|expense|spend|department spend|cost center|aggregate)\b", re.I), "finance"),
]

ORCHESTRATOR_SYSTEM = """You classify a user's question into ONE of these
specialist agents and return ONLY the agent name as plain text:

- hr: employees, leave requests, approvals, onboarding
- payroll: salary calculations, payslips, payroll runs, anomalies
- finance: salary aggregates, department spend, Zoho Books sync
- compliance: PF, ESI, TDS, Professional Tax, filings, deadlines

Reply with exactly one word: hr, payroll, finance, or compliance.
If the question doesn't fit, reply: payroll."""


class Orchestrator:
    def __init__(self) -> None:
        from . import get_anthropic_client
        self._client = get_anthropic_client

    def route(self, query: str) -> str:
        for pattern, agent_name in _KEYWORD_HINTS:
            if pattern.search(query):
                return agent_name

        from ..core.config import get_settings
        try:
            response = self._client().messages.create(
                model=get_settings().ANTHROPIC_MODEL,
                max_tokens=8,
                system=[
                    {
                        "type": "text",
                        "text": ORCHESTRATOR_SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": query}],
            )
            text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            label = (text_blocks[0] if text_blocks else "payroll").strip().lower()
            return label if label in _AGENTS else "payroll"
        except Exception:
            log.exception("orchestrator classify failed; defaulting to payroll")
            return "payroll"

    def handle(self, query: str, ctx: AgentContext) -> AgentResponse:
        agent_name = self.route(query)
        agent = _AGENTS[agent_name]
        ctx.metadata["routed_to"] = agent_name
        log.info("orchestrator routed query to %s for tenant %s", agent_name, ctx.tenant_schema)
        response = agent.run(query, ctx)
        self._log(ctx, agent_name, query, response)
        return response

    def _log(self, ctx: AgentContext, agent_name: str, query: str, response: AgentResponse) -> None:
        try:
            with tenant_session(ctx.tenant_schema) as db:
                db.execute(
                    text(
                        "INSERT INTO agent_logs (agent_name, action, input_summary, result, tenant_id) "
                        "VALUES (:n, :a, :i, :r, :t)"
                    ),
                    {
                        "n": agent_name,
                        "a": "chat",
                        "i": query[:500],
                        "r": json.dumps(
                            {
                                "text": response.text[:1000],
                                "tool_calls": response.tool_calls[:5],
                                "usage": response.usage,
                            }
                        ),
                        "t": ctx.tenant_id,
                    },
                )
        except Exception:
            log.exception("agent_log insert failed (non-fatal)")


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
