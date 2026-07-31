"""Online generation via an OpenAI-compatible API (OpenAI, DeepSeek, etc.)."""
from __future__ import annotations

from app.providers.base import LLMProvider, ProviderError


class OpenAICompatProvider(LLMProvider):
    name = "openai"
    label = "线上 API (OpenAI 兼容)"

    def __init__(self, base_url: str, api_key: str, default_model: str) -> None:
        super().__init__(default_model)
        self.base_url = base_url
        self.api_key = api_key

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())

    def _client(self, timeout: int):
        if not self.available:
            raise ProviderError("未配置线上 API Key(请在 .env 设置 OPENAI_API_KEY)。")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ProviderError("未安装 openai Python 包,请先 pip install openai") from exc
        return OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=timeout)

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.9,
        timeout: int = 600,
    ) -> str:
        model = self.resolve_model(model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            client = self._client(timeout)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"调用线上 API 失败({self.base_url}, 模型 {model}):{exc}"
            ) from exc

        content = resp.choices[0].message.content if resp.choices else ""
        if not content or not content.strip():
            raise ProviderError("线上 API 返回了空内容。")
        return content.strip()

    def health(self) -> tuple[bool, str]:
        if not self.available:
            return False, "线上 API 未配置 API Key。"
        return True, f"线上 API 已配置:{self.base_url}"
