from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.app.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={
            "timeout": settings.dependency_timeout_seconds,
            "command_timeout": settings.dependency_timeout_seconds,
        },
    )
