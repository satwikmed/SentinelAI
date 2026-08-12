"""Provider registry."""

from __future__ import annotations

from app.config import get_settings
from app.routing.providers.anthropic_provider import AnthropicProvider
from app.routing.providers.base import BaseProvider
from app.routing.providers.gemini_provider import GeminiProvider
from app.routing.providers.mock import MockProvider
from app.routing.providers.openai_provider import OpenAIProvider


def get_providers() -> dict[str, BaseProvider]:
    settings = get_settings()
    providers: dict[str, BaseProvider] = {
        "openai": OpenAIProvider(),
        "anthropic": AnthropicProvider(),
        "gemini": GeminiProvider(),
        "mock": MockProvider(),
    }
    if settings.demo_mode:
        # Keep mock available; live ones stay registered but unavailable
        pass
    return providers


def available_providers() -> list[str]:
    return [name for name, p in get_providers().items() if p.is_available()]
