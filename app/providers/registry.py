"""Builds providers from config and resolves them by name."""
from __future__ import annotations

from app.config import Settings, get_settings
from app.providers.base import LLMProvider, ProviderError
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_compat_provider import OpenAICompatProvider
from app.providers.gemini_provider import GeminiProvider


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(
                host=settings.ollama_host,
                default_model=settings.ollama_default_model,
            ),
            "openai": OpenAICompatProvider(
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                default_model=settings.openai_default_model,
            ),
            "anthropic": AnthropicProvider(
                api_key=settings.anthropic_api_key,
                default_model=settings.anthropic_default_model,
            ),
            "gemini": GeminiProvider(
                base_url=settings.gemini_base_url,
                api_key=settings.gemini_api_key,
                default_model=settings.gemini_default_model,
            ),
        }

    @property
    def default_name(self) -> str:
        return self._settings.default_provider

    def list_providers(self) -> list[LLMProvider]:
        """List the configured default first so new-story forms choose it."""
        default = self._providers.get(self.default_name)
        others = [provider for name, provider in self._providers.items() if name != self.default_name]
        return ([default] if default is not None else []) + others

    def get(self, name: str | None) -> LLMProvider:
        """Resolve a provider by name, falling back to the configured default."""
        key = name or self.default_name
        provider = self._providers.get(key)
        if provider is None:
            raise ProviderError(f"未知的模型提供方:{key}")
        if not provider.available:
            raise ProviderError(
                f"提供方 {key} 当前不可用(可能缺少 API Key 配置)。"
            )
        return provider


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry(get_settings())
    return _registry
