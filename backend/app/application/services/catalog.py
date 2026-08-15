"""Application service for read-only demo catalog projections."""

from uuid import UUID

from backend.app.domain.catalog import (
    ClusterDetail,
    ClusterSummary,
    EventDetail,
    WorkOrderDetail,
    WorkOrderSummary,
)
from backend.app.domain.ports.catalog import CatalogRepository


class CatalogService:
    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    async def list_work_orders(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None,
        analysis_state: str | None = None,
        event_type: str | None = None,
        title_tag: str | None = None,
    ) -> tuple[tuple[WorkOrderSummary, ...], int]:
        return await self._repository.list_work_orders(
            offset=offset,
            limit=limit,
            query=query,
            analysis_state=analysis_state,
            event_type=event_type,
            title_tag=title_tag,
        )

    async def get_work_order(self, work_order_id: UUID) -> WorkOrderDetail | None:
        return await self._repository.get_work_order(work_order_id)

    async def list_events(
        self,
        *,
        offset: int,
        limit: int,
        pipeline_version: str | None,
        work_order_id: UUID | None,
    ) -> tuple[tuple[EventDetail, ...], int]:
        return await self._repository.list_events(
            offset=offset,
            limit=limit,
            pipeline_version=pipeline_version,
            work_order_id=work_order_id,
        )

    async def get_event(self, event_id: UUID) -> EventDetail | None:
        return await self._repository.get_event(event_id)

    async def event_occurrence_counts(self, pipeline_version: str | None) -> tuple[int, int]:
        return await self._repository.event_occurrence_counts(pipeline_version)

    async def list_clusters(
        self, *, offset: int, limit: int
    ) -> tuple[tuple[ClusterSummary, ...], int]:
        return await self._repository.list_clusters(offset=offset, limit=limit)

    async def get_cluster(self, cluster_id: UUID) -> ClusterDetail | None:
        return await self._repository.get_cluster(cluster_id)
