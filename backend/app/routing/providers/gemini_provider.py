"""Google Gemini provider adapter."""

from __future__ import annotations

import asyncio
import time

import google.generativeai as genai

from app.config import get_settings
from app.routing.providers.base import BaseProvider, LLMResponse

_COST = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
}


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._configured = False
        if self.settings.google_api_key:
            genai.configure(api_key=self.settings.google_api_key)
            self._configured = True

    def is_available(self) -> bool:
        return self._configured

    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if not self._configured:
            raise RuntimeError("Gemini provider not configured")

        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        gmodel = genai.GenerativeModel(model)

        started = time.perf_counter()
        resp = await asyncio.to_thread(
            gmodel.generate_content,
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        latency_ms = (time.perf_counter() - started) * 1000
        content = resp.text or ""

        in_tok = 0
        out_tok = 0
        if hasattr(resp, "usage_metadata") and resp.usage_metadata:
            in_tok = getattr(resp.usage_metadata, "prompt_token_count", 0) or 0
            out_tok = getattr(resp.usage_metadata, "candidates_token_count", 0) or 0

        in_rate, out_rate = _COST.get(model, (0.1, 0.4))
        cost = (in_tok * in_rate + out_tok * out_rate) / 1_000_000

        return LLMResponse(
            content=content,
            provider=self.name,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            estimated_cost_usd=cost,
            raw={},
        )
