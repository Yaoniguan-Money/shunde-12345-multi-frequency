from dataclasses import dataclass
from datetime import datetime
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
    rows_processed: int = 0
    events_extracted: int = 0
    embeddings_written: int = 0


@dataclass(frozen=True, slots=True)
class AnalysisBatchInfo:
    batch_id: UUID
    status: str
    total_rows: int
    successful_rows: int


@dataclass(frozen=True, slots=True)
class AnalysisJobView:
    job_id: UUID
    status: str
    total_rows: int
    selected_rows: int
    processed_rows: int
    event_count: int
    match_edge_count: int
    cluster_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    trace: VersionTrace | None
    selection_mode: str = "sequential"
    current_stage: str = "queued"


@dataclass(frozen=True, slots=True)
class ResumableAnalysisJob:
    job_id: UUID
    run_id: UUID
    batch_id: UUID
    max_work_orders: int
    selection_mode: str
    idempotency_key: str
    checkpoint_source_row: int
    rows_processed: int
    events_extracted: int
    embeddings_written: int


@dataclass(frozen=True, slots=True)
class PersistedEvent:
    work_order_id: UUID
    event_id: UUID
    text: str


class UnderstandingRepository(Protocol):
    async def get_batch_info(self, batch_id: UUID) -> AnalysisBatchInfo | None: ...

    async def create_or_requeue(
        self,
        *,
        idempotency_key: str,
        pipeline_version: str,
        schema_version: str,
        model_id: str,
        provider: str,
        model_config_hash: str | None,
        total_rows: int,
        selected_rows: int,
        selection_mode: str,
        batch_id: UUID,
        max_work_orders: int,
    ) -> AnalysisJobState: ...

    async def get_job_view(self, job_id: UUID) -> AnalysisJobView | None: ...

    async def list_resumable_jobs(self) -> tuple[ResumableAnalysisJob, ...]: ...

    async def mark_running(self, job_id: UUID, run_id: UUID, stage: str) -> None: ...

    async def update_progress(
        self, job_id: UUID, run_id: UUID, stage: str, metrics: dict[str, object]
    ) -> None: ...

    async def requeue_interrupted(self, job_id: UUID, run_id: UUID, reason: str) -> None: ...

    async def select_work_orders(
        self, batch_id: UUID, limit: int, selection_mode: str
    ) -> tuple[WorkOrderSource, ...]: ...

    async def start_or_resume(
        self,
        *,
        idempotency_key: str,
        pipeline_version: str,
        schema_version: str,
        model_id: str,
        provider: str,
        model_config_hash: str | None = None,
        total_rows: int,
    ) -> AnalysisJobState: ...

    async def load_work_orders(
        self,
        batch_id: UUID,
        after_source_row: int,
        limit: int,
        max_source_row: int | None = None,
        selected_work_order_ids: tuple[UUID, ...] | None = None,
    ) -> tuple[WorkOrderSource, ...]: ...

    async def persist_records(
        self,
        run_id: UUID,
        records: tuple[UnderstandingRecord, ...],
        pipeline_version: str,
        schema_version: str,
    ) -> tuple[PersistedEvent, ...]: ...

    async def mark_results_failed(
        self,
        run_id: UUID,
        work_order_ids: tuple[UUID, ...],
        pipeline_version: str,
        error_code: str,
        error_summary: str,
    ) -> None: ...

    async def persist_embeddings(
        self,
        run_id: UUID,
        embeddings: tuple[
            tuple[UUID, UUID | None, str, tuple[float, ...], str, VersionTrace | None], ...
        ],
        pipeline_version: str,
        schema_version: str,
    ) -> None: ...

    async def checkpoint(
        self, job_id: UUID, run_id: UUID, source_row: int, metrics: dict[str, object]
    ) -> None: ...

    async def finish(self, job_id: UUID, run_id: UUID, metrics: dict[str, object]) -> None: ...

    async def fail(self, job_id: UUID, run_id: UUID, code: str, message: str) -> None: ...
