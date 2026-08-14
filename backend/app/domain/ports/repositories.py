from typing import Protocol

from backend.app.domain.types import (
    EventClusterId,
    EventClusterRecord,
    EventInstanceId,
    EventInstanceRecord,
    JobId,
    RawWorkOrderRecord,
    WorkOrderId,
)


class WorkOrderRepository(Protocol):
    async def get(self, work_order_id: WorkOrderId) -> RawWorkOrderRecord | None: ...

    async def add_immutable_raw(self, work_order: RawWorkOrderRecord) -> WorkOrderId: ...


class EventRepository(Protocol):
    async def get_instance(self, event_id: EventInstanceId) -> EventInstanceRecord | None: ...

    async def get_cluster(self, cluster_id: EventClusterId) -> EventClusterRecord | None: ...


class JobRepository(Protocol):
    async def claim_next(self, worker_id: str) -> JobId | None: ...

    async def checkpoint(self, job_id: JobId, stage: str, cursor: str | None) -> None: ...
