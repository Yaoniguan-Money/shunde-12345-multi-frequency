from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select

from backend.app.config import get_settings
from backend.app.domain.types import EventInstanceId, VersionTrace
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository
from backend.app.infrastructure.db.catalog import SQLAlchemyCatalogRepository
from backend.app.infrastructure.db.events import SQLAlchemyEventRepository
from backend.app.infrastructure.db.models import (
    AnalysisJob,
    AuditLog,
    EventCluster,
    EventInstance,
    ImportBatch,
    WorkOrder,
    WorkOrderAnalysisResult,
)
from backend.app.infrastructure.db.review import SQLAlchemyEventReviewRepository
from backend.app.infrastructure.db.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_select_work_orders_returns_full_batch() -> None:
    """WP2: select_work_orders 返回导入批次全部成功工单，不再按 limit/selection_mode 截断。"""
    engine = create_engine(get_settings())
    sessions = create_session_factory(engine)
    repository = SQLAlchemyUnderstandingRepository(sessions)
    batch_id = uuid4()
    try:
        async with sessions() as session, session.begin():
            session.add(_batch(batch_id, 4, "selection"))
            session.add_all(
                (
                    _work_order(batch_id, 1, "普通咨询", "咨询办理进度"),
                    _work_order(batch_id, 2, "道路积水", "曾反映道路积水仍未处理"),
                    _work_order(batch_id, 3, "道路积水", "再次反映，原工单号12345"),
                    _work_order(batch_id, 4, "普通建议", "建议增加设施"),
                )
            )
        selected = await repository.select_work_orders(batch_id)
        assert len(selected) == 4
        assert {item.source_row_number for item in selected} == {1, 2, 3, 4}
    finally:
        async with sessions() as session, session.begin():
            await session.execute(delete(ImportBatch).where(ImportBatch.id == batch_id))
        await engine.dispose()


