"""Compliance Agent — PF/ESI/TDS/PT deadlines and filings."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from ..core.database import tenant_session
from . import AgentContext, BaseAgent

COMPLIANCE_SYSTEM = """You are the compliance expert for Indian payroll laws,
serving {company_name}.

You track PF, ESI, TDS, and Professional Tax filings. Standard deadlines:
- PF (EPF): 15th of the following month
- ESI: 15th of the following month
- TDS: 7th of the following month (30th April for March)
- Professional Tax: 30th of the following month (Maharashtra)

Always check the database for actual filing status — don't assume. When the
user asks "what's due", call list_upcoming and report concrete deadlines
and amounts."""


class ComplianceAgent(BaseAgent):
    name = "compliance"
    system_prompt = COMPLIANCE_SYSTEM
    tools = [
        {
            "name": "list_upcoming",
            "description": "List filings with status='due' and due_date within the next N days.",
            "input_schema": {
                "type": "object",
                "properties": {"days": {"type": "integer", "default": 30}},
            },
        },
        {
            "name": "list_overdue",
            "description": "List filings with due_date in the past and status not 'filed'.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "filings_for_period",
            "description": "Get all filings for a YYYY-MM period.",
            "input_schema": {
                "type": "object",
                "properties": {"period": {"type": "string", "description": "YYYY-MM"}},
                "required": ["period"],
            },
        },
        {
            "name": "mark_filed",
            "description": "Mark a filing as filed today.",
            "input_schema": {
                "type": "object",
                "properties": {"filing_id": {"type": "string"}},
                "required": ["filing_id"],
            },
        },
    ]

    def run_tool(self, tool_name: str, tool_input: dict[str, Any], ctx: AgentContext) -> Any:
        with tenant_session(ctx.tenant_schema) as db:
            today = date.today()

            if tool_name == "list_upcoming":
                horizon = today + timedelta(days=tool_input.get("days", 30))
                rows = db.execute(
                    text(
                        "SELECT id, type, period, due_date, amount FROM compliance_filings "
                        "WHERE status='due' AND due_date BETWEEN :today AND :horizon "
                        "ORDER BY due_date"
                    ),
                    {"today": today, "horizon": horizon},
                ).all()
                return [
                    {
                        "id": str(r.id), "type": r.type, "period": r.period,
                        "due_date": r.due_date.isoformat(),
                        "days_until_due": (r.due_date - today).days,
                        "amount_inr": str(r.amount),
                    }
                    for r in rows
                ]

            if tool_name == "list_overdue":
                rows = db.execute(
                    text(
                        "SELECT id, type, period, due_date, amount FROM compliance_filings "
                        "WHERE status != 'filed' AND due_date < :today ORDER BY due_date"
                    ),
                    {"today": today},
                ).all()
                return [
                    {
                        "id": str(r.id), "type": r.type, "period": r.period,
                        "due_date": r.due_date.isoformat(),
                        "days_overdue": (today - r.due_date).days,
                        "amount_inr": str(r.amount),
                    }
                    for r in rows
                ]

            if tool_name == "filings_for_period":
                rows = db.execute(
                    text(
                        "SELECT id, type, due_date, filed_date, status, amount "
                        "FROM compliance_filings WHERE period = :p ORDER BY due_date"
                    ),
                    {"p": tool_input["period"]},
                ).all()
                return [
                    {
                        "id": str(r.id), "type": r.type,
                        "due_date": r.due_date.isoformat(),
                        "filed_date": r.filed_date.isoformat() if r.filed_date else None,
                        "status": r.status, "amount_inr": str(r.amount),
                    }
                    for r in rows
                ]

            if tool_name == "mark_filed":
                db.execute(
                    text(
                        "UPDATE compliance_filings SET status='filed', filed_date=:today "
                        "WHERE id = :fid"
                    ),
                    {"today": today, "fid": tool_input["filing_id"]},
                )
                return {"filed": tool_input["filing_id"], "date": today.isoformat()}

        raise ValueError(f"Unknown tool: {tool_name}")
