"""APScheduler jobs — IST-cron driven reminders and auto-runs."""
from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from ..core.config import get_settings
from ..core.database import master_session, tenant_session
from ..models.master_models import Tenant

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
IST = "Asia/Kolkata"


def _iter_active_tenants():
    with master_session() as s:
        return s.query(Tenant).filter(Tenant.is_active.is_(True)).all()


# ---------- Job bodies ----------

def job_payroll_reminder_25th() -> None:
    """Ping each tenant: payroll for this month is due in ~5 days."""
    log.info("[scheduler] 25th reminder running")
    for t in _iter_active_tenants():
        log.info("  reminder for tenant %s", t.slug)
        # Real impl: enqueue an email / agent task. Stub-logged here.


def job_auto_run_payroll_1st() -> None:
    """Auto-run payroll on the 1st (configurable per tenant)."""
    from ..services.payroll_calculator import calculate_payslip
    from ..models.tenant_models import Employee, Payslip, PayrollRun

    log.info("[scheduler] 1st auto-run")
    today = datetime.now()
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)

    for t in _iter_active_tenants():
        with tenant_session(t.schema_name) as db:
            existing = (
                db.query(PayrollRun)
                .filter(PayrollRun.year == year, PayrollRun.month == month)
                .first()
            )
            if existing and existing.status == "completed":
                continue
            run = existing or PayrollRun(year=year, month=month, status="running")
            if not existing:
                db.add(run)
                db.flush()
            employees = (
                db.query(Employee)
                .filter(Employee.status == "active", Employee.basic_salary > 0)
                .all()
            )
            for emp in employees:
                b = calculate_payslip(emp.basic_salary)
                db.add(
                    Payslip(
                        employee_id=emp.id,
                        payroll_run_id=run.id,
                        gross=b.gross, basic=b.basic, hra=b.hra,
                        special_allowance=b.special_allowance,
                        pf_employee=b.pf_employee, pf_employer=b.pf_employer,
                        esi_employee=b.esi_employee, esi_employer=b.esi_employer,
                        pt=b.pt, tds=b.tds, net_pay=b.net_pay,
                    )
                )
            run.status = "completed"
            run.run_at = datetime.utcnow()


def job_compliance_alert_7th() -> None:
    log.info("[scheduler] 7th compliance alert")
    for t in _iter_active_tenants():
        with tenant_session(t.schema_name) as db:
            due = db.execute(
                text(
                    "SELECT type, period, due_date FROM compliance_filings "
                    "WHERE status='due' AND due_date <= (CURRENT_DATE + INTERVAL '14 days') "
                    "ORDER BY due_date"
                )
            ).all()
            if due:
                log.info("  %s has %d upcoming filings", t.slug, len(due))


def job_hr_pending_leaves_daily() -> None:
    log.info("[scheduler] daily HR leave check")
    for t in _iter_active_tenants():
        with tenant_session(t.schema_name) as db:
            n = db.execute(
                text("SELECT COUNT(*) FROM leaves WHERE status='pending'")
            ).scalar()
            if n:
                log.info("  %s has %d pending leave requests", t.slug, n)


# ---------- Lifecycle ----------

def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    settings = get_settings()
    if settings.APP_ENV == "test":
        log.info("scheduler skipped in test env")
        return BackgroundScheduler()

    sched = BackgroundScheduler(timezone=IST)
    sched.add_job(job_payroll_reminder_25th, CronTrigger(day=25, hour=9, minute=0, timezone=IST), id="payroll_reminder_25th")
    sched.add_job(job_auto_run_payroll_1st, CronTrigger(day=1, hour=2, minute=0, timezone=IST), id="auto_run_payroll_1st")
    sched.add_job(job_compliance_alert_7th, CronTrigger(day=7, hour=9, minute=0, timezone=IST), id="compliance_alert_7th")
    sched.add_job(job_hr_pending_leaves_daily, CronTrigger(hour=9, minute=0, timezone=IST), id="hr_pending_leaves_daily")
    sched.start()
    _scheduler = sched
    log.info("scheduler started: %s", [j.id for j in sched.get_jobs()])
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler stopped")
