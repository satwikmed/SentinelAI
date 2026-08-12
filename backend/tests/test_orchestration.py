"""Module 1 — orchestration node unit tests + graph integration."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.orchestration.graph import build_graph, get_run_state, run_orchestration
from app.orchestration.nodes.executor import executor_node
from app.orchestration.nodes.planner import planner_node
from app.orchestration.nodes.router import router_node
from app.orchestration.nodes.verifier import verifier_node
from app.orchestration.state import AgentState
from app.rag.retriever import ingest_documents


@pytest.fixture(scope="module", autouse=True)
def _ingest():
    ingest_documents()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_planner_output_shape():
    state: AgentState = {
        "run_id": "t-plan",
        "query": "What is the data retention period after contract termination?",
        "metrics": {},
        "errors": [],
        "node_trace": [],
    }
    out = await planner_node(state)
    assert "plan" in out and isinstance(out["plan"], list) and len(out["plan"]) >= 1
    assert "task_type" in out and isinstance(out["task_type"], str)
    assert "planner" in out.get("node_trace", [])


@pytest.mark.asyncio
async def test_router_output_shape():
    state: AgentState = {
        "run_id": "t-route",
        "query": "Extract JSON fields from this policy",
        "task_type": "structured_extraction",
        "metrics": {},
        "errors": [],
        "node_trace": [],
    }
    out = await router_node(state)
    route = out["route"]
    assert route["provider"]
    assert route["model"]
    assert route["task_type"]
    assert "reason" in route and len(route["reason"]) > 10
    assert "fallback_chain" in route


@pytest.mark.asyncio
async def test_executor_output_shape():
    state: AgentState = {
        "run_id": "t-exec",
        "query": "How many PTO days can employees carry over?",
        "plan": ["retrieve", "answer", "verify"],
        "route": {
            "provider": "mock",
            "model": "mock-fast",
            "task_type": "document_qa",
            "reason": "test",
            "estimated_cost_usd": 0,
            "fallback_chain": [],
            "tier": "fast",
        },
        "metrics": {},
        "errors": [],
        "node_trace": [],
    }
    out = await executor_node(state)
    assert isinstance(out.get("draft_response"), str) and out["draft_response"]
    assert isinstance(out.get("citations"), list)
    assert "llm_meta" in out
    assert out["llm_meta"]["provider"] == "mock"


@pytest.mark.asyncio
async def test_verifier_output_shape():
    state: AgentState = {
        "run_id": "t-ver",
        "query": "How quickly must security incidents be reported to the SOC?",
        "draft_response": (
            "Suspected security incidents must be reported to the SOC within 1 hour."
        ),
        "context_chunks": [
            {
                "source": "incident_response_policy.md",
                "text": "Suspected security incidents must be reported to the SOC within 1 hour.",
                "score": 0.9,
            }
        ],
        "reflection_count": 0,
        "metrics": {},
        "errors": [],
        "node_trace": [],
    }
    out = await verifier_node(state)
    assert "verification" in out
    v = out["verification"]
    assert "pass" in v and "faithfulness" in v and "relevance" in v
    assert "confidence" in out
    assert isinstance(out.get("needs_revision"), bool)


@pytest.mark.asyncio
async def test_full_graph_terminates_and_is_inspectable():
    result = await run_orchestration(
        "What is the data retention period after contract termination?",
        run_id="inspect-me-001",
    )
    assert result.get("final_response") or result.get("draft_response")
    assert "planner" in (result.get("node_trace") or [])
    assert "router" in (result.get("node_trace") or [])
    assert "executor" in (result.get("node_trace") or [])
    assert "verifier" in (result.get("node_trace") or [])
    # No infinite loop — reflection_count bounded
    assert int(result.get("reflection_count") or 0) <= get_settings().max_reflection_retries

    snap = get_run_state("inspect-me-001")
    assert snap is not None
    assert snap["run_id"] == "inspect-me-001"
    assert "values" in snap


@pytest.mark.asyncio
async def test_reflection_retry_cap(monkeypatch):
    """Force verifier to always fail; graph must stop at max_reflection_retries."""
    settings = get_settings()
    max_n = settings.max_reflection_retries

    async def always_fail_verifier(state: AgentState) -> dict:
        count = int(state.get("reflection_count") or 0)
        needs = count < max_n
        return {
            "verification": {
                "pass": False,
                "faithfulness": 0.1,
                "relevance": 0.1,
                "issues": ["forced failure for retry-cap test"],
                "method": "test",
            },
            "needs_revision": needs,
            "reflection_count": count + (1 if needs else 0),
            "confidence": 0.1,
            "final_response": state.get("draft_response", ""),
            "node_trace": ["verifier"],
            "metrics": {"faithfulness": 0.1, "relevance": 0.1, "verification_pass": False},
        }

    monkeypatch.setattr(
        "app.orchestration.graph.verifier_node",
        always_fail_verifier,
    )
    # Force graph rebuild with patched verifier
    import app.orchestration.graph as g

    g._compiled = None
    graph = build_graph()

    result = await graph.ainvoke(
        {
            "run_id": "retry-cap",
            "query": "What is the data retention period after contract termination?",
            "reflection_count": 0,
            "needs_revision": False,
            "metrics": {},
            "errors": [],
            "node_trace": [],
            "escalate_to_human": False,
            "escalation_reason": "",
        },
        config={"configurable": {"thread_id": "retry-cap"}},
    )
    # Reset compiled graph for other tests
    g._compiled = None

    assert int(result.get("reflection_count") or 0) <= max_n
    # Graph should have finished (finalize ran or verifier stopped revising)
    assert result.get("needs_revision") is False or int(result.get("reflection_count") or 0) >= max_n
    verifier_hits = (result.get("node_trace") or []).count("verifier")
    executor_hits = (result.get("node_trace") or []).count("executor")
    assert verifier_hits <= max_n + 1
    assert executor_hits <= max_n + 1
