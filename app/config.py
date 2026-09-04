"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # General
    default_provider: str = "gemini"
    db_path: str = "./data/novels.db"

    # Local model (Ollama)
    ollama_host: str = "http://localhost:11434"
    ollama_default_model: str = "gemma4:12b"

    # Online model (OpenAI-compatible)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_default_model: str = "gpt-4o-mini"

    # Online model (Anthropic / Claude)
    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-opus-4-8"

    # Gemini via the local Antigravity-compatible REST proxy
    gemini_base_url: str = "http://127.0.0.1:8045"
    gemini_api_key: str = ""
    gemini_default_model: str = "gemini-3.6-flash-high"

    # Generation tuning
    chapter_target_chars: int = 2000
    temperature: float = 0.9
    request_timeout: int = 600

    # CORS: comma-separated origins allowed to call the API (Vite dev server).
    cors_origins: str = "http://localhost:5288,http://127.0.0.1:5288"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def online_enabled(self) -> bool:
        """The online provider is usable only when an API key is configured."""
        return bool(self.openai_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
