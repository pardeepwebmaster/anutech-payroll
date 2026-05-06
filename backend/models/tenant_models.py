from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Employee(Base):
    """One row per employee. Lives in the tenant's schema."""

    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False)
    basic_salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, doc="Monthly gross salary in INR"
    )
    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(16), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    payslips: Mapped[list[Payslip]] = relationship(back_populates="employee")
    leaves: Mapped[list[Leave]] = relationship(
        back_populates="employee", foreign_keys="Leave.employee_id"
    )


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_payroll_runs_year_month"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    total_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    run_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    payslips: Mapped[list[Payslip]] = relationship(back_populates="payroll_run")


class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "payroll_run_id", name="uq_payslips_employee_run"
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("employees.id"), nullable=False
    )
    payroll_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("payroll_runs.id"), nullable=False
    )

    gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    basic: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hra: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    special_allowance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    pf_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pf_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    esi_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    esi_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pt: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tds: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    net_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    employee: Mapped[Employee] = relationship(back_populates="payslips")
    payroll_run: Mapped[PayrollRun] = relationship(back_populates="payslips")


class Leave(Base):
    __tablename__ = "leaves"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("employees.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # casual, sick, earned
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )  # pending|approved|rejected
    approved_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("employees.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    employee: Mapped[Employee] = relationship(
        back_populates="leaves", foreign_keys=[employee_id]
    )


class ComplianceFiling(Base):
    __tablename__ = "compliance_filings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # PF | ESI | TDS | PT
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    filed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="due", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
