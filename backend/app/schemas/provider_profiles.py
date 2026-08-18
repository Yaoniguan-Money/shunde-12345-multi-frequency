from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ProviderDeploymentKind = Literal["local", "cloud"]
ProviderValidationStatus = Literal["configured", "validated", "unavailable", "validation_failed"]


class ProviderProfileResponse(BaseModel):
    profile_id: str
    deployment_kind: ProviderDeploymentKind
    display_name: str
    configured: bool
    validation_status: ProviderValidationStatus
    last_validated_at: datetime | None = None
    model_display_name: str | None = None
    service_description: str
    configuration_version: str


class ProviderProfileListResponse(BaseModel):
    items: list[ProviderProfileResponse]


class ProviderValidationStage(BaseModel):
    name: str
    status: Literal["passed", "failed"]
    latency_ms: int
    model_id: str | None = None
    error: str | None = None


class ProviderValidationResponse(BaseModel):
    profile: ProviderProfileResponse
    stages: list[ProviderValidationStage]
