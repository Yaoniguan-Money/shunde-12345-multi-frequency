from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import ResolverDependency
from backend.app.schemas.entities import (
    EntityCandidateResponse,
    EntityCandidateSetResponse,
    EntityResolveRequest,
    EntityResolveResponse,
)

router = APIRouter(prefix="/entities", tags=["entities"])


@router.post("/resolve", response_model=EntityResolveResponse)
async def resolve(
    request: EntityResolveRequest, resolver: ResolverDependency
) -> EntityResolveResponse:
    if resolver is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="地名运行时快照未配置；请设置 SHUNDE_GAZETTEER_HOME",
        )
    results = await resolver.resolve_many(tuple(request.mentions))
    return EntityResolveResponse(
        results=[
            EntityCandidateSetResponse(
                mention=result.mention,
                state=result.state.value,
                candidates=[
                    EntityCandidateResponse(
                        entity_id=candidate.entity.entity_id,
                        standard_name=candidate.entity.standard_name,
                        entity_type=candidate.entity.entity_type,
                        confidence=candidate.confidence,
                        evidence=list(candidate.evidence),
                    )
                    for candidate in result.candidates
                ],
            )
            for result in results
        ]
    )
