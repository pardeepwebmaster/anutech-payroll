"""Reports router — salary, compliance, and dashboard summary."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.database import get_tenant_session
from ..core.security import CurrentUser, require_admin
from ..models.tenant_models import (
    ComplianceFiling,
    Employee,
    Leave,
    Payslip,
    PayrollRun,
)

router = APIRouter()


@router.get("/dashboard")
def dashboard_summary(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> dict:
    active_emp = db.query(Employee).filter(Employee.status == "active").count()
    pending_leaves = db.query(Leave).filter(Leave.status == "pending").count()
    last_run = (
        db.query(PayrollRun)
        .filter(PayrollRun.status == "completed")
        .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
        .first()
    )
    open_filings = db.query(ComplianceFiling).filter(ComplianceFiling.status == "due").count()

    return {
        "active_employees": active_emp,
        "pending_leaves": pending_leaves,
        "open_filings": open_filings,
        "last_payroll_run": (
            {
                "year": last_run.year,
                "month": last_run.month,
                "total_gross": str(last_run.total_gross),
                "total_net": str(last_run.total_net),
            }
            if last_run
            else None
        ),
    }


@router.get("/salary")
def salary_report(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
    year: int | None = Query(default=None),
) -> dict:
    """Aggregate gross/net per month for the year."""
    q = db.query(
        PayrollRun.year, PayrollRun.month, PayrollRun.total_gross, PayrollRun.total_net
    ).filter(PayrollRun.status == "completed")
    if year:
        q = q.filter(PayrollRun.year == year)
    rows = q.order_by(PayrollRun.year, PayrollRun.month).all()
    return {
        "rows": [
            {"year": r.year, "month": r.month, "total_gross": str(r.total_gross), "total_net": str(r.total_net)}
            for r in rows
        ],
        "total_gross": str(sum((Decimal(str(r.total_gross)) for r in rows), Decimal("0"))),
        "total_net": str(sum((Decimal(str(r.total_net)) for r in rows), Decimal("0"))),
    }


@router.get("/department-spend")
def department_spend(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> list[dict]:
    rows = (
        db.query(Employee.department, func.sum(Employee.basic_salary).label("monthly_total"))
        .filter(Employee.status == "active")
        .group_by(Employee.department)
        .order_by(func.sum(Employee.basic_salary).desc())
        .all()
    )
    return [{"department": r.department, "monthly_total": str(r.monthly_total)} for r in rows]


@router.get("/payroll-summary/{year}/{month}")
def payroll_run_summary(
    year: int,
    month: int,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> dict:
    run = (
        db.query(PayrollRun)
        .filter(PayrollRun.year == year, PayrollRun.month == month)
        .first()
    )
    if not run:
        return {"found": False}
    sums = db.query(
        func.sum(Payslip.gross).label("gross"),
        func.sum(Payslip.pf_employee).label("pf_e"),
        func.sum(Payslip.pf_employer).label("pf_r"),
        func.sum(Payslip.esi_employee).label("esi_e"),
        func.sum(Payslip.esi_employer).label("esi_r"),
        func.sum(Payslip.pt).label("pt"),
        func.sum(Payslip.tds).label("tds"),
        func.sum(Payslip.net_pay).label("net"),
    ).filter(Payslip.payroll_run_id == run.id).one()
    return {
        "found": True,
        "year": year,
        "month": month,
        "status": run.status,
        "gross": str(sums.gross or 0),
        "pf_employee": str(sums.pf_e or 0),
        "pf_employer": str(sums.pf_r or 0),
        "esi_employee": str(sums.esi_e or 0),
        "esi_employer": str(sums.esi_r or 0),
        "pt": str(sums.pt or 0),
        "tds": str(sums.tds or 0),
        "net": str(sums.net or 0),
    }
