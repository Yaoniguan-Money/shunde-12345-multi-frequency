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
        self.cluster = ClusterSummary(
            cluster_id=self.cluster_id,
            name="同一地点商业噪音",
            status="active",
            confidence=0.95,
            handling_status="unhandled",
            member_count=1,
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

    async def list_clusters(self, **_kwargs):
        return (self.cluster,), 1

    async def get_cluster(self, _cluster_id):
        return ClusterDetail(
            summary=self.cluster,
            members=(self.detail,),
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
    assert clusters.json()["items"][0]["member_count"] == 1
    assert cluster.json()["edges"][0]["evidence"]["same_issue"] is True
