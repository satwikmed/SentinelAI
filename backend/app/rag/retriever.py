"""Document ingestion and ChromaDB retrieval for the enterprise document copilot."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_collection = None
_chunks_cache: list[dict[str, Any]] = []


def _docs_dir() -> Path:
    settings = get_settings()
    p = Path(settings.docs_dir)
    if not p.is_absolute():
        # Resolve relative to backend package root
        backend_root = Path(__file__).resolve().parents[2]
        p = backend_root / settings.docs_dir.lstrip("./")
    return p


def _simple_embed(text: str, dim: int = 64) -> list[float]:
    """Deterministic bag-of-hashes embedding — works offline without OpenAI.

    Good enough for demo retrieval; when OPENAI_API_KEY is set we still use this
    for local Chroma to avoid embedding API cost during ingest of seed docs.
    """
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    # L2 normalize
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def _chunk_text(text: str, size: int = 600, overlap: int = 80) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + size])
        if chunk.strip():
            chunks.append(chunk.strip())
        i += max(1, size - overlap)
    return chunks


def _load_documents() -> list[tuple[str, str]]:
    docs_dir = _docs_dir()
    docs: list[tuple[str, str]] = []
    if not docs_dir.exists():
        logger.warning("Docs dir missing: %s", docs_dir)
        return docs
    for path in sorted(docs_dir.rglob("*")):
        if path.suffix.lower() in {".md", ".txt"}:
            docs.append((path.name, path.read_text(encoding="utf-8", errors="ignore")))
        elif path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                docs.append((path.name, text))
            except Exception as exc:  # noqa: BLE001
                logger.warning("PDF read failed %s: %s", path, exc)
    return docs


def ingest_documents(force: bool = False) -> dict[str, Any]:
    """Ingest seed enterprise documents into Chroma (or in-memory fallback)."""
    global _collection, _chunks_cache
    settings = get_settings()
    documents = _load_documents()
    all_chunks: list[dict[str, Any]] = []
    for source, text in documents:
        for i, chunk in enumerate(_chunk_text(text)):
            all_chunks.append(
                {
                    "id": hashlib.sha256(f"{source}:{i}:{chunk[:40]}".encode()).hexdigest()[:16],
                    "source": source,
                    "text": chunk,
                    "embedding": _simple_embed(chunk),
                }
            )

    _chunks_cache = all_chunks

    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir
            if Path(settings.chroma_persist_dir).is_absolute()
            else str(Path(__file__).resolve().parents[2] / settings.chroma_persist_dir.lstrip("./")),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        if force:
            try:
                client.delete_collection("enterprise_docs")
            except Exception:  # noqa: BLE001
                pass
        _collection = client.get_or_create_collection(
            name="enterprise_docs",
            metadata={"hnsw:space": "cosine"},
        )
        if _collection.count() == 0 and all_chunks:
            _collection.add(
                ids=[c["id"] for c in all_chunks],
                documents=[c["text"] for c in all_chunks],
                metadatas=[{"source": c["source"]} for c in all_chunks],
                embeddings=[c["embedding"] for c in all_chunks],
            )
        return {"documents": len(documents), "chunks": len(all_chunks), "backend": "chromadb"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chroma unavailable (%s); using in-memory retrieval", exc)
        _collection = None
        return {
            "documents": len(documents),
            "chunks": len(all_chunks),
            "backend": "memory",
            "warning": str(exc),
        }


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


async def retrieve_chunks(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    k = top_k or settings.rag_top_k
    if not _chunks_cache and _collection is None:
        ingest_documents()

    q_emb = _simple_embed(query)

    if _collection is not None:
        try:
            result = _collection.query(query_embeddings=[q_emb], n_results=k)
            out = []
            docs = (result.get("documents") or [[]])[0]
            metas = (result.get("metadatas") or [[]])[0]
            dists = (result.get("distances") or [[]])[0]
            for doc, meta, dist in zip(docs, metas, dists):
                out.append(
                    {
                        "source": (meta or {}).get("source", "unknown"),
                        "text": doc,
                        "score": round(1.0 - float(dist), 4),
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chroma query failed: %s", exc)

    # In-memory cosine fallback
    scored = []
    for c in _chunks_cache:
        scored.append(
            {
                "source": c["source"],
                "text": c["text"],
                "score": round(_cosine(q_emb, c["embedding"]), 4),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]
