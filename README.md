# GPF Q4 2022 Quarter Close

Two-agent system that closes Q4 2022 for **The Greatness PE Fund, L.P.** (GPF).

Agent A parses the bank statement and categorises transactions using an LLM; Agent B holds the valuation marks, reviews them for anomalies, and computes the NAV bridge. They communicate over the **A2A protocol** (JSON-RPC 2.0 / HTTP).

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env — add your LLM_API_KEY (any OpenAI-compatible endpoint)

# 3. Run (single command)
python main.py ./pack
```

Results are written to `./output/`.

## How it works

```
main.py
  ├── Starts Agent B (port 8002) ─ FastAPI, A2A endpoint
  ├── Starts Agent A (port 8001) ─ FastAPI, A2A endpoint
  │
  ├── 1. Parse bank statement PDF (pdfplumber + regex)
  ├── 2. Categorise 39 transactions via LLM (OpenAI-compatible)
  ├── 3. Validate all running balances (Decimal arithmetic)
  │
  ├── 4. A2A Turn 1: Agent A → Agent B  "Give me Q4 marks for GPF"
  ├── 5. A2A Turn 2: Agent B says "Prove your purchases/sales first"
  ├── 6. Agent A sends purchases/sales from bank statement
  ├── 7. Agent B validates → releases marks
  │
  ├── 8. Review marks R1–R4 (material change, method change, no mark, sold)
  ├── 9. Compute Q4 NAV + NAV bridge (must balance to the cent)
  │
  └── 10. Write output/ files and shut down
```

## Project structure

```
main.py                  # Single entry-point
agent_a/
  server.py              # FastAPI — Bank & Ingestion Agent (A2A endpoint)
  pdf_parser.py          # Deterministic PDF → Transaction list
  categoriser.py         # LLM-based transaction categorisation
  models.py              # Pydantic models (Transaction, Purchase, Sale)
agent_b/
  server.py              # FastAPI — Valuation & NAV Agent (A2A endpoint)
  review.py              # Q3→Q4 mark comparison, rules R1–R4
  nav.py                 # NAV and NAV-bridge computation
  models.py              # Pydantic models (Mark, NavBridge, NavOutput, etc.)
shared/
  a2a.py                 # A2A protocol helpers
  config.py              # Pydantic settings from .env
  schemas.py             # Shared A2A Pydantic models
  data_loader.py         # Load Q3 data from Excel files
pack/                    # Input data (provided)
output/                  # Generated output
tests/                   # 43 offline pytest tests
```

## Output files

| File | Description |
|---|---|
| `transactions.json` | 40 rows (opening + 39 txns) with category, LP code, company |
| `a2a_log.jsonl` | Timestamped JSON-RPC request/response log (4 entries) |
| `marks.json` | Q4 marks received from Agent B, unchanged |
| `review.json` | Per-company review with flags R1–R4, threshold, FX rate |
| `nav.json` | Q4 NAV, closing cash, investments, liabilities, bridge |

## Key numbers (Q4 2022)

| Metric | Value |
|---|---|
| Closing cash | 23,896,579.25 |
| Investments (USD) | 146,062,460.00 |
| Liabilities | 195,000.00 |
| **NAV** | **169,764,039.25** |
| Bridge difference | **0.00** |

## Testing

```bash
python -m pytest tests/ -v
# 43 tests, all offline, no LLM or network required
```

## What I would do next

- Streaming A2A (SSE) for long-running tasks
- Confidence scores on LLM categorisation with human review
- Configurable review rules (YAML definitions)
- Multi-fund support via parameterised agent cards
- Integration tests against a mock LLM server
- Proper retry/back-off on LLM rate limits

## Known limitations

- The LLM categoriser may produce slightly different company name casing across runs; the A2A matching normalises this.
- EUR/USD rate is hardcoded to the ECB reference rate for 30 Dec 2022 (1.0666). In production, this would be fetched from an API.
- See ASSUMPTIONS.md for judgment calls on FX rate date, unvalued companies, materiality threshold.
