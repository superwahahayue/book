"""Provider interface and shared errors."""
from __future__ import annotations

import abc


class ProviderError(RuntimeError):
    """Raised when a provider cannot fulfil a generation request."""


class LLMProvider(abc.ABC):
    """Common interface for local and online text-generation backends."""

    #: Stable identifier used to reference this provider from a novel.
    name: str = "base"
    #: Human-friendly label for the UI.
    label: str = "Base"
    models: tuple[str, ...] = ()

    def __init__(self, default_model: str) -> None:
        self.default_model = default_model

    @property
    def available(self) -> bool:
        """Whether the provider is configured well enough to be selected."""
        return True

    def resolve_model(self, model: str | None) -> str:
        return model or self.default_model

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.9,
        timeout: int = 600,
    ) -> str:
        """Generate text for the prompt and return the model's reply."""

    @abc.abstractmethod
    def health(self) -> tuple[bool, str]:
        """Return (ok, message) describing connectivity."""
