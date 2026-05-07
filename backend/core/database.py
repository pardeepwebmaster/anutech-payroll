from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base. Master and tenant models both extend this."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _normalize_db_url(url: str) -> str:
    """Render and other PaaS providers hand out plain postgres:// URLs.
    SQLAlchemy 2.x dropped that scheme — coerce to postgresql+psycopg2://.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            _normalize_db_url(settings.DATABASE_URL),
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


@contextmanager
def tenant_session(schema: str) -> Iterator[Session]:
    """Open a session pinned to {schema}, public via SET search_path.

    Use this when you need a session outside a request (scheduler, scripts).
    Inside requests, prefer Depends(get_tenant_session).
    """
    factory = get_session_factory()
    session = factory()
    try:
        session.execute(text(f'SET search_path TO "{schema}", public'))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def master_session() -> Iterator[Session]:
    """Open a session for master DB operations (tenants, plans, billing)."""
    settings = get_settings()
    factory = get_session_factory()
    session = factory()
    try:
        session.execute(text(f'SET search_path TO "{settings.MASTER_SCHEMA}"'))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_tenant_session(request: Request) -> Generator[Session, None, None]:  # FastAPI dependency
    """Request-scoped tenant session. Tenant slug comes from request.state.tenant_schema,
    set by tenant_middleware. Routers should depend on this — never construct sessions
    by hand inside routers.
    """
    schema = getattr(request.state, "tenant_schema", None)
    if not schema:
        raise RuntimeError(
            "tenant_schema not set on request.state. "
            "Did tenant_middleware run? Routers must include the JWT auth dependency."
        )
    factory = get_session_factory()
    session = factory()
    try:
        session.execute(text(f'SET search_path TO "{schema}", public'))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_master_session(request: Request) -> Generator[Session, None, None]:  # FastAPI dependency
    """Request-scoped master session — for /auth/register and admin-only endpoints."""
    settings = get_settings()
    factory = get_session_factory()
    session = factory()
    try:
        session.execute(text(f'SET search_path TO "{settings.MASTER_SCHEMA}"'))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tenant_schema(tenant_slug: str, ddl_sql: str) -> None:
    """Create a fresh schema and run the tenant DDL inside it. Used during onboarding.
    The DDL_SQL should be the contents of migrations/tenant_schema.sql.
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{tenant_slug}"'))
        conn.execute(text(f'SET search_path TO "{tenant_slug}"'))
        for stmt in _split_sql(ddl_sql):
            if stmt.strip():
                conn.execute(text(stmt))


def _split_sql(sql: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    in_dollar = False
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        if "$$" in line:
            in_dollar = not in_dollar
        buf.append(line)
        if line.rstrip().endswith(";") and not in_dollar:
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out
