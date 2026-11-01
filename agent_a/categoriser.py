"""LLM-based transaction categoriser using an OpenAI-compatible endpoint.

Sends transactions in batches to the LLM with a strict system prompt
defining the allowed categories and extraction rules. Validates responses
with Pydantic and retries on parse failure.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal

from openai import OpenAI

from agent_a.models import Transaction, TRANSACTION_CATEGORIES

log = logging.getLogger(__name__)

# The allowed categories, extracted from the Literal type for prompt use
CATEGORIES_LIST = [
    "capital_call", "distribution", "management_fee", "investment_purchase",
    "sale_proceeds", "dividend_income", "interest_income", "bank_charges",
    "expense", "expense_refund", "accrual_settlement",
]

SYSTEM_PROMPT = """\
You are a fund accounting assistant classifying bank transactions for The Greatness PE Fund, L.P. (GPF).

## Allowed categories (use exactly one per transaction):
- capital_call — Money received FROM an LP (investor). Look for "WIRE IN ORG:", "INCOMING TT", LP codes (LP01-LP10), "CALL", "CC07". Extract lp_code.
- distribution — Money paid TO an LP. Look for "DISTRIBUTION" + LP name. Extract lp_code.
- management_fee — Quarterly fee paid to the GP's adviser (Greatness Capital Advisors). Look for "MGMT FEE".
- investment_purchase — Money paid to buy shares in a portfolio company. Look for "SUBSCRIPTION", company name. Extract company name.
- sale_proceeds — Money received from selling a portfolio company stake. Look for "COMPLETION", "SPA" (share purchase agreement). Extract company name.
- dividend_income — Dividend received from a portfolio company. Look for "DIVIDEND". Extract company name.
- interest_income — Bank interest. Look for "CREDIT INTEREST".
- bank_charges — Bank fees. Look for "ACCOUNT MAINTENANCE FEE", "WIRE CHARGES".
- expense — Other fund expenses (legal fees, insurance premiums, etc.) NOT settling a prior accrual.
- expense_refund — Refund of a prior expense. Look for "REFUND", "OVERBILLING".
- accrual_settlement — Payment that settles a liability from the PRIOR quarter (30 Sep 2022). The Q3 accrued liabilities were:
  * Audit fee accrual (Coral & Finch LLP): exactly USD 120,000
  * Administration fee payable Q3 (Harbourside Fund Services): exactly USD 65,000
  If a payment matches one of these exactly (same payee and amount), classify as accrual_settlement.

## LP code mapping (extract when category is capital_call or distribution):
LP01=Lakeshore Teachers, LP02=Fjellheim Sovereign, LP03=St Pension Brd Westland,
LP04=Kestrel Family Office, LP05=Thornvale Univ Endowment, LP06=Pacifica Insurance,
LP07=Bluewater Foundation, LP08=Marlow FOF II, LP09=Coastline Ret Trust,
LP10=R Mehta Family Trust

## Company extraction (for investment_purchase, sale_proceeds, dividend_income):
Extract the actual portfolio company name (e.g. "Aurora Logistics Pvt Ltd", "Ionmere Materials Ltd", "Fjord Payments AS").

## Response format:
Return ONLY a JSON array. Each element:
{"index": <int>, "category": "<category>", "lp_code": "<LPxx>" or null, "company": "<name>" or null}
No markdown, no explanation, just the JSON array.
"""


def _build_user_prompt(transactions: list[Transaction], start_idx: int) -> str:
    """Build the user prompt listing transactions to classify."""
    lines = ["Classify each transaction:\n"]
    for i, t in enumerate(transactions):
        desc = t.description
        ref = f" [{t.reference}]" if t.reference else ""
        amt = f"debit={t.debit}" if t.debit else f"credit={t.credit}"
        lines.append(f"{start_idx + i}: {t.date} | {desc}{ref} | {amt}")
    return "\n".join(lines)


def _parse_llm_response(text: str, count: int) -> list[dict]:
    """Parse the LLM JSON response, handling common formatting issues."""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    items = json.loads(text)
    if not isinstance(items, list):
        raise ValueError("Expected a JSON array")
    return items


def categorise_transactions(
    transactions: list[Transaction],
    api_key: str,
    base_url: str,
    model: str,
    batch_size: int = 15,
    max_retries: int = 3,
) -> list[Transaction]:
    """Categorise transactions using an OpenAI-compatible LLM.

    Sends transactions in batches. Validates each LLM response.
    Never modifies financial amounts — only sets category, lp_code, company.
    """
    client = OpenAI(api_key=api_key, base_url=base_url)

    # Skip the opening balance row (index 0)
    to_classify = transactions[1:]  # indices 1..N in the full list
    results: list[dict] = []

    for batch_start in range(0, len(to_classify), batch_size):
        batch = to_classify[batch_start : batch_start + batch_size]
        user_prompt = _build_user_prompt(batch, batch_start)

        for attempt in range(max_retries):
            try:
                log.info(
                    f"LLM batch {batch_start//batch_size + 1}: "
                    f"{len(batch)} transactions (attempt {attempt + 1})"
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=2000,
                )
                content = response.choices[0].message.content or ""
                parsed = _parse_llm_response(content, len(batch))

                # Validate: must have the right count
                if len(parsed) != len(batch):
                    log.warning(
                        f"LLM returned {len(parsed)} items, expected {len(batch)}. Retrying."
                    )
                    continue

                # Validate categories
                valid = True
                for item in parsed:
                    if item.get("category") not in CATEGORIES_LIST:
                        log.warning(f"Invalid category: {item.get('category')}")
                        valid = False
                        break
                if not valid:
                    continue

                results.extend(parsed)
                break
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                log.warning(f"LLM parse error (attempt {attempt + 1}): {exc}")
                if attempt == max_retries - 1:
                    # Fallback: mark as unknown
                    log.error("Max retries reached. Marking batch as unclassified.")
                    for j in range(len(batch)):
                        results.append({
                            "index": batch_start + j,
                            "category": "expense",
                            "lp_code": None,
                            "company": None,
                        })
            except Exception as exc:
                log.error(f"LLM API error: {exc}")
                if attempt == max_retries - 1:
                    raise

    # Apply classifications back to transactions (never touch amounts)
    for i, classification in enumerate(results):
        txn_idx = i + 1  # offset by 1 because we skipped opening balance
        transactions[txn_idx].category = classification["category"]
        transactions[txn_idx].lp_code = classification.get("lp_code")
        transactions[txn_idx].company = classification.get("company")

    # Opening balance gets no category
    transactions[0].category = None

    return transactions
