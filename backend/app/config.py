from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.domain.types import ProviderMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SHUNDE_",
        extra="ignore",
    )

    app_name: str = "顺德 12345 多频工单智能研判"
    environment: str = "development"
    database_url: SecretStr = SecretStr("postgresql+asyncpg://shunde:shunde@127.0.0.1:5432/shunde")
    gazetteer_api_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8000")
    model_api_base_url: AnyHttpUrl | None = None
    llm_model_id: str | None = None
    embedding_api_base_url: AnyHttpUrl | None = None
    embedding_model_id: str | None = None
    ai_provider_mode: ProviderMode = ProviderMode.LOCAL
    ai_local_llm_base_url: AnyHttpUrl | None = None
    ai_local_llm_model_id: str | None = None
    ai_local_embedding_base_url: AnyHttpUrl | None = None
    ai_local_embedding_model_id: str | None = None
    ai_local_embedding_protocol: str = "ollama"
    ai_remote_base_url: AnyHttpUrl | None = None
    ai_remote_llm_model_id: str | None = None
    ai_remote_embedding_model_id: str | None = None
    ai_remote_api_key: SecretStr | None = None
    ai_hybrid_policy: str = "explicit-route-local-default"
    model_timeout_seconds: float = 120.0
    # 默认 8 并发：qwen-plus/dashscope 支持并发调用，单次 LLM 推断 30-60 秒，
    # 串行（concurrency=1）会导致 100 张工单研判 50-100 分钟。8 并发理论 8 倍提速，
    # 不改 schema/pipeline/prompt，正确性不变。若触发 429 限流可回调到 4。
    model_concurrency: int = 8
    analysis_pipeline_version: str = "understanding.v2"
    analysis_schema_version: str = "understanding.v2"
    dependency_timeout_seconds: float = 2.0
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    runtime_dir: Path = Path("./data/runtime")
    attachment_max_bytes: int = 10 * 1024 * 1024
    gazetteer_home: Path | None = None
    gazetteer_database_path: Path | None = None
    gazetteer_snapshot_path: Path = Path("./data/runtime/gazetteer.snapshot.json")


@lru_cache
def get_settings() -> Settings:
    return Settings()
