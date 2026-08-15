"""Audited handling and human-correction commands for event clusters."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from backend.app.api.dependencies import (
    ExporterDependency,
    ReviewServiceDependency,
)
from backend.app.application.services.review import ReviewCommandError
from backend.app.domain.catalog import HandlingRecordView, HumanCorrectionView
from backend.app.domain.types import EventClusterId, ExportRequest
from backend.app.schemas.catalog import (
    HandlingHistoryResponse,
    HandlingRecordCreate,
    HandlingRecordResponse,
    HumanCorrectionCreate,
    HumanCorrectionHistoryResponse,
    HumanCorrectionResponse,
)

router = APIRouter(tags=["review"])


@router.post(
    "/multi-frequency-events/{cluster_id}/handling-records",
    response_model=HandlingRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_handling_record(
    cluster_id: UUID,
    request: HandlingRecordCreate,
    service: ReviewServiceDependency,
) -> HandlingRecordResponse:
    try:
        record = await service.add_handling_record(
            cluster_id,
            new_status=request.new_status,
            actor_id=request.actor_id,
            description=request.description,
            result=request.result,
            attachment_references=tuple(request.attachment_references),
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _handling_record_response(record)


@router.get(
    "/multi-frequency-events/{cluster_id}/handling-records",
    response_model=HandlingHistoryResponse,
)
async def list_handling_records(
    cluster_id: UUID, service: ReviewServiceDependency
) -> HandlingHistoryResponse:
    try:
        records = await service.list_handling_records(cluster_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return HandlingHistoryResponse(items=[_handling_record_response(item) for item in records])


@router.post(
    "/multi-frequency-events/{cluster_id}/corrections",
    response_model=HumanCorrectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_correction(
    cluster_id: UUID,
    request: HumanCorrectionCreate,
    service: ReviewServiceDependency,
) -> HumanCorrectionResponse:
    try:
        correction = await service.add_correction(
            cluster_id,
            correction_type=request.correction_type,
            event_instance_id=request.event_instance_id,
            actor_id=request.actor_id,
            reason=request.reason,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ReviewCommandError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _correction_response(correction)


@router.get(
    "/multi-frequency-events/{cluster_id}/corrections",
    response_model=HumanCorrectionHistoryResponse,
)
async def list_corrections(
    cluster_id: UUID, service: ReviewServiceDependency
) -> HumanCorrectionHistoryResponse:
    try:
        corrections = await service.list_corrections(cluster_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return HumanCorrectionHistoryResponse(
        items=[_correction_response(item) for item in corrections]
    )


@router.get("/multi-frequency-events/export.csv")
async def export_clusters(
    exporter: ExporterDependency,
    cluster_id: UUID | None = None,
) -> Response:
    try:
        artifact = await exporter.export(
            ExportRequest(
                format="csv",
                event_cluster_ids=(EventClusterId(cluster_id),) if cluster_id else (),
            )
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


def _handling_record_response(record: HandlingRecordView) -> HandlingRecordResponse:
    return HandlingRecordResponse(
        record_id=record.record_id,
        cluster_id=record.cluster_id,
        previous_status=record.previous_status,
        new_status=record.new_status,
        actor_id=record.actor_id,
        description=record.description,
        result=record.result,
        attachment_references=list(record.attachment_references),
        created_at=record.created_at,
    )


def _correction_response(correction: HumanCorrectionView) -> HumanCorrectionResponse:
    return HumanCorrectionResponse(
        correction_id=correction.correction_id,
        cluster_id=correction.cluster_id,
        work_order_id=correction.work_order_id,
        correction_type=correction.correction_type,
        actor_id=correction.actor_id,
        reason=correction.reason,
        payload=correction.payload,
        supersedes_correction_id=correction.supersedes_correction_id,
        created_at=correction.created_at,
    )
