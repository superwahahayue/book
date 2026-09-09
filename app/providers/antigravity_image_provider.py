"""Image generation through Antigravity's OpenAI-compatible image endpoint."""
from __future__ import annotations

import base64

from app.providers.base import ProviderError


class AntigravityImageProvider:
    """Small binary-image client kept separate from the text LLM abstraction."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key.strip())

    @property
    def endpoint(self) -> str:
        root = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        return f"{root}/v1/images/generations"

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        size: str,
        quality: str,
        timeout: int,
    ) -> bytes:
        if not self.available:
            raise ProviderError("未配置 Gemini 图片代理，请检查 GEMINI_BASE_URL 和 GEMINI_API_KEY。")
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - deployment dependency failure
            raise ProviderError("未安装 httpx，无法调用图片生成服务。") from exc

        try:
            response = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "quality": quality,
                    "n": 1,
                    "response_format": "b64_json",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:800].strip()
            raise ProviderError(
                f"图片生成服务返回 HTTP {exc.response.status_code}: {detail or '未知错误'}"
            ) from exc
        except Exception as exc:
            raise ProviderError(f"调用图片生成服务失败({self.endpoint}): {exc}") from exc

        try:
            item = (payload.get("data") or [])[0]
            encoded = item.get("b64_json")
            if not encoded:
                url = item.get("url") or ""
                if isinstance(url, str) and url.startswith("data:image") and "," in url:
                    encoded = url.split(",", 1)[1]
            if not isinstance(encoded, str) or not encoded.strip():
                raise ValueError("响应中没有 b64_json 图片数据")
            return base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ProviderError(f"图片生成服务返回格式无效: {exc}") from exc
