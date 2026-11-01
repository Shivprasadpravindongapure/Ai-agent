"""PDF parser for GPF_Bank_Statement_Q4_2022.pdf.

Extracts all transactions from the bank statement using pdfplumber for text
extraction and regex for structured parsing.  Multi-line descriptions are
accumulated until the next dated line.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pdfplumber

from agent_a.models import Transaction

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"^(\d{2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\s+"
)
_MONEY_RE = re.compile(r"([\d,]+\.\d{2})")
_REF_RE = re.compile(r"\b([A-Z]{2}-\d{6}-\d{2})\b")

_MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

# Lines to skip entirely
_SKIP_PATTERNS = [
    "Meridian Trust Bank",
    "Date Description Reference",
    "TOTAL DEBITS",
    "This statement is generated",
    "fictional",
]


def _parse_money(s: str) -> Decimal:
    """Parse a money string like '1,250,000.00' into a Decimal."""
    return Decimal(s.replace(",", ""))


def _parse_date(day: str, month_name: str, year: str) -> str:
    """Convert '03 Oct 2022' parts into 'YYYY-MM-DD'."""
    return f"{year}-{_MONTH_MAP[month_name]}-{day}"


def _should_skip(line: str) -> bool:
    """Return True if the line is a header/footer that should be skipped."""
    for pat in _SKIP_PATTERNS:
        if pat in line:
            return True
    return False


def _extract_text(pdf_path: Path) -> str:
    """Extract all text from the PDF."""
    pages_text: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n".join(pages_text)


def parse_bank_statement(pdf_path: Path) -> list[Transaction]:
    """Parse the bank statement PDF and return a list of Transaction objects.

    The opening-balance row is included (it has no debit or credit).
    """
    raw_text = _extract_text(pdf_path)
    lines = raw_text.split("\n")

    # ---- Phase 1: group lines into raw transaction blocks ----
    blocks: list[dict] = []  # {"first_line": str, "cont_lines": [str]}
    current_block: dict | None = None
    in_data = False

    for line in lines:
        line = line.strip()
        if not line or _should_skip(line):
            continue

        date_match = _DATE_RE.match(line)

        if not in_data:
            # Look for the opening balance line
            if date_match and "BALANCE BROUGHT FORWARD" in line:
                in_data = True
                current_block = {"first_line": line, "cont_lines": []}
            continue

        if date_match:
            # Save previous block, start a new one
            if current_block is not None:
                blocks.append(current_block)
            current_block = {"first_line": line, "cont_lines": []}
        else:
            # Continuation line
            if current_block is not None:
                current_block["cont_lines"].append(line)

    # Don't forget the last block
    if current_block is not None:
        blocks.append(current_block)

    # ---- Phase 2: parse each block into a Transaction ----
    transactions: list[Transaction] = []
    prev_balance: Decimal | None = None

    for block in blocks:
        first_line = block["first_line"]
        cont_lines = block["cont_lines"]

        # Extract date
        dm = _DATE_RE.match(first_line)
        assert dm, f"Expected date at start of line: {first_line!r}"
        date_str = _parse_date(dm.group(1), dm.group(2), dm.group(3))
        rest = first_line[dm.end():]

        # Extract all money amounts from the first line
        amounts = _MONEY_RE.findall(rest)
        amounts_dec = [_parse_money(a) for a in amounts]

        # Extract reference (e.g. OW-221003-01) from the first line
        ref_match = _REF_RE.search(rest)
        reference = ref_match.group(1) if ref_match else None

        # Build full description: everything except date, ref and trailing amounts
        # Strip trailing amounts from the first-line text
        desc_part = rest
        # Remove amounts from end, working backwards
        for amt_str in reversed(amounts):
            idx = desc_part.rfind(amt_str)
            if idx >= 0:
                desc_part = desc_part[:idx]
        # Remove reference from description
        if reference:
            desc_part = desc_part.replace(reference, "")
        desc_part = " ".join(desc_part.split()).strip()

        # Append continuation lines
        full_desc_parts = [desc_part] if desc_part else []
        for cl in cont_lines:
            cl_clean = cl.strip()
            if cl_clean:
                full_desc_parts.append(cl_clean)
        full_description = " ".join(full_desc_parts).strip()

        # Determine balance, debit, credit
        if len(amounts_dec) == 1:
            # Opening balance line
            balance = amounts_dec[0]
            debit = None
            credit = None
        elif len(amounts_dec) >= 2:
            balance = amounts_dec[-1]
            amount = amounts_dec[-2]
            if prev_balance is not None:
                diff = balance - prev_balance
                if diff < 0:
                    # Balance decreased → debit
                    debit = amount
                    credit = None
                else:
                    # Balance increased → credit
                    debit = None
                    credit = amount
            else:
                # First transaction after opening — shouldn't happen but handle
                debit = amount
                credit = None
        else:
            raise ValueError(f"No amounts found in line: {first_line!r}")

        transactions.append(Transaction(
            date=date_str,
            description=full_description,
            reference=reference,
            debit=debit,
            credit=credit,
            balance=balance,
        ))
        prev_balance = balance

    return transactions


def validate_balances(transactions: list[Transaction]) -> None:
    """Verify that opening balance + movements = each running balance.

    Raises AssertionError if any balance doesn't reconcile.
    """
    if not transactions:
        return

    running = transactions[0].balance  # opening balance

    for i, txn in enumerate(transactions[1:], start=1):
        expected = running
        if txn.credit:
            expected += txn.credit
        if txn.debit:
            expected -= txn.debit
        assert expected == txn.balance, (
            f"Balance mismatch at txn {i} ({txn.date} {txn.description[:40]}): "
            f"expected {expected}, got {txn.balance}"
        )
        running = txn.balance
