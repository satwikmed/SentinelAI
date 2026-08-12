"""Executor node — runs RAG retrieval + LLM generation via the routed provider."""

from __future__ import annotations

from app.observability.tracing import span
from app.orchestration.state import AgentState
from app.rag.retriever import retrieve_chunks
from app.routing.fallback import call_with_fallback
from app.routing.policy import RouteChoice, TaskType


EXECUTOR_SYSTEM = (
    "You are the Executor agent in SentinelAI, an enterprise document intelligence copilot. "
    "Answer ONLY using the provided context snippets. Cite sources as [doc:title]. "
    "If the context is insufficient, say what is missing. Be precise and professional."
)


async def executor_node(state: AgentState) -> dict:
    with span("executor"):
        query = state["query"]
        revision_note = ""
        if state.get("needs_revision") and state.get("verification"):
            issues = state["verification"].get("issues") or []
            revision_note = (
                "\n\nREVISION REQUIRED based on verifier feedback:\n- "
                + "\n- ".join(issues)
            )

        chunks = await retrieve_chunks(query)
        context_block = "\n\n".join(
            f"[{c['source']}] {c['text']}" for c in chunks
        ) or "(No documents retrieved — answer carefully and note limited context.)"

        prompt = (
            f"Plan steps: {state.get('plan', [])}\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {query}"
            f"{revision_note}"
        )

        route_dict = state.get("route") or {}
        route = RouteChoice(
            provider=route_dict.get("provider", "mock"),
            model=route_dict.get("model", "mock-fast"),
            task_type=TaskType(route_dict.get("task_type", "document_qa")),
            reason=route_dict.get("reason", ""),
            estimated_cost_usd=float(route_dict.get("estimated_cost_usd", 0)),
            fallback_chain=[
                (f["provider"], f["model"]) for f in route_dict.get("fallback_chain", [])
            ],
            tier=route_dict.get("tier", "fast"),
        )

        resp, meta = await call_with_fallback(prompt, route, system=EXECUTOR_SYSTEM)

        citations = [
            {
                "source": c["source"],
                "snippet": c["text"][:240],
                "score": c.get("score", 0.0),
            }
            for c in chunks
        ]

        return {
            "context_chunks": chunks,
            "draft_response": resp.content,
            "citations": citations,
            "llm_meta": {
                "provider": resp.provider,
                "model": resp.model,
                "latency_ms": resp.latency_ms,
                "cost_usd": resp.estimated_cost_usd,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "fallback_meta": meta,
            },
            "needs_revision": False,
            "node_trace": ["executor"],
            "metrics": {
                "executor_provider": resp.provider,
                "executor_model": resp.model,
                "executor_latency_ms": resp.latency_ms,
                "executor_cost": resp.estimated_cost_usd,
                "fallback_used": meta.get("fallback_used", False),
            },
        }
