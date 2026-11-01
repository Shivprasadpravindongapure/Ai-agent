# Decisions

## Decision 1: PDF parsing approach
**Decision:** Use pdfplumber to extract the full text from the bank statement PDF, then parse transactions with regex line-by-line, handling multi-line descriptions by accumulating lines until the next dated entry.
**Alternatives:** (a) Use pdfplumber's table extraction, (b) Send the entire PDF text to the LLM for structured extraction, (c) Use Tabula or Camelot.
**Why:** pdfplumber text extraction is reliable for this single-format PDF and keeps parsing deterministic and testable. Table extraction was unreliable with the multi-line descriptions. Sending the entire PDF to the LLM would be slow, expensive, and non-deterministic. The LLM is used only for categorisation (as required), not for parsing.

## Decision 2: A2A implementation — minimal JSON-RPC 2.0
**Decision:** Implement only `message/send` with the exact two-turn conversation flow described in the brief. No task store, no streaming, no generic task management.
**Alternatives:** (a) Full A2A 0.3 spec implementation with task store, SSE, and discovery, (b) Use an existing A2A library.
**Why:** The brief requires only `message/send` and a specific two-turn flow. A minimal implementation is easier to debug, test, and review in the time available. No existing Python A2A library was mature enough to trust without reading all its code.

## Decision 3: Decimal for all financial arithmetic
**Decision:** Use Python's `Decimal` type for all money values throughout the pipeline. Parse string values from JSON and Excel as `Decimal`. Round to 2 decimal places only for final output.
**Alternatives:** (a) Use float throughout, (b) Use integer cents.
**Why:** The NAV bridge must balance to the cent. Float arithmetic introduces rounding errors that compound across ~40 transactions and 8+ portfolio companies. Decimal avoids this entirely. Integer cents would work but add conversion noise for every read/write.
