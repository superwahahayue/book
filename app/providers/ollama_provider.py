"""Local generation via an Ollama server."""
from __future__ import annotations

from app.providers.base import LLMProvider, ProviderError


class OllamaProvider(LLMProvider):
    name = "ollama"
    label = "本地 Ollama"

    def __init__(self, host: str, default_model: str) -> None:
        super().__init__(default_model)
        self.host = host

    def _client(self):
        try:
            from ollama import Client
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ProviderError("未安装 ollama Python 包,请先 pip install ollama") from exc
        return Client(host=self.host)

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
            client = self._client()
            resp = client.chat(
                model=model,
                messages=messages,
                options={"temperature": temperature},
            )
        except Exception as exc:  # ollama raises various connection/runtime errors
            raise ProviderError(
                f"调用本地 Ollama 失败({self.host}, 模型 {model}):{exc}。"
                f"请确认 Ollama 已启动且已 `ollama pull {model}`。"
            ) from exc

        content = (resp.get("message") or {}).get("content", "")
        if not content.strip():
            raise ProviderError("Ollama 返回了空内容。")
        return content.strip()

    def health(self) -> tuple[bool, str]:
        try:
            self._client().list()
            return True, f"Ollama 可用:{self.host}"
        except Exception as exc:
            return False, f"无法连接 Ollama({self.host}):{exc}"
