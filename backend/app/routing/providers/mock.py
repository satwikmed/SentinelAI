"""Deterministic mock provider for demo mode (no API keys)."""

from __future__ import annotations

import hashlib
import re
import time

from app.routing.providers.base import BaseProvider, LLMResponse


def _extract_focus(prompt: str) -> str:
    """Prefer the user question over retrieved context when keyword-matching."""
    for pattern in (
        r"Question:\s*(.+?)(?:\n\n|\Z)",
        r"User question:\s*(.+?)(?:\n|\Z)",
    ):
        m = re.search(pattern, prompt, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip().lower()
    # Fall back to last 400 chars (usually the ask) rather than full RAG dump
    return prompt[-400:].lower()


class MockProvider(BaseProvider):
    name = "mock"

    def is_available(self) -> bool:
        return True

    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        started = time.perf_counter()
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:8]

        full = prompt.lower()
        focus = _extract_focus(prompt)

        # Check planner/verifier intents before domain keywords
        if "json array of plan steps" in full or ("decompose" in full and "steps" in full):
            content = (
                '["retrieve relevant policy documents", "extract answer with citations", '
                '"verify faithfulness against sources"]'
            )
        elif "return json with pass" in full or (
            "faithfulness" in full and "relevance" in full and "draft" in full
        ):
            content = '{"pass": true, "faithfulness": 0.82, "relevance": 0.88, "issues": []}'
        elif "retention" in focus:
            content = (
                "According to the Information Security Policy (Section 4.2), customer data "
                "must be retained for a maximum of 36 months after contract termination, "
                "unless a longer period is required by applicable law. Backups follow the "
                "same retention schedule. [demo-mock]"
            )
        elif "incident" in focus or "breach" in focus or "soc" in focus:
            content = (
                "The Incident Response Policy requires that suspected security incidents be "
                "reported to the Security Operations Center within 1 hour. Confirmed breaches "
                "affecting personal data must be escalated to Legal within 24 hours for "
                "regulatory notification assessment. [demo-mock]"
            )
        elif any(k in focus for k in ("vacation", "pto", "leave", "carry")):
            content = (
                "Per the Employee Handbook, full-time employees accrue 20 days of PTO annually, "
                "with a maximum carryover of 5 days into the next calendar year. Requests must "
                "be submitted at least 10 business days in advance for absences longer than "
                "3 consecutive days. [demo-mock]"
            )
        elif any(k in focus for k in ("vendor", "procurement", "dpa")):
            content = (
                "The Vendor Management Policy requires security questionnaires for any vendor "
                "processing confidential or personal data. Contracts above $50,000 require "
                "Legal review and a signed DPA before onboarding. [demo-mock]"
            )
        elif "json" in full or "classify" in full or "task_type" in full:
            content = '{"task_type": "document_qa", "complexity": "medium", "needs_rag": true}'
        else:
            content = (
                f"[Demo mode — no live LLM keys configured.] "
                f"Processed request {digest}. Configure OPENAI_API_KEY, ANTHROPIC_API_KEY, "
                f"or GOOGLE_API_KEY for live multi-cloud routing. Model requested: {model}."
            )

        latency_ms = (time.perf_counter() - started) * 1000 + 12.0
        return LLMResponse(
            content=content,
            provider=self.name,
            model=model or "mock-v1",
            input_tokens=max(1, len(prompt) // 4),
            output_tokens=max(1, len(content) // 4),
            latency_ms=latency_ms,
            estimated_cost_usd=0.0,
            raw={"demo": True},
        )
