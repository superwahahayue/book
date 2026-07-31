"""Online generation via Anthropic's native API (Claude models)."""
from __future__ import annotations

from app.providers.base import LLMProvider, ProviderError


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    label = "Claude API (Anthropic)"

    def __init__(self, api_key: str, default_model: str) -> None:
        super().__init__(default_model)
        self.api_key = api_key

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())

    def _client(self, timeout: int):
        if not self.available:
            raise ProviderError("未配置 Anthropic API Key(请在 .env 设置 ANTHROPIC_API_KEY)。")
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError("未安装 anthropic Python 包,请先 pip install anthropic") from exc
        return anthropic.Anthropic(api_key=self.api_key, timeout=timeout)

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
        try:
            client = self._client(timeout)
            kwargs: dict = dict(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            if system:
                kwargs["system"] = system
            resp = client.messages.create(**kwargs)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"调用 Claude API 失败(模型 {model}):{exc}") from exc

        content = resp.content[0].text if resp.content else ""
        if not content or not content.strip():
            raise ProviderError("Claude API 返回了空内容。")
        return content.strip()

    def health(self) -> tuple[bool, str]:
        if not self.available:
            return False, "Claude API 未配置 API Key。"
        try:
            client = self._client(timeout=15)
            client.models.retrieve(self.default_model)
            return True, f"Claude API 已连接,模型:{self.default_model}"
        except ProviderError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"Claude API 连通性检查失败:{exc}"
