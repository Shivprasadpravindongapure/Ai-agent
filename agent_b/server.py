"""FastAPI server for Agent B — Valuation & NAV Agent.

Implements the A2A v0.3 two-turn handshake:
  Turn 1: Agent A requests marks → Agent B replies input-required (needs purchases/sales)
  Turn 2: Agent A sends purchases/sales → Agent B validates, returns marks
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Agent B — Valuation & NAV Agent")

# Module-level state (set by main.py before server starts)
_agent_b_data: dict | None = None
_port: int = 8002
_task_store: dict[str, dict] = {}  # taskId → task state


def configure(data: dict, port: int) -> None:
    """Configure Agent B with its data and port. Called before server start."""
    global _agent_b_data, _port
    _agent_b_data = data
    _port = port


@app.get("/.well-known/agent-card.json")
async def agent_card():
    return {
        "name": "Agent B — Valuation & NAV Agent",
        "description": "Holds Q4 valuation marks for The Greatness PE Fund. "
                       "Releases marks after verifying purchases/sales with Agent A.",
        "url": f"http://localhost:{_port}/a2a",
        "version": "0.3",
        "capabilities": {"message_send": True},
    }


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Not serializable: {type(obj)}")


def _make_task(task_id: str, ctx_id: str, state: str,
               message: dict | None = None,
               artifacts: list | None = None) -> dict:
    task = {
        "kind": "task",
        "id": task_id,
        "contextId": ctx_id,
        "status": {"state": state},
    }
    if message:
        task["status"]["message"] = message
    if artifacts:
        task["artifacts"] = artifacts
    return task


def _match_purchases_sales(submitted: dict) -> tuple[bool, str]:
    """Check if submitted purchases/sales match agent_b_data records.

    Normalizes company names (strip/lower) and amounts (integer Decimal)
    to handle minor formatting differences between Agent A and Agent B.
    """
    expected_purchases = _agent_b_data.get("purchases", [])
    expected_sales = _agent_b_data.get("sales", [])

    sub_purchases = submitted.get("purchases", [])
    sub_sales = submitted.get("sales", [])

    def _norm_amount(v: Any) -> Decimal:
        """Normalize an amount to integer-precision Decimal for comparison."""
        return Decimal(str(v)).quantize(Decimal("1"))

    def norm_purchase(p: dict) -> tuple:
        return (
            p["company"].strip().lower(),
            p["date"],
            _norm_amount(p["amount_usd"]),
        )

    def norm_sale(s: dict) -> tuple:
        return (
            s["company"].strip().lower(),
            s["date"],
            _norm_amount(s["proceeds_usd"]),
        )

    exp_p = {norm_purchase(p) for p in expected_purchases}
    sub_p = {norm_purchase(p) for p in sub_purchases}
    exp_s = {norm_sale(s) for s in expected_sales}
    sub_s = {norm_sale(s) for s in sub_sales}

    p_match = exp_p == sub_p
    s_match = exp_s == sub_s

    if p_match and s_match:
        return True, "All purchases and sales match."

    msg_parts = []
    if not p_match:
        msg_parts.append(
            f"Purchases: {len(exp_p & sub_p)}/{len(exp_p)} matched"
        )
    if not s_match:
        msg_parts.append(
            f"Sales: {len(exp_s & sub_s)}/{len(exp_s)} matched"
        )
    return False, "; ".join(msg_parts)


@app.post("/a2a")
async def a2a_endpoint(request: Request):
    """Handle JSON-RPC 2.0 message/send requests."""
    body = await request.json()

    rpc_id = body.get("id", 1)
    method = body.get("method")
    params = body.get("params", {})

    if method != "message/send":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    message = params.get("message", params)
    task_id = message.get("taskId")
    context_id = message.get("contextId")

    # --- Turn 1: Initial request for marks ---
    if task_id is None:
        # Extract fund and valuation_date from parts
        parts = message.get("parts", [])
        data_part = None
        for p in parts:
            if p.get("kind") == "data":
                data_part = p.get("data", {})
                break

        if not data_part or data_part.get("fund") != "GPF":
            return JSONResponse({
                "jsonrpc": "2.0", "id": rpc_id,
                "error": {"code": -32602, "message": "Missing or invalid fund code"},
            })

        # Create a new task in input-required state
        new_task_id = f"task-{uuid.uuid4().hex[:8]}"
        new_ctx_id = f"ctx-{uuid.uuid4().hex[:8]}"

        task = _make_task(
            new_task_id, new_ctx_id, "input-required",
            message={
                "kind": "message",
                "role": "agent",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text":
                    "Please provide the fund's Q4 purchases and sales of companies. "
                    "Send a data part with 'purchases' (list of {company, date, amount_usd}) "
                    "and 'sales' (list of {company, date, proceeds_usd}). "
                    "Send empty lists if there were none."
                }],
            },
        )
        _task_store[new_task_id] = {
            "task": task,
            "attempts": 0,
        }

        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": task})

    # --- Turn 2: Agent A sends purchases/sales ---
    if task_id not in _task_store:
        return JSONResponse({
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32602, "message": f"Unknown taskId: {task_id}"},
        })

    stored = _task_store[task_id]
    stored["attempts"] += 1

    # Extract purchases/sales from parts
    parts = message.get("parts", [])
    submitted_data = None
    for p in parts:
        if p.get("kind") == "data":
            submitted_data = p.get("data", {})
            break

    if submitted_data is None:
        return JSONResponse({
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32602, "message": "Missing data part with purchases/sales"},
        })

    matched, match_msg = _match_purchases_sales(submitted_data)

    if not matched:
        # Stay in input-required
        task = _make_task(
            task_id, context_id or stored["task"]["contextId"], "input-required",
            message={
                "kind": "message",
                "role": "agent",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text":
                    f"Purchases/sales do not match. {match_msg}. Please correct and resend."
                }],
            },
        )
        stored["task"] = task
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": task})

    # Match successful — return marks as completed task
    marks_artifact = {
        "fund": _agent_b_data["fund"]["name"],
        "valuation_date": _agent_b_data["valuation_date"],
        "marks": _agent_b_data["marks"],
        "notes": _agent_b_data["notes"],
    }

    task = _make_task(
        task_id,
        context_id or stored["task"]["contextId"],
        "completed",
        message={
            "kind": "message",
            "role": "agent",
            "messageId": str(uuid.uuid4()),
            "parts": [{"kind": "text", "text": "Marks released. " + match_msg}],
        },
        artifacts=[{
            "artifactId": f"marks-GPF-{_agent_b_data['valuation_date']}",
            "parts": [{"kind": "data", "data": marks_artifact}],
        }],
    )
    stored["task"] = task

    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": task})
