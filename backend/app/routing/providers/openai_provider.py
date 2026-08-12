"""OpenAI provider adapter."""

from __future__ import annotations

import time

from openai import AsyncOpenAI

from app.config import get_settings
from app.routing.providers.base import BaseProvider, LLMResponse

# Approximate USD per 1M tokens
_COST = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: AsyncOpenAI | None = None
        if self.settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)

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
            raise RuntimeError("OpenAI provider not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        started = time.perf_counter()
        resp = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        in_rate, out_rate = _COST.get(model, (1.0, 3.0))
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
