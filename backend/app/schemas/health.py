from enum import StrEnum

from pydantic import BaseModel


class DependencyState(StrEnum):
    UP = "up"
    DOWN = "down"
    NOT_CONFIGURED = "not_configured"


class DependencyStatus(BaseModel):
    state: DependencyState
    version: str | None = None
    detail: str | None = None


class LivenessResponse(BaseModel):
    status: str = "alive"


class ReadinessResponse(BaseModel):
    status: str
    database: DependencyStatus


class DependenciesResponse(BaseModel):
    status: str
    database: DependencyStatus
    gazetteer: DependencyStatus
    local_model: DependencyStatus


class HealthSnapshot(BaseModel):
    database: DependencyStatus
    gazetteer: DependencyStatus
    local_model: DependencyStatus
