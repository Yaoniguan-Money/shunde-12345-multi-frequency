from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.application.services.indexing import UnderstandingAndIndexingPipeline
from backend.app.domain.analysis_jobs import (
    AnalysisJobState,
    PersistedEvent,
    WorkOrderSource,
)
from backend.app.domain.types import EmbeddingResult, VersionTrace


class _BoundedRepository:
    def __init__(self) -> None:
        self.sources = tuple(
            WorkOrderSource(uuid4(), row, f"标题-{row}", f"内容-{row}") for row in range(1, 6)
        )
        self.limits: list[tuple[int, int | None]] = []
        self.checkpoints: list[int] = []

    async def start_or_resume(self, **_kwargs):
        return AnalysisJobState(uuid4(), uuid4(), 0, "running")

    async def load_work_orders(
        self,
        _batch_id,
        after_source_row,
        limit,
        max_source_row=None,
        selected_work_order_ids=None,
    ):
        self.limits.append((limit, max_source_row))
        return tuple(
            source
            for source in self.sources
            if source.source_row_number > after_source_row
            and (max_source_row is None or source.source_row_number <= max_source_row)
            and (selected_work_order_ids is None or source.work_order_id in selected_work_order_ids)
        )[:limit]

    async def persist_records(self, _run_id, records, *_args):
        return tuple(
            PersistedEvent(record.work_order_id, uuid4(), "事件摘要") for record in records
        )

    async def persist_embeddings(self, *_args):
        return None

    async def checkpoint(self, _job_id, _run_id, source_row, _metrics):
        self.checkpoints.append(source_row)

    async def finish(self, *_args):
        raise AssertionError("bounded run must pause before full-batch finish")

    async def fail(self, *_args):
        raise AssertionError("bounded run must not fail")

    async def mark_results_failed(self, *_args):
        raise AssertionError("bounded run must not mark successful rows failed")


class _Understanding:
    async def understand_batch(self, items):
        trace = VersionTrace("qwen-plus", "hash", "understanding.v2", None, "understanding.v2")
        return tuple(
            SimpleNamespace(
                work_order_id=work_order_id,
                segments=(),
                understanding=SimpleNamespace(events=(), mentions=()),
                trace=trace,
            )
            for work_order_id, _title, _content in items
        )


class _Embedding:
    async def embed_batch(self, requests):
        return tuple(
            EmbeddingResult(request.item_id, (0.1, 0.2), "qwen3.7-text-embedding")
            for request in requests
        )


@pytest.mark.asyncio
async def test_indexing_pipeline_never_reads_past_bounded_selection() -> None:
    repository = _BoundedRepository()
    pipeline = UnderstandingAndIndexingPipeline(
        repository,
        _Understanding(),
        _Embedding(),
        pipeline_version="understanding.v2",
        schema_version="understanding.v2",
        model_id="qwen-plus",
        embedding_model_id="qwen3.7-text-embedding",
        chunk_size=2,
    )

    summary = await pipeline.run(
        uuid4(),
        total_rows=128278,
        max_rows=3,
        max_source_row=3,
    )

    assert summary.status == "paused"
    assert summary.rows_processed == 3
    assert repository.limits == [(2, 3), (1, 3)]
    assert repository.checkpoints == [2, 3]


@pytest.mark.asyncio
async def test_composed_indexing_preserves_cumulative_progress_without_finishing_job() -> None:
    repository = _BoundedRepository()
    pipeline = UnderstandingAndIndexingPipeline(
        repository,
        _Understanding(),
        _Embedding(),
        pipeline_version="understanding.v2",
        schema_version="understanding.v2",
        model_id="qwen-plus",
        embedding_model_id="qwen3.7-text-embedding",
        chunk_size=2,
    )
    state = AnalysisJobState(
        uuid4(),
        uuid4(),
        5,
        "running",
        rows_processed=5,
        events_extracted=7,
        embeddings_written=7,
    )

    summary = await pipeline.run(
        uuid4(),
        total_rows=100,
        max_rows=5,
        analysis_state=state,
        manage_job_lifecycle=False,
    )

    assert summary.status == "indexed"
    assert summary.rows_processed == 5
    assert summary.events_extracted == 7
    assert summary.embeddings_written == 7
    assert repository.limits == []
