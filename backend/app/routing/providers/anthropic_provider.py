"""Anthropic provider adapter."""

from __future__ import annotations

import time

from anthropic import AsyncAnthropic

from app.config import get_settings
from app.routing.providers.base import BaseProvider, LLMResponse

_COST = {
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
}


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: AsyncAnthropic | None = None
        if self.settings.anthropic_api_key:
            self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    def is_available(self) -> bool:
        return self._client is not None

    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if not self._client:
            raise RuntimeError("Anthropic provider not configured")

        started = time.perf_counter()
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        resp = await self._client.messages.create(**kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        content = ""
        for block in resp.content:
            if hasattr(block, "text"):
                content += block.text

        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        in_rate, out_rate = _COST.get(model, (3.0, 15.0))
        cost = (in_tok * in_rate + out_tok * out_rate) / 1_000_000

        return LLMResponse(
            content=content,
            provider=self.name,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            estimated_cost_usd=cost,
            raw={"id": resp.id},
        )
