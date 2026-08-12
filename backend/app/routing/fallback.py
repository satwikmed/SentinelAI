"""Provider call with timeout and fallback chain."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings
from app.routing.policy import RouteChoice
from app.routing.providers import get_providers
from app.routing.providers.base import LLMResponse

logger = logging.getLogger(__name__)


async def call_with_fallback(
    prompt: str,
    route: RouteChoice,
    *,
    system: str | None = None,
    temperature: float = 0.2,
) -> tuple[LLMResponse, dict[str, Any]]:
    """Try primary provider, then walk the fallback chain on failure/timeout.

    Returns (response, routing_meta) where routing_meta records whether fallback fired.
    """
    settings = get_settings()
    providers = get_providers()
    timeout = settings.provider_timeout_seconds

    attempts: list[dict[str, Any]] = []
    chain = [(route.provider, route.model), *route.fallback_chain]

    last_error: Exception | None = None
    for idx, (provider_name, model) in enumerate(chain):
        provider = providers.get(provider_name)
        if provider is None or not provider.is_available():
            attempts.append(
                {"provider": provider_name, "model": model, "status": "unavailable"}
            )
            continue
        try:
            resp = await asyncio.wait_for(
                provider.complete(
                    prompt,
                    model=model,
                    system=system,
                    temperature=temperature,
                ),
                timeout=timeout,
            )
            meta = {
                "fallback_used": idx > 0,
                "attempts": attempts
                + [{"provider": provider_name, "model": model, "status": "ok"}],
                "final_provider": provider_name,
                "final_model": model,
            }
            return resp, meta
        except Exception as exc:  # noqa: BLE001 — intentional broad catch for provider failover
            last_error = exc
            logger.warning("Provider %s/%s failed: %s", provider_name, model, exc)
            attempts.append(
                {
                    "provider": provider_name,
                    "model": model,
                    "status": "error",
                    "error": str(exc),
                }
            )

    raise RuntimeError(f"All providers failed. Last error: {last_error}. Attempts: {attempts}")
