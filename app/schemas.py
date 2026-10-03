from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Decision = Literal["ANSWER", "ASK", "ACT", "ESCALATE"]


class ChatRequest(BaseModel):
    customer_id: str | None = Field(None, description="Authenticated customer (conversation owner)")
    message: str = Field(..., max_length=5000)
    session_id: str | None = None
    current_time: str | None = Field(None, description="ISO time of the conversation; defaults to now (IST)")
    attachments: list[str] = Field(default_factory=list, description="Names of files/images the customer attached")


class ToolCall(BaseModel):
    name: str
    params: dict[str, Any]
    ok: bool = True
    result_summary: str = ""
    result: dict[str, Any] = Field(default_factory=dict)  # structured version of result_summary


class ChatResponse(BaseModel):
    reply: str
    decision: Decision
    intents: list[dict[str, Any]]
    tool_calls: list[ToolCall]
    refund_amount: float | None = None
    escalate: bool = False
    ticket_id: str | None = None
    reasoning: list[str]
    policy_version: str | None = None
    flags: list[str] = Field(default_factory=list)
    language: str = "en"
    session_id: str
    parser: str = "rules"
    reply_source: str = "template"
    tokens: dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0, "llm_calls": 0})
    usage: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0
