"""A2A protocol helpers: agent card serving and message/send client."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from shared.schemas import AgentCard, JsonRpcRequest, JsonRpcResponse


# ---------------------------------------------------------------------------
# A2A log (one JSONL line per request/response)
# ---------------------------------------------------------------------------

_LOG_PATH: Path | None = None


def set_a2a_log_path(path: Path) -> None:
    global _LOG_PATH
    _LOG_PATH = path
    # Ensure the file exists (truncate on each run)
    path.write_text("")


def log_a2a(direction: str, payload: dict[str, Any]) -> None:
    """Append a timestamped entry to the A2A log."""
    if _LOG_PATH is None:
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "direction": direction,
        "payload": payload,
    }
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Client helper: send message/send to an agent
# ---------------------------------------------------------------------------

async def send_message(
    agent_url: str,
    params: dict[str, Any],
    rpc_id: str | int = 1,
) -> dict[str, Any]:
    """Send a JSON-RPC 2.0 message/send to *agent_url* and return the result."""
    request_body = JsonRpcRequest(
        id=rpc_id,
        method="message/send",
        params=params,
    ).model_dump()

    log_a2a("request", request_body)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(agent_url, json=request_body)
        resp.raise_for_status()

    response_body = resp.json()
    log_a2a("response", response_body)
    return response_body
