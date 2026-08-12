"""Module 2 — routing policy, fallback, cost ceiling."""

from __future__ import annotations

import asyncio

import pytest

from app.routing.fallback import call_with_fallback
from app.routing.policy import TaskType, classify_task, decide_route
from app.routing.providers.base import BaseProvider, LLMResponse
from app.routing.providers.mock import MockProvider


def test_classify_task_types():
    assert classify_task("extract JSON fields from the contract") == TaskType.STRUCTURED_EXTRACTION
    assert classify_task("why should we redesign the architecture?") == TaskType.COMPLEX_REASONING
    assert classify_task("what does the policy say about retention?") == TaskType.DOCUMENT_QA
    assert classify_task("classify this ticket sentiment") == TaskType.CLASSIFICATION


def test_cost_ceiling_routes_to_cheaper_tier():
    # Strong preference would be anthropic, but tiny ceiling forces affordable/mock
    choice = decide_route(
        "why should we redesign the multi-cloud architecture?",
        available=["anthropic", "openai", "gemini", "mock"],
        cost_ceiling_usd=0.0001,
    )
    assert choice.estimated_cost_usd <= 0.0001 or choice.provider == "mock"
    assert choice.provider in {"gemini", "openai", "mock"}  # never error on ceiling


def test_task_type_drives_tier():
    extraction = decide_route(
        "extract fields as JSON",
        available=["openai", "anthropic", "gemini"],
        task_hint="structured_extraction",
    )
    reasoning = decide_route(
        "analyze trade-offs in the architecture",
        available=["openai", "anthropic", "gemini"],
        task_hint="complex_reasoning",
    )
    assert extraction.tier == "fast"
    assert reasoning.tier == "strong"
    assert "task_type=" in extraction.reason


def test_routing_reason_is_logged():
    choice = decide_route("policy question about vendors", available=["mock"])
    assert "cost_ceiling" in choice.reason
    assert "selected=" in choice.reason


@pytest.mark.asyncio
async def test_fallback_on_timeout(monkeypatch):
    class BoomProvider(BaseProvider):
        name = "openai"

        def is_available(self) -> bool:
            return True

        async def complete(self, prompt, *, model, system=None, temperature=0.2, max_tokens=2048):
            await asyncio.sleep(0.01)
            raise TimeoutError("simulated provider timeout")

    class OkProvider(BaseProvider):
        name = "mock"

        def is_available(self) -> bool:
            return True

        async def complete(self, prompt, *, model, system=None, temperature=0.2, max_tokens=2048):
            return LLMResponse(content="fallback-ok", provider="mock", model=model)

    def fake_providers():
        return {"openai": BoomProvider(), "mock": OkProvider()}

    monkeypatch.setattr("app.routing.fallback.get_providers", fake_providers)

    route = decide_route("hello", available=["openai", "mock"])
    # Force primary to openai even if policy prefers gemini
    route.provider = "openai"
    route.model = "gpt-4o-mini"
    route.fallback_chain = [("mock", "mock-fast")]

    resp, meta = await call_with_fallback("hello", route)
    assert resp.content == "fallback-ok"
    assert meta["fallback_used"] is True
    assert meta["final_provider"] == "mock"


@pytest.mark.asyncio
async def test_mock_provider_contract():
    p = MockProvider()
    assert p.is_available()
    resp = await p.complete(
        "Question: What is the data retention period after contract termination?",
        model="mock-fast",
        system="test",
    )
    assert isinstance(resp.content, str) and resp.content
    assert resp.provider == "mock"
    assert resp.model == "mock-fast"
    assert resp.latency_ms >= 0
    assert resp.estimated_cost_usd == 0.0
