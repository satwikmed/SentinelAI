"""LangGraph orchestration graph.

Patterns implemented explicitly:
1. Planner-Executor — Planner decomposes; Executor performs RAG + generation.
2. Reflection — Verifier scores output and can send work back to Executor (max N times).

State is checkpointed so runs are inspectable via GET /runs/{id}.
"""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.orchestration.nodes import executor_node, planner_node, router_node, verifier_node
from app.orchestration.state import AgentState

# Module-level checkpointer — MemorySaver for simplicity across sqlite/postgres deploy;
# run history is also persisted to the audit DB for operator inspection.
_checkpointer = MemorySaver()
_compiled = None


def _should_reflect(state: AgentState) -> str:
    if state.get("needs_revision"):
        return "executor"
    return "finalize"


async def _finalize_node(state: AgentState) -> dict:
    """Terminal node — package final response fields."""
    draft = state.get("final_response") or state.get("draft_response") or ""
    confidence = float(state.get("confidence") or 0.0)
    verification = state.get("verification") or {}
    return {
        "final_response": draft,
        "governance_passed": bool(verification.get("pass", False)),
        "node_trace": ["finalize"],
    }


def build_graph():
    """Compile the SentinelAI orchestration graph with reflection loop."""
    global _compiled
    if _compiled is not None:
        return _compiled

    g = StateGraph(AgentState)
    g.add_node("planner", planner_node)
    g.add_node("router", router_node)
    g.add_node("executor", executor_node)
    g.add_node("verifier", verifier_node)
    g.add_node("finalize", _finalize_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "router")
    g.add_edge("router", "executor")
    g.add_edge("executor", "verifier")
    g.add_conditional_edges(
        "verifier",
        _should_reflect,
        {"executor": "executor", "finalize": "finalize"},
    )
    g.add_edge("finalize", END)

    _compiled = g.compile(checkpointer=_checkpointer)
    return _compiled


async def run_orchestration(
    query: str,
    *,
    run_id: str | None = None,
    input_guardrails: dict[str, Any] | None = None,
) -> AgentState:
    graph = build_graph()
    run_id = run_id or str(uuid.uuid4())
    initial: AgentState = {
        "run_id": run_id,
        "query": query,
        "reflection_count": 0,
        "needs_revision": False,
        "input_guardrails": input_guardrails or {},
        "metrics": {},
        "errors": [],
        "node_trace": [],
        "escalate_to_human": False,
        "escalation_reason": "",
    }
    config = {"configurable": {"thread_id": run_id}}
    result = await graph.ainvoke(initial, config=config)
    return result  # type: ignore[return-value]


def get_run_state(run_id: str) -> dict[str, Any] | None:
    """Inspect checkpointed state for a run (step-by-step interview talking point)."""
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    try:
        snap = graph.get_state(config)
        if snap is None or snap.values is None:
            return None
        return {
            "run_id": run_id,
            "values": dict(snap.values),
            "next": list(snap.next) if snap.next else [],
            "created_at": str(getattr(snap, "created_at", "")),
        }
    except Exception:  # noqa: BLE001
        return None
