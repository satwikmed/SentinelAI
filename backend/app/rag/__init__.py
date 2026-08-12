"""RAG package."""

from app.rag.retriever import ingest_documents, retrieve_chunks

__all__ = ["ingest_documents", "retrieve_chunks"]
