"""FastAPI entry point — wires all routers, middleware, and the scheduler."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
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


@asynccontextmanager
async def lifespan(app: FastAPI):
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


app.include_router(auth.router,       prefix="/api/v1/auth",        tags=["auth"])
app.include_router(employees.router,  prefix="/api/v1/employees",   tags=["employees"])
app.include_router(payroll.router,    prefix="/api/v1/payroll",     tags=["payroll"])
app.include_router(leaves.router,     prefix="/api/v1/leaves",      tags=["leaves"])
app.include_router(compliance.router, prefix="/api/v1/compliance",  tags=["compliance"])
app.include_router(reports.router,    prefix="/api/v1/reports",     tags=["reports"])
app.include_router(ai_chat.router,    prefix="/api/v1/ai-chat",     tags=["ai-chat"])
