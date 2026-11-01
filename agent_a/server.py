"""FastAPI server for Agent A — Bank & Ingestion Agent.

Exposes the A2A agent card. The main orchestration (parsing, categorising,
calling Agent B) is driven by main.py.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Agent A — Bank & Ingestion Agent")

_port: int = 8001


def configure(port: int) -> None:
    global _port
    _port = port


@app.get("/.well-known/agent-card.json")
async def agent_card():
    return {
        "name": "Agent A — Bank & Ingestion Agent",
        "description": "Parses and categorises the fund's bank statement. "
                       "Requests valuation marks from Agent B via A2A.",
        "url": f"http://localhost:{_port}/a2a",
        "version": "0.3",
        "capabilities": {"message_send": True},
    }


@app.post("/a2a")
async def a2a_endpoint():
    """Placeholder A2A endpoint for Agent A.

    In this exercise Agent A acts as the A2A client (calling Agent B).
    This endpoint exists so Agent A is a conforming A2A agent.
    """
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32601,
            "message": "Agent A does not accept inbound A2A tasks in this exercise.",
        },
    }
