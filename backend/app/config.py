from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    model_timeout_seconds: float = 120.0
    model_concurrency: int = 1
    analysis_pipeline_version: str = "understanding.v1"
    analysis_schema_version: str = "understanding.v1"
    dependency_timeout_seconds: float = 2.0
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    runtime_dir: Path = Path("./data/runtime")
    gazetteer_home: Path | None = None
    gazetteer_database_path: Path | None = None
    gazetteer_snapshot_path: Path = Path("./data/runtime/gazetteer.snapshot.json")


@lru_cache
def get_settings() -> Settings:
    return Settings()
