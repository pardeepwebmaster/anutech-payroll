"""FastAPI entry point.

At Phase 0 only `health` is wired. Teammates plug in their routers as they
land. Order of router registration here is the contract for `backend-api`.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.tenant_middleware import TenantMiddleware

settings = get_settings()
logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger("anutech-payroll")

app = FastAPI(
    title="Anutech Payroll",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "dev" else [
        f"https://*.{settings.APP_BASE_DOMAIN}"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.APP_ENV}


# --- Router registration (uncommented by `backend-api` teammate as routers land) ---
# from .routers import auth, employees, payroll, leaves, compliance, reports, ai_chat
# app.include_router(auth.router,       prefix="/api/v1/auth",        tags=["auth"])
# app.include_router(employees.router,  prefix="/api/v1/employees",   tags=["employees"])
# app.include_router(payroll.router,    prefix="/api/v1/payroll",     tags=["payroll"])
# app.include_router(leaves.router,     prefix="/api/v1/leaves",      tags=["leaves"])
# app.include_router(compliance.router, prefix="/api/v1/compliance",  tags=["compliance"])
# app.include_router(reports.router,    prefix="/api/v1/reports",     tags=["reports"])
# app.include_router(ai_chat.router,    prefix="/api/v1/ai-chat",     tags=["ai-chat"])


# --- Scheduler (started by `payroll-engine` teammate) ---
# from .services.scheduler import start_scheduler, shutdown_scheduler
#
# @app.on_event("startup")
# def _start_scheduler() -> None:
#     start_scheduler()
#
# @app.on_event("shutdown")
# def _stop_scheduler() -> None:
#     shutdown_scheduler()
