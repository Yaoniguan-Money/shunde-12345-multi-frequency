"""Read-only catalog port used by the demo/API projection."""

from typing import Protocol
from uuid import UUID

from backend.app.domain.catalog import (
    ClusterDetail,
    ClusterSummary,
    EventDetail,
    WorkOrderDetail,
    WorkOrderSummary,
)


class CatalogRepository(Protocol):
    async def list_work_orders(
        self, *, offset: int, limit: int, query: str | None
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

    async def list_clusters(
        self, *, offset: int, limit: int
    ) -> tuple[tuple[ClusterSummary, ...], int]: ...

    async def get_cluster(self, cluster_id: UUID) -> ClusterDetail | None: ...
