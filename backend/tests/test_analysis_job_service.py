import asyncio
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from backend.app.application.services.analysis import AnalysisExecution
from backend.app.application.services.analysis_jobs import AnalysisJobService
from backend.app.config import Settings, get_settings
from backend.app.domain.analysis_jobs import (
    AnalysisBatchInfo,
    AnalysisJobState,
    AnalysisJobView,
    ResumableAnalysisJob,
    WorkOrderSource,
)
from backend.app.domain.types import (
    EventInstanceId,
    EventMatchEdgeRecord,
    ProviderMode,
    SameEventEvidence,
    VersionTrace,
)
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository
from backend.app.infrastructure.db.models import AnalysisJob
from backend.app.infrastructure.db.session import create_engine, create_session_factory


class _JobRepository:
    def __init__(self, batch_id):
        self.batch = AnalysisBatchInfo(batch_id, "completed", 128278, 128278)
        self.job_id = uuid4()
        self.run_id = uuid4()
        self.view = AnalysisJobView(
            self.job_id,
            "queued",
            128278,
            0,
            0,
            0,
            0,
            0,
            None,
            None,
            None,
            VersionTrace("qwen-plus", "hash", "understanding.v2", None, "understanding.v2"),
        )
        self.finished_metrics = None
        self.resumable = ()
        self.interrupted_reason = None
        self.running = asyncio.Event()

    async def get_batch_info(self, batch_id):
        return self.batch if batch_id == self.batch.batch_id else None

    async def load_work_orders(self, _batch_id, _after, limit, _max_source_row=None):
        return tuple(
            WorkOrderSource(uuid4(), row, f"标题-{row}", f"内容-{row}")
            for row in range(1, min(limit, 3) + 1)
        )

    async def select_work_orders(self, batch_id, limit, _selection_mode):
        return await self.load_work_orders(batch_id, 0, limit)

    async def create_or_requeue(self, **_kwargs):
        return AnalysisJobState(self.job_id, self.run_id, 0, "queued")

    async def list_resumable_jobs(self):
        return self.resumable

    async def mark_running(self, _job_id, _run_id, _stage):
        self.view = AnalysisJobView(
            self.job_id,
            "running",
            128278,
            3,
            self.view.processed_rows,
            self.view.event_count,
            self.view.match_edge_count,
            self.view.cluster_count,
            self.view.started_at,
            None,
            None,
            self.view.trace,
        )
        self.running.set()

    async def update_progress(self, _job_id, _run_id, _stage, _metrics):
        return None

    async def requeue_interrupted(self, _job_id, _run_id, _reason):
        self.interrupted_reason = _reason

    async def get_job_view(self, job_id):
        return self.view if job_id == self.job_id else None

    async def finish(self, _job_id, _run_id, metrics):
        self.finished_metrics = metrics
        self.view = AnalysisJobView(
            self.job_id,
            "completed",
            128278,
            3,
            metrics["processed_rows"],
            metrics["event_count"],
            metrics["match_edge_count"],
            metrics["cluster_count"],
            self.view.started_at,
            self.view.started_at,
            None,
            self.view.trace,
        )

    async def fail(self, _job_id, _run_id, _code, message):
        self.view = AnalysisJobView(
            self.job_id,
            "failed",
            128278,
            3,
            0,
            0,
            0,
            0,
            self.view.started_at,
            None,
            message,
            self.view.trace,
        )


class _Orchestrator:
    def __init__(self, *, fail=False, gate: asyncio.Event | None = None):
        self.fail = fail
        self.gate = gate

    async def run_import_batch(
        self,
        _batch_id,
        _max_work_orders,
        *,
        idempotency_key,
        analysis_state,
        selection_mode="sequential",
    ):
        assert idempotency_key.startswith("demo-analysis:")
        assert analysis_state.job_id == self._job_id
        assert analysis_state.run_id == self._run_id
        assert selection_mode in {"sequential", "recurrence_candidates"}
        if self.fail:
            raise RuntimeError("remote provider unavailable")
        if self.gate is not None:
            await self.gate.wait()
        edge = EventMatchEdgeRecord(
            EventInstanceId(uuid4()),
            EventInstanceId(uuid4()),
            True,
            0.9,
            SameEventEvidence(True, True, True, True),
            VersionTrace("qwen-plus", "hash", "same-event.v1", None, "demo-event-graph.v1"),
        )
        return AnalysisExecution(
            self._job_id,
            self._run_id,
            (uuid4(), uuid4(), uuid4()),
            (EventInstanceId(uuid4()), EventInstanceId(uuid4())),
            (edge,),
            (uuid4(),),
            3,
            2,
            1024,
        )


def _settings() -> Settings:
    return Settings(
        ai_provider_mode=ProviderMode.REMOTE,
        ai_remote_base_url="https://example.invalid/v1",
        ai_remote_llm_model_id="qwen-plus",
        ai_remote_embedding_model_id="qwen3.7-text-embedding",
        ai_remote_api_key=SecretStr("test-only"),
    )


