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
        self.last_request: tuple[object, int, str] | None = None
        self.view = AnalysisJobView(
            job_id=self.job_id,
            status=status,
            total_rows=128278,
            selected_rows=3,
            processed_rows=3,
            event_count=4,
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
            selection_mode="recurrence_candidates",
            current_stage="completed" if status == "completed" else "matching",
        )

    async def submit(self, batch_id, max_work_orders, selection_mode="sequential"):
        self.last_request = (batch_id, max_work_orders, selection_mode)
        return self.view

    async def get(self, job_id):
        return self.view if job_id == self.job_id else None


@pytest.mark.asyncio
async def test_analysis_job_api_exposes_bounded_progress_and_trace() -> None:
    fixture = _AnalysisFixture()
    app = create_app()
    app.dependency_overrides[get_analysis_job_service] = lambda: fixture
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/analysis-jobs",
            json={
                "import_batch_id": str(fixture.batch_id),
                "max_work_orders": 3,
                "selection_mode": "recurrence_candidates",
            },
        )
        progress = await client.get(f"/analysis-jobs/{fixture.job_id}")
        missing_limit = await client.post(
            "/analysis-jobs", json={"import_batch_id": str(fixture.batch_id)}
        )
        too_large = await client.post(
            "/analysis-jobs",
            json={"import_batch_id": str(fixture.batch_id), "max_work_orders": 301},
        )

    assert created.status_code == 202
    assert created.json()["status"] == "completed"
    assert created.json()["selected_rows"] == 3
    assert created.json()["total_rows"] == 128278
    assert created.json()["selection_mode"] == "recurrence_candidates"
    assert created.json()["event_count"] == 4
    assert created.json()["match_edge_count"] == 2
    assert created.json()["cluster_count"] == 1
    assert created.json()["current_stage"] == "completed"
    assert created.json()["trace"]["model_id"] == "qwen-plus"
    assert progress.status_code == 200
    assert fixture.last_request == (fixture.batch_id, 3, "recurrence_candidates")
    assert missing_limit.status_code == 422
    assert too_large.status_code == 422


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
