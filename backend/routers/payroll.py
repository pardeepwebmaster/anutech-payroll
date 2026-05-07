"""Payroll router — run payroll for a month, list/get payslips, download PDF."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_tenant_session
from ..core.security import (
    CurrentUser,
    get_current_user,
    require_admin,
)
from ..models.tenant_models import Employee, PayrollRun, Payslip
from ..services.payroll_calculator import calculate_payslip
from ..services.email_service import render_payslip_pdf
from ..services.zoho_books import (
    get_zoho_status as zoho_status_dict,
    sync_payroll_run_to_zoho,
)

router = APIRouter()


# ---------- Schemas ----------

class RunPayrollRequest(BaseModel):
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    force: bool = Field(default=False, description="Re-run even if already completed")


class PayslipRead(BaseModel):
    id: str
    employee_id: str
    payroll_run_id: str
    gross: Decimal
    basic: Decimal
    hra: Decimal
    special_allowance: Decimal
    pf_employee: Decimal
    pf_employer: Decimal
    esi_employee: Decimal
    esi_employer: Decimal
    pt: Decimal
    tds: Decimal
    net_pay: Decimal

    model_config = {"from_attributes": True}


class PayrollRunRead(BaseModel):
    id: str
    year: int
    month: int
    status: str
    total_gross: Decimal
    total_net: Decimal
    payslip_count: int

    model_config = {"from_attributes": True}


# ---------- Endpoints ----------

@router.post("/run", response_model=PayrollRunRead, status_code=status.HTTP_201_CREATED)
def run_payroll(
    payload: RunPayrollRequest,
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(require_admin),
) -> dict:
    existing = (
        db.query(PayrollRun)
        .filter(PayrollRun.year == payload.year, PayrollRun.month == payload.month)
        .first()
    )
    if existing and existing.status == "completed" and not payload.force:
        raise HTTPException(
            status_code=409,
            detail=f"Payroll for {payload.year}-{payload.month:02d} already completed. Use force=true to re-run.",
        )

    if existing:
        for ps in db.query(Payslip).filter(Payslip.payroll_run_id == existing.id).all():
            db.delete(ps)
        run = existing
        run.status = "running"
    else:
        run = PayrollRun(
            year=payload.year,
            month=payload.month,
            status="running",
            run_by=current.user_id,
        )
        db.add(run)
        db.flush()

    employees = (
        db.query(Employee)
        .filter(Employee.status == "active", Employee.basic_salary > 0)
        .all()
    )

    total_gross = Decimal("0")
    total_net = Decimal("0")

    for emp in employees:
        breakdown = calculate_payslip(emp.basic_salary)
        ps = Payslip(
            employee_id=emp.id,
            payroll_run_id=run.id,
            gross=breakdown.gross,
            basic=breakdown.basic,
            hra=breakdown.hra,
            special_allowance=breakdown.special_allowance,
            pf_employee=breakdown.pf_employee,
            pf_employer=breakdown.pf_employer,
            esi_employee=breakdown.esi_employee,
            esi_employer=breakdown.esi_employer,
            pt=breakdown.pt,
            tds=breakdown.tds,
            net_pay=breakdown.net_pay,
        )
        db.add(ps)
        total_gross += breakdown.gross
        total_net += breakdown.net_pay

    run.total_gross = total_gross
    run.total_net = total_net
    run.status = "completed"
    run.run_at = datetime.now(timezone.utc)
    db.flush()

    count = db.query(Payslip).filter(Payslip.payroll_run_id == run.id).count()
    return {
        "id": run.id,
        "year": run.year,
        "month": run.month,
        "status": run.status,
        "total_gross": run.total_gross,
        "total_net": run.total_net,
        "payslip_count": count,
    }


@router.get("/runs", response_model=list[PayrollRunRead])
def list_runs(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    runs = db.query(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).all()
    out = []
    for r in runs:
        count = db.query(Payslip).filter(Payslip.payroll_run_id == r.id).count()
        out.append(
            {
                "id": r.id,
                "year": r.year,
                "month": r.month,
                "status": r.status,
                "total_gross": r.total_gross,
                "total_net": r.total_net,
                "payslip_count": count,
            }
        )
    return out


@router.get("/runs/{run_id}/payslips", response_model=list[PayslipRead])
def list_payslips_for_run(
    run_id: str,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(get_current_user),
) -> list[Payslip]:
    return (
        db.query(Payslip)
        .filter(Payslip.payroll_run_id == run_id)
        .order_by(Payslip.created_at)
        .all()
    )


@router.get("/zoho-status")
def zoho_status(
    _: CurrentUser = Depends(require_admin),
) -> dict:
    """Diagnostic — verifies Zoho creds + lists organizations.

    Used by the frontend to decide whether to show the \"Sync to Zoho\" button.
    """
    return zoho_status_dict()


@router.post("/runs/{run_id}/sync-zoho")
def sync_run_to_zoho(
    run_id: str,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> dict:
    """Push this payroll run's total net to Zoho Books as an Expense entry.

    Idempotency: each call creates a new expense in Zoho. The reference_number
    on the expense is set to the run id, so duplicates are easy to spot in
    Zoho's expense list and clean up if needed.
    """
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Run is in status '{run.status}'. Complete the run before syncing.",
        )

    period_iso = f"{run.year:04d}-{run.month:02d}-01"
    result = sync_payroll_run_to_zoho(
        run_id=str(run.id),
        period_iso=period_iso,
        total_net=run.total_net,
    )
    if not result or not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=(result or {}).get("reason", "Zoho sync failed"),
        )
    return result


@router.get("/payslips/me", response_model=list[PayslipRead])
def my_payslips(
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(get_current_user),
) -> list[Payslip]:
    return (
        db.query(Payslip)
        .filter(Payslip.employee_id == current.user_id)
        .order_by(Payslip.created_at.desc())
        .all()
    )


@router.get("/payslips/{payslip_id}", response_model=PayslipRead)
def get_payslip(
    payslip_id: str,
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(get_current_user),
) -> Payslip:
    ps = db.query(Payslip).filter(Payslip.id == payslip_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if current.role != "admin" and ps.employee_id != current.user_id:
        raise HTTPException(status_code=403, detail="Cannot view another employee's payslip")
    return ps


@router.get("/payslips/{payslip_id}/pdf")
def download_payslip_pdf(
    payslip_id: str,
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(get_current_user),
):
    ps = db.query(Payslip).filter(Payslip.id == payslip_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if current.role != "admin" and ps.employee_id != current.user_id:
        raise HTTPException(status_code=403, detail="Cannot view another employee's payslip")

    emp = db.query(Employee).filter(Employee.id == ps.employee_id).first()
    run = db.query(PayrollRun).filter(PayrollRun.id == ps.payroll_run_id).first()

    pdf_bytes = render_payslip_pdf(employee=emp, payslip=ps, run=run, tenant_name=current.tenant_schema)

    filename = f"payslip-{run.year}-{run.month:02d}-{emp.name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
