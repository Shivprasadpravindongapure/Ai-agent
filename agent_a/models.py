"""Pydantic models for Agent A (Bank & Ingestion Agent)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


TRANSACTION_CATEGORIES = Literal[
    "capital_call",
    "distribution",
    "management_fee",
    "investment_purchase",
    "sale_proceeds",
    "dividend_income",
    "interest_income",
    "bank_charges",
    "expense",
    "expense_refund",
    "accrual_settlement",
]


class Transaction(BaseModel):
    """A single bank-statement transaction."""
    date: str                           # YYYY-MM-DD
    description: str
    reference: str | None = None
    debit: Decimal | None = None        # amount leaving the account
    credit: Decimal | None = None       # amount entering the account
    balance: Decimal
    category: TRANSACTION_CATEGORIES | None = None
    lp_code: str | None = None          # e.g. "LP01" for capital calls / distributions
    company: str | None = None          # for investment_purchase / sale_proceeds


class Purchase(BaseModel):
    company: str
    date: str  # YYYY-MM-DD
    amount_usd: Decimal


class Sale(BaseModel):
    company: str
    date: str  # YYYY-MM-DD
    proceeds_usd: Decimal
