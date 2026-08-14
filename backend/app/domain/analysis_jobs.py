from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.app.domain.analysis import StructuredUnderstanding, TextSegment
from backend.app.domain.types import VersionTrace


@dataclass(frozen=True, slots=True)
class WorkOrderSource:
    work_order_id: UUID
    source_row_number: int
    raw_title: str | None
    raw_content: str


@dataclass(frozen=True, slots=True)
class UnderstandingRecord:
    work_order_id: UUID
    segments: tuple[TextSegment, ...]
    understanding: StructuredUnderstanding
    trace: VersionTrace


@dataclass(frozen=True, slots=True)
class AnalysisJobState:
    job_id: UUID
    run_id: UUID
    checkpoint_source_row: int
    status: str


@dataclass(frozen=True, slots=True)
class PersistedEvent:
    work_order_id: UUID
    event_id: UUID
    text: str


class UnderstandingRepository(Protocol):
    async def start_or_resume(
        self,
        *,
        idempotency_key: str,
        pipeline_version: str,
        schema_version: str,
        model_id: str,
        total_rows: int,
    ) -> AnalysisJobState: ...

    async def load_work_orders(
        self, batch_id: UUID, after_source_row: int, limit: int
    ) -> tuple[WorkOrderSource, ...]: ...

    async def persist_records(
        self,
        run_id: UUID,
        records: tuple[UnderstandingRecord, ...],
        pipeline_version: str,
        schema_version: str,
    ) -> tuple[PersistedEvent, ...]: ...

    async def persist_embeddings(
        self,
        run_id: UUID,
        embeddings: tuple[tuple[UUID, UUID | None, str, tuple[float, ...], str], ...],
        pipeline_version: str,
        schema_version: str,
    ) -> None: ...

    async def checkpoint(
        self, job_id: UUID, run_id: UUID, source_row: int, metrics: dict[str, object]
    ) -> None: ...

    async def finish(self, job_id: UUID, run_id: UUID, metrics: dict[str, object]) -> None: ...

    async def fail(self, job_id: UUID, run_id: UUID, code: str, message: str) -> None: ...