@pytest.mark.asyncio
async def test_catalog_current_pipeline_analysis_state_cluster_undo_and_dedup() -> None:
    engine = create_engine(get_settings())
    sessions = create_session_factory(engine)
    events = SQLAlchemyEventRepository(sessions)
    catalog = SQLAlchemyCatalogRepository(sessions, "understanding.v2")
    review = SQLAlchemyEventReviewRepository(sessions)
    batch_id = uuid4()
    work_order_ids = (uuid4(), uuid4(), uuid4())
    event_ids = (uuid4(), uuid4(), uuid4())
    job_ids: list[UUID] = []
    cluster_id: UUID | None = None
    try:
        async with sessions() as session, session.begin():
            session.add(_batch(batch_id, 3, "catalog"))
            session.add_all(
                (
                    _work_order(batch_id, 1, "（急）道路噪音", "投诉道路噪音", work_order_ids[0]),
                    _work_order(batch_id, 2, "道路噪音", "再次投诉道路噪音", work_order_ids[1]),
                    _work_order(batch_id, 3, "普通咨询", "咨询办理进度", work_order_ids[2]),
                )
            )
            await session.flush()
            session.add_all(
                (
                    _event(event_ids[0], work_order_ids[0], "understanding.v1", 0),
                    _event(event_ids[1], work_order_ids[0], "understanding.v2", 0),
                    _event(event_ids[2], work_order_ids[1], "understanding.v2", 0),
                )
            )

        job_id, run_id = await events.start_run(
            pipeline_version="understanding.v2", schema_version="understanding.v2"
        )
        job_ids.append(job_id)
        async with sessions() as session, session.begin():
            session.add_all(
                (
                    WorkOrderAnalysisResult(
                        work_order_id=work_order_ids[0],
                        analysis_run_id=run_id,
                        pipeline_version="understanding.v2",
                        status="analyzed",
                        event_count=1,
                        analyzed_at=datetime.now(UTC),
                    ),
                    WorkOrderAnalysisResult(
                        work_order_id=work_order_ids[2],
                        analysis_run_id=run_id,
                        pipeline_version="understanding.v2",
                        status="analyzed_no_event",
                        event_count=0,
                        analyzed_at=datetime.now(UTC),
                    ),
                )
            )
        trace = VersionTrace("test", None, "understanding.v2", None, "understanding.v2", "test")
        cluster_id = await events.save_cluster(
            run_id,
            (EventInstanceId(event_ids[1]), EventInstanceId(event_ids[2])),
            name="道路噪音重复反映",
            confidence=0.9,
            evidence={"same_issue": True},
            trace=trace,
            pipeline_version="understanding.v2",
            schema_version="understanding.v2",
        )

        detail = await catalog.get_work_order(work_order_ids[0])
        assert detail is not None
        assert [item.trace.pipeline_version for item in detail.events] == ["understanding.v2"]
        assert detail.summary.event_count == 1
        assert detail.summary.analysis_state == "analyzed"
        assert detail.summary.title_tags == ("急",)
        assert detail.summary.is_urgent is True
        assert detail.cluster_refs[0].cluster_id == cluster_id

        no_event = await catalog.get_work_order(work_order_ids[2])
        assert no_event is not None
        assert no_event.summary.analysis_state == "analyzed_no_event"
        assert no_event.summary.event_count == 0
        unprocessed = await catalog.get_work_order(work_order_ids[1])
        assert unprocessed is not None
        assert unprocessed.summary.analysis_state == "unprocessed"

        filtered, total = await catalog.list_work_orders(
            offset=0,
            limit=10,
            query=None,
            analysis_state="analyzed",
            event_type="noise",
            title_tag="急",
        )
        assert total == 1
        assert filtered[0].work_order_id == work_order_ids[0]

        await review.add_correction(
            cluster_id,
            correction_type="remove_member",
            event_instance_id=event_ids[2],
            actor_id="reviewer",
            reason="误操作回归",
        )
        listed, total = await catalog.list_clusters(offset=0, limit=20)
        assert cluster_id not in {item.cluster_id for item in listed}
        inactive = await catalog.get_cluster(cluster_id)
        assert inactive is not None
        assert inactive.summary.is_multi_frequency is False
        assert inactive.human_corrections[-1].correction_type == "remove_member"
        assert len(inactive.removed_members) == 1
        assert inactive.removed_members[0].event is not None
        assert inactive.removed_members[0].event.event.event_id == event_ids[2]
        assert inactive.removed_members[0].can_restore is True

        with pytest.raises(ValueError, match="already a member"):
            await review.add_correction(
                cluster_id,
                correction_type="confirm_member",
                event_instance_id=event_ids[1],
                actor_id="reviewer",
                reason="重复恢复不应被接受",
            )

        await review.add_correction(
            cluster_id,
            correction_type="confirm_member",
            event_instance_id=event_ids[2],
            actor_id="reviewer",
            reason="撤销误移除",
        )
        restored = await catalog.get_cluster(cluster_id)
        assert restored is not None
        assert restored.removed_members == ()
        assert [item.correction_type for item in restored.human_corrections[-2:]] == [
            "remove_member",
            "confirm_member",
        ]
        async with sessions() as session:
            correction_audits = int(
                await session.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.target_id == str(cluster_id),
                        AuditLog.action.in_(
                            ["event_cluster.remove_member", "event_cluster.confirm_member"]
                        ),
                    )
                )
                or 0
            )
        assert correction_audits == 2
        listed, total = await catalog.list_clusters(offset=0, limit=20)
        assert cluster_id in {item.cluster_id for item in listed}

        second_job_id, second_run_id = await events.start_run(
            pipeline_version="understanding.v2", schema_version="understanding.v2"
        )
        job_ids.append(second_job_id)
        duplicate = await events.save_cluster(
            second_run_id,
            (EventInstanceId(event_ids[2]), EventInstanceId(event_ids[1])),
            name="重复运行不应新建",
            confidence=0.91,
            evidence={"same_issue": True},
            trace=trace,
            pipeline_version="understanding.v2",
            schema_version="understanding.v2",
        )
        assert duplicate == cluster_id

        changed = await review.set_review_status(
            cluster_id,
            review_status="confirmed",
            actor_id="reviewer",
            reason="证据已核对",
        )
        assert changed.previous_status == "pending_review"
        assert changed.review_status == "confirmed"
        async with sessions() as session:
            audit_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.target_id == str(cluster_id),
                        AuditLog.action == "event_cluster.review_status_changed",
                    )
                )
                or 0
            )
        assert audit_count == 1
    finally:
        async with sessions() as session, session.begin():
            if cluster_id is not None:
                await session.execute(delete(EventCluster).where(EventCluster.id == cluster_id))
            if job_ids:
                await session.execute(delete(AnalysisJob).where(AnalysisJob.id.in_(job_ids)))
            await session.execute(delete(ImportBatch).where(ImportBatch.id == batch_id))
        await engine.dispose()


def _batch(batch_id: UUID, rows: int, suffix: str) -> ImportBatch:
    return ImportBatch(
        id=batch_id,
        source_filename=f"product-{suffix}.xlsx",
        source_sha256=uuid4().hex + uuid4().hex,
        source_size_bytes=1,
        field_mapping={},
        total_rows=rows,
        successful_rows=rows,
        failed_rows=0,
        duplicate_rows=0,
        checkpoint_row=rows,
        status="completed",
    )


def _work_order(
    batch_id: UUID,
    row: int,
    title: str,
    content: str,
    work_order_id: UUID | None = None,
) -> WorkOrder:
    return WorkOrder(
        id=work_order_id or uuid4(),
        import_batch_id=batch_id,
        source_row_number=row,
        external_work_order_number=f"WO-{row}-{uuid4().hex[:6]}",
        raw_title=title,
        raw_content=content,
        raw_fields={"标题": title},
        raw_sha256=uuid4().hex + uuid4().hex,
    )


def _event(event_id: UUID, work_order_id: UUID, pipeline: str, ordinal: int) -> EventInstance:
    return EventInstance(
        id=event_id,
        work_order_id=work_order_id,
        ordinal=ordinal,
        event_type="noise",
        behavior=None,
        normalized_summary="道路噪音",
        entity_ids=[],
        location_signals=[],
        time_signals=["2025年1月3日"],
        occurrence_date=None,
        evidence={},
        model_id="test",
        model_config_hash=None,
        schema_version=pipeline,
        knowledge_snapshot_id=None,
        pipeline_version=pipeline,
    )
