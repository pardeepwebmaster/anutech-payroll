"""Auth router — tenant onboarding, login, JWT issue."""
from __future__ import annotations

import os
import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import (
    create_tenant_schema,
    get_master_session,
    tenant_session,
)
from ..core.security import (
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..models.master_models import SubscriptionPlan, Tenant

router = APIRouter()

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,32}$")


def _read_tenant_ddl() -> str:
    here = os.path.dirname(__file__)
    path = os.path.join(here, "..", "migrations", "tenant_schema.sql")
    with open(os.path.abspath(path), encoding="utf-8") as f:
        return f.read()


# ---------- Schemas ----------

class TenantRegister(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=3, max_length=32)
    plan: str = Field(description="Plan name: Starter | Growth | Scale")
    admin_name: str
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        v = v.lower()
        if not SLUG_RE.match(v):
            raise ValueError("slug must be lowercase, 3-32 chars, start with a letter")
        if v in {"public", "pg_catalog", "information_schema", "admin", "api"}:
            raise ValueError("slug is reserved")
        return v


class TenantRegisterResponse(BaseModel):
    tenant_id: str
    slug: str
    schema_name: str
    admin_user_id: str
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    slug: str
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_slug: str


# ---------- Endpoints ----------

@router.post("/register", response_model=TenantRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_tenant(
    payload: TenantRegister,
    master: Session = Depends(get_master_session),
) -> TenantRegisterResponse:
    existing = master.query(Tenant).filter(Tenant.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")

    plan = master.query(SubscriptionPlan).filter(SubscriptionPlan.name == payload.plan).first()
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {payload.plan}")

    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.company_name,
        slug=payload.slug,
        schema_name=payload.slug,
        plan_id=plan.id,
        status="active",
        is_active=True,
    )
    master.add(tenant)
    master.flush()

    create_tenant_schema(payload.slug, _read_tenant_ddl())

    admin_id = str(uuid.uuid4())
    pw_hash = hash_password(payload.admin_password)
    with tenant_session(payload.slug) as ts:
        ts.execute(
            text(
                """
                INSERT INTO employees (
                    id, name, email, role, department, basic_salary, joining_date,
                    status, password_hash, is_admin
                ) VALUES (
                    :id, :name, :email, :role, :department, :basic_salary, :joining_date,
                    'active', :password_hash, TRUE
                )
                """
            ),
            {
                "id": admin_id,
                "name": payload.admin_name,
                "email": payload.admin_email,
                "role": "Administrator",
                "department": "Leadership",
                "basic_salary": 0,
                "joining_date": date.today(),
                "password_hash": pw_hash,
            },
        )

    token = create_access_token(
        user_id=admin_id, tenant_schema=payload.slug, role="admin"
    )

    return TenantRegisterResponse(
        tenant_id=tenant.id,
        slug=tenant.slug,
        schema_name=tenant.schema_name,
        admin_user_id=admin_id,
        access_token=token,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    master: Session = Depends(get_master_session),
) -> LoginResponse:
    tenant = master.query(Tenant).filter(Tenant.slug == payload.slug).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    with tenant_session(tenant.schema_name) as ts:
        row = ts.execute(
            text(
                """
                SELECT id, password_hash, is_admin, status
                FROM employees
                WHERE email = :email
                """
            ),
            {"email": payload.email},
        ).first()

    if not row or row.status != "active":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not row.password_hash or not verify_password(payload.password, row.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = "admin" if row.is_admin else "employee"
    token = create_access_token(
        user_id=str(row.id), tenant_schema=tenant.schema_name, role=role
    )
    return LoginResponse(access_token=token, role=role, tenant_slug=tenant.slug)


@router.get("/me")
def me(current: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    return {
        "user_id": current.user_id,
        "tenant_schema": current.tenant_schema,
        "role": current.role,
    }
