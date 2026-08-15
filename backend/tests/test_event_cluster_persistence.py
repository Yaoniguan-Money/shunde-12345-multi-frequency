from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import get_settings
from backend.app.domain.types import EventInstanceId, VersionTrace
from backend.app.infrastructure.db.catalog import SQLAlchemyCatalogRepository
from backend.app.infrastructure.db.events import SQLAlchemyEventRepository
from backend.app.infrastructure.db.models import (
    AnalysisJob,
    EventCluster,
    EventInstance,
    ImportBatch,
    WorkOrder,
)
from backend.app.infrastructure.db.session import create_engine, create_session_factory


async def test_cluster_repository_rejects_members_from_only_one_work_order() -> None:
    engine = create_engine(get_settings())
    session_factory = create_session_factory(engine)
    repository = SQLAlchemyEventRepository(session_factory)
    batch_id = uuid4()
    work_order_id = uuid4()
    event_ids = (uuid4(), uuid4())
    job_id: UUID | None = None
    created_cluster_id: UUID | None = None
    rejected = False
    try:
        try:
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        ImportBatch(
                            id=batch_id,
                            source_filename="cluster-invariant-test.xlsx",
                            source_sha256=uuid4().hex + uuid4().hex,
                            source_size_bytes=1,
                            field_mapping={},
                            total_rows=1,
                            successful_rows=1,
                            failed_rows=0,
                            duplicate_rows=0,
                            checkpoint_row=1,
                            status="completed",
                        )
                    )
                    session.add(
                        WorkOrder(
                            id=work_order_id,
                            import_batch_id=batch_id,
                            source_row_number=1,
                            raw_title=None,
                            raw_content="同一工单包含两个AI事件",
                            raw_fields={},
                            raw_sha256=uuid4().hex + uuid4().hex,
                        )
                    )
                    await session.flush()
                    session.add_all(
                        EventInstance(
                            id=event_id,
                            work_order_id=work_order_id,
                            ordinal=ordinal,
                            event_type="noise",
                            behavior=None,
                            normalized_summary=f"事件{ordinal}",
                            entity_ids=[],
                            location_signals=[],
                            time_signals=[],
                            evidence={},
                            model_id="test",
                            model_config_hash=None,
                            schema_version="test.v1",
                            knowledge_snapshot_id=None,
                            pipeline_version="test.v1",
                        )
                        for ordinal, event_id in enumerate(event_ids)
                    )
            job_id, run_id = await repository.start_run(
                pipeline_version="test-cross-work-order.v1",
                schema_version="test.v1",
            )
            trace = VersionTrace("test", None, "test.v1", None, "test.v1", "test")
            try:
                created_cluster_id = await repository.save_cluster(
                    run_id,
                    tuple(EventInstanceId(event_id) for event_id in event_ids),
                    name="invalid single-work-order cluster",
                    confidence=0.99,
                    evidence={"same_issue": True},
                    trace=trace,
                    pipeline_version="test.v1",
                    schema_version="test.v1",
                )
            except ValueError:
                rejected = True
        except (OSError, SQLAlchemyError) as error:
            pytest.skip(f"PostgreSQL not available; cluster invariant deferred: {error}")

        assert rejected, "repository persisted a cluster with only one distinct work order"
    finally:
        try:
            async with session_factory() as session:
                async with session.begin():
                    if created_cluster_id is not None:
                        await session.execute(
                            delete(EventCluster).where(EventCluster.id == created_cluster_id)
                        )
                    await session.execute(delete(ImportBatch).where(ImportBatch.id == batch_id))
                    if job_id is not None:
                        await session.execute(delete(AnalysisJob).where(AnalysisJob.id == job_id))
        except (OSError, SQLAlchemyError):
            pass
        await engine.dispose()


async def test_catalog_counts_distinct_work_orders_and_groups_member_events() -> None:
    engine = create_engine(get_settings())
    session_factory = create_session_factory(engine)
    event_repository = SQLAlchemyEventRepository(session_factory)
    catalog = SQLAlchemyCatalogRepository(session_factory)
    batch_id = uuid4()
    work_order_ids = (uuid4(), uuid4())
    event_ids = (uuid4(), uuid4(), uuid4())
    job_id: UUID | None = None
    cluster_id: UUID | None = None
    try:
        try:
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        ImportBatch(
                            id=batch_id,
                            source_filename="cluster-catalog-test.xlsx",
                            source_sha256=uuid4().hex + uuid4().hex,
                            source_size_bytes=1,
                            field_mapping={},
                            total_rows=2,
                            successful_rows=2,
                            failed_rows=0,
                            duplicate_rows=0,
                            checkpoint_row=2,
                            status="completed",
                        )
                    )
                    session.add_all(
                        WorkOrder(
                            id=work_order_id,
                            import_batch_id=batch_id,
                            source_row_number=index,
                            external_work_order_number=f"WO-{index}",
                            raw_title="商业噪声",
                            raw_content=f"第{index}张工单原文",
                            raw_fields={"工单编号": f"WO-{index}"},
                            raw_sha256=uuid4().hex + uuid4().hex,
                        )
                        for index, work_order_id in enumerate(work_order_ids, start=1)
                    )
                    await session.flush()
                    session.add_all(
                        EventInstance(
                            id=event_id,
                            work_order_id=work_order_id,
                            ordinal=ordinal,
                            event_type="noise",
                            behavior=None,
                            normalized_summary=summary,
                            entity_ids=[],
                            location_signals=["同一地点"],
                            time_signals=[],
                            evidence={},
                            model_id="test",
                            model_config_hash=None,
                            schema_version="test.v1",
                            knowledge_snapshot_id=None,
                            pipeline_version="test.v1",
                        )
                        for event_id, work_order_id, ordinal, summary in (
                            (event_ids[0], work_order_ids[0], 0, "商业噪声"),
                            (event_ids[1], work_order_ids[0], 1, "要求关停音响"),
                            (event_ids[2], work_order_ids[1], 0, "再次反映商业噪声"),
                        )
                    )
            job_id, run_id = await event_repository.start_run(
                pipeline_version="test-catalog-counts.v1",
                schema_version="test.v1",
            )
            trace = VersionTrace("test", None, "test.v1", None, "test.v1", "test")
            cluster_id = await event_repository.save_cluster(
                run_id,
                tuple(EventInstanceId(event_id) for event_id in event_ids),
                name="valid two-work-order cluster",
                confidence=0.95,
                evidence={"same_issue": True},
                trace=trace,
                pipeline_version="test.v1",
                schema_version="test.v1",
            )
            detail = await catalog.get_cluster(cluster_id)
        except (OSError, SQLAlchemyError) as error:
            pytest.skip(f"PostgreSQL not available; catalog invariant deferred: {error}")

        assert detail is not None
        assert detail.summary.member_count == 2
        assert detail.summary.work_order_count == 2
        assert detail.summary.event_count == 3
        assert len(detail.work_orders) == 2
        assert sorted(len(item.events) for item in detail.work_orders) == [1, 2]
    finally:
        try:
            async with session_factory() as session:
                async with session.begin():
                    if cluster_id is not None:
                        await session.execute(
                            delete(EventCluster).where(EventCluster.id == cluster_id)
                        )
                    await session.execute(delete(ImportBatch).where(ImportBatch.id == batch_id))
                    if job_id is not None:
                        await session.execute(delete(AnalysisJob).where(AnalysisJob.id == job_id))
        except (OSError, SQLAlchemyError):
            pass
        await engine.dispose()
