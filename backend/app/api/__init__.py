"""FastAPI routers."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import ChatRequest, ChatResponse, ReviewResolveRequest
from app.config import get_settings
from app.rag.retriever import ingest_documents
from app.routing.providers import available_providers
from app.services import gateway

router = APIRouter()


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "demo_mode": settings.demo_mode,
        "providers_available": available_providers(),
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    result = await gateway.process_chat(body.query, cost_ceiling_usd=body.cost_ceiling_usd)
    return ChatResponse(**result)


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    state = gateway.inspect_run(run_id)
    if not state:
        # Still return audit trail even if checkpoint expired
        events = await gateway.list_audit_events(run_id=run_id)
        if not events:
            raise HTTPException(404, "Run not found")
        return {"run_id": run_id, "values": None, "audit": events}
    events = await gateway.list_audit_events(run_id=run_id)
    return {**state, "audit": events}


@router.get("/routing/decisions")
async def routing_decisions(limit: int = Query(50, ge=1, le=200)):
    return {"decisions": await gateway.list_routing_decisions(limit=limit)}


@router.get("/audit")
async def audit(run_id: str | None = None, limit: int = Query(100, ge=1, le=500)):
    return {"events": await gateway.list_audit_events(run_id=run_id, limit=limit)}


@router.get("/review")
async def review_queue(status: str = Query("pending")):
    return {"items": await gateway.list_review_queue(status=status)}


@router.post("/review/{item_id}/resolve")
async def resolve_review(item_id: int, body: ReviewResolveRequest):
    result = await gateway.resolve_review(item_id, body.status, body.notes)
    if not result:
        raise HTTPException(404, "Review item not found")
    return result


@router.get("/metrics")
async def metrics(limit: int = Query(50, ge=1, le=200)):
    return {"metrics": await gateway.list_metrics(limit=limit)}


@router.post("/admin/reingest")
async def reingest():
    return ingest_documents(force=True)
