"""Pytest fixtures shared across all teammates' tests.

Tenant isolation tests must hit a real PostgreSQL — no SQLite. Spin up
the test DB via docker-compose before running:
    docker-compose up -d postgres
    pytest tests/
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Force test env BEFORE importing app modules.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://anutech:anutech@localhost:5432/anutech_payroll_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

from backend.core.database import (  # noqa: E402
    create_tenant_schema,
    get_engine,
    master_session,
    tenant_session,
)
from backend.main import app  # noqa: E402

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "migrations")


def _read(path: str) -> str:
    with open(os.path.join(MIGRATIONS_DIR, path), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="session", autouse=True)
def _setup_master_db() -> Iterator[None]:
    """Create master schema once per test session."""
    engine = get_engine()
    with engine.begin() as conn:
        for stmt in _read("master_schema.sql").split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    yield


@pytest.fixture
def tenant_schema() -> Iterator[str]:
    """Create a throwaway tenant schema, drop after the test."""
    schema = f"t_{uuid.uuid4().hex[:8]}"
    create_tenant_schema(schema, _read("tenant_schema.sql"))
    yield schema
    with get_engine().begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


@pytest.fixture
def db(tenant_schema: str):
    """Tenant-scoped session for the throwaway schema."""
    with tenant_session(tenant_schema) as s:
        yield s


@pytest.fixture
def master_db():
    with master_session() as s:
        yield s


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
