"""Seed the first tenant (Anutech) for demos and end-to-end verification.

Run inside the backend container:
    docker-compose exec backend python -m backend.scripts.seed_first_tenant

Idempotent — safe to re-run; it skips existing rows.
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text

from backend.core.database import (
    create_tenant_schema,
    get_engine,
    master_session,
    tenant_session,
)
from backend.core.security import hash_password
from backend.models.master_models import SubscriptionPlan, Tenant

log = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

TENANT_SLUG = "anutech"
TENANT_NAME = "Anutech"
PLAN_NAME = "Scale"
ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "pardeep@anutech.in")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!")


# (name, email, role, department, monthly_gross_inr, is_admin)
EMPLOYEES: list[tuple[str, str | None, str, str, int, bool]] = [
    ("Pardeep Sharma", ADMIN_EMAIL, "Director + Sales Head", "Leadership", 180000, True),
    ("Abhishek", "abhishek@anutech.in", "CTO", "Engineering", 35000, False),
    ("Hitesh Baghel", "hitesh@anutech.in", "COO + HR", "Operations", 52000, False),
    ("Pawan", "pawan@anutech.in", "Developer", "Engineering", 24000, False),
    ("Ananya Sharma", "ananya@anutech.in", "Sales Executive", "Sales", 90000, False),
    ("Darshan Kumar", "darshan@anutech.in", "Marketing Executive", "Sales", 20000, False),
    ("Ranjeet Raj", "ranjeet@anutech.in", "Support", "Operations", 38000, False),
    ("Mayank Sharma", "mayank@anutech.in", "Accounts", "Accounts", 80000, False),
]


def _read_tenant_ddl() -> str:
    here = os.path.dirname(__file__)
    path = os.path.abspath(os.path.join(here, "..", "migrations", "tenant_schema.sql"))
    with open(path, encoding="utf-8") as f:
        return f.read()


def ensure_master_schema() -> None:
    here = os.path.dirname(__file__)
    sql_path = os.path.abspath(os.path.join(here, "..", "migrations", "master_schema.sql"))
    with open(sql_path, encoding="utf-8") as f:
        sql = f.read()
    engine = get_engine()
    with engine.begin() as conn:
        for stmt in sql.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    log.info("master schema ensured")


def ensure_tenant() -> str:
    """Create tenant + schema if missing. Returns tenant.id."""
    with master_session() as s:
        plan = s.query(SubscriptionPlan).filter(SubscriptionPlan.name == PLAN_NAME).first()
        if not plan:
            raise RuntimeError(f"Plan {PLAN_NAME} not found — run master schema seed first")

        existing = s.query(Tenant).filter(Tenant.slug == TENANT_SLUG).first()
        if existing:
            log.info("tenant %s already exists (id=%s)", TENANT_SLUG, existing.id)
            return existing.id

        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=TENANT_NAME,
            slug=TENANT_SLUG,
            schema_name=TENANT_SLUG,
            plan_id=plan.id,
            status="active",
            is_active=True,
        )
        s.add(tenant)
        s.flush()
        log.info("created tenant %s (id=%s)", TENANT_SLUG, tenant.id)

    create_tenant_schema(TENANT_SLUG, _read_tenant_ddl())
    log.info("created schema %s", TENANT_SLUG)
    with master_session() as s:
        return s.query(Tenant).filter(Tenant.slug == TENANT_SLUG).one().id


def ensure_employees() -> None:
    pw = hash_password(ADMIN_PASSWORD)
    with tenant_session(TENANT_SLUG) as s:
        for name, email, role, dept, salary, is_admin in EMPLOYEES:
            row = s.execute(
                text("SELECT id FROM employees WHERE name = :n"),
                {"n": name},
            ).first()
            if row:
                continue
            s.execute(
                text(
                    "INSERT INTO employees ("
                    "id, name, email, role, department, basic_salary, joining_date, "
                    "status, is_admin, password_hash"
                    ") VALUES ("
                    ":id, :name, :email, :role, :dept, :salary, :jd, "
                    "'active', :admin, :pw"
                    ")"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "email": email,
                    "role": role,
                    "dept": dept,
                    "salary": Decimal(salary),
                    "jd": date(2024, 1, 1),
                    "admin": is_admin,
                    "pw": pw if is_admin else None,
                },
            )
            log.info("inserted employee %s", name)


def main() -> int:
    ensure_master_schema()
    ensure_tenant()
    ensure_employees()
    log.info("seed complete. Admin login → slug=%s, email=%s", TENANT_SLUG, ADMIN_EMAIL)
    log.info("(Set SEED_ADMIN_PASSWORD env var to override default password.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
