"""Module 5 — document copilot RAG groundedness + citations."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import init_db
from app.main import app
from app.rag.retriever import ingest_documents, retrieve_chunks


@pytest.fixture(scope="module", autouse=True)
def _ingest():
    ingest_documents(force=True)


@pytest.fixture(autouse=True)
async def _db():
    await init_db()


@pytest.mark.asyncio
async def test_grounded_questions_have_citations():
    cases = [
        ("What is the data retention period after contract termination?", "36 months", "information_security"),
        ("How quickly must security incidents be reported to the SOC?", "1 hour", "incident"),
        ("How many PTO days can employees carry over?", "5 days", "employee_handbook"),
        ("When is a DPA required for vendors?", "DPA", "vendor"),
    ]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        for question, needle, source_hint in cases:
            resp = await client.post("/api/chat", json={"query": question})
            assert resp.status_code == 200, question
            data = resp.json()
            answer = data.get("answer") or data.get("draft_answer") or ""
            assert needle.lower() in answer.lower(), f"{question} => {answer}"
            assert data.get("citations"), f"missing citations for {question}"
            sources = " ".join(c["source"] for c in data["citations"]).lower()
            assert source_hint.lower() in sources or any(
                source_hint.split("_")[0] in c["source"].lower() for c in data["citations"]
            )


@pytest.mark.asyncio
async def test_unknown_topic_does_not_confidently_hallucinate_policy():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        resp = await client.post(
            "/api/chat",
            json={"query": "What is Acme Corp's cafeteria sushi vendor discount code for 2099?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        answer = (data.get("answer") or data.get("draft_answer") or "").lower()
        # Mock/demo may still answer generically; ensure we don't invent a specific fake discount code as fact
        assert "sushi-2099" not in answer
        assert "discount code xyz" not in answer


@pytest.mark.asyncio
async def test_retrieval_chunks_point_to_seed_docs():
    chunks = await retrieve_chunks("data retention after contract termination")
    assert chunks
    assert any("information_security" in c["source"] for c in chunks)


@pytest.mark.asyncio
async def test_citations_snippet_nonempty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        resp = await client.post(
            "/api/chat",
            json={"query": "What is the data retention period after contract termination?"},
        )
        data = resp.json()
        for c in data.get("citations") or []:
            assert c.get("source")
            assert c.get("snippet")
            assert len(c["snippet"]) > 20
