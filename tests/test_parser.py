"""Offline tests for PDF parser (fixture-based, no actual PDF needed)."""

from decimal import Decimal

from agent_a.models import Transaction


class TestTransactionModel:
    """Test the Transaction Pydantic model."""

    def test_create_capital_call(self):
        t = Transaction(
            date="2022-10-28",
            description="WIRE IN ORG:FJELLHEIM SOV RESERVE REF GPF CC07 LP02",
            reference=None,
            debit=None,
            credit=Decimal("3200000.00"),
            balance=Decimal("14635000.00"),
            category="capital_call",
            lp_code="LP02",
            company=None,
        )
        assert t.category == "capital_call"
        assert t.lp_code == "LP02"

    def test_create_distribution(self):
        t = Transaction(
            date="2022-11-30",
            description="OUTWARD WIRE DISTRIBUTION 2022-04 TO LAKESHORE TEACHERS PB (LP01)",
            debit=Decimal("4500000.00"),
            credit=None,
            balance=Decimal("46929178.15"),
            category="distribution",
            lp_code="LP01",
        )
        assert t.category == "distribution"
        assert t.lp_code == "LP01"

    def test_balance_validation(self):
        """Verify that running balance can be tracked with Decimal."""
        opening = Decimal("12450000.00")
        credit = Decimal("420000.00")
        debit = Decimal("65000.00")
        expected = opening + credit - debit
        assert expected == Decimal("12805000.00")

    def test_investment_purchase(self):
        t = Transaction(
            date="2022-12-15",
            description="OUTWARD WIRE IONMERE MATERIALS LTD SUBSCRIPTION SERIES B SHARES",
            reference="OW-221215-01",
            debit=Decimal("14000000.00"),
            credit=None,
            balance=Decimal("23886903.15"),
            category="investment_purchase",
            company="Ionmere Materials Ltd",
        )
        assert t.category == "investment_purchase"
        assert t.company == "Ionmere Materials Ltd"
