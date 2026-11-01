"""Offline tests for PDF parser and transaction model."""

from decimal import Decimal
from pathlib import Path

import pytest

from agent_a.models import Transaction
from agent_a.pdf_parser import parse_bank_statement, validate_balances


# Use the actual pack if available, otherwise skip
PACK = Path("pack")
PDF_PATH = PACK / "GPF_Bank_Statement_Q4_2022.pdf"


@pytest.fixture
def transactions():
    if not PDF_PATH.exists():
        pytest.skip("Bank statement PDF not found")
    return parse_bank_statement(PDF_PATH)


class TestPDFParser:
    """Integration tests against the actual bank statement."""

    def test_transaction_count(self, transactions):
        """39 transactions + 1 opening balance = 40 rows."""
        assert len(transactions) == 40

    def test_opening_balance(self, transactions):
        assert transactions[0].balance == Decimal("12450000.00")
        assert transactions[0].description == "BALANCE BROUGHT FORWARD"
        assert transactions[0].debit is None
        assert transactions[0].credit is None

    def test_closing_balance(self, transactions):
        assert transactions[-1].balance == Decimal("23896579.25")

    def test_balance_validation(self, transactions):
        """All running balances must reconcile."""
        validate_balances(transactions)

    def test_bank_reconciliation(self, transactions):
        """opening + credits - debits = closing."""
        opening = transactions[0].balance
        total_debits = sum(t.debit for t in transactions if t.debit)
        total_credits = sum(t.credit for t in transactions if t.credit)
        closing = transactions[-1].balance
        assert opening + total_credits - total_debits == closing

    def test_total_debits(self, transactions):
        total = sum(t.debit for t in transactions if t.debit)
        assert total == Decimal("38016350.00")

    def test_total_credits(self, transactions):
        total = sum(t.credit for t in transactions if t.credit)
        assert total == Decimal("49462929.25")

    def test_management_fee(self, transactions):
        """First transaction: mgmt fee of 1,250,000."""
        t = transactions[1]
        assert t.debit == Decimal("1250000.00")
        assert "GREATNESS CAPITAL" in t.description

    def test_multiline_description(self, transactions):
        """Mgmt fee description wraps onto multiple lines."""
        t = transactions[1]
        assert "MGMT FEE" in t.description
        assert "LPA" in t.description

    def test_investment_purchase(self, transactions):
        """Ionmere purchase on 15 Dec."""
        t = transactions[36]  # index 36
        assert t.debit == Decimal("14000000.00")
        assert "IONMERE" in t.description

    def test_sale_proceeds(self, transactions):
        """Fjord sale on 18 Nov."""
        t = transactions[20]
        assert t.credit == Decimal("29000000.00")
        assert "FJORD" in t.description

    def test_interest(self, transactions):
        """Three interest entries: Oct, Nov, Dec."""
        interest = [t for t in transactions if "CREDIT INTEREST" in t.description]
        assert len(interest) == 3
        total = sum(t.credit for t in interest)
        assert total == Decimal("39429.25")

    def test_distribution_count(self, transactions):
        """10 distributions on 30 Nov."""
        dist = [t for t in transactions if "DISTRIBUTION" in t.description]
        assert len(dist) == 10


class TestTransactionModel:
    def test_capital_call_model(self):
        t = Transaction(
            date="2022-10-28",
            description="WIRE IN ORG:FJELLHEIM SOV RESERVE REF GPF CC07 LP02",
            credit=Decimal("3200000.00"),
            balance=Decimal("14635000.00"),
            category="capital_call",
            lp_code="LP02",
        )
        assert t.category == "capital_call"
        assert t.lp_code == "LP02"

    def test_distribution_model(self):
        t = Transaction(
            date="2022-11-30",
            description="OUTWARD WIRE DISTRIBUTION 2022-04 TO LAKESHORE TEACHERS PB (LP01)",
            debit=Decimal("4500000.00"),
            balance=Decimal("46929178.15"),
            category="distribution",
            lp_code="LP01",
        )
        assert t.category == "distribution"

    def test_decimal_precision(self):
        """Verify Decimal arithmetic preserves cents."""
        a = Decimal("12450000.00")
        b = Decimal("8150.27")
        assert a + b == Decimal("12458150.27")
