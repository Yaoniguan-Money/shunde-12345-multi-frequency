from asyncio import gather
from typing import Final

import httpx
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.config import Settings
from backend.app.schemas.health import DependencyState, DependencyStatus, HealthSnapshot

_REDACTED_ERROR: Final = "dependency check failed"


class _OpenAPIInfo(BaseModel):
    version: str


class _OpenAPIDocument(BaseModel):
    info: _OpenAPIInfo


class _ModelDescriptor(BaseModel):
    id: str


class _ModelList(BaseModel):
    data: list[_ModelDescriptor]


class DependencyHealthProbe:
    def __init__(self, engine: AsyncEngine, settings: Settings) -> None:
        self._engine = engine
        self._settings = settings

    async def database(self) -> DependencyStatus:
        try:
            async with self._engine.connect() as connection:
                version = (await connection.execute(text("SELECT version()"))).scalar_one()
            return DependencyStatus(state=DependencyState.UP, version=str(version).split(",")[0])
        except (OSError, SQLAlchemyError, TimeoutError):
            return DependencyStatus(state=DependencyState.DOWN, detail=_REDACTED_ERROR)

    async def gazetteer(self) -> DependencyStatus:
        return await self._http_openapi(str(self._settings.gazetteer_api_base_url))

    async def local_model(self) -> DependencyStatus:
        if self._settings.model_api_base_url is None:
            return DependencyStatus(state=DependencyState.NOT_CONFIGURED)
        return await self._http_model(str(self._settings.model_api_base_url))

    async def snapshot(self) -> HealthSnapshot:
        database, gazetteer, local_model = await gather(
            self.database(), self.gazetteer(), self.local_model()
        )
        return HealthSnapshot(
            database=database,
            gazetteer=gazetteer,
            local_model=local_model,
        )

    async def _http_openapi(self, base_url: str) -> DependencyStatus:
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.dependency_timeout_seconds
            ) as client:
                response = await client.get(f"{base_url.rstrip('/')}/openapi.json")
                response.raise_for_status()
                document = _OpenAPIDocument.model_validate(response.json())
            return DependencyStatus(
                state=DependencyState.UP,
                version=document.info.version,
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return DependencyStatus(state=DependencyState.DOWN, detail=_REDACTED_ERROR)

    async def _http_model(self, base_url: str) -> DependencyStatus:
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.dependency_timeout_seconds
            ) as client:
                response = await client.get(f"{base_url.rstrip('/')}/v1/models")
                response.raise_for_status()
                document = _ModelList.model_validate(response.json())
            version = document.data[0].id if document.data else "no_models"
            return DependencyStatus(state=DependencyState.UP, version=version)
        except (httpx.HTTPError, ValueError, TypeError, IndexError):
            return DependencyStatus(state=DependencyState.DOWN, detail=_REDACTED_ERROR)
