"""FastAPI entry point — wires all routers, middleware, and the scheduler."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .core.config import get_settings
from .core.database import get_engine
from .core.tenant_middleware import TenantMiddleware
from .routers import (
    ai_chat,
    auth,
    compliance,
    employees,
    leaves,
    payroll,
    reports,
)
from .services.scheduler import shutdown_scheduler, start_scheduler

settings = get_settings()
logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger("anutech-payroll")


def _run_master_schema() -> None:
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "migrations", "master_schema.sql")
    with open(sql_path, encoding="utf-8") as f:
        sql = f.read()
    with get_engine().begin() as conn:
        for stmt in sql.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    log.info("master schema applied")


def _maybe_seed_tenant() -> None:
    try:
        from .scripts.seed_first_tenant import (
            ensure_employees,
            ensure_tenant,
        )
        ensure_tenant()
        ensure_employees()
        log.info("demo tenant seeded")
    except Exception:
        log.exception("seed failed (non-fatal)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_INIT_DB:
        try:
            _run_master_schema()
        except Exception:
            log.exception("master schema apply failed (continuing — may already exist)")
    if settings.AUTO_SEED_TENANT:
        _maybe_seed_tenant()
    if settings.APP_ENV != "test":
        start_scheduler()
        log.info("scheduler started")
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Anutech Payroll",
    description="Multi-tenant SaaS payroll for Indian companies",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


_default_origins = (
    ["*"]
    if settings.APP_ENV == "dev"
    else [
        f"https://{settings.APP_BASE_DOMAIN}",
        f"https://*.{settings.APP_BASE_DOMAIN}",
    ]
)
allow_origins = _default_origins + settings.cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.APP_ENV}


app.include_router(auth.router,       prefix="/api/v1/auth",        tags=["auth"])
app.include_router(employees.router,  prefix="/api/v1/employees",   tags=["employees"])
app.include_router(payroll.router,    prefix="/api/v1/payroll",     tags=["payroll"])
app.include_router(leaves.router,     prefix="/api/v1/leaves",      tags=["leaves"])
app.include_router(compliance.router, prefix="/api/v1/compliance",  tags=["compliance"])
app.include_router(reports.router,    prefix="/api/v1/reports",     tags=["reports"])
app.include_router(ai_chat.router,    prefix="/api/v1/ai-chat",     tags=["ai-chat"])
