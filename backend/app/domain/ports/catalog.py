"""Read-only catalog port used by the demo/API projection."""

from typing import Protocol
from uuid import UUID

from backend.app.domain.catalog import (
    CatalogFacets,
    CatalogOverview,
    ClusterDetail,
    ClusterSummary,
    EventDetail,
    WorkOrderDetail,
    WorkOrderSummary,
)


class CatalogRepository(Protocol):
    async def get_overview(
        self,
        *,
        query: str | None,
        analysis_state: str | None,
        event_type: str | None,
        title_tag: str | None,
    ) -> CatalogOverview: ...

    async def get_facets(self) -> CatalogFacets: ...

    async def list_work_orders(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None,
        analysis_state: str | None,
        event_type: str | None,
        title_tag: str | None,
    ) -> tuple[tuple[WorkOrderSummary, ...], int]: ...

    async def get_work_order(self, work_order_id: UUID) -> WorkOrderDetail | None: ...

    async def list_events(
        self,
        *,
        offset: int,
        limit: int,
        pipeline_version: str | None,
        work_order_id: UUID | None,
    ) -> tuple[tuple[EventDetail, ...], int]: ...

    async def get_event(self, event_id: UUID) -> EventDetail | None: ...

    async def event_occurrence_counts(self, pipeline_version: str | None) -> tuple[int, int]: ...

    async def list_clusters(
        self, *, offset: int, limit: int
    ) -> tuple[tuple[ClusterSummary, ...], int]: ...

    async def get_cluster(self, cluster_id: UUID) -> ClusterDetail | None: ...
