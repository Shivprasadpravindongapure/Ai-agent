"""Shared Pydantic models for the A2A protocol (JSON-RPC 2.0, A2A v0.3 subset)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# A2A protocol models (subset used by this project)
# ---------------------------------------------------------------------------

class Part(BaseModel):
    """A single part of an A2A message."""
    kind: Literal["text", "data"]
    text: str | None = None
    data: dict[str, Any] | None = None


class Message(BaseModel):
    """An A2A message."""
    kind: Literal["message"] = "message"
    role: Literal["user", "agent"] = "user"
    messageId: str
    taskId: str | None = None
    contextId: str | None = None
    parts: list[Part]


class TaskStatus(BaseModel):
    state: Literal["submitted", "working", "input-required", "completed", "failed"]
    message: Message | None = None


class Artifact(BaseModel):
    artifactId: str
    parts: list[Part]


class Task(BaseModel):
    kind: Literal["task"] = "task"
    id: str
    contextId: str
    status: TaskStatus
    artifacts: list[Artifact] = Field(default_factory=list)


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: str
    params: dict[str, Any]


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class AgentCard(BaseModel):
    """GET /.well-known/agent-card.json"""
    name: str
    description: str
    url: str
    version: str = "0.3"
    capabilities: dict[str, Any] = Field(default_factory=lambda: {"message_send": True})
