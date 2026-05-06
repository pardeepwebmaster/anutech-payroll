"""Payroll Agent — salary calculations, anomaly detection, payslips."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from ..core.database import tenant_session
from ..services.payroll_calculator import calculate_payslip, detect_anomalies
from . import AgentContext, BaseAgent

PAYROLL_SYSTEM = """You are the payroll expert for {company_name}.

You answer questions about salaries, payroll runs, and payslips. You can
also project payslip components for hypothetical salaries using the Indian
payroll engine (calculate_payslip).

Indian payroll rules you must follow (these are the engine's rules — never
override them):
- Basic = 40% of gross
- HRA = 40% of basic
- PF Employee = 12% of basic, PF Employer = 12% of basic
- ESI = 0.75%/3.25% of gross when gross <= 21,000; otherwise 0
- Professional Tax = ₹200/month (Maharashtra default)
- TDS = annual income-tax slabs / 12 (new regime)
- Net = Gross - PF_Employee - ESI_Employee - PT - TDS

Always cite specific numbers from tool calls — never estimate. When asked
about anomalies, run detect_anomalies and report the warnings verbatim."""


class PayrollAgent(BaseAgent):
    name = "payroll"
    system_prompt = PAYROLL_SYSTEM
    tools = [
        {
            "name": "calculate_payslip",
            "description": "Compute payslip components for a hypothetical monthly gross salary.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "gross_monthly": {"type": "number", "description": "INR per month"}
                },
                "required": ["gross_monthly"],
            },
        },
        {
            "name": "list_payroll_runs",
            "description": "List recent payroll runs with totals.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 12}},
            },
        },
        {
            "name": "get_payslip_for_run",
            "description": "Get all payslips for a year/month payroll run.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
                },
                "required": ["year", "month"],
            },
        },
        {
            "name": "detect_anomalies_for_run",
            "description": "Compare a payroll run to the previous month and flag anomalies per employee.",
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
        if tool_name == "calculate_payslip":
            b = calculate_payslip(tool_input["gross_monthly"])
            return b.as_dict()

        with tenant_session(ctx.tenant_schema) as db:
            if tool_name == "list_payroll_runs":
                rows = db.execute(
                    text(
                        "SELECT year, month, status, total_gross, total_net "
                        "FROM payroll_runs ORDER BY year DESC, month DESC LIMIT :lim"
                    ),
                    {"lim": tool_input.get("limit", 12)},
                ).all()
                return [
                    {
                        "year": r.year, "month": r.month, "status": r.status,
                        "total_gross": str(r.total_gross), "total_net": str(r.total_net),
                    }
                    for r in rows
                ]

            if tool_name == "get_payslip_for_run":
                rows = db.execute(
                    text(
                        "SELECT e.name, p.gross, p.net_pay, p.pf_employee, p.tds "
                        "FROM payslips p JOIN payroll_runs r ON r.id = p.payroll_run_id "
                        "JOIN employees e ON e.id = p.employee_id "
                        "WHERE r.year = :y AND r.month = :m"
                    ),
                    {"y": tool_input["year"], "m": tool_input["month"]},
                ).all()
                return [
                    {
                        "employee": r.name, "gross": str(r.gross),
                        "net_pay": str(r.net_pay), "pf_employee": str(r.pf_employee),
                        "tds": str(r.tds),
                    }
                    for r in rows
                ]

            if tool_name == "detect_anomalies_for_run":
                year = tool_input["year"]
                month = tool_input["month"]
                prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)

                curr = db.execute(
                    text(
                        "SELECT e.id, e.name, p.gross, p.basic, p.hra, p.special_allowance, "
                        "p.pf_employee, p.pf_employer, p.esi_employee, p.esi_employer, "
                        "p.pt, p.tds, p.net_pay "
                        "FROM payslips p JOIN payroll_runs r ON r.id = p.payroll_run_id "
                        "JOIN employees e ON e.id = p.employee_id "
                        "WHERE r.year = :y AND r.month = :m"
                    ),
                    {"y": year, "m": month},
                ).all()

                prev = {
                    r.id: r
                    for r in db.execute(
                        text(
                            "SELECT e.id, p.gross, p.basic, p.hra, p.special_allowance, "
                            "p.pf_employee, p.pf_employer, p.esi_employee, p.esi_employer, "
                            "p.pt, p.tds, p.net_pay "
                            "FROM payslips p JOIN payroll_runs r ON r.id = p.payroll_run_id "
                            "JOIN employees e ON e.id = p.employee_id "
                            "WHERE r.year = :y AND r.month = :m"
                        ),
                        {"y": prev_year, "m": prev_month},
                    ).all()
                }

                from ..services.payroll_calculator import PayslipBreakdown

                def to_breakdown(row) -> PayslipBreakdown:
                    return PayslipBreakdown(
                        gross=Decimal(str(row.gross)),
                        basic=Decimal(str(row.basic)),
                        hra=Decimal(str(row.hra)),
                        special_allowance=Decimal(str(row.special_allowance)),
                        pf_employee=Decimal(str(row.pf_employee)),
                        pf_employer=Decimal(str(row.pf_employer)),
                        esi_employee=Decimal(str(row.esi_employee)),
                        esi_employer=Decimal(str(row.esi_employer)),
                        pt=Decimal(str(row.pt)),
                        tds=Decimal(str(row.tds)),
                        net_pay=Decimal(str(row.net_pay)),
                    )

                anomalies = []
                for row in curr:
                    warnings = detect_anomalies(
                        to_breakdown(row),
                        previous=to_breakdown(prev[row.id]) if row.id in prev else None,
                    )
                    if warnings:
                        anomalies.append({"employee": row.name, "warnings": warnings})
                return {"anomalies": anomalies, "compared_with": f"{prev_year}-{prev_month:02d}"}

        raise ValueError(f"Unknown tool: {tool_name}")
