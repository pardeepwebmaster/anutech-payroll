"""Payslip PDF rendering (WeasyPrint) + SMTP delivery.

WeasyPrint needs GTK on Windows — production runs through Docker, where it
works out of the box. The render function falls back to plain HTML→bytes if
weasyprint can't import (dev convenience).
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..core.config import get_settings

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


PAYSLIP_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Payslip</title>
<style>
  body { font-family: Arial, sans-serif; padding: 32px; color: #1a1a1a; }
  h1 { color: #5C52C9; margin: 0 0 4px; }
  .sub { color: #555; margin: 0 0 24px; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #e5e5e5; }
  th { background: #F1F0FB; color: #463E9C; font-size: 13px; }
  .right { text-align: right; }
  .total { font-weight: 700; background: #F1F0FB; }
  .meta td { border: none; padding: 4px 0; font-size: 13px; color: #444; }
  .footer { margin-top: 32px; font-size: 11px; color: #777; }
</style>
</head><body>
  <h1>{{ tenant_name|upper }}</h1>
  <p class="sub">Payslip for {{ month_name }} {{ year }}</p>

  <table class="meta">
    <tr><td><b>Employee</b></td><td>{{ emp.name }}</td>
        <td><b>Role</b></td><td>{{ emp.role }}</td></tr>
    <tr><td><b>Department</b></td><td>{{ emp.department }}</td>
        <td><b>PAN</b></td><td>{{ emp.pan or '-' }}</td></tr>
    <tr><td><b>Bank A/c</b></td><td>{{ emp.bank_account or '-' }}</td>
        <td><b>IFSC</b></td><td>{{ emp.bank_ifsc or '-' }}</td></tr>
  </table>

  <table>
    <thead><tr><th>Earnings</th><th class="right">Amount (₹)</th><th>Deductions</th><th class="right">Amount (₹)</th></tr></thead>
    <tbody>
      <tr><td>Basic</td><td class="right">{{ ps.basic }}</td>
          <td>PF (Employee)</td><td class="right">{{ ps.pf_employee }}</td></tr>
      <tr><td>HRA</td><td class="right">{{ ps.hra }}</td>
          <td>ESI (Employee)</td><td class="right">{{ ps.esi_employee }}</td></tr>
      <tr><td>Special Allowance</td><td class="right">{{ ps.special_allowance }}</td>
          <td>Professional Tax</td><td class="right">{{ ps.pt }}</td></tr>
      <tr><td></td><td></td><td>TDS</td><td class="right">{{ ps.tds }}</td></tr>
      <tr class="total">
        <td>Gross</td><td class="right">{{ ps.gross }}</td>
        <td>Total Deductions</td>
        <td class="right">{{ "%.2f"|format(ps.gross|float - ps.net_pay|float) }}</td>
      </tr>
    </tbody>
  </table>

  <h2 style="margin-top:24px;color:#5C52C9;">Net Pay: ₹{{ ps.net_pay }}</h2>

  <p class="footer">
    This is a system-generated payslip. Employer PF (₹{{ ps.pf_employer }}) and
    Employer ESI (₹{{ ps.esi_employer }}) are not deducted from your salary.
  </p>
</body></html>
"""

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def render_payslip_html(*, employee, payslip, run, tenant_name: str) -> str:
    template = _env.from_string(PAYSLIP_TEMPLATE)
    return template.render(
        emp=employee,
        ps=payslip,
        year=run.year,
        month_name=_MONTH_NAMES[run.month],
        tenant_name=tenant_name,
    )


def render_payslip_pdf(*, employee, payslip, run, tenant_name: str) -> bytes:
    html = render_payslip_html(
        employee=employee, payslip=payslip, run=run, tenant_name=tenant_name
    )
    try:
        from weasyprint import HTML  # type: ignore
        return HTML(string=html).write_pdf()
    except (ImportError, OSError) as exc:  # WeasyPrint unavailable on this platform
        log.warning("WeasyPrint unavailable (%s); returning HTML as PDF fallback", exc)
        return html.encode("utf-8")


def send_email(*, to: str, subject: str, html_body: str, attachments: list[tuple[str, bytes, str]] | None = None) -> None:
    """Plain SMTP sender. Skips silently if SMTP not configured."""
    settings = get_settings()
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        log.info("SMTP not configured; skipping email to %s", to)
        return

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("Your email client does not support HTML. Please view in a modern client.")
    msg.add_alternative(html_body, subtype="html")

    for filename, content, mime in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(content, maintype=maintype, subtype=subtype or "octet-stream", filename=filename)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
    log.info("Email sent to %s: %s", to, subject)


def send_payslip_email(*, employee, payslip, run, tenant_name: str) -> None:
    if not employee.email:
        return
    html = render_payslip_html(employee=employee, payslip=payslip, run=run, tenant_name=tenant_name)
    pdf = render_payslip_pdf(employee=employee, payslip=payslip, run=run, tenant_name=tenant_name)
    filename = f"payslip-{run.year}-{run.month:02d}.pdf"
    send_email(
        to=employee.email,
        subject=f"Payslip for {_MONTH_NAMES[run.month]} {run.year}",
        html_body=html,
        attachments=[(filename, pdf, "application/pdf")],
    )
