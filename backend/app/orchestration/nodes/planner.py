"""Planner node — decomposes the user request into executable steps.

Part of the planner-executor orchestration pattern.
"""

from __future__ import annotations

import json
import re

from app.observability.tracing import span
from app.orchestration.state import AgentState
from app.routing.fallback import call_with_fallback
from app.routing.policy import classify_task, decide_route
from app.routing.providers import available_providers


PLANNER_SYSTEM = (
    "You are the Planner agent in SentinelAI. Decompose the user question into "
    "2-4 short executable steps for a document intelligence pipeline. "
    "Respond with a JSON array of strings only."
)


async def planner_node(state: AgentState) -> dict:
    with span("planner"):
        query = state["query"]
        task = classify_task(query)
        available = available_providers()
        # Planner itself uses a cheap/fast route
        route = decide_route(
            query,
            available=available,
            task_hint="classification",
        )
        prompt = (
            f"User question: {query}\n"
            f"Inferred task type: {task.value}\n"
            "Return a JSON array of plan steps."
        )
        try:
            resp, meta = await call_with_fallback(prompt, route, system=PLANNER_SYSTEM)
            plan = _parse_plan(resp.content)
        except Exception as exc:  # noqa: BLE001
            plan = [
                "Retrieve relevant enterprise documents",
                "Draft answer with citations",
                "Verify faithfulness against sources",
            ]
            return {
                "plan": plan,
                "task_type": task.value,
                "errors": [f"planner_fallback: {exc}"],
                "node_trace": ["planner"],
                "metrics": {"planner_model": "fallback"},
            }

        return {
            "plan": plan,
            "task_type": task.value,
            "node_trace": ["planner"],
            "metrics": {
                "planner_provider": resp.provider,
                "planner_model": resp.model,
                "planner_cost": resp.estimated_cost_usd,
            },
        }


def _parse_plan(text: str) -> list[str]:
    text = text.strip()
    try:
        # Extract JSON array if wrapped in markdown
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, list) and data:
                return [str(x) for x in data][:6]
    except json.JSONDecodeError:
        pass
    # Line-based fallback
    lines = [ln.strip("-• ").strip() for ln in text.splitlines() if ln.strip()]
    return lines[:4] or ["Retrieve documents", "Answer with citations", "Verify"]
