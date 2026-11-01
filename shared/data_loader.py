"""Load Q3 reference data from the supplied Excel files."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl


def _d(v: Any) -> Decimal:
    """Coerce a cell value to Decimal."""
    if v is None:
        return Decimal("0")
    if isinstance(v, str):
        return Decimal(v.replace(",", ""))
    return Decimal(str(v))


def load_q3_valuations(pack: Path) -> list[dict]:
    """Load CVP Q3 valuation report.

    Returns a list of dicts with keys:
      company, currency, cost_local, fair_value_local, fx_rate, fair_value_usd,
      valuation_method, valuation_date
    """
    wb = openpyxl.load_workbook(pack / "CVP_Valuation_Report_Q3_2022.xlsx", data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows: list[dict] = []
    for row in ws.iter_rows(min_row=6, values_only=True):
        company = row[0]
        if not company or company == "Total (USD)":
            break
        rows.append({
            "company": str(company),
            "currency": str(row[1]),
            "cost_local": _d(row[2]),
            "fair_value_local": _d(row[3]),
            "fx_rate": _d(row[4]),
            "fair_value_usd": _d(row[5]),
            "valuation_method": str(row[6]),
            "valuation_date": str(row[7].strftime("%Y-%m-%d") if hasattr(row[7], "strftime") else row[7]),
        })
    return rows


def load_q3_nav_summary(pack: Path) -> dict:
    """Load Q3 NAV summary (sheet 1) and Q4 accruals (sheet 2).

    Returns a dict with keys:
      cash, investments, audit_accrual_q3, admin_accrual_q3, total_liabilities_q3,
      nav_q3, holdings (list of dicts with cost_usd, fair_value_usd, unrealized),
      lp_commitments (list of dicts), q4_accruals (dict)
    """
    wb = openpyxl.load_workbook(pack / "GPF_NAV_Summary_Q3_2022.xlsx", data_only=True)

    # --- Sheet 1: Net assets 30 Sep 2022 ---
    ws1 = wb[wb.sheetnames[0]]
    result: dict[str, Any] = {}

    # Row 6: Cash at bank
    result["cash"] = _d(ws1["B6"].value)
    # Row 7: Investments at fair value
    result["investments"] = _d(ws1["B7"].value)
    # Row 10: Audit fee accrual
    result["audit_accrual_q3"] = _d(ws1["B10"].value)
    # Row 11: Admin fee payable Q3
    result["admin_accrual_q3"] = _d(ws1["B11"].value)
    # Row 12: Total liabilities
    result["total_liabilities_q3"] = _d(ws1["B12"].value)
    # Row 13: NAV
    result["nav_q3"] = _d(ws1["B13"].value)

    # Rows 17-24: Holdings detail
    holdings = []
    for r in range(17, 25):
        company = ws1.cell(row=r, column=1).value
        if not company:
            break
        holdings.append({
            "company": str(company),
            "cost_usd": _d(ws1.cell(row=r, column=2).value),
            "fair_value_usd": _d(ws1.cell(row=r, column=3).value),
            "unrealized": _d(ws1.cell(row=r, column=4).value),
        })
    result["holdings"] = holdings

    # Rows 29-38: LP commitments
    lps = []
    for r in range(29, 39):
        name = ws1.cell(row=r, column=1).value
        if not name:
            break
        lps.append({
            "name": str(name),
            "code": str(ws1.cell(row=r, column=2).value),
            "commitment": _d(ws1.cell(row=r, column=3).value),
        })
    result["lp_commitments"] = lps

    # --- Sheet 2: Q4 accruals 31 Dec 2022 ---
    ws2 = wb[wb.sheetnames[1]]
    result["q4_accruals"] = {
        "audit_accrual": _d(ws2["B4"].value),
        "admin_accrual": _d(ws2["B5"].value),
        "total": _d(ws2["B4"].value) + _d(ws2["B5"].value),
    }

    return result
