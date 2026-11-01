# GPF Q4 2022 Quarter Close

Two-agent system that closes Q4 2022 for **The Greatness PE Fund, L.P.** (GPF).  
Agent A parses the bank statement and categorises transactions; Agent B holds the valuation marks, reviews them for anomalies, and computes the NAV bridge. They communicate over the A2A protocol (JSON-RPC 2.0 / HTTP).

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env with your LLM_API_KEY

# 3. Run
python main.py ./pack
```

Results are written to `./output/`.

## Project structure

```
main.py                  # Single entry-point: starts both agents, orchestrates the run
agent_a/
  server.py              # FastAPI app – Bank & Ingestion Agent (A2A endpoint)
  pdf_parser.py          # Extracts transactions from GPF_Bank_Statement_Q4_2022.pdf
  categoriser.py         # LLM-based transaction categorisation
  models.py              # Pydantic models for transactions
agent_b/
  server.py              # FastAPI app – Valuation & NAV Agent (A2A endpoint)
  review.py              # Q3→Q4 mark comparison and anomaly flagging (rules R1–R4)
  nav.py                 # NAV and NAV-bridge computation
  models.py              # Pydantic models for marks, NAV, review
shared/
  a2a.py                 # A2A protocol helpers (message/send, agent card)
  config.py              # Pydantic settings loaded from .env
  schemas.py             # Shared Pydantic models (A2A messages, tasks, artifacts)
pack/                    # Input data (provided)
output/                  # Generated output (transactions.json, marks.json, etc.)
tests/
  test_nav.py            # Offline NAV-bridge arithmetic tests
  test_parser.py         # Offline PDF-parse tests with fixture data
  test_review.py         # Offline review-rule tests
```

## Output files

| File | Description |
|---|---|
| `transactions.json` | All bank transactions with category, LP code, company |
| `a2a_log.jsonl` | Timestamped A2A request/response log |
| `marks.json` | Q4 marks received from Agent B |
| `review.json` | Per-company review with flags (R1–R4) |
| `nav.json` | Q4 NAV and NAV bridge |

## What I would do next

- Structured retry / back-off on LLM rate limits
- Confidence scores on LLM categorisation with human-in-the-loop review
- Streaming A2A (SSE) for long-running tasks
- Proper async task management with cancellation
- Configurable review rules (YAML/JSON rule definitions)
- Multi-fund support via parameterised agent cards
- Integration tests against a mock LLM server

## Known gaps

- See ASSUMPTIONS.md for judgment calls on FX rate, unvalued companies, materiality threshold.
