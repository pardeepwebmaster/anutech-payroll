"""Zoho Books integration — sync payroll runs as expense entries.

OAuth 2.0 flow (one-time setup):
  1. User creates a "Self Client" in https://api-console.zoho.<region>
  2. Generates an authorization code with scopes: ZohoBooks.expenses.CREATE,
     ZohoBooks.settings.READ
  3. Exchanges the code for a refresh_token (one-time)
  4. Stores client_id + client_secret + refresh_token + organization_id
     + salaries_account_id in env vars

Per-tenant credentials would live in the tenant DB; this v1 uses global
.env credentials for simplicity (one Zoho org per Anutech instance).

For step-by-step setup see ZOHO_SETUP.md.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import requests

from ..core.config import get_settings

log = logging.getLogger(__name__)


def _accounts_host(region: str) -> str:
    region = (region or "in").lower()
    return f"https://accounts.zoho.{region}"


def _api_host(region: str) -> str:
    region = (region or "in").lower()
    return f"https://www.zohoapis.{region}/books/v3"


class ZohoBooksClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        organization_id: str | None = None,
        region: str = "in",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.organization_id = organization_id
        self.region = region
        self._access_token: str | None = None

    def _refresh(self) -> str:
        resp = requests.post(
            f"{_accounts_host(self.region)}/oauth/v2/token",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if "access_token" not in body:
            raise RuntimeError(f"Zoho refresh failed: {body}")
        self._access_token = body["access_token"]
        return body["access_token"]

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            self._refresh()
        return {"Authorization": f"Zoho-oauthtoken {self._access_token}"}

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        params = kwargs.pop("params", {}) or {}
        if self.organization_id and "organization_id" not in params:
            params["organization_id"] = self.organization_id
        url = f"{_api_host(self.region)}{path}"
        resp = requests.request(
            method, url, params=params, headers=self._headers(), timeout=15, **kwargs
        )
        if resp.status_code == 401:
            self._refresh()
            resp = requests.request(
                method, url, params=params, headers=self._headers(), timeout=15, **kwargs
            )
        return resp

    def test_connection(self) -> dict[str, Any]:
        """Light call to verify creds + return organization info."""
        resp = self._request("GET", "/organizations")
        if not resp.ok:
            return {"ok": False, "status": resp.status_code, "error": resp.text[:300]}
        data = resp.json()
        orgs = data.get("organizations", [])
        return {
            "ok": True,
            "organization_count": len(orgs),
            "organizations": [
                {"id": o["organization_id"], "name": o["name"]} for o in orgs[:5]
            ],
        }

    def list_expense_accounts(self) -> list[dict[str, str]]:
        """List Chart of Accounts entries with type=expense — useful to find the
        salaries account ID during setup."""
        resp = self._request("GET", "/chartofaccounts", params={"filter_by": "AccountType.expense"})
        if not resp.ok:
            return []
        data = resp.json()
        return [
            {"id": a["account_id"], "name": a["account_name"]}
            for a in data.get("chartofaccounts", [])
        ]

    def create_expense(
        self,
        *,
        account_id: str,
        amount: Decimal,
        date_iso: str,
        description: str,
        reference: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "account_id": account_id,
            "amount": float(amount),
            "date": date_iso,
            "description": description,
        }
        if reference:
            body["reference_number"] = reference
        resp = self._request("POST", "/expenses", json=body)
        resp.raise_for_status()
        return resp.json()


def get_default_client() -> ZohoBooksClient | None:
    """Build a client from env. Returns None if creds missing."""
    s = get_settings()
    if not (s.ZOHO_CLIENT_ID and s.ZOHO_CLIENT_SECRET and s.ZOHO_REFRESH_TOKEN):
        return None
    return ZohoBooksClient(
        client_id=s.ZOHO_CLIENT_ID,
        client_secret=s.ZOHO_CLIENT_SECRET,
        refresh_token=s.ZOHO_REFRESH_TOKEN,
        organization_id=s.ZOHO_ORGANIZATION_ID or None,
        region=s.ZOHO_REGION,
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
        return {"ok": False, "skipped": True, "reason": "Zoho credentials not configured"}

    s = get_settings()
    org = organization_id or s.ZOHO_ORGANIZATION_ID
    account = salary_account_id or s.ZOHO_SALARIES_ACCOUNT_ID
    if not account:
        return {
            "ok": False,
            "reason": "ZOHO_SALARIES_ACCOUNT_ID not set — pick an expense account from Zoho Books",
        }
    if org:
        client.organization_id = org

    try:
        result = client.create_expense(
            account_id=account,
            amount=total_net,
            date_iso=period_iso,
            description=f"Salaries — payroll run {period_iso}",
            reference=f"payroll-run-{run_id}",
        )
        expense = result.get("expense", {})
        return {
            "ok": True,
            "expense_id": expense.get("expense_id"),
            "amount": expense.get("total"),
            "date": expense.get("date"),
            "reference_number": expense.get("reference_number"),
        }
    except requests.HTTPError as exc:
        log.exception("Zoho sync failed for run %s", run_id)
        body = ""
        try:
            body = exc.response.text[:300] if exc.response is not None else ""
        except Exception:
            pass
        return {"ok": False, "reason": f"Zoho API error: {exc} {body}"}
    except Exception as exc:
        log.exception("Zoho sync failed for run %s", run_id)
        return {"ok": False, "reason": str(exc)}


def get_zoho_status() -> dict[str, Any]:
    """Diagnostic — used by GET /payroll/zoho-status."""
    s = get_settings()
    configured = bool(s.ZOHO_CLIENT_ID and s.ZOHO_CLIENT_SECRET and s.ZOHO_REFRESH_TOKEN)
    if not configured:
        return {
            "configured": False,
            "missing": [
                k for k in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN")
                if not getattr(s, k)
            ],
        }
    client = get_default_client()
    if client is None:
        return {"configured": False}
    test = client.test_connection()
    return {
        "configured": True,
        "region": s.ZOHO_REGION,
        "organization_id_set": bool(s.ZOHO_ORGANIZATION_ID),
        "salaries_account_id_set": bool(s.ZOHO_SALARIES_ACCOUNT_ID),
        "connection": test,
    }
