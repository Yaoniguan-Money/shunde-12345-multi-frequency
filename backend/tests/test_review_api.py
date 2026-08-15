from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from backend.app.api.dependencies import get_exporter, get_review_service
from backend.app.domain.catalog import HandlingRecordView, HumanCorrectionView
from backend.app.domain.types import ExportArtifact, ExportRequest
from backend.app.main import create_app


class _ReviewFixture:
    def __init__(self) -> None:
        self.cluster_id = uuid4()
        self.event_id = uuid4()
        self.record = HandlingRecordView(
            record_id=uuid4(),
            cluster_id=self.cluster_id,
            previous_status="unhandled",
            new_status="investigating",
            actor_id="reviewer",
            description="已联系属地核查",
            result="待回访",
            attachment_references=("memo-1",),
            created_at=datetime.now(UTC),
        )
        self.correction = HumanCorrectionView(
            correction_id=uuid4(),
            cluster_id=self.cluster_id,
            work_order_id=uuid4(),
            correction_type="confirm_member",
            actor_id="reviewer",
            reason="人工核对为同一事件",
            payload={"event_instance_id": str(self.event_id), "member_added": True},
            supersedes_correction_id=None,
            created_at=datetime.now(UTC),
        )
        self.export_requests: list[ExportRequest] = []

    async def add_handling_record(self, *_args, **_kwargs):
        return self.record

    async def list_handling_records(self, _cluster_id):
        return (self.record,)

    async def add_correction(self, *_args, **_kwargs):
        return self.correction

    async def list_corrections(self, _cluster_id):
        return (self.correction,)

    async def export(self, request: ExportRequest) -> ExportArtifact:
        self.export_requests.append(request)
        return ExportArtifact(
            filename="multi-frequency-events.csv",
            media_type="text/csv; charset=utf-8",
            content=b"cluster_id,handling_status\n",
        )


@pytest.mark.asyncio
async def test_review_api_exposes_audited_write_contracts_and_csv_export() -> None:
    fixture = _ReviewFixture()
    app = create_app()
    app.dependency_overrides[get_review_service] = lambda: fixture
    app.dependency_overrides[get_exporter] = lambda: fixture
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        handling = await client.post(
            f"/multi-frequency-events/{fixture.cluster_id}/handling-records",
            json={
                "new_status": "investigating",
                "actor_id": "reviewer",
                "description": "已联系属地核查",
                "result": "待回访",
                "attachment_references": ["memo-1"],
            },
        )
        handling_history = await client.get(
            f"/multi-frequency-events/{fixture.cluster_id}/handling-records"
        )
        correction = await client.post(
            f"/multi-frequency-events/{fixture.cluster_id}/corrections",
            json={
                "correction_type": "confirm_member",
                "event_instance_id": str(fixture.event_id),
                "actor_id": "reviewer",
                "reason": "人工核对为同一事件",
            },
        )
        corrections = await client.get(f"/multi-frequency-events/{fixture.cluster_id}/corrections")
        exported = await client.get(
            f"/multi-frequency-events/export.csv?cluster_id={fixture.cluster_id}"
        )

    assert handling.status_code == 201
    assert handling.json()["new_status"] == "investigating"
    assert handling_history.json()["items"][0]["result"] == "待回访"
    assert correction.status_code == 201
    assert correction.json()["correction_type"] == "confirm_member"
    assert corrections.json()["items"][0]["payload"]["member_added"] is True
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].endswith('filename="multi-frequency-events.csv"')
    assert exported.text.startswith("cluster_id,handling_status")
    assert fixture.export_requests[0].format == "csv"
    assert fixture.export_requests[0].event_cluster_ids
