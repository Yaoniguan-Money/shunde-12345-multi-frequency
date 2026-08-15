from typing import Protocol
from uuid import UUID

from backend.app.domain.types import (
    EventClusterId,
    EventClusterRecord,
    EventForMatching,
    EventInstanceId,
    EventInstanceRecord,
    EventMatchEdgeRecord,
    JobId,
    RawWorkOrderRecord,
    VersionTrace,
    WorkOrderId,
)


class WorkOrderRepository(Protocol):
    async def get(self, work_order_id: WorkOrderId) -> RawWorkOrderRecord | None: ...

    async def add_immutable_raw(self, work_order: RawWorkOrderRecord) -> WorkOrderId: ...


class EventRepository(Protocol):
    async def get_instance(self, event_id: EventInstanceId) -> EventInstanceRecord | None: ...

    async def get_cluster(self, cluster_id: EventClusterId) -> EventClusterRecord | None: ...

    async def get_for_matching(self, event_id: EventInstanceId) -> EventForMatching | None: ...

    async def list_event_ids(
        self, work_order_ids: tuple[WorkOrderId, ...], pipeline_version: str
    ) -> tuple[EventInstanceId, ...]: ...


class EventGraphRepository(Protocol):
    async def start_run(
        self, *, pipeline_version: str, schema_version: str
    ) -> tuple[JobId, UUID]: ...

    async def save_match_edge(
        self,
        run_id: UUID,
        edge: EventMatchEdgeRecord,
        *,
        pipeline_version: str,
        schema_version: str,
    ) -> None: ...

    async def list_positive_edges(self, run_id: UUID) -> tuple[EventMatchEdgeRecord, ...]: ...

    async def save_cluster(
        self,
        run_id: UUID,
        member_ids: tuple[EventInstanceId, ...],
        *,
        name: str,
        confidence: float,
        evidence: dict[str, object],
        trace: VersionTrace,
        pipeline_version: str,
        schema_version: str,
    ) -> EventClusterId: ...

    async def finish_run(self, run_id: UUID, metrics: dict[str, object]) -> None: ...


class JobRepository(Protocol):
    async def claim_next(self, worker_id: str) -> JobId | None: ...

    async def checkpoint(self, job_id: JobId, stage: str, cursor: str | None) -> None: ...
