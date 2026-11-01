"""Mark review logic — compares Q3 vs Q4 marks and flags anomalies.

Rules (from the assignment):
  R1: Material change in fair value from Q3 (threshold-based, local currency)
  R2: Valuation method changed Q3→Q4
  R3: Fund holds a company at 31 Dec but CVP gave no Q4 mark
  R4: CVP gave a mark for a company the fund does not hold at 31 Dec
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# ECB EUR/USD rate on 30 Dec 2022 (last TARGET2 business day before 31 Dec 2022)
EURUSD_RATE = Decimal("1.0666")

# Materiality threshold for R1 (percentage)
THRESHOLD_PCT = Decimal("15")


def review_marks(
    q3_valuations: list[dict],
    q4_marks: list[dict],
    q4_notes: list[dict],
    q4_purchases: list[dict],
    q4_sales: list[dict],
    q3_holdings: list[dict],
) -> dict:
    """Run review rules R1–R4 and return the review output.

    Parameters
    ----------
    q3_valuations : Q3 CVP valuation data (from Excel)
    q4_marks : Q4 marks from agent_b_data.json
    q4_notes : notes from agent_b_data.json
    q4_purchases : purchases from agent_b_data.json
    q4_sales : sales from agent_b_data.json
    q3_holdings : Q3 holdings from NAV summary (cost, fair_value in USD)

    Returns
    -------
    dict with threshold_pct, eurusd_rate, and companies list
    """
    # Build lookup maps
    q3_by_company = {v["company"]: v for v in q3_valuations}
    q4_by_company = {m["company"]: m for m in q4_marks}
    notes_by_company = {n["company"]: n["note"] for n in q4_notes}
    q3_holdings_by_company = {h["company"]: h for h in q3_holdings}

    # Determine which companies are held at 31 Dec 2022
    # Start with Q3 holdings, remove sold, add purchased
    sold_companies = {s["company"] for s in q4_sales}
    purchased_companies = {p["company"] for p in q4_purchases}
    held_at_q4 = (
        {h["company"] for h in q3_holdings} - sold_companies | purchased_companies
    )

    # All companies to review (union of Q3 holdings, Q4 marks, purchases, sales)
    all_companies = (
        {v["company"] for v in q3_valuations}
        | {m["company"] for m in q4_marks}
        | purchased_companies
        | sold_companies
    )

    companies = []

    for company in sorted(all_companies):
        q3 = q3_by_company.get(company)
        q4 = q4_by_company.get(company)
        flags: list[str] = []
        reasons: list[str] = []

        # Determine currency
        currency = "USD"
        if q4:
            currency = q4["currency"]
        elif q3:
            currency = q3["currency"]

        # Q3 and Q4 fair values in local currency
        q3_fv_local = Decimal(str(q3["fair_value_local"])) if q3 else None
        q4_fv_local = Decimal(str(q4["fair_value"])) if q4 else None

        # Q3 and Q4 methods
        q3_method = q3["valuation_method"] if q3 else None
        q4_method = q4["valuation_method"] if q4 else None

        # --- R1: Material change ---
        if q3_fv_local is not None and q4_fv_local is not None and q3_fv_local != 0:
            change_pct = ((q4_fv_local - q3_fv_local) / q3_fv_local * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if abs(change_pct) > THRESHOLD_PCT:
                flags.append("R1")
                reasons.append(
                    f"Fair value changed {change_pct}% in {currency} "
                    f"(Q3: {q3_fv_local}, Q4: {q4_fv_local}), exceeds {THRESHOLD_PCT}% threshold"
                )
        else:
            change_pct = None

        # --- R2: Method change ---
        if q3_method and q4_method and q3_method != q4_method:
            flags.append("R2")
            reasons.append(
                f"Valuation method changed: {q3_method} → {q4_method}"
            )

        # --- R3: Held but no Q4 mark ---
        if company in held_at_q4 and q4 is None:
            flags.append("R3")
            note = notes_by_company.get(company, "No note provided")
            reasons.append(f"Held at 31 Dec but no Q4 mark. Note: {note}")

        # --- R4: Mark for company not held ---
        if company not in held_at_q4 and q4 is not None:
            flags.append("R4")
            reasons.append("Q4 mark exists but company not held at 31 Dec")

        companies.append({
            "company": company,
            "currency": currency,
            "q3_fair_value": str(q3_fv_local) if q3_fv_local is not None else None,
            "q4_fair_value": str(q4_fv_local) if q4_fv_local is not None else None,
            "change_pct": str(change_pct) if change_pct is not None else None,
            "q3_method": q3_method,
            "q4_method": q4_method,
            "flags": flags,
            "reason": "; ".join(reasons) if reasons else "",
        })

    return {
        "threshold_pct": str(THRESHOLD_PCT),
        "eurusd_rate": str(EURUSD_RATE),
        "companies": companies,
    }
