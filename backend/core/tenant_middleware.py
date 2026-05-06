from __future__ import annotations

import logging

from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .config import get_settings

log = logging.getLogger(__name__)

PUBLIC_PATH_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """Decode JWT (when present), pin tenant_schema onto request.state.

    Does NOT enforce auth — that's `get_current_user`'s job. This middleware
    only sets state so downstream dependencies can use it. Routes that don't
    require auth (login, register) are skipped.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(p) for p in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            settings = get_settings()
            try:
                payload = jwt.decode(
                    token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
                )
                request.state.tenant_schema = payload.get("tenant_schema")
                request.state.user_id = payload.get("sub")
                request.state.role = payload.get("role")
            except JWTError:
                # Let downstream auth dependency handle the rejection
                pass

        return await call_next(request)
