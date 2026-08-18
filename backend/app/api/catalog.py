"""Read-only demo catalog endpoints."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.api.dependencies import CatalogServiceDependency
from backend.app.domain.catalog import (
    CatalogEvent,
    ClusterDetail,
    ClusterSummary,
    EventDetail,
    HandlingRecordView,
    HumanCorrectionView,
    RemovedClusterMember,
    WorkOrderDetail,
    WorkOrderSummary,
)
from backend.app.domain.types import VersionTrace
from backend.app.schemas.catalog import (
    AnalysisState,
    ClusterDetailResponse,
    ClusterListResponse,
    ClusterReferenceResponse,
    ClusterSummaryResponse,
    EntityReferenceResponse,
    EventDetailResponse,
    EventListResponse,
    EventResponse,
    HandlingRecordResponse,
    HumanCorrectionResponse,
    MatchEdgeResponse,
    RemovedMemberResponse,
    ReviewStatus,
    TraceResponse,
    WorkOrderDetailResponse,
    WorkOrderFacetsResponse,
    WorkOrderListResponse,
    WorkOrderOverviewResponse,
    WorkOrderSummaryResponse,
)

router = APIRouter(tags=["catalog"])


@router.get("/work-orders/overview", response_model=WorkOrderOverviewResponse)
async def work_order_overview(
    service: CatalogServiceDependency,
    query: str | None = Query(default=None, min_length=1, max_length=128),
    analysis_state: str | None = Query(default=None, max_length=32),
    event_type: str | None = Query(default=None, max_length=128),
    title_tag: str | None = Query(default=None, max_length=64),
) -> WorkOrderOverviewResponse:
    overview = await service.get_overview(
        query=query,
        analysis_state=analysis_state,
        event_type=event_type,
        title_tag=title_tag,
    )
    return WorkOrderOverviewResponse(
        total_work_orders=overview.total_work_orders,
        total_event_instances=overview.total_event_instances,
        analysis_state_counts=overview.analysis_state_counts,
        multi_frequency_work_order_count=overview.multi_frequency_work_order_count,
        high_frequency_cluster_count=overview.high_frequency_cluster_count,
    )


@router.get("/work-orders/facets", response_model=WorkOrderFacetsResponse)
async def work_order_facets(
    service: CatalogServiceDependency,
) -> WorkOrderFacetsResponse:
    facets = await service.get_facets()
    return WorkOrderFacetsResponse(
        classification_nodes=facets.classification_nodes,
        source_tags=facets.source_tags,
    )


@router.get("/work-orders", response_model=WorkOrderListResponse)
async def list_work_orders(
    service: CatalogServiceDependency,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    query: str | None = Query(default=None, min_length=1, max_length=128),
    analysis_state: str | None = Query(default=None, max_length=32),
    event_type: str | None = Query(default=None, max_length=128),
    title_tag: str | None = Query(default=None, max_length=64),
) -> WorkOrderListResponse:
    items, total = await service.list_work_orders(
        offset=offset,
        limit=limit,
        query=query,
        analysis_state=analysis_state,
        event_type=event_type,
        title_tag=title_tag,
    )
    return WorkOrderListResponse(
        items=[_work_order_summary(item) for item in items],
        offset=offset,
        limit=limit,
        total=total,
    )


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderDetailResponse)
async def get_work_order(
    work_order_id: UUID, service: CatalogServiceDependency
) -> WorkOrderDetailResponse:
    detail = await service.get_work_order(work_order_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="work order not found")
    return _work_order_detail(detail)


@router.get("/events", response_model=EventListResponse)
async def list_events(
    service: CatalogServiceDependency,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    pipeline_version: str | None = Query(default="understanding.v3", max_length=64),
    work_order_id: UUID | None = None,
) -> EventListResponse:
    items, total = await service.list_events(
        offset=offset,
        limit=limit,
        pipeline_version=pipeline_version,
        work_order_id=work_order_id,
    )
    occurrence_dated_total, occurrence_unknown_total = await service.event_occurrence_counts(
        pipeline_version
    )
    return EventListResponse(
        items=[_event_detail(item) for item in items],
        offset=offset,
        limit=limit,
        total=total,
        occurrence_dated_total=occurrence_dated_total,
        occurrence_unknown_total=occurrence_unknown_total,
    )


@router.get("/events/{event_id}", response_model=EventDetailResponse)
async def get_event(event_id: UUID, service: CatalogServiceDependency) -> EventDetailResponse:
    detail = await service.get_event(event_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")
    return _event_detail(detail)


@router.get("/multi-frequency-events", response_model=ClusterListResponse)
async def list_clusters(
    service: CatalogServiceDependency,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ClusterListResponse:
    items, total = await service.list_clusters(offset=offset, limit=limit)
    return ClusterListResponse(
        items=[_cluster_summary(item) for item in items],
        offset=offset,
        limit=limit,
        total=total,
    )


@router.get("/multi-frequency-events/{cluster_id}", response_model=ClusterDetailResponse)
async def get_cluster(cluster_id: UUID, service: CatalogServiceDependency) -> ClusterDetailResponse:
    detail = await service.get_cluster(cluster_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="multi-frequency event not found"
        )
    return _cluster_detail(detail)


def _trace(trace: VersionTrace) -> TraceResponse:
    return TraceResponse(
        provider=trace.provider,
        model_id=trace.model_id,
        model_config_hash=trace.model_config_hash,
        schema_version=trace.schema_version,
        knowledge_snapshot_id=trace.knowledge_snapshot_id,
        pipeline_version=trace.pipeline_version,
    )


def _work_order_summary(summary: WorkOrderSummary) -> WorkOrderSummaryResponse:
    return WorkOrderSummaryResponse(
        work_order_id=summary.work_order_id,
        external_work_order_number=summary.external_work_order_number,
        source_row_number=summary.source_row_number,
        raw_title=summary.raw_title,
        created_at=summary.created_at,
        event_count=summary.event_count,
        cluster_count=summary.cluster_count,
        analysis_state=cast(AnalysisState, summary.analysis_state),
        title_tags=list(summary.title_tags),
        is_urgent=summary.is_urgent,
    )


def _event(event: CatalogEvent) -> EventResponse:
    return EventResponse(
        event_id=event.event_id,
        work_order_id=event.work_order_id,
        ordinal=event.ordinal,
        event_type=event.event_type,
        behavior=event.behavior,
        normalized_summary=event.normalized_summary,
        entities=[
            EntityReferenceResponse(
                entity_id=entity.entity_id,
                standard_name=entity.standard_name,
                entity_type=entity.entity_type,
                resolution_state=entity.resolution_state,
            )
            for entity in event.entities
        ],
        location_signals=list(event.location_signals),
        time_signals=list(event.time_signals),
        evidence=list(event.evidence),
        trace=_trace(event.trace),
        occurrence_date=event.occurrence_date,
        classification_node_id=event.classification_node_id,
        classification_source=event.classification_source,
        classification_confidence=event.classification_confidence,
        classification_ambiguity=event.classification_ambiguity,
        current_problem=event.current_problem,
        current_request=event.current_request,
        history_context=event.history_context,
        evidence_spans=list(event.evidence_spans),
        unknown_fields=list(event.unknown_fields),
    )


def _work_order_detail(detail: WorkOrderDetail) -> WorkOrderDetailResponse:
    return WorkOrderDetailResponse(
        summary=_work_order_summary(detail.summary),
        import_batch_id=detail.import_batch_id,
        raw_content=detail.raw_content,
        raw_fields=detail.raw_fields,
        events=[_event(item) for item in detail.events],
        cluster_refs=[
            ClusterReferenceResponse(
                cluster_id=item.cluster_id,
                cluster_name=item.cluster_name,
                review_status=item.review_status,
                handling_status=item.handling_status,
            )
            for item in detail.cluster_refs
        ],
    )


def _event_detail(detail: EventDetail) -> EventDetailResponse:
    return EventDetailResponse(
        event=_event(detail.event),
        work_order=_work_order_summary(detail.work_order),
        raw_title=detail.raw_title,
        raw_content=detail.raw_content,
    )


def _cluster_summary(summary: ClusterSummary) -> ClusterSummaryResponse:
    return ClusterSummaryResponse(
        cluster_id=summary.cluster_id,
        name=summary.name,
        status=summary.status,
        confidence=summary.confidence,
        handling_status=summary.handling_status,
        member_count=summary.member_count,
        work_order_count=summary.work_order_count,
        event_count=summary.event_count,
        evidence=summary.evidence,
        trace=_trace(summary.trace) if summary.trace else None,
        review_status=cast(ReviewStatus, summary.review_status),
        is_multi_frequency=summary.is_multi_frequency,
        is_high_frequency=summary.is_high_frequency,
        frequency_window_days=summary.frequency_window_days,
        frequency_work_order_count=summary.frequency_work_order_count,
    )


def _cluster_detail(detail: ClusterDetail) -> ClusterDetailResponse:
    return ClusterDetailResponse(
        summary=_cluster_summary(detail.summary),
        members=[_event_detail(member) for member in detail.members],
        work_orders=[_work_order_detail(work_order) for work_order in detail.work_orders],
        edges=[
            MatchEdgeResponse(
                left_event_id=edge.left_event_id,
                right_event_id=edge.right_event_id,
                same_event=edge.same_event,
                confidence=edge.confidence,
                evidence=edge.evidence,
                trace=_trace(edge.trace),
            )
            for edge in detail.edges
        ],
        handling_history=[_handling_record(item) for item in detail.handling_history],
        human_corrections=[_correction(item) for item in detail.human_corrections],
        removed_members=[_removed_member(item) for item in detail.removed_members],
    )


def _removed_member(item: RemovedClusterMember) -> RemovedMemberResponse:
    event = item.event
    return RemovedMemberResponse(
        event=_event(event.event) if event else None,
        event_instance_id=item.event_instance_id,
        work_order=_work_order_summary(event.work_order) if event else None,
        raw_title=event.raw_title if event else None,
        raw_content=event.raw_content if event else None,
        correction_id=item.correction_id,
        actor_id=item.actor_id,
        reason=item.reason,
        removed_at=item.removed_at,
        can_restore=item.can_restore,
    )


def _handling_record(record: HandlingRecordView) -> HandlingRecordResponse:
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


def _correction(correction: HumanCorrectionView) -> HumanCorrectionResponse:
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
