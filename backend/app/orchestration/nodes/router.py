"""Router node — selects provider/model and records the decision reason."""

from __future__ import annotations

from app.observability.tracing import span
from app.orchestration.state import AgentState
from app.routing.policy import decide_route, route_to_dict
from app.routing.providers import available_providers


async def router_node(state: AgentState) -> dict:
    with span("router"):
        available = available_providers()
        choice = decide_route(
            state["query"],
            available=available,
            task_hint=state.get("task_type"),
        )
        route = route_to_dict(choice)
        return {
            "route": route,
            "node_trace": ["router"],
            "metrics": {
                "routed_provider": choice.provider,
                "routed_model": choice.model,
                "route_reason": choice.reason,
            },
        }
