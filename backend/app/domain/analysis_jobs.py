from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.app.domain.analysis import EventFact, StructuredUnderstanding, TextSegment
from backend.app.domain.taxonomy import ClassificationOutcome
from backend.app.domain.types import VersionTrace


@dataclass(frozen=True, slots=True)
class WorkOrderSource:
    work_order_id: UUID
    source_row_number: int
    raw_title: str | None
    raw_content: str
    reported_at: datetime | None = None
    external_work_order_number: str | None = None
    source_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnderstandingRecord:
    work_order_id: UUID
    segments: tuple[TextSegment, ...]
    understanding: StructuredUnderstanding
    trace: VersionTrace
    facts: tuple[EventFact, ...] = ()
    classifications: tuple[ClassificationOutcome, ...] = ()


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
    target_work_order_count: int
    processed_work_order_count: int
    failed_work_order_count: int
    produced_event_instance_count: int
    match_edge_count: int
    cluster_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    trace: VersionTrace | None
    current_stage: str = "queued"
    # 旧字段兼容（从 metrics 投影），新代码应使用上面的字段
    selected_rows: int = 0
    processed_rows: int = 0
    event_count: int = 0
    provider_profile_snapshot: dict[str, object] | None = None
    execution_policy_snapshot: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ResumableAnalysisJob:
    job_id: UUID
    run_id: UUID
    batch_id: UUID
    target_work_order_count: int
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


@dataclass(frozen=True, slots=True)
class FrozenScope:
    scope_id: UUID
    job_id: UUID
    batch_id: UUID
    target_work_order_count: int
    work_order_ids: tuple[UUID, ...]
    work_order_id_hash: str
    pipeline_version: str
    taxonomy_version_id: UUID | None
    provider_profile_snapshot: dict[str, object] | None
    execution_policy_snapshot: dict[str, object] | None


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
        target_work_order_count: int,
        batch_id: UUID,
    ) -> AnalysisJobState: ...

    async def get_job_view(self, job_id: UUID) -> AnalysisJobView | None: ...

    async def list_resumable_jobs(self) -> tuple[ResumableAnalysisJob, ...]: ...

    async def mark_running(self, job_id: UUID, run_id: UUID, stage: str) -> None: ...

    async def update_progress(
        self, job_id: UUID, run_id: UUID, stage: str, metrics: dict[str, object]
    ) -> None: ...

    async def requeue_interrupted(self, job_id: UUID, run_id: UUID, reason: str) -> None: ...

    async def select_work_orders(self, batch_id: UUID) -> tuple[WorkOrderSource, ...]: ...

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

    async def freeze_scope(
        self,
        job_id: UUID,
        batch_id: UUID,
        work_order_ids: tuple[UUID, ...],
        target_work_order_count: int,
        pipeline_version: str,
        taxonomy_version_id: UUID | None,
        provider_profile_snapshot: dict[str, object] | None,
        execution_policy_snapshot: dict[str, object] | None,
    ) -> FrozenScope: ...

    async def get_scope(self, job_id: UUID) -> FrozenScope | None: ...
