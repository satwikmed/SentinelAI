"""Typed LangGraph agent state.

Persisted via LangGraph checkpointing so every run can be inspected step-by-step —
a core interview talking point for enterprise agent systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def _merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {**a, **b}


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    query: str

    # Planner output (planner-executor pattern)
    plan: list[str]
    task_type: str

    # Router output
    route: dict[str, Any]

    # Executor output
    context_chunks: list[dict[str, Any]]
    draft_response: str
    citations: list[dict[str, Any]]
    llm_meta: dict[str, Any]

    # Verifier / reflection
    verification: dict[str, Any]
    reflection_count: int
    needs_revision: bool

    # Guardrails
    input_guardrails: dict[str, Any]
    output_guardrails: dict[str, Any]
    escalate_to_human: bool
    escalation_reason: str

    # Final
    final_response: str
    confidence: float
    governance_passed: bool

    # Metrics accumulated across nodes
    metrics: Annotated[dict[str, Any], _merge_dicts]

    # Trace / errors
    errors: Annotated[list[str], operator.add]
    node_trace: Annotated[list[str], operator.add]
