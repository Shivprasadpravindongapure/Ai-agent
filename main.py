"""Main entry point: starts both agents, orchestrates the quarter-close run.

Usage:
    python main.py [pack_dir]

pack_dir defaults to ./pack.  Results are written to ./output/.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from dotenv import load_dotenv

from shared.config import Settings
from shared.data_loader import load_q3_valuations, load_q3_nav_summary
from agent_a.pdf_parser import parse_bank_statement, validate_balances
from agent_a.categoriser import categorise_transactions
from agent_b.review import review_marks
from agent_b.nav import compute_nav

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _json_serial(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        # Use string for Decimal to preserve precision
        return str(obj)
    raise TypeError(f"Not serializable: {type(obj)}")


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=_json_serial)
    log.info(f"Wrote {path}")


def _append_jsonl(path: Path, entry: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(entry, default=_json_serial) + "\n")


async def run_pipeline(pack_dir: str = "./pack") -> None:
    """Run the full quarter-close pipeline."""
    load_dotenv()
    settings = Settings()

    pack = Path(pack_dir)
    output = Path("./output")
    output.mkdir(exist_ok=True)

    a2a_log_path = output / "a2a_log.jsonl"
    a2a_log_path.write_text("")  # clear on each run

    # Validate input files
    required = [
        "GPF_Bank_Statement_Q4_2022.pdf",
        "CVP_Valuation_Report_Q3_2022.xlsx",
        "GPF_NAV_Summary_Q3_2022.xlsx",
        "agent_b_data.json",
    ]
    for fname in required:
        if not (pack / fname).exists():
            log.error(f"Missing required file: {pack / fname}")
            sys.exit(1)

    log.info(f"Pack directory: {pack.resolve()}")
    log.info(f"Output directory: {output.resolve()}")

    # ================================================================
    # 1. Load reference data
    # ================================================================
    log.info("Loading Q3 reference data...")
    q3_valuations = load_q3_valuations(pack)
    q3_nav_data = load_q3_nav_summary(pack)

    with open(pack / "agent_b_data.json") as f:
        agent_b_data = json.load(f)

    log.info(f"Q3 NAV: {q3_nav_data['nav_q3']}")
    log.info(f"Q4 marks: {len(agent_b_data['marks'])} companies")

    # ================================================================
    # 2. Start Agent B server
    # ================================================================
    from agent_b.server import app as app_b, configure as configure_b
    configure_b(agent_b_data, settings.agent_b_port)

    config_b = uvicorn.Config(
        app_b, host="127.0.0.1", port=settings.agent_b_port,
        log_level="warning",
    )
    server_b = uvicorn.Server(config_b)
    server_b_task = asyncio.create_task(server_b.serve())

    # Wait for Agent B to be ready
    for _ in range(50):
        await asyncio.sleep(0.1)
        if server_b.started:
            break
    log.info(f"Agent B running on port {settings.agent_b_port}")

    # ================================================================
    # 3. Start Agent A server
    # ================================================================
    from agent_a.server import app as app_a, configure as configure_a
    configure_a(settings.agent_a_port)

    config_a = uvicorn.Config(
        app_a, host="127.0.0.1", port=settings.agent_a_port,
        log_level="warning",
    )
    server_a = uvicorn.Server(config_a)
    server_a_task = asyncio.create_task(server_a.serve())

    for _ in range(50):
        await asyncio.sleep(0.1)
        if server_a.started:
            break
    log.info(f"Agent A running on port {settings.agent_a_port}")

    try:
        # ================================================================
        # 4. Parse bank statement
        # ================================================================
        log.info("Parsing bank statement PDF...")
        transactions = parse_bank_statement(pack / "GPF_Bank_Statement_Q4_2022.pdf")
        log.info(f"Parsed {len(transactions)} rows ({len(transactions)-1} transactions + opening)")

        # Validate running balances
        validate_balances(transactions)
        log.info("Balance validation PASSED")

        opening = transactions[0].balance
        closing = transactions[-1].balance
        total_debits = sum(t.debit for t in transactions if t.debit)
        total_credits = sum(t.credit for t in transactions if t.credit)
        recon = opening + total_credits - total_debits
        assert recon == closing, f"Reconciliation failed: {recon} != {closing}"
        log.info(f"Bank reconciliation PASSED: {opening} + {total_credits} - {total_debits} = {closing}")

        # ================================================================
        # 5. Categorise transactions via LLM
        # ================================================================
        log.info("Categorising transactions via LLM...")
        transactions = categorise_transactions(
            transactions,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
        log.info("LLM categorisation complete")

        # Log category summary
        from collections import Counter
        cats = Counter(t.category for t in transactions if t.category)
        for cat, count in sorted(cats.items()):
            log.info(f"  {cat}: {count}")

        # ================================================================
        # 6. Write transactions.json
        # ================================================================
        txn_dicts = []
        for t in transactions:
            d = t.model_dump()
            # Convert Decimals to strings for JSON
            for k in ("debit", "credit", "balance"):
                if d[k] is not None:
                    d[k] = str(d[k])
            txn_dicts.append(d)

        _write_json(output / "transactions.json", txn_dicts)

        # ================================================================
        # 7. A2A: Agent A → Agent B (two-turn marks exchange)
        # ================================================================
        agent_b_url = f"http://127.0.0.1:{settings.agent_b_port}/a2a"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # --- Turn 1: Request marks ---
            log.info("A2A Turn 1: Requesting marks from Agent B...")
            turn1_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "message/send",
                "params": {
                    "message": {
                        "kind": "message",
                        "role": "user",
                        "messageId": str(uuid.uuid4()),
                        "parts": [{"kind": "data", "data": {
                            "fund": "GPF",
                            "valuation_date": "2022-12-31",
                        }}],
                    }
                },
            }

            _append_jsonl(a2a_log_path, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": "request",
                "payload": turn1_request,
            })

            resp1 = await client.post(agent_b_url, json=turn1_request)
            resp1_json = resp1.json()

            _append_jsonl(a2a_log_path, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": "response",
                "payload": resp1_json,
            })

            task = resp1_json["result"]
            assert task["status"]["state"] == "input-required", (
                f"Expected input-required, got {task['status']['state']}"
            )
            task_id = task["id"]
            context_id = task["contextId"]
            log.info(f"Agent B requests purchases/sales (taskId={task_id})")

            # --- Prepare purchases/sales from categorised transactions ---
            purchases = []
            sales = []
            for t in transactions:
                if t.category == "investment_purchase" and t.debit:
                    purchases.append({
                        "company": t.company or "",
                        "date": t.date,
                        "amount_usd": float(t.debit),
                    })
                elif t.category == "sale_proceeds" and t.credit:
                    sales.append({
                        "company": t.company or "",
                        "date": t.date,
                        "proceeds_usd": float(t.credit),
                    })

            # --- Turn 2: Send purchases/sales ---
            log.info(f"A2A Turn 2: Sending {len(purchases)} purchases, {len(sales)} sales...")
            turn2_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "message/send",
                "params": {
                    "message": {
                        "kind": "message",
                        "role": "user",
                        "messageId": str(uuid.uuid4()),
                        "taskId": task_id,
                        "contextId": context_id,
                        "parts": [{"kind": "data", "data": {
                            "purchases": purchases,
                            "sales": sales,
                        }}],
                    }
                },
            }

            _append_jsonl(a2a_log_path, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": "request",
                "payload": turn2_request,
            })

            resp2 = await client.post(agent_b_url, json=turn2_request)
            resp2_json = resp2.json()

            _append_jsonl(a2a_log_path, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": "response",
                "payload": resp2_json,
            })

            task2 = resp2_json["result"]

            if task2["status"]["state"] != "completed":
                log.error(f"A2A handshake failed: {task2['status']}")
                log.error("Purchases/sales may not match Agent B's records.")
                # Try to continue anyway — use agent_b_data directly
                marks_data = {
                    "fund": agent_b_data["fund"]["name"],
                    "valuation_date": agent_b_data["valuation_date"],
                    "marks": agent_b_data["marks"],
                    "notes": agent_b_data["notes"],
                }
            else:
                log.info("A2A handshake completed — marks received")
                marks_data = task2["artifacts"][0]["parts"][0]["data"]

        # ================================================================
        # 8. Write marks.json (unchanged artifact from Agent B)
        # ================================================================
        _write_json(output / "marks.json", marks_data)

        # ================================================================
        # 9. Review marks (R1–R4)
        # ================================================================
        log.info("Running mark review (R1–R4)...")
        review_result = review_marks(
            q3_valuations=q3_valuations,
            q4_marks=marks_data["marks"],
            q4_notes=marks_data.get("notes", []),
            q4_purchases=agent_b_data.get("purchases", []),
            q4_sales=agent_b_data.get("sales", []),
            q3_holdings=q3_nav_data["holdings"],
        )

        flagged = [c for c in review_result["companies"] if c["flags"]]
        log.info(f"Flagged companies: {[c['company'] for c in flagged]}")
        _write_json(output / "review.json", review_result)

        # ================================================================
        # 10. Compute NAV and NAV bridge
        # ================================================================
        log.info("Computing NAV and NAV bridge...")
        nav_result = compute_nav(
            q3_nav_data=q3_nav_data,
            q4_marks=marks_data["marks"],
            q4_notes=marks_data.get("notes", []),
            q4_purchases=agent_b_data.get("purchases", []),
            q4_sales=agent_b_data.get("sales", []),
            transactions=txn_dicts,
        )

        log.info(f"Closing cash:       {nav_result['closing_cash']}")
        log.info(f"Investments (USD):  {nav_result['investments_usd']}")
        log.info(f"Liabilities:        {nav_result['liabilities']}")
        log.info(f"NAV Q4:             {nav_result['nav_q4']}")
        log.info(f"Bridge difference:  {nav_result['bridge']['difference']}")

        if Decimal(nav_result["bridge"]["difference"]) != 0:
            log.warning("NAV bridge does NOT balance!")
        else:
            log.info("NAV bridge BALANCED ✓")

        _write_json(output / "nav.json", nav_result)

        log.info("=" * 60)
        log.info("PIPELINE COMPLETE — all output files written to ./output/")
        log.info("=" * 60)

    finally:
        # ================================================================
        # 11. Shutdown servers
        # ================================================================
        server_a.should_exit = True
        server_b.should_exit = True
        await asyncio.sleep(0.5)


def main(pack_dir: str = "./pack") -> None:
    asyncio.run(run_pipeline(pack_dir))


if __name__ == "__main__":
    pack_arg = sys.argv[1] if len(sys.argv) > 1 else "./pack"
    main(pack_arg)
