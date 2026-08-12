"""Gateway service — wires guardrails, orchestration, audit, and escalation."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db import AuditEvent, HumanReviewItem, RequestMetrics, RoutingDecision, SessionLocal
from app.guardrails import run_input_guardrails, run_output_guardrails
from app.orchestration.graph import get_run_state, run_orchestration


async def _audit(run_id: str, event_type: str, detail: str) -> None:
    async with SessionLocal() as session:
        session.add(AuditEvent(run_id=run_id, event_type=event_type, detail=detail[:8000]))
        await session.commit()


async def process_chat(
    query: str,
    *,
    cost_ceiling_usd: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    run_id = str(uuid.uuid4())
    started = time.perf_counter()

    await _audit(run_id, "request_received", query)

    # --- Input guardrails ---
    input_g = run_input_guardrails(query)
    await _audit(run_id, "input_guardrails", str(input_g))

    if input_g.get("blocked"):
        reason = "Prompt injection heuristic exceeded threshold"
        async with SessionLocal() as session:
            session.add(
                HumanReviewItem(
                    run_id=run_id,
                    query=query,
                    draft_response="",
                    reason=reason,
                    status="pending",
                )
            )
            await session.commit()
        await _audit(run_id, "escalated", reason)
        latency = (time.perf_counter() - started) * 1000
        return {
            "run_id": run_id,
            "answer": None,
            "escalated": True,
            "escalation_reason": reason,
            "governance_passed": False,
            "confidence": 0.0,
            "citations": [],
            "input_guardrails": input_g,
            "output_guardrails": None,
            "route": None,
            "verification": None,
            "metrics": {"latency_ms": latency},
            "node_trace": ["input_guardrails", "escalate"],
            "demo_mode": settings.demo_mode,
        }

    sanitized = input_g.get("sanitized_query") or query

    # --- Orchestration (planner → router → executor → verifier [reflection]) ---
    state = await run_orchestration(sanitized, run_id=run_id, input_guardrails=input_g)

    # Persist routing decision
    route = state.get("route") or {}
    async with SessionLocal() as session:
        session.add(
            RoutingDecision(
                run_id=run_id,
                task_type=route.get("task_type", "unknown"),
                selected_provider=route.get("provider", ""),
                selected_model=route.get("model", ""),
                reason=route.get("reason", ""),
                fallback_used=bool((state.get("metrics") or {}).get("fallback_used")),
                estimated_cost_usd=float(route.get("estimated_cost_usd") or 0),
            )
        )
        await session.commit()
    await _audit(run_id, "routing_decision", str(route))

    answer = state.get("final_response") or state.get("draft_response") or ""
    confidence = float(state.get("confidence") or 0.0)
    verification = state.get("verification") or {}

    # --- Output guardrails ---
    output_g = run_output_guardrails(answer, confidence if confidence > 0 else 0.01)
    await _audit(run_id, "output_guardrails", str(output_g))

    escalate = False
    escalation_reason = ""
    if not output_g.get("passed"):
        escalate = True
        escalation_reason = "Output guardrail failure"
    elif confidence < settings.min_confidence_for_auto_reply:
        escalate = True
        escalation_reason = f"Confidence {confidence:.2f} below threshold"
    elif not verification.get("pass", False):
        escalate = True
        escalation_reason = "Verifier did not pass after reflection retries"

    governance_passed = (not escalate) and bool(output_g.get("passed")) and bool(
        verification.get("pass", False)
    )

    if escalate:
        async with SessionLocal() as session:
            session.add(
                HumanReviewItem(
                    run_id=run_id,
                    query=query,
                    draft_response=answer,
                    reason=escalation_reason,
                    status="pending",
                )
            )
            await session.commit()
        await _audit(run_id, "escalated", escalation_reason)

    latency_ms = (time.perf_counter() - started) * 1000
    metrics = state.get("metrics") or {}
    cost = float(metrics.get("executor_cost") or 0) + float(metrics.get("planner_cost") or 0)

    async with SessionLocal() as session:
        session.add(
            RequestMetrics(
                run_id=run_id,
                latency_ms=latency_ms,
                token_cost_usd=cost,
                faithfulness=float(verification.get("faithfulness") or 0),
                relevance=float(verification.get("relevance") or 0),
                guardrail_pass=governance_passed,
                provider=str(metrics.get("executor_provider") or route.get("provider") or ""),
                model=str(metrics.get("executor_model") or route.get("model") or ""),
            )
        )
        await session.commit()

    await _audit(run_id, "response_ready", answer[:2000])

    return {
        "run_id": run_id,
        "answer": None if escalate and not answer else answer,
        "draft_answer": answer if escalate else None,
        "escalated": escalate,
        "escalation_reason": escalation_reason if escalate else None,
        "governance_passed": governance_passed,
        "confidence": confidence,
        "citations": state.get("citations") or [],
        "plan": state.get("plan") or [],
        "input_guardrails": input_g,
        "output_guardrails": output_g,
        "route": route,
        "verification": verification,
        "metrics": {
            "latency_ms": round(latency_ms, 2),
            "token_cost_usd": round(cost, 6),
            "faithfulness": verification.get("faithfulness"),
            "relevance": verification.get("relevance"),
            "guardrail_pass": governance_passed,
            **{k: v for k, v in metrics.items() if isinstance(v, (str, int, float, bool))},
        },
        "node_trace": state.get("node_trace") or [],
        "demo_mode": settings.demo_mode,
    }


async def list_routing_decisions(limit: int = 50) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(RoutingDecision).order_by(RoutingDecision.id.desc()).limit(limit)
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "task_type": r.task_type,
                "selected_provider": r.selected_provider,
                "selected_model": r.selected_model,
                "reason": r.reason,
                "fallback_used": r.fallback_used,
                "estimated_cost_usd": r.estimated_cost_usd,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


async def list_audit_events(run_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
        if run_id:
            stmt = (
                select(AuditEvent)
                .where(AuditEvent.run_id == run_id)
                .order_by(AuditEvent.id.asc())
                .limit(limit)
            )
        rows = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "event_type": r.event_type,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


async def list_review_queue(status: str = "pending") -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(HumanReviewItem)
                .where(HumanReviewItem.status == status)
                .order_by(HumanReviewItem.id.desc())
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "query": r.query,
                "draft_response": r.draft_response,
                "reason": r.reason,
                "status": r.status,
                "reviewer_notes": r.reviewer_notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


async def resolve_review(item_id: int, status: str, notes: str = "") -> dict[str, Any] | None:
    async with SessionLocal() as session:
        row = await session.get(HumanReviewItem, item_id)
        if not row:
            return None
        row.status = status
        row.reviewer_notes = notes
        row.resolved_at = datetime.now(timezone.utc)
        await session.commit()
        await _audit(row.run_id, "human_review_resolved", f"{status}: {notes}")
        return {"id": row.id, "status": row.status, "run_id": row.run_id}


async def list_metrics(limit: int = 50) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(RequestMetrics).order_by(RequestMetrics.id.desc()).limit(limit)
            )
        ).scalars().all()
        return [
            {
                "run_id": r.run_id,
                "latency_ms": r.latency_ms,
                "token_cost_usd": r.token_cost_usd,
                "faithfulness": r.faithfulness,
                "relevance": r.relevance,
                "guardrail_pass": r.guardrail_pass,
                "provider": r.provider,
                "model": r.model,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def inspect_run(run_id: str) -> dict[str, Any] | None:
    return get_run_state(run_id)
