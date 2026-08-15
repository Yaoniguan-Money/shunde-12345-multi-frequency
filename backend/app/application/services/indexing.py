import hashlib
import time
from dataclasses import dataclass
from uuid import UUID

from backend.app.application.services.understanding import WorkOrderUnderstandingService
from backend.app.domain.analysis_jobs import (
    UnderstandingRecord,
    UnderstandingRepository,
)
from backend.app.domain.ports.analysis import EmbeddingProvider
from backend.app.domain.types import EmbeddingRequest


@dataclass(frozen=True, slots=True)
class IndexingSummary:
    job_id: UUID
    run_id: UUID
    status: str
    rows_processed: int
    events_extracted: int
    embeddings_written: int
    checkpoint_source_row: int
    elapsed_seconds: float
    idempotent: bool


class UnderstandingAndIndexingPipeline:
    """Resumable batch orchestration for segmentation, structured extraction and vector indexing."""

    def __init__(
        self,
        repository: UnderstandingRepository,
        understanding: WorkOrderUnderstandingService,
        embeddings: EmbeddingProvider,
        *,
        pipeline_version: str,
        schema_version: str,
        model_id: str,
        embedding_model_id: str,
        provider: str = "unknown",
        model_config_hash: str | None = None,
        chunk_size: int = 16,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        self._repository = repository
        self._understanding = understanding
        self._embeddings = embeddings
        self._pipeline_version = pipeline_version
        self._schema_version = schema_version
        self._model_id = model_id
        self._embedding_model_id = embedding_model_id
        self._provider = provider
        self._model_config_hash = model_config_hash
        self._chunk_size = chunk_size

    async def run(
        self,
        batch_id: UUID,
        total_rows: int,
        *,
        max_rows: int | None = None,
        max_source_row: int | None = None,
        idempotency_key: str | None = None,
    ) -> IndexingSummary:
        started = time.perf_counter()
        state = await self._repository.start_or_resume(
            idempotency_key=idempotency_key or f"understanding:{batch_id}",
            pipeline_version=self._pipeline_version,
            schema_version=self._schema_version,
            model_id=self._model_id,
            provider=self._provider,
            model_config_hash=self._model_config_hash,
            total_rows=total_rows,
        )
        if state.status == "completed":
            return IndexingSummary(
                state.job_id,
                state.run_id,
                state.status,
                0,
                0,
                0,
                state.checkpoint_source_row,
                time.perf_counter() - started,
                True,
            )
        rows_processed = 0
        events_extracted = 0
        embeddings_written = 0
        checkpoint = state.checkpoint_source_row
        try:
            while True:
                remaining = None if max_rows is None else max_rows - rows_processed
                if remaining is not None and remaining <= 0:
                    return IndexingSummary(
                        state.job_id,
                        state.run_id,
                        "paused",
                        rows_processed,
                        events_extracted,
                        embeddings_written,
                        checkpoint,
                        time.perf_counter() - started,
                        False,
                    )
                sources = await self._repository.load_work_orders(
                    batch_id,
                    checkpoint,
                    min(self._chunk_size, remaining) if remaining is not None else self._chunk_size,
                    max_source_row,
                )
                if not sources:
                    break
                inputs = tuple(
                    (source.work_order_id, source.raw_title, source.raw_content)
                    for source in sources
                )
                results = await self._understanding.understand_batch(inputs)
                records = tuple(
                    UnderstandingRecord(
                        result.work_order_id,
                        result.segments,
                        result.understanding,
                        result.trace,
                    )
                    for result in results
                )
                persisted_events = await self._repository.persist_records(
                    state.run_id, records, self._pipeline_version, self._schema_version
                )
                embedding_requests = tuple(
                    EmbeddingRequest(
                        str(event.event_id),
                        event.text,
                        schema_version=self._schema_version,
                        pipeline_version=self._pipeline_version,
                    )
                    for event in persisted_events
                )
                embedding_results = await self._embeddings.embed_batch(embedding_requests)
                embedding_rows = tuple(
                    (
                        event.work_order_id,
                        event.event_id,
                        hashlib.sha256(event.text.encode("utf-8")).hexdigest(),
                        embedding.vector,
                        embedding.model_id,
                        embedding.trace,
                    )
                    for event, embedding in zip(persisted_events, embedding_results, strict=True)
                )
                await self._repository.persist_embeddings(
                    state.run_id,
                    embedding_rows,
                    self._pipeline_version,
                    self._schema_version,
                )
                checkpoint = sources[-1].source_row_number
                rows_processed += len(sources)
                events_extracted += len(persisted_events)
                embeddings_written += len(embedding_rows)
                await self._repository.checkpoint(
                    state.job_id,
                    state.run_id,
                    checkpoint,
                    {
                        "rows_processed": rows_processed,
                        "events_extracted": events_extracted,
                        "embeddings_written": embeddings_written,
                    },
                )
                if max_rows is not None and rows_processed >= max_rows:
                    return IndexingSummary(
                        state.job_id,
                        state.run_id,
                        "paused",
                        rows_processed,
                        events_extracted,
                        embeddings_written,
                        checkpoint,
                        time.perf_counter() - started,
                        False,
                    )
            await self._repository.finish(
                state.job_id,
                state.run_id,
                {
                    "rows_processed": rows_processed,
                    "events_extracted": events_extracted,
                    "embeddings_written": embeddings_written,
                },
            )
            return IndexingSummary(
                state.job_id,
                state.run_id,
                "completed",
                rows_processed,
                events_extracted,
                embeddings_written,
                checkpoint,
                time.perf_counter() - started,
                False,
            )
        except Exception as error:
            await self._repository.fail(state.job_id, state.run_id, "analysis_failed", str(error))
            raise
