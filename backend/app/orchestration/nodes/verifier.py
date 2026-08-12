"""Verifier node — checks draft against sources (reflection pattern).

If verification fails, sets needs_revision=True so the graph loops back to Executor.
This implements the reflection orchestration pattern named in enterprise GenAI JDs.
"""

from __future__ import annotations

import json
import re

from app.config import get_settings
from app.observability.tracing import span
from app.orchestration.state import AgentState
from app.routing.fallback import call_with_fallback
from app.routing.policy import decide_route
from app.routing.providers import available_providers


VERIFIER_SYSTEM = (
    "You are the Verifier agent. Score whether the draft answer is faithful to the "
    "provided context and relevant to the question. Return JSON only: "
    '{"pass": bool, "faithfulness": float 0-1, "relevance": float 0-1, "issues": [str]}'
)


async def verifier_node(state: AgentState) -> dict:
    with span("verifier"):
        settings = get_settings()
        draft = state.get("draft_response", "")
        chunks = state.get("context_chunks") or []
        context = "\n".join(c.get("text", "") for c in chunks)[:4000]
        query = state["query"]

        # Heuristic baseline (always computed; LLM can refine when available)
        faithfulness, relevance, issues = _heuristic_scores(draft, context, query)
        verification = {
            "pass": faithfulness >= settings.faithfulness_threshold
            and relevance >= settings.faithfulness_threshold,
            "faithfulness": faithfulness,
            "relevance": relevance,
            "issues": issues,
            "method": "heuristic",
        }

        # Optional LLM reflection pass for richer issues list
        try:
            route = decide_route(
                "verify faithfulness",
                available=available_providers(),
                task_hint="classification",
            )
            prompt = (
                f"Question: {query}\n\nContext:\n{context}\n\nDraft:\n{draft}\n\n"
                "Return JSON with pass, faithfulness, relevance, issues."
            )
            resp, _ = await call_with_fallback(prompt, route, system=VERIFIER_SYSTEM)
            parsed = _parse_verification(resp.content)
            if parsed:
                verification = {**parsed, "method": "llm+heuristic"}
                # Blend with heuristic to avoid over-trusting a single call
                verification["faithfulness"] = (
                    verification.get("faithfulness", faithfulness) + faithfulness
                ) / 2
                verification["relevance"] = (
                    verification.get("relevance", relevance) + relevance
                ) / 2
                verification["pass"] = (
                    verification["faithfulness"] >= settings.faithfulness_threshold
                    and verification["relevance"] >= settings.faithfulness_threshold
                    and not (verification.get("issues") and len(verification["issues"]) > 2)
                )
        except Exception:  # noqa: BLE001
            pass

        reflection_count = int(state.get("reflection_count") or 0)
        needs_revision = (not verification["pass"]) and reflection_count < settings.max_reflection_retries

        result: dict = {
            "verification": verification,
            "needs_revision": needs_revision,
            "reflection_count": reflection_count + (1 if needs_revision else 0),
            "confidence": float(
                (verification.get("faithfulness", 0) + verification.get("relevance", 0)) / 2
            ),
            "node_trace": ["verifier"],
            "metrics": {
                "faithfulness": verification.get("faithfulness", 0),
                "relevance": verification.get("relevance", 0),
                "verification_pass": verification.get("pass", False),
            },
        }

        if not needs_revision:
            result["final_response"] = draft
        return result


def _heuristic_scores(draft: str, context: str, query: str) -> tuple[float, float, list[str]]:
    issues: list[str] = []
    if not draft.strip():
        return 0.0, 0.0, ["empty draft"]

    draft_l = draft.lower()
    ctx_l = context.lower()
    # Token overlap faithfulness proxy
    draft_tokens = set(re.findall(r"[a-z0-9]{4,}", draft_l))
    ctx_tokens = set(re.findall(r"[a-z0-9]{4,}", ctx_l))
    if not draft_tokens:
        faithfulness = 0.0
    elif not ctx_tokens:
        faithfulness = 0.55  # no context — neutral
        issues.append("no retrieval context available")
    else:
        overlap = len(draft_tokens & ctx_tokens) / max(len(draft_tokens), 1)
        faithfulness = min(1.0, 0.35 + overlap)

    q_tokens = set(re.findall(r"[a-z0-9]{3,}", query.lower()))
    relevance = min(1.0, 0.4 + len(q_tokens & draft_tokens) / max(len(q_tokens), 1))

    if faithfulness < 0.5:
        issues.append("low lexical overlap with source context")
    if relevance < 0.5:
        issues.append("draft may not address the question")
    if "i don't know" in draft_l or "insufficient" in draft_l:
        faithfulness = max(faithfulness, 0.7)  # honest abstention is faithful

    return round(faithfulness, 3), round(relevance, 3), issues


def _parse_verification(text: str) -> dict | None:
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
        return {
            "pass": bool(data.get("pass", False)),
            "faithfulness": float(data.get("faithfulness", 0)),
            "relevance": float(data.get("relevance", 0)),
            "issues": list(data.get("issues") or []),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
