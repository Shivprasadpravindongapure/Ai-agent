"""NAV and NAV-bridge computation for Q4 2022.

NAV = cash + investments_at_fair_value - liabilities
Bridge: nav_q3 + capital_called - distributions + income - expenses
        + realized_gain + change_in_unrealized = nav_q4
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from agent_b.review import EURUSD_RATE


def compute_nav(
    q3_nav_data: dict,
    q4_marks: list[dict],
    q4_notes: list[dict],
    q4_purchases: list[dict],
    q4_sales: list[dict],
    transactions: list[dict],
) -> dict:
    """Compute the Q4 NAV and NAV bridge.

    Parameters
    ----------
    q3_nav_data : loaded Q3 NAV summary (from data_loader)
    q4_marks : Q4 marks from agent_b_data.json
    q4_notes : notes from agent_b_data.json
    q4_purchases : purchases from agent_b_data.json
    q4_sales : sales from agent_b_data.json
    transactions : categorised bank transactions (list of dicts)

    Returns
    -------
    dict with closing_cash, investments_usd, liabilities, nav_q4, and bridge
    """
    D = Decimal

    # ================================================================
    # 1. Closing cash (from bank statement — last transaction balance)
    # ================================================================
    closing_cash = D(str(transactions[-1]["balance"]))

    # ================================================================
    # 2. Investments at fair value (USD) at 31 Dec 2022
    # ================================================================
    # Start with Q3 holdings, remove sold companies, add purchased ones
    q3_holdings = {h["company"]: h for h in q3_nav_data["holdings"]}
    sold = {s["company"] for s in q4_sales}
    purchased = {p["company"]: D(str(p["amount_usd"])) for p in q4_purchases}

    # Build Q4 holdings with costs
    q4_holdings: dict[str, dict] = {}

    # Carry forward Q3 holdings (except sold)
    for company, h in q3_holdings.items():
        if company in sold:
            continue
        q4_holdings[company] = {
            "cost_usd": D(str(h["cost_usd"])),
        }

    # Add new purchases
    for company, cost in purchased.items():
        q4_holdings[company] = {
            "cost_usd": cost,
        }

    # Build Q4 mark lookup
    q4_mark_by_company = {m["company"]: m for m in q4_marks}

    # Notes: companies with no mark yet
    no_mark_companies = set()
    for note in q4_notes:
        if "Not yet valued" in note["note"] or "not yet valued" in note["note"]:
            no_mark_companies.add(note["company"])

    # Calculate Q4 fair values in USD
    investments_usd = D("0")
    for company, holding in q4_holdings.items():
        mark = q4_mark_by_company.get(company)
        if mark:
            fv_local = D(str(mark["fair_value"]))
            currency = mark["currency"]
            if currency == "EUR":
                fv_usd = (fv_local * EURUSD_RATE).quantize(D("0.01"), rounding=ROUND_HALF_UP)
            else:
                fv_usd = fv_local
        elif company in no_mark_companies:
            # Carry at cost (Assumption 2)
            fv_usd = holding["cost_usd"]
        else:
            # Should not happen — flag it
            fv_usd = holding["cost_usd"]

        holding["fair_value_usd"] = fv_usd
        investments_usd += fv_usd

    # ================================================================
    # 3. Liabilities (Q4 accruals from sheet 2)
    # ================================================================
    liabilities = D(str(q3_nav_data["q4_accruals"]["total"]))

    # ================================================================
    # 4. Q4 NAV (direct calculation)
    # ================================================================
    nav_q4 = closing_cash + investments_usd - liabilities

    # ================================================================
    # 5. NAV Bridge
    # ================================================================
    nav_q3 = D(str(q3_nav_data["nav_q3"]))

    # Aggregate from categorised transactions
    capital_called = D("0")
    distributions = D("0")
    income = D("0")
    management_fee = D("0")
    other_expenses = D("0")
    expense_refunds = D("0")
    bank_charges = D("0")
    realized_gain_proceeds = D("0")
    # accrual_settlements do NOT count as expenses

    for t in transactions:
        cat = t.get("category")
        debit = D(str(t.get("debit") or 0))
        credit = D(str(t.get("credit") or 0))

        if cat == "capital_call":
            capital_called += credit
        elif cat == "distribution":
            distributions += debit
        elif cat == "dividend_income":
            income += credit
        elif cat == "interest_income":
            income += credit
        elif cat == "management_fee":
            management_fee += debit
        elif cat == "expense":
            other_expenses += debit
        elif cat == "expense_refund":
            expense_refunds += credit
        elif cat == "bank_charges":
            bank_charges += debit
        elif cat == "sale_proceeds":
            realized_gain_proceeds += credit
        # investment_purchase and accrual_settlement: not bridge components
        # (purchase changes cash and investments equally; settlement changes cash and liability equally)

    # Expenses = mgmt fee + other expenses - refunds + bank charges + Q4 accruals
    expenses = management_fee + other_expenses - expense_refunds + bank_charges + liabilities

    # Realized gain = sale proceeds - cost of sold stake
    realized_gain = D("0")
    for sale in q4_sales:
        proceeds = D(str(sale["proceeds_usd"]))
        company = sale["company"]
        cost = D(str(q3_holdings[company]["cost_usd"]))
        realized_gain += proceeds - cost

    # Unrealized gains
    # Q3: sum of (fair_value_usd - cost_usd) for all Q3 holdings
    unrealized_q3 = D("0")
    for h in q3_nav_data["holdings"]:
        unrealized_q3 += D(str(h["fair_value_usd"])) - D(str(h["cost_usd"]))

    # Q4: sum of (fair_value_usd - cost_usd) for all Q4 holdings
    unrealized_q4 = D("0")
    for company, holding in q4_holdings.items():
        unrealized_q4 += holding["fair_value_usd"] - holding["cost_usd"]

    change_in_unrealized = unrealized_q4 - unrealized_q3

    # Bridge check
    nav_q4_bridge = (
        nav_q3
        + capital_called
        - distributions
        + income
        - expenses
        + realized_gain
        + change_in_unrealized
    )
    difference = nav_q4 - nav_q4_bridge

    return {
        "closing_cash": str(closing_cash),
        "investments_usd": str(investments_usd),
        "liabilities": str(liabilities),
        "nav_q4": str(nav_q4),
        "bridge": {
            "nav_q3": str(nav_q3),
            "capital_called": str(capital_called),
            "distributions": str(distributions),
            "income": str(income),
            "expenses": str(expenses),
            "realized_gain": str(realized_gain),
            "change_in_unrealized": str(change_in_unrealized),
            "nav_q4": str(nav_q4_bridge),
            "difference": str(difference),
        },
    }
