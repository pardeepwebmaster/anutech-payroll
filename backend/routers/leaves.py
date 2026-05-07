"""Leaves router — apply, list, approve/reject, balance."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..core.database import get_tenant_session
from ..core.security import CurrentUser, get_current_user, require_admin
from ..models.tenant_models import Employee, Leave

router = APIRouter()

# Only "unpaid" type is unpaid; the rest deduct from a paid annual balance.
LEAVE_TYPES = {"casual", "sick", "earned", "unpaid"}
PAID_TYPES = {"casual", "sick", "earned"}
DEFAULT_ANNUAL_BALANCE = {"casual": 12, "sick": 12, "earned": 18, "unpaid": 365}


def _is_paid(leave_type: str) -> bool:
    return leave_type in PAID_TYPES


class LeaveApply(BaseModel):
    type: str
    from_date: date
    to_date: date
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        v = v.lower()
        if v not in LEAVE_TYPES:
            raise ValueError(f"type must be one of {sorted(LEAVE_TYPES)}")
        return v


class LeaveDecide(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        v = v.lower()
        if v not in {"approved", "rejected"}:
            raise ValueError("status must be approved or rejected")
        return v


class LeaveRead(BaseModel):
    id: str
    employee_id: str
    employee_name: str | None = None
    type: str
    is_paid: bool
    days: int
    from_date: date
    to_date: date
    reason: str | None
    status: str
    approved_by: str | None
    approved_by_name: str | None = None


def _serialize(leave: Leave, employees_by_id: dict[str, str]) -> dict:
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "employee_name": employees_by_id.get(leave.employee_id),
        "type": leave.type,
        "is_paid": _is_paid(leave.type),
        "days": (leave.to_date - leave.from_date).days + 1,
        "from_date": leave.from_date,
        "to_date": leave.to_date,
        "reason": leave.reason,
        "status": leave.status,
        "approved_by": leave.approved_by,
        "approved_by_name": employees_by_id.get(leave.approved_by) if leave.approved_by else None,
    }


@router.post("", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
def apply_leave(
    payload: LeaveApply,
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(get_current_user),
) -> dict:
    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=400, detail="from_date must be <= to_date")

    leave = Leave(
        employee_id=current.user_id,
        type=payload.type,
        from_date=payload.from_date,
        to_date=payload.to_date,
        reason=payload.reason,
    )
    db.add(leave)
    db.flush()

    emp_names: dict[str, str] = {
        r.id: r.name for r in db.query(Employee.id, Employee.name).all()
    }
    return _serialize(leave, emp_names)


@router.get("", response_model=list[LeaveRead])
def list_leaves(
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    employee_id: str | None = None,
) -> list[dict]:
    q = db.query(Leave)
    if current.role != "admin":
        q = q.filter(Leave.employee_id == current.user_id)
    elif employee_id:
        q = q.filter(Leave.employee_id == employee_id)
    if status_filter:
        q = q.filter(Leave.status == status_filter)
    leaves = q.order_by(Leave.from_date.desc()).all()

    emp_names: dict[str, str] = {
        r.id: r.name for r in db.query(Employee.id, Employee.name).all()
    }
    return [_serialize(l, emp_names) for l in leaves]


@router.get("/balance/me")
def my_balance(
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, dict]:
    """Days remaining + days used per leave type, with paid/unpaid flag."""
    used: dict[str, int] = {k: 0 for k in DEFAULT_ANNUAL_BALANCE}
    rows = (
        db.query(Leave)
        .filter(Leave.employee_id == current.user_id, Leave.status == "approved")
        .all()
    )
    for r in rows:
        days = (r.to_date - r.from_date).days + 1
        used[r.type] = used.get(r.type, 0) + days
    return {
        k: {
            "remaining": max(DEFAULT_ANNUAL_BALANCE[k] - used.get(k, 0), 0),
            "used": used.get(k, 0),
            "total": DEFAULT_ANNUAL_BALANCE[k],
            "is_paid": _is_paid(k),
        }
        for k in DEFAULT_ANNUAL_BALANCE
    }


@router.get("/pending-count")
def pending_count(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> dict[str, int]:
    """Lightweight count for admin sidebar badge."""
    n = db.query(Leave).filter(Leave.status == "pending").count()
    return {"pending": n}


@router.patch("/{leave_id}", response_model=LeaveRead)
def decide_leave(
    leave_id: str,
    payload: LeaveDecide,
    db: Session = Depends(get_tenant_session),
    current: CurrentUser = Depends(require_admin),
) -> dict:
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    leave.status = payload.status
    leave.approved_by = current.user_id
    db.flush()

    emp_names: dict[str, str] = {
        r.id: r.name for r in db.query(Employee.id, Employee.name).all()
    }
    return _serialize(leave, emp_names)
