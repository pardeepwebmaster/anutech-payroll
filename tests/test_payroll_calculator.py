"""Unit tests for the Indian payroll calculator. NO mocks — pure logic."""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.services.payroll_calculator import (
    DEFAULT_PT,
    calculate_payslip,
    compute_annual_tax,
    compute_monthly_tds,
    detect_anomalies,
)


class TestBasicSplit:
    def test_basic_is_40_percent(self):
        b = calculate_payslip(50000)
        assert b.basic == Decimal("20000.00")

    def test_hra_is_40_percent_of_basic(self):
        b = calculate_payslip(50000)
        assert b.hra == Decimal("8000.00")

    def test_components_sum_to_gross(self):
        b = calculate_payslip(50000)
        assert b.basic + b.hra + b.special_allowance == Decimal("50000.00")

    def test_zero_gross(self):
        b = calculate_payslip(0)
        assert b.gross == Decimal("0.00")
        assert b.net_pay == -DEFAULT_PT - Decimal("0.00")  # only PT applies
        # Nobody actually has zero gross, but make sure we don't crash.

    def test_negative_gross_raises(self):
        with pytest.raises(ValueError):
            calculate_payslip(-1)


class TestPF:
    def test_pf_employee_12_percent_of_basic(self):
        b = calculate_payslip(50000)
        # basic = 20000, PF = 12% = 2400
        assert b.pf_employee == Decimal("2400.00")

    def test_pf_employer_matches_employee(self):
        b = calculate_payslip(50000)
        assert b.pf_employer == b.pf_employee

    def test_pf_zero_when_basic_zero(self):
        b = calculate_payslip(0)
        assert b.pf_employee == Decimal("0.00")


class TestESI:
    def test_esi_applies_below_threshold(self):
        b = calculate_payslip(20000)
        assert b.esi_employee == Decimal("150.00")  # 20000 * 0.0075
        assert b.esi_employer == Decimal("650.00")  # 20000 * 0.0325

    def test_esi_at_exact_threshold(self):
        b = calculate_payslip(21000)
        assert b.esi_employee > 0  # <=, not <

    def test_esi_zero_above_threshold(self):
        b = calculate_payslip(21001)
        assert b.esi_employee == Decimal("0.00")
        assert b.esi_employer == Decimal("0.00")

    def test_esi_zero_for_high_earners(self):
        b = calculate_payslip(180000)
        assert b.esi_employee == Decimal("0.00")
        assert b.esi_employer == Decimal("0.00")


class TestProfessionalTax:
    def test_default_pt_is_200(self):
        b = calculate_payslip(50000)
        assert b.pt == Decimal("200.00")

    def test_custom_pt(self):
        b = calculate_payslip(50000, professional_tax=300)
        assert b.pt == Decimal("300.00")

    def test_negative_pt_raises(self):
        with pytest.raises(ValueError):
            calculate_payslip(50000, professional_tax=-1)


class TestTDS:
    def test_tds_zero_below_taxable_threshold(self):
        # Annual 3L gross → 3L - 75K standard ded = 2.25L taxable < 3L slab
        assert compute_monthly_tds(Decimal("300000")) == Decimal("0.00")

    def test_tds_increases_with_income(self):
        low = compute_monthly_tds(Decimal("600000"))
        high = compute_monthly_tds(Decimal("2000000"))
        assert high > low > 0

    def test_annual_tax_at_slab_boundaries(self):
        # 7L taxable: first 3L free, next 4L @ 5% = 20000
        assert compute_annual_tax(Decimal("700000")) == Decimal("20000.00")
        # 10L taxable: 0 + 20000 + (3L @ 10%) = 50000
        assert compute_annual_tax(Decimal("1000000")) == Decimal("50000.00")

    def test_health_cess_applied(self):
        tds = compute_monthly_tds(Decimal("1000000"))
        # tax = 50000, cess = 2000, total = 52000, monthly = 4333.33
        assert tds == Decimal("4333.33")


class TestNetPay:
    def test_net_pay_subtracts_only_employee_deductions(self):
        # Employer PF/ESI must NOT reduce net pay
        b = calculate_payslip(20000)
        expected = (
            Decimal("20000")
            - b.pf_employee
            - b.esi_employee
            - b.pt
            - b.tds
        )
        assert b.net_pay == expected

    def test_high_earner_no_esi(self):
        b = calculate_payslip(180000)
        # 180000 - PF(12% of 72000 = 8640) - 0 - 200 - tds
        assert b.esi_employee == Decimal("0.00")
        assert b.pf_employee == Decimal("8640.00")
        assert b.net_pay == Decimal("180000") - Decimal("8640") - Decimal("200") - b.tds


class TestAnutechSeedEmployees:
    """Spot-check with actual Anutech tenant employees from CLAUDE.md."""

    @pytest.mark.parametrize(
        "name,gross",
        [
            ("Pardeep Sharma", 180000),
            ("Abhishek", 35000),
            ("Hitesh Baghel", 52000),
            ("Pawan", 24000),
            ("Ananya Sharma", 90000),
            ("Darshan Kumar", 20000),
            ("Ranjeet Raj", 38000),
            ("Mayank Sharma", 80000),
        ],
    )
    def test_no_negative_net_pay(self, name, gross):
        b = calculate_payslip(gross)
        assert b.net_pay > 0, f"{name} ({gross}) has non-positive net pay"

    def test_low_earner_gets_esi(self):
        # Darshan @ 20000 < 21000 → eligible for ESI
        b = calculate_payslip(20000)
        assert b.esi_employee > 0

    def test_director_no_esi(self):
        b = calculate_payslip(180000)
        assert b.esi_employee == 0


class TestAnomalies:
    def test_clean_payslip_no_warnings(self):
        b = calculate_payslip(50000)
        assert detect_anomalies(b) == []

    def test_huge_swing_flagged(self):
        prev = calculate_payslip(50000)
        curr = calculate_payslip(20000)  # 60% drop
        warnings = detect_anomalies(curr, previous=prev)
        assert any("changed" in w for w in warnings)

    def test_small_swing_not_flagged(self):
        prev = calculate_payslip(50000)
        curr = calculate_payslip(52000)  # 4% bump
        warnings = detect_anomalies(curr, previous=prev)
        assert all("changed" not in w for w in warnings)
