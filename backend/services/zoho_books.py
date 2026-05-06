"""Per-tenant Zoho Books sync — pushes payroll runs as expense entries.

This is intentionally a thin wrapper. Real Zoho integration requires
per-tenant OAuth (refresh tokens stored in tenant DB). For now it uses
global creds from .env as a fallback.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import requests

from ..core.config import get_settings

log = logging.getLogger(__name__)

ZOHO_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"
ZOHO_API_BASE = "https://www.zohoapis.in/books/v3"


class ZohoBooksClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        organization_id: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.organization_id = organization_id
        self._access_token: str | None = None

    def _refresh(self) -> str:
        resp = requests.post(
            ZOHO_TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        self._access_token = token
        return token

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            self._refresh()
        return {"Authorization": f"Zoho-oauthtoken {self._access_token}"}

    def create_expense(
        self,
        *,
        account_id: str,
        amount: Decimal,
        date_iso: str,
        description: str,
        reference: str | None = None,
    ) -> dict[str, Any]:
        params = {"organization_id": self.organization_id} if self.organization_id else {}
        body = {
            "account_id": account_id,
            "amount": float(amount),
            "date": date_iso,
            "description": description,
        }
        if reference:
            body["reference_number"] = reference
        resp = requests.post(
            f"{ZOHO_API_BASE}/expenses",
            params=params,
            json=body,
            headers=self._headers(),
            timeout=15,
        )
        if resp.status_code == 401:
            # token expired mid-call
            self._refresh()
            resp = requests.post(
                f"{ZOHO_API_BASE}/expenses",
                params=params,
                json=body,
                headers=self._headers(),
                timeout=15,
            )
        resp.raise_for_status()
        return resp.json()


def get_default_client() -> ZohoBooksClient | None:
    """Build a client from .env. Returns None if creds missing."""
    s = get_settings()
    if not (s.ZOHO_CLIENT_ID and s.ZOHO_CLIENT_SECRET and s.ZOHO_REFRESH_TOKEN):
        return None
    return ZohoBooksClient(
        client_id=s.ZOHO_CLIENT_ID,
        client_secret=s.ZOHO_CLIENT_SECRET,
        refresh_token=s.ZOHO_REFRESH_TOKEN,
    )


def sync_payroll_run_to_zoho(
    *,
    run_id: str,
    period_iso: str,
    total_net: Decimal,
    organization_id: str | None = None,
    salary_account_id: str | None = None,
) -> dict[str, Any] | None:
    client = get_default_client()
    if client is None:
        log.info("Zoho not configured; skipping sync for run %s", run_id)
        return None
    if organization_id:
        client.organization_id = organization_id
    account = salary_account_id or "salary-default"
    return client.create_expense(
        account_id=account,
        amount=total_net,
        date_iso=period_iso,
        description=f"Salaries for {period_iso}",
        reference=f"payroll-run-{run_id}",
    )
