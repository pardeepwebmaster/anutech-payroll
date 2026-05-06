"""Compliance router — PF/ESI/TDS/PT filing tracker."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..core.database import get_tenant_session
from ..core.security import CurrentUser, get_current_user, require_admin
from ..models.tenant_models import ComplianceFiling

router = APIRouter()

VALID_TYPES = {"PF", "ESI", "TDS", "PT"}


class FilingCreate(BaseModel):
    type: str
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    due_date: date
    amount: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        v = v.upper()
        if v not in VALID_TYPES:
            raise ValueError(f"type must be one of {sorted(VALID_TYPES)}")
        return v


class FilingUpdate(BaseModel):
    filed_date: date | None = None
    status: str | None = None
    amount: Decimal | None = None


class FilingRead(BaseModel):
    id: str
    type: str
    period: str
    due_date: date
    filed_date: date | None
    status: str
    amount: Decimal

    model_config = {"from_attributes": True}


@router.post("", response_model=FilingRead, status_code=status.HTTP_201_CREATED)
def create_filing(
    payload: FilingCreate,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> ComplianceFiling:
    f = ComplianceFiling(
        type=payload.type,
        period=payload.period,
        due_date=payload.due_date,
        amount=payload.amount,
    )
    db.add(f)
    db.flush()
    return f


@router.get("", response_model=list[FilingRead])
def list_filings(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(get_current_user),
    status_filter: str | None = None,
    type_filter: str | None = None,
) -> list[ComplianceFiling]:
    q = db.query(ComplianceFiling)
    if status_filter:
        q = q.filter(ComplianceFiling.status == status_filter)
    if type_filter:
        q = q.filter(ComplianceFiling.type == type_filter.upper())
    return q.order_by(ComplianceFiling.due_date.desc()).all()


@router.patch("/{filing_id}", response_model=FilingRead)
def update_filing(
    filing_id: str,
    payload: FilingUpdate,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> ComplianceFiling:
    f = db.query(ComplianceFiling).filter(ComplianceFiling.id == filing_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Filing not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(f, k, v)
    if data.get("filed_date") and not data.get("status"):
        f.status = "filed"
    db.flush()
    return f


@router.get("/upcoming")
def upcoming_dues(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    today = date.today()
    rows = (
        db.query(ComplianceFiling)
        .filter(ComplianceFiling.status == "due", ComplianceFiling.due_date >= today)
        .order_by(ComplianceFiling.due_date)
        .all()
    )
    return [
        {
            "id": r.id,
            "type": r.type,
            "period": r.period,
            "due_date": r.due_date.isoformat(),
            "days_until_due": (r.due_date - today).days,
            "amount": str(r.amount),
        }
        for r in rows
    ]
