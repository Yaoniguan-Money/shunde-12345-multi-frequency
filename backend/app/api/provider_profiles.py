from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import ProviderProfileServiceDependency
from backend.app.schemas.provider_profiles import (
    ProviderProfileListResponse,
    ProviderValidationResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/provider-profiles", response_model=ProviderProfileListResponse)
async def list_provider_profiles(
    service: ProviderProfileServiceDependency,
) -> ProviderProfileListResponse:
    return ProviderProfileListResponse(items=await service.list_profiles())


@router.post(
    "/provider-profiles/{profile_id}/validate",
    response_model=ProviderValidationResponse,
    status_code=status.HTTP_200_OK,
)
async def validate_provider_profile(
    profile_id: str,
    service: ProviderProfileServiceDependency,
) -> ProviderValidationResponse:
    try:
        return await service.validate(profile_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
