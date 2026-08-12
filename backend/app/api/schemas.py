"""API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    cost_ceiling_usd: float | None = None


class ChatResponse(BaseModel):
    run_id: str
    answer: str | None = None
    draft_answer: str | None = None
    escalated: bool = False
    escalation_reason: str | None = None
    governance_passed: bool = False
    confidence: float = 0.0
    citations: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    input_guardrails: dict[str, Any] | None = None
    output_guardrails: dict[str, Any] | None = None
    route: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    node_trace: list[str] = Field(default_factory=list)
    demo_mode: bool = False


class ReviewResolveRequest(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""
