from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from backend.app.api.dependencies import get_catalog_service
from backend.app.domain.catalog import (
    CatalogEvent,
    ClusterDetail,
    ClusterSummary,
    EntityReference,
    EventDetail,
    MatchEdgeView,
    RemovedClusterMember,
    WorkOrderDetail,
    WorkOrderSummary,
)
from backend.app.domain.types import VersionTrace
from backend.app.main import create_app


class _CatalogFixture:
    def __init__(self) -> None:
        self.work_order_id = uuid4()
        self.event_id = uuid4()
        self.cluster_id = uuid4()
        self.trace = VersionTrace(
            model_id="qwen-plus",
            model_config_hash="hash",
            schema_version="understanding.v2",
            knowledge_snapshot_id=None,
            pipeline_version="understanding.v2",
            provider="remote-openai-compatible",
        )
        self.summary = WorkOrderSummary(
            work_order_id=self.work_order_id,
            external_work_order_number="WO-1",
            source_row_number=1,
            raw_title="商业噪音",
            created_at=datetime.now(UTC),
            event_count=1,
            cluster_count=1,
        )
        self.event = CatalogEvent(
            event_id=self.event_id,
            work_order_id=self.work_order_id,
            ordinal=0,
            event_type="commercial_noise",
            behavior="要求处理",
            normalized_summary="同一地点商业噪音",
            entities=(EntityReference(uuid4(), "恒艺工作室", "place"),),
            location_signals=("新桂北路29号116号铺",),
            time_signals=("2025年1月1日",),
            evidence=({"quote": "新桂北路29号116号铺有噪音", "validation": "exact_quote"},),
            trace=self.trace,
        )
        self.detail = EventDetail(
            event=self.event,
            work_order=self.summary,
            raw_title=self.summary.raw_title,
            raw_content="新桂北路29号116号铺有噪音",
        )
        second_event = replace(
            self.event,
            event_id=uuid4(),
            ordinal=1,
            normalized_summary="要求再次关停音响",
        )
        second_work_order = replace(
            self.summary,
            work_order_id=uuid4(),
            external_work_order_number="WO-2",
            source_row_number=2,
        )
        third_event = replace(
            self.event,
            event_id=uuid4(),
            work_order_id=second_work_order.work_order_id,
            normalized_summary="再次反映同一地点商业噪音",
        )
        self.members = (
            self.detail,
            EventDetail(
                event=second_event,
                work_order=self.summary,
                raw_title=self.summary.raw_title,
                raw_content=self.detail.raw_content,
            ),
            EventDetail(
                event=third_event,
                work_order=second_work_order,
                raw_title=second_work_order.raw_title,
                raw_content="再次反映新桂北路29号116号铺商业噪音",
            ),
        )
        self.removed_member = RemovedClusterMember(
            event=self.members[0],
            event_instance_id=self.event_id,
            correction_id=uuid4(),
            actor_id="reviewer",
            reason="误判",
            removed_at=datetime.now(UTC),
            can_restore=True,
        )
        self.cluster = ClusterSummary(
            cluster_id=self.cluster_id,
            name="同一地点商业噪音",
            status="active",
            confidence=0.95,
            handling_status="unhandled",
            member_count=2,
            work_order_count=2,
            event_count=3,
            evidence={"positive_edge_count": 1},
            trace=self.trace,
        )

    async def list_work_orders(self, **_kwargs):
        return (self.summary,), 1

    async def get_work_order(self, _work_order_id):
        return None

    async def list_events(self, **_kwargs):
        return (self.detail,), 1

    async def get_event(self, _event_id):
        return self.detail

    async def event_occurrence_counts(self, _pipeline_version):
        return 1, 0

    async def list_clusters(self, **_kwargs):
        return (self.cluster,), 1

    async def get_cluster(self, _cluster_id):
        return ClusterDetail(
            summary=self.cluster,
            members=self.members,
            work_orders=(
                WorkOrderDetail(
                    summary=self.summary,
                    import_batch_id=uuid4(),
                    raw_content=self.detail.raw_content,
                    raw_fields={"工单编号": "WO-1"},
                    events=(self.members[0].event, self.members[1].event),
                ),
                WorkOrderDetail(
                    summary=self.members[2].work_order,
                    import_batch_id=uuid4(),
                    raw_content=self.members[2].raw_content,
                    raw_fields={"工单编号": "WO-2"},
                    events=(self.members[2].event,),
                ),
            ),
            edges=(
                MatchEdgeView(
                    left_event_id=self.event_id,
                    right_event_id=self.event_id,
                    same_event=True,
                    confidence=0.95,
                    evidence={"same_issue": True},
                    trace=self.trace,
                ),
            ),
            removed_members=(self.removed_member,),
        )


@pytest.mark.asyncio
async def test_catalog_api_exposes_trace_evidence_and_pagination() -> None:
    fixture = _CatalogFixture()
    app = create_app()
    app.dependency_overrides[get_catalog_service] = lambda: fixture
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        work_orders = await client.get("/work-orders?limit=1")
        events = await client.get("/events?limit=1")
        event = await client.get(f"/events/{fixture.event_id}")
        clusters = await client.get("/multi-frequency-events?limit=1")
        cluster = await client.get(f"/multi-frequency-events/{fixture.cluster_id}")

    assert work_orders.status_code == 200
    assert work_orders.json()["total"] == 1
    assert events.json()["items"][0]["event"]["trace"]["provider"] == ("remote-openai-compatible")
    assert event.json()["event"]["evidence"][0]["validation"] == "exact_quote"
    assert events.json()["occurrence_dated_total"] == 1
    assert events.json()["occurrence_unknown_total"] == 0
    assert clusters.json()["items"][0]["member_count"] == 2
    assert clusters.json()["items"][0]["work_order_count"] == 2
    assert clusters.json()["items"][0]["event_count"] == 3
    assert clusters.json()["items"][0]["is_high_frequency"] is False
    assert clusters.json()["items"][0]["frequency_window_days"] == 3
    assert clusters.json()["items"][0]["frequency_work_order_count"] == 0
    assert cluster.json()["summary"]["work_order_count"] == 2
    assert cluster.json()["summary"]["event_count"] == 3
    assert cluster.json()["summary"]["is_high_frequency"] is False
    assert len(cluster.json()["work_orders"]) == 2
    assert sorted(len(item["events"]) for item in cluster.json()["work_orders"]) == [1, 2]
    assert cluster.json()["edges"][0]["evidence"]["same_issue"] is True
    assert cluster.json()["removed_members"][0]["event_instance_id"] == str(fixture.event_id)
    assert cluster.json()["removed_members"][0]["can_restore"] is True
