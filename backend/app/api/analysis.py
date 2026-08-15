"""HTTP endpoints for bounded, asynchronous Demo AI analysis."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import AnalysisJobServiceDependency
from backend.app.domain.analysis_jobs import AnalysisJobView
from backend.app.schemas.analysis import (
    AnalysisJobCreate,
    AnalysisJobResponse,
    AnalysisJobStage,
    AnalysisJobStatus,
    AnalysisSelectionMode,
)
from backend.app.schemas.catalog import TraceResponse

router = APIRouter(tags=["analysis"])


@router.post(
    "/analysis-jobs",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_analysis_job(
    request: AnalysisJobCreate,
    service: AnalysisJobServiceDependency,
) -> AnalysisJobResponse:
    try:
        view = await service.submit(
            request.import_batch_id, request.max_work_orders, request.selection_mode
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _response(view)


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(
    job_id: UUID,
    service: AnalysisJobServiceDependency,
) -> AnalysisJobResponse:
    view = await service.get(job_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="analysis job not found")
    return _response(view)


def _response(view: AnalysisJobView) -> AnalysisJobResponse:
    trace = view.trace
    return AnalysisJobResponse(
        job_id=view.job_id,
        status=_status(view.status),
        current_stage=_stage(view.current_stage),
        total_rows=view.total_rows,
        selected_rows=view.selected_rows,
        processed_rows=view.processed_rows,
        event_count=view.event_count,
        match_edge_count=view.match_edge_count,
        cluster_count=view.cluster_count,
        started_at=view.started_at,
        finished_at=view.finished_at,
        error=view.error,
        trace=(
            TraceResponse(
                provider=trace.provider,
                model_id=trace.model_id,
                model_config_hash=trace.model_config_hash,
                schema_version=trace.schema_version,
                knowledge_snapshot_id=trace.knowledge_snapshot_id,
                pipeline_version=trace.pipeline_version,
            )
            if trace is not None
            else None
        ),
        selection_mode=cast(AnalysisSelectionMode, view.selection_mode),
    )


def _status(value: str) -> AnalysisJobStatus:
    if value in {"queued", "running", "completed", "failed"}:
        return cast(AnalysisJobStatus, value)
    return "failed"


def _stage(value: str) -> AnalysisJobStage:
    aliases = {"segment": "understanding", "embed": "embedding"}
    normalized = aliases.get(value, value)
    if normalized in {
        "queued",
        "understanding",
        "embedding",
        "retrieval",
        "matching",
        "clustering",
        "completed",
    }:
        return cast(AnalysisJobStage, normalized)
    return "queued"
