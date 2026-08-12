"""Observability package."""

from app.observability.tracing import init_tracing, span

__all__ = ["init_tracing", "span"]
