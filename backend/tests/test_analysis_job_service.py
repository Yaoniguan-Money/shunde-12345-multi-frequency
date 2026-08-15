from uuid import uuid4

import pytest
from pydantic import SecretStr

from backend.app.application.services.analysis import AnalysisExecution
from backend.app.application.services.analysis_jobs import AnalysisJobService
from backend.app.config import Settings
from backend.app.domain.analysis_jobs import (
    AnalysisBatchInfo,
    AnalysisJobState,
    AnalysisJobView,
    WorkOrderSource,
)
from backend.app.domain.types import (
    EventInstanceId,
    EventMatchEdgeRecord,
    ProviderMode,
    SameEventEvidence,
    VersionTrace,
)


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

    async def get_batch_info(self, batch_id):
        return self.batch if batch_id == self.batch.batch_id else None

    async def load_work_orders(self, _batch_id, _after, limit, _max_source_row=None):
        return tuple(
            WorkOrderSource(uuid4(), row, f"标题-{row}", f"内容-{row}")
            for row in range(1, min(limit, 3) + 1)
        )

    async def create_or_requeue(self, **_kwargs):
        return AnalysisJobState(self.job_id, self.run_id, 0, "queued")

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
    def __init__(self, *, fail=False):
        self.fail = fail

    async def run_import_batch(self, _batch_id, _max_work_orders, *, idempotency_key):
        assert idempotency_key.startswith("demo-analysis:")
        if self.fail:
            raise RuntimeError("remote provider unavailable")
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
