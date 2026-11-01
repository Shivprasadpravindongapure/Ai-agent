"""Pydantic models for Agent B (Valuation & NAV Agent)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class Mark(BaseModel):
    """A single Q4 fair-value mark from CVP."""
    company: str
    currency: str
    fair_value: Decimal
    valuation_method: str
    valuation_date: str


class Note(BaseModel):
    company: str
    note: str


class CompanyReview(BaseModel):
    """Review output for one portfolio company."""
    company: str
    currency: str
    q3_fair_value: Decimal | None = None
    q4_fair_value: Decimal | None = None
    change_pct: Decimal | None = None
    q3_method: str | None = None
    q4_method: str | None = None
    flags: list[str] = Field(default_factory=list)   # e.g. ["R1", "R2"]
    reason: str = ""


class ReviewOutput(BaseModel):
    threshold_pct: Decimal
    eurusd_rate: Decimal
    companies: list[CompanyReview]


class NavBridge(BaseModel):
    nav_q3: Decimal
    capital_called: Decimal
    distributions: Decimal
    income: Decimal
    expenses: Decimal
    realized_gain: Decimal
    change_in_unrealized: Decimal
    nav_q4: Decimal
    difference: Decimal  # should be 0.00


class NavOutput(BaseModel):
    closing_cash: Decimal
    investments_usd: Decimal
    liabilities: Decimal
    nav_q4: Decimal
    bridge: NavBridge
