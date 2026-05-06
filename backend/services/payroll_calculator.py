"""Indian payroll calculation engine — canonical source of truth.

NEVER re-implement these rules elsewhere. Anyone displaying or persisting
payslip components must call `calculate_payslip(gross, ...)`.

Rules (also documented in CLAUDE.md):
  Basic              = gross * 40%
  HRA                = basic * 40%
  Special Allowance  = gross - basic - hra
  PF Employee        = basic * 12%   (if basic > 0)
  PF Employer        = basic * 12%
  ESI Employee       = gross * 0.75% (only if gross <= 21000)
  ESI Employer       = gross * 3.25% (only if gross <= 21000)
  Professional Tax   = ₹200/month (Maharashtra default; configurable)
  TDS                = annual income tax slab, divided by 12

  Net Pay = gross - PF_Employee - ESI_Employee - PT - TDS

All amounts rounded half-up to 2 decimals using Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ESI_GROSS_THRESHOLD = Decimal("21000")
PF_RATE = Decimal("0.12")
ESI_EMPLOYEE_RATE = Decimal("0.0075")
ESI_EMPLOYER_RATE = Decimal("0.0325")
BASIC_RATE = Decimal("0.40")
HRA_RATE = Decimal("0.40")
DEFAULT_PT = Decimal("200")
TWO_PLACES = Decimal("0.01")

# FY 2024-25 / 2025-26 — New Regime slabs (default).
# Annual income → marginal rate. Standard deduction of ₹75,000 applied.
NEW_REGIME_STANDARD_DEDUCTION = Decimal("75000")
NEW_REGIME_SLABS: list[tuple[Decimal, Decimal, Decimal]] = [
    # (slab_start, slab_end, rate)
    (Decimal("0"), Decimal("300000"), Decimal("0.00")),
    (Decimal("300000"), Decimal("700000"), Decimal("0.05")),
    (Decimal("700000"), Decimal("1000000"), Decimal("0.10")),
    (Decimal("1000000"), Decimal("1200000"), Decimal("0.15")),
    (Decimal("1200000"), Decimal("1500000"), Decimal("0.20")),
    (Decimal("1500000"), Decimal("999999999"), Decimal("0.30")),
]
HEALTH_CESS_RATE = Decimal("0.04")  # 4% on tax


@dataclass(frozen=True)
class PayslipBreakdown:
    """Pure value object — no DB coupling. Routers convert to ORM as needed."""

    gross: Decimal
    basic: Decimal
    hra: Decimal
    special_allowance: Decimal
    pf_employee: Decimal
    pf_employer: Decimal
    esi_employee: Decimal
    esi_employer: Decimal
    pt: Decimal
    tds: Decimal
    net_pay: Decimal

    def as_dict(self) -> dict[str, str]:
        """Serialise to JSON-safe strings (preserves precision)."""
        return {k: str(v) for k, v in self.__dict__.items()}


def _q(x: Decimal | float | int | str) -> Decimal:
    """Quantise to 2 decimal places, half-up."""
    return Decimal(str(x)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_annual_tax(annual_taxable: Decimal) -> Decimal:
    """Slab-wise tax on annual taxable income (after standard deduction)."""
    tax = Decimal("0")
    for start, end, rate in NEW_REGIME_SLABS:
        if annual_taxable <= start:
            break
        slice_amount = min(annual_taxable, end) - start
        tax += slice_amount * rate
    return tax


def compute_monthly_tds(annual_gross: Decimal) -> Decimal:
    """Divide annual tax (with cess) by 12 for monthly TDS deduction."""
    annual_gross = Decimal(str(annual_gross))
    taxable = max(annual_gross - NEW_REGIME_STANDARD_DEDUCTION, Decimal("0"))
    tax = compute_annual_tax(taxable)
    tax_with_cess = tax * (Decimal("1") + HEALTH_CESS_RATE)
    return _q(tax_with_cess / Decimal("12"))


def calculate_payslip(
    gross_monthly: Decimal | float | int | str,
    *,
    professional_tax: Decimal | float | int | str = DEFAULT_PT,
    annual_gross_override: Decimal | float | int | str | None = None,
) -> PayslipBreakdown:
    """Compute every payslip component for one month.

    Args:
      gross_monthly: monthly gross salary (₹).
      professional_tax: state-specific PT (default ₹200).
      annual_gross_override: useful for mid-year joiners or bonus
                             projections. Defaults to gross * 12.
    """
    gross = Decimal(str(gross_monthly))
    if gross < 0:
        raise ValueError("gross_monthly cannot be negative")

    pt = Decimal(str(professional_tax))
    if pt < 0:
        raise ValueError("professional_tax cannot be negative")

    annual_gross = (
        Decimal(str(annual_gross_override))
        if annual_gross_override is not None
        else gross * Decimal("12")
    )

    basic = _q(gross * BASIC_RATE)
    hra = _q(basic * HRA_RATE)
    special_allowance = _q(gross - basic - hra)

    pf_employee = _q(basic * PF_RATE) if basic > 0 else Decimal("0.00")
    pf_employer = _q(basic * PF_RATE)

    if gross <= ESI_GROSS_THRESHOLD:
        esi_employee = _q(gross * ESI_EMPLOYEE_RATE)
        esi_employer = _q(gross * ESI_EMPLOYER_RATE)
    else:
        esi_employee = Decimal("0.00")
        esi_employer = Decimal("0.00")

    tds = compute_monthly_tds(annual_gross)

    net_pay = _q(gross - pf_employee - esi_employee - pt - tds)

    return PayslipBreakdown(
        gross=_q(gross),
        basic=basic,
        hra=hra,
        special_allowance=special_allowance,
        pf_employee=pf_employee,
        pf_employer=pf_employer,
        esi_employee=esi_employee,
        esi_employer=esi_employer,
        pt=_q(pt),
        tds=tds,
        net_pay=net_pay,
    )


def detect_anomalies(
    breakdown: PayslipBreakdown,
    previous: PayslipBreakdown | None = None,
    *,
    variance_threshold: Decimal = Decimal("0.20"),
) -> list[str]:
    """Heuristic anomaly checks for the payroll-anomaly Claude tool.

    Returns a list of human-readable warnings (empty = clean).
    """
    warnings: list[str] = []

    if breakdown.net_pay <= 0:
        warnings.append("Net pay is zero or negative")
    if breakdown.tds > breakdown.gross * Decimal("0.40"):
        warnings.append("TDS exceeds 40% of gross — verify slab calculation")
    if breakdown.basic + breakdown.hra + breakdown.special_allowance != breakdown.gross:
        warnings.append("Basic + HRA + Special does not sum to gross")

    if previous is not None and previous.gross > 0:
        delta = abs(breakdown.net_pay - previous.net_pay) / previous.net_pay
        if delta > variance_threshold:
            warnings.append(
                f"Net pay changed {delta:.0%} vs previous month "
                f"(₹{previous.net_pay} → ₹{breakdown.net_pay})"
            )

    return warnings
