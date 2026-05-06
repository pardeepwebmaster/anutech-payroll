"""HR Agent — employees, leaves, approvals."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from ..core.database import tenant_session
from . import AgentContext, BaseAgent

HR_SYSTEM = """You are the HR assistant for {company_name}.

You help administrators and managers with employee information, leave
requests, and approvals. Your responses are professional, concise, and
factual. When the user asks about employees or leaves, ALWAYS call the
relevant tool to get fresh data — never invent names, dates, or counts.

Privacy rules:
- Never reveal salaries, PAN numbers, or bank details unless explicitly asked
  by an administrator about a specific employee.
- Treat all employee data as confidential.

When approving or rejecting a leave, briefly explain the decision in your
final response."""


class HRAgent(BaseAgent):
    name = "hr"
    system_prompt = HR_SYSTEM
    tools = [
        {
            "name": "list_employees",
            "description": "List all active employees for the tenant. Returns name, role, department.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "department": {"type": "string", "description": "Optional filter"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
        {
            "name": "list_pending_leaves",
            "description": "List leave requests with status=pending.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "approve_leave",
            "description": "Approve a pending leave request by ID.",
            "input_schema": {
                "type": "object",
                "properties": {"leave_id": {"type": "string"}},
                "required": ["leave_id"],
            },
        },
        {
            "name": "reject_leave",
            "description": "Reject a pending leave request by ID.",
            "input_schema": {
                "type": "object",
                "properties": {"leave_id": {"type": "string"}},
                "required": ["leave_id"],
            },
        },
    ]

    def run_tool(self, tool_name: str, tool_input: dict[str, Any], ctx: AgentContext) -> Any:
        with tenant_session(ctx.tenant_schema) as db:
            if tool_name == "list_employees":
                q = "SELECT name, role, department FROM employees WHERE status='active'"
                params: dict[str, Any] = {}
                if dept := tool_input.get("department"):
                    q += " AND department = :dept"
                    params["dept"] = dept
                q += " ORDER BY name LIMIT :lim"
                params["lim"] = tool_input.get("limit", 50)
                rows = db.execute(text(q), params).all()
                return [
                    {"name": r.name, "role": r.role, "department": r.department}
                    for r in rows
                ]

            if tool_name == "list_pending_leaves":
                rows = db.execute(
                    text(
                        "SELECT l.id, e.name, l.type, l.from_date, l.to_date, l.reason "
                        "FROM leaves l JOIN employees e ON e.id = l.employee_id "
                        "WHERE l.status='pending' ORDER BY l.from_date"
                    )
                ).all()
                return [
                    {
                        "id": str(r.id),
                        "employee": r.name,
                        "type": r.type,
                        "from": r.from_date.isoformat(),
                        "to": r.to_date.isoformat(),
                        "reason": r.reason,
                    }
                    for r in rows
                ]

            if tool_name == "approve_leave":
                db.execute(
                    text(
                        "UPDATE leaves SET status='approved', approved_by = :uid "
                        "WHERE id = :lid AND status='pending'"
                    ),
                    {"uid": ctx.user_id, "lid": tool_input["leave_id"]},
                )
                return {"approved": tool_input["leave_id"]}

            if tool_name == "reject_leave":
                db.execute(
                    text(
                        "UPDATE leaves SET status='rejected', approved_by = :uid "
                        "WHERE id = :lid AND status='pending'"
                    ),
                    {"uid": ctx.user_id, "lid": tool_input["leave_id"]},
                )
                return {"rejected": tool_input["leave_id"]}

        raise ValueError(f"Unknown tool: {tool_name}")
