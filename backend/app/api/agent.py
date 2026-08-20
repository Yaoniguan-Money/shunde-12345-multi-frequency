"""HTTP boundary for the intelligent assessment assistant."""

from typing import cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from backend.app.api.dependencies import AgentOrchestratorDependency
from backend.app.application.services.agent import AgentCommandError
from backend.app.schemas.agent import (
    AgentExportRequest,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentQueryResultsRequest,
    AgentQueryResultsResponse,
    BatchActionExecuteRequest,
    BatchActionExecuteResponse,
    BatchActionPayload,
    BatchActionPreviewResponse,
    BatchActionType,
    DynamicDashboardRequest,
    DynamicDashboardResponse,
    WorksetCreateRequest,
    WorksetListResponse,
    WorksetResponse,
    WorksetWorkspaceResponse,
)

router = APIRouter(tags=["agent"])


@router.post("/agent/query", response_model=AgentQueryResponse)
async def query_agent(
    request: AgentQueryRequest, service: AgentOrchestratorDependency
) -> AgentQueryResponse:
    return await service.query(request)


@router.post("/agent/query/results", response_model=AgentQueryResultsResponse)
async def query_agent_results(
    request: AgentQueryResultsRequest, service: AgentOrchestratorDependency
) -> AgentQueryResultsResponse:
    return await service.query_results(request)


@router.post("/agent/export.xlsx")
async def export_agent_xlsx(
    request: AgentExportRequest, service: AgentOrchestratorDependency
) -> Response:
    try:
        filename, content = await service.export_xlsx(request)
    except AgentCommandError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/worksets", response_model=WorksetResponse, status_code=status.HTTP_201_CREATED)
async def create_workset(
    request: WorksetCreateRequest, service: AgentOrchestratorDependency
) -> WorksetResponse:
    return await service.create_workset(request)


@router.get("/worksets/{workset_id}", response_model=WorksetResponse)
async def get_workset(workset_id: UUID, service: AgentOrchestratorDependency) -> WorksetResponse:
    result = await service.get_workset(workset_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workset not found")
    return result


@router.get("/worksets", response_model=WorksetListResponse)
async def list_worksets(service: AgentOrchestratorDependency) -> WorksetListResponse:
    return await service.list_worksets()


@router.get("/worksets/{workset_id}/workspace", response_model=WorksetWorkspaceResponse)
async def get_workset_workspace(
    workset_id: UUID, service: AgentOrchestratorDependency
) -> WorksetWorkspaceResponse:
    result = await service.workspace(workset_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workset not found")
    return result


@router.post("/worksets/{workset_id}/actions/preview", response_model=BatchActionPreviewResponse)
async def preview_workset_action(
    workset_id: UUID, request: BatchActionPayload, service: AgentOrchestratorDependency
) -> BatchActionPreviewResponse:
    try:
        return await service.preview_action(workset_id, request)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AgentCommandError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@router.post("/worksets/{workset_id}/actions/execute", response_model=BatchActionExecuteResponse)
async def execute_workset_action(
    workset_id: UUID,
    request: BatchActionExecuteRequest,
    service: AgentOrchestratorDependency,
) -> BatchActionExecuteResponse:
    try:
        action_type, count, csv_content = await service.execute_action(
            workset_id, request.preview_id, request.actor_id
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return BatchActionExecuteResponse(
        preview_id=request.preview_id,
        action_type=cast(BatchActionType, action_type),
        executed_work_order_count=count,
        audit_action="agent.workset_batch_action_executed",
        csv_content=csv_content,
    )


@router.post("/agent/dashboard", response_model=DynamicDashboardResponse)
async def generate_dashboard(
    request: DynamicDashboardRequest, service: AgentOrchestratorDependency
) -> DynamicDashboardResponse:
    return await service.dashboard(
        title=request.title,
        work_order_ids=tuple(request.work_order_ids),
        cluster_ids=tuple(request.cluster_ids),
        compiled_query=request.compiled_query,
        drilldown=request.drilldown,
    )