@pytest.mark.asyncio
async def test_analysis_job_service_finishes_with_real_graph_counts() -> None:
    batch_id = uuid4()
    repository = _JobRepository(batch_id)

    async def factory():
        orchestrator = _Orchestrator()
        orchestrator._job_id = repository.job_id
        orchestrator._run_id = repository.run_id
        return orchestrator

    service = AnalysisJobService(
        _settings(),
        None,
        repository=repository,
        orchestrator_factory=factory,
    )
    queued = await service.submit(batch_id, 3)
    completed = await service.wait_for_completion(queued.job_id)

    assert completed is not None
    assert completed.status == "completed"
    assert repository.finished_metrics == {
        "processed_rows": 3,
        "event_count": 2,
        "match_edge_count": 1,
        "cluster_count": 1,
        "embeddings_written": 2,
    }


@pytest.mark.asyncio
async def test_analysis_job_service_records_failure_without_completed_status() -> None:
    batch_id = uuid4()
    repository = _JobRepository(batch_id)

    async def factory():
        orchestrator = _Orchestrator(fail=True)
        orchestrator._job_id = repository.job_id
        orchestrator._run_id = repository.run_id
        return orchestrator

    service = AnalysisJobService(
        _settings(),
        None,
        repository=repository,
        orchestrator_factory=factory,
    )
    queued = await service.submit(batch_id, 3)
    failed = await service.wait_for_completion(queued.job_id)

    assert failed is not None
    assert failed.status == "failed"
    assert failed.error == "remote provider unavailable"


@pytest.mark.asyncio
async def test_analysis_job_stays_running_until_event_graph_returns() -> None:
    batch_id = uuid4()
    repository = _JobRepository(batch_id)
    graph_gate = asyncio.Event()

    async def factory():
        orchestrator = _Orchestrator(gate=graph_gate)
        orchestrator._job_id = repository.job_id
        orchestrator._run_id = repository.run_id
        return orchestrator

    service = AnalysisJobService(
        _settings(),
        None,
        repository=repository,
        orchestrator_factory=factory,
    )
    queued = await service.submit(batch_id, 3)
    await repository.running.wait()

    in_progress = await service.get(queued.job_id)
    assert in_progress is not None
    assert in_progress.status == "running"
    assert repository.finished_metrics is None

    graph_gate.set()
    completed = await service.wait_for_completion(queued.job_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.cluster_count == 1


@pytest.mark.asyncio
async def test_analysis_job_service_requeues_interrupted_work_and_recovers_on_startup() -> None:
    batch_id = uuid4()
    repository = _JobRepository(batch_id)
    repository.resumable = (
        ResumableAnalysisJob(
            repository.job_id,
            repository.run_id,
            batch_id,
            3,
            "sequential",
            f"demo-analysis:{batch_id}:sequential:3:understanding.v2",
            2,
            2,
            3,
            3,
        ),
    )
    gate = asyncio.Event()

    async def factory():
        orchestrator = _Orchestrator(gate=gate)
        orchestrator._job_id = repository.job_id
        orchestrator._run_id = repository.run_id
        return orchestrator

    service = AnalysisJobService(
        _settings(),
        None,
        repository=repository,
        orchestrator_factory=factory,
    )

    assert await service.resume_incomplete() == 1
    await repository.running.wait()
    await service.shutdown()

    assert repository.interrupted_reason == "service_shutdown"


@pytest.mark.asyncio
async def test_failed_job_retry_preserves_checkpoint_and_cumulative_metrics() -> None:
    engine = create_engine(get_settings())
    sessions = create_session_factory(engine)
    repository = SQLAlchemyUnderstandingRepository(sessions)
    batch_id = uuid4()
    pipeline_version = f"retry-test.{uuid4()}"
    job_id = None
    try:
        try:
            state = await repository.create_or_requeue(
                idempotency_key=f"retry-test:{batch_id}",
                pipeline_version=pipeline_version,
                schema_version="understanding.v2",
                model_id="test-model",
                provider="test-provider",
                model_config_hash="test-hash",
                total_rows=100,
                selected_rows=5,
                selection_mode="sequential",
                batch_id=batch_id,
                max_work_orders=5,
            )
            job_id = state.job_id
            await repository.checkpoint(
                state.job_id,
                state.run_id,
                42,
                {
                    "rows_processed": 3,
                    "events_extracted": 4,
                    "embeddings_written": 4,
                },
            )
            await repository.fail(state.job_id, state.run_id, "test_failure", "interrupted")
            resumed = await repository.create_or_requeue(
                idempotency_key=f"retry-test:{batch_id}",
                pipeline_version=pipeline_version,
                schema_version="understanding.v2",
                model_id="test-model",
                provider="test-provider",
                model_config_hash="test-hash",
                total_rows=100,
                selected_rows=5,
                selection_mode="sequential",
                batch_id=batch_id,
                max_work_orders=5,
            )
        except (OSError, SQLAlchemyError) as error:
            pytest.skip(f"PostgreSQL not available; retry persistence deferred: {error}")

        assert resumed.job_id == state.job_id
        assert resumed.run_id == state.run_id
        assert resumed.checkpoint_source_row == 42
        assert resumed.rows_processed == 3
        assert resumed.events_extracted == 4
        assert resumed.embeddings_written == 4
    finally:
        if job_id is not None:
            try:
                async with sessions() as session:
                    async with session.begin():
                        await session.execute(delete(AnalysisJob).where(AnalysisJob.id == job_id))
            except (OSError, SQLAlchemyError):
                pass
        await engine.dispose()
