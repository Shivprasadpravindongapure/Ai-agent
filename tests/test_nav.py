"""Comprehensive offline tests for NAV bridge arithmetic and computation."""

from decimal import Decimal

import pytest

from agent_b.models import NavBridge


class TestNavBridge:
    """Test that the NAV bridge formula balances."""

    def test_bridge_balances_simple(self):
        bridge = NavBridge(
            nav_q3=Decimal("160224800.00"),
            capital_called=Decimal("20000000.00"),
            distributions=Decimal("22500000.00"),
            income=Decimal("500000.00"),
            expenses=Decimal("1600000.00"),
            realized_gain=Decimal("9000000.00"),
            change_in_unrealized=Decimal("5000000.00"),
            nav_q4=Decimal("170624800.00"),
            difference=Decimal("0.00"),
        )
        computed = (
            bridge.nav_q3 + bridge.capital_called - bridge.distributions
            + bridge.income - bridge.expenses
            + bridge.realized_gain + bridge.change_in_unrealized
        )
        assert computed == bridge.nav_q4

    def test_bridge_difference_is_zero(self):
        nav_q3 = Decimal("100000000")
        capital = Decimal("10000000")
        dist = Decimal("5000000")
        income = Decimal("200000")
        expenses = Decimal("300000")
        realized = Decimal("1000000")
        unrealized = Decimal("2000000")
        nav_q4 = nav_q3 + capital - dist + income - expenses + realized + unrealized

        bridge = NavBridge(
            nav_q3=nav_q3, capital_called=capital, distributions=dist,
            income=income, expenses=expenses, realized_gain=realized,
            change_in_unrealized=unrealized, nav_q4=nav_q4,
            difference=Decimal("0.00"),
        )
        computed = (
            bridge.nav_q3 + bridge.capital_called - bridge.distributions
            + bridge.income - bridge.expenses
            + bridge.realized_gain + bridge.change_in_unrealized
        )
        assert bridge.nav_q4 - computed == bridge.difference

    def test_actual_q4_bridge(self):
        """Test with the actual GPF Q4 2022 numbers."""
        bridge = NavBridge(
            nav_q3=Decimal("160224800.00"),
            capital_called=Decimal("20000000.00"),
            distributions=Decimal("22500000.00"),
            income=Decimal("459429.25"),
            expenses=Decimal("1522850.00"),
            realized_gain=Decimal("9000000.00"),
            change_in_unrealized=Decimal("4102660.00"),
            nav_q4=Decimal("169764039.25"),
            difference=Decimal("0.00"),
        )
        computed = (
            bridge.nav_q3 + bridge.capital_called - bridge.distributions
            + bridge.income - bridge.expenses
            + bridge.realized_gain + bridge.change_in_unrealized
        )
        assert computed == bridge.nav_q4
        assert bridge.difference == Decimal("0.00")


class TestActualNAV:
    """Test NAV = cash + investments - liabilities."""

    def test_nav_direct(self):
        cash = Decimal("23896579.25")
        investments = Decimal("146062460.00")
        liabilities = Decimal("195000")
        nav = cash + investments - liabilities
        assert nav == Decimal("169764039.25")

    def test_ember_fx_conversion(self):
        """Ember Retail GmbH EUR → USD conversion at ECB rate 1.0666."""
        eur_fv = Decimal("13100000")
        rate = Decimal("1.0666")
        usd_fv = (eur_fv * rate).quantize(Decimal("0.01"))
        # 13100000 * 1.0666 = 13972460.00
        assert usd_fv == Decimal("13972460.00")

    def test_total_investments(self):
        """Sum of all Q4 holdings at fair value in USD."""
        holdings = {
            "Aurora": Decimal("25700000"),
            "Bluetarn": Decimal("42900000"),
            "Cedar": Decimal("9600000"),
            "Delta": Decimal("12150000"),
            "Ember": Decimal("13972460.00"),  # EUR converted
            "Granite": Decimal("16900000"),
            "Harbor": Decimal("10840000"),
            "Ionmere": Decimal("14000000"),  # at cost
        }
        total = sum(holdings.values())
        assert total == Decimal("146062460.00")

    def test_realized_gain_fjord(self):
        """Fjord Payments AS: proceeds - cost = realized gain."""
        proceeds = Decimal("29000000")
        cost = Decimal("20000000")
        assert proceeds - cost == Decimal("9000000")

    def test_unrealized_q3(self):
        """Q3 total unrealized gain."""
        q3_unrealized = {
            "Aurora": Decimal("6600000"),
            "Bluetarn": Decimal("8700000"),
            "Cedar": Decimal("-900000"),
            "Delta": Decimal("2300000"),
            "Ember": Decimal("-1024200"),
            "Fjord": Decimal("7500000"),
            "Granite": Decimal("-600000"),
            "Harbor": Decimal("1200000"),
        }
        total = sum(q3_unrealized.values())
        assert total == Decimal("23775800")

    def test_unrealized_q4(self):
        """Q4 total unrealized gain (Fjord removed, Ionmere at 0)."""
        q4_unrealized = {
            "Aurora": Decimal("25700000") - Decimal("18000000"),
            "Bluetarn": Decimal("42900000") - Decimal("22500000"),
            "Cedar": Decimal("9600000") - Decimal("15000000"),
            "Delta": Decimal("12150000") - Decimal("9500000"),
            "Ember": Decimal("13972460.00") - Decimal("14184000"),
            "Granite": Decimal("16900000") - Decimal("17000000"),
            "Harbor": Decimal("10840000") - Decimal("8000000"),
            "Ionmere": Decimal("14000000") - Decimal("14000000"),
        }
        total = sum(q4_unrealized.values())
        expected = Decimal("27878460.00")
        assert total == expected

    def test_change_in_unrealized(self):
        q3 = Decimal("23775800")
        q4 = Decimal("27878460.00")
        change = q4 - q3
        assert change == Decimal("4102660.00")

    def test_expenses_calculation(self):
        """Total expenses = mgmt_fee + other_expense - refunds + bank_charges + Q4 accruals."""
        mgmt_fee = Decimal("1250000.00")
        other_expenses = Decimal("80500.00")  # legal 38500 + D&O 42000
        refunds = Decimal("3500.00")
        bank_charges = Decimal("850.00")  # 150*3 + 75 + 275 + 50
        q4_accruals = Decimal("195000")

        total = mgmt_fee + other_expenses - refunds + bank_charges + q4_accruals
        assert total == Decimal("1522850.00")

    def test_income_calculation(self):
        """Total income = dividend + interest."""
        dividend = Decimal("420000.00")
        interest = Decimal("8150.27") + Decimal("21402.88") + Decimal("9876.10")
        total = dividend + interest
        assert total == Decimal("459429.25")
