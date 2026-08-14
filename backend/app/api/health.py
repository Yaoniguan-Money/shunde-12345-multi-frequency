from fastapi import APIRouter, Response, status

from backend.app.api.dependencies import HealthHandlerDependency, HealthProbeDependency
from backend.app.schemas.health import DependenciesResponse, LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    return LivenessResponse()


@router.get("/ready", response_model=ReadinessResponse)
async def ready(
    response: Response,
    probe: HealthProbeDependency,
    handler: HealthHandlerDependency,
) -> ReadinessResponse:
    result = handler.readiness(await probe.snapshot())
    if result.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/dependencies", response_model=DependenciesResponse)
async def dependencies(
    probe: HealthProbeDependency,
    handler: HealthHandlerDependency,
) -> DependenciesResponse:
    return handler.dependencies(await probe.snapshot())
