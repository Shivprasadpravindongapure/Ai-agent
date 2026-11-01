"""Offline tests for NAV bridge arithmetic."""

from decimal import Decimal

from agent_b.models import NavBridge


class TestNavBridge:
    """Test that the NAV bridge formula balances."""

    def test_bridge_balances_simple(self):
        """A simple bridge where all components are known."""
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
        # bridge formula: nav_q3 + capital_called - distributions + income - expenses
        #                 + realized_gain + change_in_unrealized = nav_q4
        computed = (
            bridge.nav_q3
            + bridge.capital_called
            - bridge.distributions
            + bridge.income
            - bridge.expenses
            + bridge.realized_gain
            + bridge.change_in_unrealized
        )
        assert computed == bridge.nav_q4, (
            f"Bridge does not balance: computed={computed}, nav_q4={bridge.nav_q4}"
        )

    def test_bridge_difference_is_zero(self):
        """The difference field should be nav_q4 minus the computed value."""
        nav_q3 = Decimal("100000000")
        capital = Decimal("10000000")
        dist = Decimal("5000000")
        income = Decimal("200000")
        expenses = Decimal("300000")
        realized = Decimal("1000000")
        unrealized = Decimal("2000000")
        nav_q4 = nav_q3 + capital - dist + income - expenses + realized + unrealized

        bridge = NavBridge(
            nav_q3=nav_q3,
            capital_called=capital,
            distributions=dist,
            income=income,
            expenses=expenses,
            realized_gain=realized,
            change_in_unrealized=unrealized,
            nav_q4=nav_q4,
            difference=Decimal("0.00"),
        )
        computed = (
            bridge.nav_q3 + bridge.capital_called - bridge.distributions
            + bridge.income - bridge.expenses
            + bridge.realized_gain + bridge.change_in_unrealized
        )
        assert bridge.nav_q4 - computed == bridge.difference

    def test_bridge_detects_imbalance(self):
        """If nav_q4 doesn't match the formula, difference should be non-zero."""
        bridge = NavBridge(
            nav_q3=Decimal("100000000"),
            capital_called=Decimal("10000000"),
            distributions=Decimal("5000000"),
            income=Decimal("200000"),
            expenses=Decimal("300000"),
            realized_gain=Decimal("1000000"),
            change_in_unrealized=Decimal("2000000"),
            nav_q4=Decimal("107900001"),  # off by 1
            difference=Decimal("1"),
        )
        computed = (
            bridge.nav_q3 + bridge.capital_called - bridge.distributions
            + bridge.income - bridge.expenses
            + bridge.realized_gain + bridge.change_in_unrealized
        )
        assert bridge.nav_q4 - computed == bridge.difference
