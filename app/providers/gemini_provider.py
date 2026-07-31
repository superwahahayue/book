"""Text generation through Google's Gemini SDK and a local REST proxy."""
from __future__ import annotations

from app.providers.base import LLMProvider, ProviderError


class GeminiProvider(LLMProvider):
    name = "gemini"
    label = "Gemini (代理)"
    models = (
        "gemini-3.6-flash-high", "gpt-oss-120b-medium", "gemini-3.6-flash-tiered",
        "gemini-2.5-flash", "gemini-3.1-pro", "gemini-2.5-pro",
        "claude-opus-4-6-thinking", "gemini-3.5-flash", "gemini-3.1-flash-image",
        "gemini-2.5-flash-thinking", "claude-sonnet-4-6", "gemini-3.6-flash-low",
        "gemini-3.6-flash-medium", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite",
        "gemini-3.1-pro-high", "gemini-3-flash", "gemini-3-pro-image",
        "gemini-3.1-pro-low",
    )

    def __init__(self, base_url: str, api_key: str, default_model: str) -> None:
        super().__init__(default_model)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip() and self.base_url.strip())

    def _configure(self):
        if not self.available:
            raise ProviderError("未配置 Gemini API Key 或代理地址，请检查 GEMINI_API_KEY 和 GEMINI_BASE_URL。")
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("未安装 google-generativeai，请先 pip install google-generativeai。") from exc
        genai.configure(
            api_key=self.api_key,
            transport="rest",
            client_options={"api_endpoint": self.base_url},
        )
        return genai

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.9,
        timeout: int = 600,
    ) -> str:
        del timeout
        model_name = self.resolve_model(model)
        try:
            genai = self._configure()
            kwargs = {"model_name": model_name}
            if system:
                kwargs["system_instruction"] = system
            client = genai.GenerativeModel(**kwargs)
            response = client.generate_content(
                prompt,
                generation_config={"temperature": temperature},
            )
            content = getattr(response, "text", "") or ""
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"调用 Gemini 失败({self.base_url}，模型 {model_name}): {exc}") from exc
        if not content.strip():
            raise ProviderError("Gemini 返回了空内容。")
        return content.strip()

    def health(self) -> tuple[bool, str]:
        if not self.available:
            return False, "Gemini 未配置 API Key 或代理地址。"
        return True, f"Gemini 代理已配置: {self.base_url}"
