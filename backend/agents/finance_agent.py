"""Finance Agent — Zoho Books, expense reports, salary aggregates."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ..core.database import tenant_session
from ..services.zoho_books import sync_payroll_run_to_zoho
from . import AgentContext, BaseAgent

FINANCE_SYSTEM = """You are the finance assistant for {company_name}.

You provide salary aggregates, department-level spend, and can sync
payroll runs to Zoho Books on request. Always confirm before triggering
a sync — use the sync_zoho tool only when the user explicitly asks.

Be precise with numbers. Quote amounts in INR and round to 2 decimals."""


class FinanceAgent(BaseAgent):
    name = "finance"
    system_prompt = FINANCE_SYSTEM
    tools = [
        {
            "name": "salary_aggregate",
            "description": "Total monthly salary spend across active employees.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "department_spend",
            "description": "Monthly spend grouped by department.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "payroll_year_summary",
            "description": "Aggregate gross and net for all completed runs in a year.",
            "input_schema": {
                "type": "object",
                "properties": {"year": {"type": "integer"}},
                "required": ["year"],
            },
        },
        {
            "name": "sync_zoho",
            "description": "Sync a payroll run to Zoho Books as an expense entry. Returns Zoho's response or 'not configured'.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
                },
                "required": ["year", "month"],
            },
        },
    ]

    def run_tool(self, tool_name: str, tool_input: dict[str, Any], ctx: AgentContext) -> Any:
        with tenant_session(ctx.tenant_schema) as db:
            if tool_name == "salary_aggregate":
                row = db.execute(
                    text(
                        "SELECT COUNT(*) AS n, COALESCE(SUM(basic_salary), 0) AS total "
                        "FROM employees WHERE status='active'"
                    )
                ).one()
                return {"active_employees": row.n, "monthly_total_inr": str(row.total)}

            if tool_name == "department_spend":
                rows = db.execute(
                    text(
                        "SELECT department, SUM(basic_salary) AS total FROM employees "
                        "WHERE status='active' GROUP BY department ORDER BY total DESC"
                    )
                ).all()
                return [
                    {"department": r.department, "monthly_total_inr": str(r.total)}
                    for r in rows
                ]

            if tool_name == "payroll_year_summary":
                rows = db.execute(
                    text(
                        "SELECT month, total_gross, total_net FROM payroll_runs "
                        "WHERE year = :y AND status='completed' ORDER BY month"
                    ),
                    {"y": tool_input["year"]},
                ).all()
                return [
                    {
                        "month": r.month,
                        "total_gross": str(r.total_gross),
                        "total_net": str(r.total_net),
                    }
                    for r in rows
                ]

            if tool_name == "sync_zoho":
                run = db.execute(
                    text(
                        "SELECT id, total_net FROM payroll_runs "
                        "WHERE year = :y AND month = :m AND status='completed'"
                    ),
                    {"y": tool_input["year"], "m": tool_input["month"]},
                ).first()
                if not run:
                    return {"error": "No completed payroll run found for that period"}
                period = f"{tool_input['year']}-{tool_input['month']:02d}-01"
                result = sync_payroll_run_to_zoho(
                    run_id=str(run.id),
                    period_iso=period,
                    total_net=run.total_net,
                )
                return result if result is not None else {"status": "Zoho not configured"}

        raise ValueError(f"Unknown tool: {tool_name}")
