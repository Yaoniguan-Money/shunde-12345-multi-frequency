from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from backend.app.api.dependencies import get_analysis_job_service
from backend.app.domain.analysis_jobs import AnalysisJobView
from backend.app.domain.types import VersionTrace
from backend.app.main import create_app


class _AnalysisFixture:
    def __init__(self, *, status: str = "completed", error: str | None = None) -> None:
        self.job_id = uuid4()
        self.batch_id = uuid4()
        self.last_request: tuple[object, str | None] | None = None
        self.view = AnalysisJobView(
            job_id=self.job_id,
            status=status,
            total_rows=128278,
            target_work_order_count=128278,
            processed_work_order_count=3,
            failed_work_order_count=0,
            produced_event_instance_count=4,
            match_edge_count=2,
            cluster_count=1,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC) if status == "completed" else None,
            error=error,
            trace=VersionTrace(
                model_id="qwen-plus",
                model_config_hash="config-hash",
                schema_version="understanding.v2",
                knowledge_snapshot_id=None,
                pipeline_version="understanding.v2",
                provider="remote-openai-compatible",
            ),
            current_stage="completed" if status == "completed" else "matching",
            selected_rows=128278,
            processed_rows=3,
            event_count=4,
        )

    async def submit(self, batch_id, provider_profile_id=None):
        self.last_request = (batch_id, provider_profile_id)
        return self.view

    async def get(self, job_id):
        return self.view if job_id == self.job_id else None


@pytest.mark.asyncio
async def test_analysis_job_api_exposes_full_batch_progress_and_trace() -> None:
    fixture = _AnalysisFixture()
    app = create_app()
    app.dependency_overrides[get_analysis_job_service] = lambda: fixture
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/analysis-jobs",
            json={
                "import_batch_id": str(fixture.batch_id),
            },
        )
        progress = await client.get(f"/analysis-jobs/{fixture.job_id}")

    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "completed"
    assert body["target_work_order_count"] == 128278
    assert body["total_rows"] == 128278
    assert body["produced_event_instance_count"] == 4
    assert body["match_edge_count"] == 2
    assert body["cluster_count"] == 1
    assert body["current_stage"] == "completed"
    assert body["trace"]["model_id"] == "qwen-plus"
    # 请求体中不存在 max_work_orders 或 selection_mode
    assert fixture.last_request == (fixture.batch_id, None)
    assert progress.status_code == 200


@pytest.mark.asyncio
async def test_analysis_job_api_accepts_provider_profile_id() -> None:
    fixture = _AnalysisFixture()
    app = create_app()
    app.dependency_overrides[get_analysis_job_service] = lambda: fixture
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/analysis-jobs",
            json={
                "import_batch_id": str(fixture.batch_id),
                "provider_profile_id": "cloud-qwen",
            },
        )

    assert created.status_code == 202
    assert fixture.last_request == (fixture.batch_id, "cloud-qwen")


@pytest.mark.asyncio
async def test_failed_analysis_job_is_not_presented_as_completed() -> None:
    fixture = _AnalysisFixture(status="failed", error="remote provider unavailable")
    app = create_app()
    app.dependency_overrides[get_analysis_job_service] = lambda: fixture
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/analysis-jobs/{fixture.job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["finished_at"] is None
    assert response.json()["error"] == "remote provider unavailable"
