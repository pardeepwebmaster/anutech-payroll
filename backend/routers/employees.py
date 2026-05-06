"""Employees router — CRUD with tenant scope, search/filter, CSV export."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.database import get_tenant_session
from ..core.security import (
    CurrentUser,
    get_current_user,
    hash_password,
    require_admin,
)
from ..models.tenant_models import Employee

router = APIRouter()


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr | None = None
    role: str
    department: str
    basic_salary: Decimal = Field(ge=0)
    joining_date: date
    pan: str | None = Field(default=None, max_length=10)
    bank_account: str | None = None
    bank_ifsc: str | None = None
    is_admin: bool = False
    password: str | None = Field(default=None, min_length=8)


class EmployeeUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    department: str | None = None
    basic_salary: Decimal | None = None
    status: str | None = None
    pan: str | None = None
    bank_account: str | None = None
    bank_ifsc: str | None = None
    is_admin: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class EmployeeRead(BaseModel):
    id: str
    name: str
    email: str | None
    role: str
    department: str
    basic_salary: Decimal
    joining_date: date
    status: str
    pan: str | None
    bank_account: str | None
    bank_ifsc: str | None
    is_admin: bool

    model_config = {"from_attributes": True}


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> Employee:
    if payload.email:
        existing = db.query(Employee).filter(Employee.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")

    emp = Employee(
        name=payload.name,
        email=payload.email,
        role=payload.role,
        department=payload.department,
        basic_salary=payload.basic_salary,
        joining_date=payload.joining_date,
        pan=payload.pan,
        bank_account=payload.bank_account,
        bank_ifsc=payload.bank_ifsc,
        is_admin=payload.is_admin,
        password_hash=hash_password(payload.password) if payload.password else None,
    )
    db.add(emp)
    db.flush()
    return emp


@router.get("", response_model=list[EmployeeRead])
def list_employees(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(get_current_user),
    q: str | None = Query(default=None, description="Search name/email/role"),
    department: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> list[Employee]:
    query = db.query(Employee)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Employee.name.ilike(like), Employee.email.ilike(like), Employee.role.ilike(like))
        )
    if department:
        query = query.filter(Employee.department == department)
    if status_filter:
        query = query.filter(Employee.status == status_filter)
    return query.order_by(Employee.name).offset(offset).limit(limit).all()


@router.get("/export.csv")
def export_csv(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> StreamingResponse:
    rows = db.query(Employee).order_by(Employee.name).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "name", "email", "role", "department", "basic_salary",
         "joining_date", "status", "pan"]
    )
    for e in rows:
        writer.writerow(
            [e.id, e.name, e.email or "", e.role, e.department, e.basic_salary,
             e.joining_date.isoformat(), e.status, e.pan or ""]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="employees.csv"'},
    )


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(
    employee_id: str,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(get_current_user),
) -> Employee:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> Employee:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    data = payload.model_dump(exclude_unset=True)
    pw = data.pop("password", None)
    for k, v in data.items():
        setattr(emp, k, v)
    if pw:
        emp.password_hash = hash_password(pw)
    db.flush()
    return emp


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_employee(
    employee_id: str,
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(require_admin),
) -> None:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.status = "inactive"
    db.flush()
