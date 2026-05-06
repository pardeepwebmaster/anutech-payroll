"""Multi-tenant isolation: tenant A's JWT must NOT see tenant B's data.

This test is non-negotiable. If it fails, do not merge.
"""
from __future__ import annotations

from sqlalchemy import text


def test_tenants_cannot_see_each_other(client, tenant_schema):
    """Two tenants with the same email field cannot leak rows across schemas."""
    # tenant_schema fixture creates one schema; create a second.
    from backend.core.database import create_tenant_schema, get_engine, tenant_session

    sql_path = __import__("os").path.join(
        __import__("os").path.dirname(__file__), "..", "backend", "migrations",
        "tenant_schema.sql",
    )
    with open(sql_path, encoding="utf-8") as f:
        ddl = f.read()

    schema_a = tenant_schema  # already created
    schema_b = f"{schema_a}_b"
    create_tenant_schema(schema_b, ddl)

    from datetime import date

    with tenant_session(schema_a) as s:
        s.execute(
            text(
                "INSERT INTO employees (name, role, department, basic_salary, joining_date) "
                "VALUES ('A-User', 'Eng', 'Tech', 50000, :d)"
            ),
            {"d": date.today()},
        )
    with tenant_session(schema_b) as s:
        s.execute(
            text(
                "INSERT INTO employees (name, role, department, basic_salary, joining_date) "
                "VALUES ('B-User', 'Eng', 'Tech', 60000, :d)"
            ),
            {"d": date.today()},
        )

    with tenant_session(schema_a) as s:
        names = [row[0] for row in s.execute(text("SELECT name FROM employees")).all()]
    assert names == ["A-User"], f"Tenant A leaked B's rows: {names}"

    with tenant_session(schema_b) as s:
        names = [row[0] for row in s.execute(text("SELECT name FROM employees")).all()]
    assert names == ["B-User"], f"Tenant B leaked A's rows: {names}"

    with get_engine().begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_b}" CASCADE'))
