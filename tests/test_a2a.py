"""Offline tests for A2A protocol endpoints."""

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from agent_b.server import app as app_b, configure as configure_b


@pytest.fixture(autouse=True)
def setup_agent_b():
    """Load agent_b_data and configure the server before each test."""
    from pathlib import Path
    data_path = Path("pack/agent_b_data.json")
    if not data_path.exists():
        pytest.skip("agent_b_data.json not found")
    with open(data_path) as f:
        data = json.load(f)
    configure_b(data, 8002)


@pytest.fixture
def client_b():
    return TestClient(app_b)


class TestAgentBCard:
    def test_agent_card(self, client_b):
        resp = client_b.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        card = resp.json()
        assert card["name"] == "Agent B — Valuation & NAV Agent"
        assert card["version"] == "0.3"
        assert "message_send" in card["capabilities"]
        assert "/a2a" in card["url"]


class TestA2ATwoTurnHandshake:
    def test_turn1_returns_input_required(self, client_b):
        req = {
            "jsonrpc": "2.0", "id": 1,
            "method": "message/send",
            "params": {"message": {
                "kind": "message", "role": "user",
                "messageId": "test-msg-1",
                "parts": [{"kind": "data", "data": {
                    "fund": "GPF", "valuation_date": "2022-12-31"
                }}],
            }},
        }
        resp = client_b.post("/a2a", json=req)
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["status"]["state"] == "input-required"
        assert result["id"].startswith("task-")
        assert result["contextId"].startswith("ctx-")

    def test_turn2_with_correct_data(self, client_b):
        # Turn 1
        req1 = {
            "jsonrpc": "2.0", "id": 1,
            "method": "message/send",
            "params": {"message": {
                "kind": "message", "role": "user",
                "messageId": "test-msg-1",
                "parts": [{"kind": "data", "data": {
                    "fund": "GPF", "valuation_date": "2022-12-31"
                }}],
            }},
        }
        r1 = client_b.post("/a2a", json=req1).json()
        task_id = r1["result"]["id"]
        ctx_id = r1["result"]["contextId"]

        # Turn 2: correct purchases/sales
        req2 = {
            "jsonrpc": "2.0", "id": 2,
            "method": "message/send",
            "params": {"message": {
                "kind": "message", "role": "user",
                "messageId": "test-msg-2",
                "taskId": task_id,
                "contextId": ctx_id,
                "parts": [{"kind": "data", "data": {
                    "purchases": [{"company": "Ionmere Materials Ltd", "date": "2022-12-15", "amount_usd": 14000000}],
                    "sales": [{"company": "Fjord Payments AS", "date": "2022-11-18", "proceeds_usd": 29000000}],
                }}],
            }},
        }
        r2 = client_b.post("/a2a", json=req2).json()
        result = r2["result"]
        assert result["status"]["state"] == "completed"
        assert len(result["artifacts"]) == 1
        marks = result["artifacts"][0]["parts"][0]["data"]
        assert marks["fund"] == "The Greatness PE Fund, L.P."
        assert len(marks["marks"]) == 7

    def test_turn2_with_wrong_data(self, client_b):
        # Turn 1
        req1 = {
            "jsonrpc": "2.0", "id": 1,
            "method": "message/send",
            "params": {"message": {
                "kind": "message", "role": "user",
                "messageId": "test-msg-1",
                "parts": [{"kind": "data", "data": {
                    "fund": "GPF", "valuation_date": "2022-12-31"
                }}],
            }},
        }
        r1 = client_b.post("/a2a", json=req1).json()
        task_id = r1["result"]["id"]
        ctx_id = r1["result"]["contextId"]

        # Turn 2: WRONG data
        req2 = {
            "jsonrpc": "2.0", "id": 2,
            "method": "message/send",
            "params": {"message": {
                "kind": "message", "role": "user",
                "messageId": "test-msg-2",
                "taskId": task_id,
                "contextId": ctx_id,
                "parts": [{"kind": "data", "data": {
                    "purchases": [],
                    "sales": [],
                }}],
            }},
        }
        r2 = client_b.post("/a2a", json=req2).json()
        assert r2["result"]["status"]["state"] == "input-required"

    def test_invalid_method(self, client_b):
        req = {"jsonrpc": "2.0", "id": 1, "method": "task/get", "params": {}}
        resp = client_b.post("/a2a", json=req)
        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == -32601


class TestAgentACard:
    def test_agent_card(self):
        from agent_a.server import app as app_a, configure as configure_a
        configure_a(8001)
        client = TestClient(app_a)
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        card = resp.json()
        assert card["name"] == "Agent A — Bank & Ingestion Agent"
        assert card["version"] == "0.3"
