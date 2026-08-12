"""Routing policy: task type → model tier, cost ceiling, fallback chain.

This is the multi-cloud routing layer that separates SentinelAI from a bare RAG demo.
Every decision is logged with an explicit reason for the operator dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.config import Settings, get_settings


class TaskType(str, Enum):
    STRUCTURED_EXTRACTION = "structured_extraction"
    DOCUMENT_QA = "document_qa"
    COMPLEX_REASONING = "complex_reasoning"
    CLASSIFICATION = "classification"
    GENERAL = "general"


@dataclass
class RouteChoice:
    provider: str
    model: str
    task_type: TaskType
    reason: str
    estimated_cost_usd: float
    fallback_chain: list[tuple[str, str]] = field(default_factory=list)
    tier: str = "fast"


# Rough per-request cost estimates used for ceiling checks (before actual usage)
_EST_COST = {
    ("openai", "fast"): 0.002,
    ("openai", "strong"): 0.02,
    ("anthropic", "fast"): 0.003,
    ("anthropic", "strong"): 0.03,
    ("gemini", "fast"): 0.001,
    ("gemini", "strong"): 0.008,
    ("mock", "fast"): 0.0,
    ("mock", "strong"): 0.0,
}


def classify_task(query: str, hint: str | None = None) -> TaskType:
    if hint:
        try:
            return TaskType(hint)
        except ValueError:
            pass
    q = query.lower()
    if any(k in q for k in ("extract", "json", "schema", "fields", "parse")):
        return TaskType.STRUCTURED_EXTRACTION
    if any(k in q for k in ("why", "compare", "analyze", "trade-off", "architect", "design")):
        return TaskType.COMPLEX_REASONING
    if any(k in q for k in ("classify", "category", "label", "sentiment")):
        return TaskType.CLASSIFICATION
    if any(k in q for k in ("policy", "document", "contract", "handbook", "according to", "section")):
        return TaskType.DOCUMENT_QA
    return TaskType.GENERAL


def _tier_for_task(task: TaskType) -> str:
    if task in (TaskType.STRUCTURED_EXTRACTION, TaskType.CLASSIFICATION):
        return "fast"
    if task == TaskType.COMPLEX_REASONING:
        return "strong"
    return "fast"


def _model_for(settings: Settings, provider: str, tier: str) -> str:
    table = {
        ("openai", "fast"): settings.openai_fast_model,
        ("openai", "strong"): settings.openai_strong_model,
        ("anthropic", "fast"): settings.anthropic_fast_model,
        ("anthropic", "strong"): settings.anthropic_strong_model,
        ("gemini", "fast"): settings.gemini_fast_model,
        ("gemini", "strong"): settings.gemini_strong_model,
        ("mock", "fast"): "mock-fast",
        ("mock", "strong"): "mock-strong",
    }
    return table[(provider, tier)]


def decide_route(
    query: str,
    *,
    available: list[str],
    task_hint: str | None = None,
    cost_ceiling_usd: float | None = None,
    settings: Settings | None = None,
) -> RouteChoice:
    """Select provider/model by task type, cost ceiling, and availability.

    Preference order (when available):
      fast tier:  gemini → openai → anthropic → mock
      strong tier: anthropic → openai → gemini → mock
    """
    settings = settings or get_settings()
    ceiling = cost_ceiling_usd if cost_ceiling_usd is not None else settings.default_cost_ceiling_usd
    task = classify_task(query, task_hint)
    tier = _tier_for_task(task)

    if not available:
        available = ["mock"]

    if tier == "fast":
        preference = ["gemini", "openai", "anthropic", "mock"]
    else:
        preference = ["anthropic", "openai", "gemini", "mock"]

    candidates = [p for p in preference if p in available]
    if not candidates:
        candidates = ["mock"] if "mock" in available or True else available

    # Apply cost ceiling: drop candidates whose estimated cost exceeds ceiling
    affordable: list[str] = []
    for p in candidates:
        est = _EST_COST.get((p, tier), 0.01)
        if est <= ceiling or p == "mock":
            affordable.append(p)

    if not affordable:
        # Fall back to cheapest available rather than fail
        affordable = sorted(candidates, key=lambda p: _EST_COST.get((p, "fast"), 0.01))

    primary = affordable[0]
    model = _model_for(settings, primary, tier)
    est = _EST_COST.get((primary, tier), 0.0)

    fallback_chain = [
        (p, _model_for(settings, p, tier if p != "mock" else "fast"))
        for p in affordable[1:]
    ]
    # Always keep mock as last resort if not already present
    if not any(p == "mock" for p, _ in fallback_chain) and primary != "mock":
        fallback_chain.append(("mock", "mock-fast"))

    reasons = [
        f"task_type={task.value}",
        f"tier={tier} (extraction/classification→fast, complex_reasoning→strong)",
        f"cost_ceiling=${ceiling:.4f}, estimated=${est:.4f}",
        f"selected={primary}/{model} from available={available}",
    ]
    if primary != preference[0] and preference[0] not in available:
        reasons.append(f"preferred {preference[0]} unavailable; used next preference")

    return RouteChoice(
        provider=primary,
        model=model,
        task_type=task,
        reason="; ".join(reasons),
        estimated_cost_usd=est,
        fallback_chain=fallback_chain,
        tier=tier,
    )


def route_to_dict(choice: RouteChoice) -> dict[str, Any]:
    return {
        "provider": choice.provider,
        "model": choice.model,
        "task_type": choice.task_type.value,
        "reason": choice.reason,
        "estimated_cost_usd": choice.estimated_cost_usd,
        "fallback_chain": [{"provider": p, "model": m} for p, m in choice.fallback_chain],
        "tier": choice.tier,
    }
