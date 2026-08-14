from uuid import UUID

from pydantic import BaseModel, Field


class EntityResolveRequest(BaseModel):
    mentions: list[str] = Field(min_length=1, max_length=1000)


class EntityCandidateResponse(BaseModel):
    entity_id: UUID
    standard_name: str
    entity_type: str
    confidence: float
    evidence: list[str]


class EntityCandidateSetResponse(BaseModel):
    mention: str
    state: str
    candidates: list[EntityCandidateResponse]


class EntityResolveResponse(BaseModel):
    results: list[EntityCandidateSetResponse]
