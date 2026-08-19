from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import get_settings
from backend.app.infrastructure.db.agent import AgentRepository
from backend.app.infrastructure.db.models import EventInstance, ImportBatch, WorkOrder
from backend.app.infrastructure.db.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_explicit_issue_gate_keeps_only_location_and_issue_intersection() -> None:
    """A place scope must not fill the limit with unrelated local complaints."""
    engine = create_engine(get_settings())
    sessions = create_session_factory(engine)
    batch_id = uuid4()
    now = datetime.now(UTC)
    cases = (
        (
            "测试大良甲拖欠工资",
            "测试大良甲中通仓库拖欠司机工资约7500元",
            "拖欠工资",
            "测试大良甲",
            now,
        ),
        ("【急】测试大良甲噪声", "测试大良甲小区夜间噪声扰民", "噪音扰民", "测试大良甲", now),
        ("测试大良甲垃圾", "测试大良甲街边垃圾未清理", "垃圾堆放", "测试大良甲", now),
        ("测试大良甲占道", "测试大良甲商户占道经营", "占道经营", "测试大良甲", now),
        ("测试大良甲时间未知", "测试大良甲历史投诉，业务受理时间缺失", "咨询", "测试大良甲", None),
        ("测试容桂乙欠薪", "测试容桂乙工地工资一直没有结清", "欠薪", "测试容桂乙", now),
    )
    try:
        try:
            async with sessions() as session, session.begin():
                session.add(
                    ImportBatch(
                        id=batch_id,
                        source_filename="agent-retrieval-contract.xlsx",
                        source_sha256=uuid4().hex + uuid4().hex,
                        source_size_bytes=1,
                        field_mapping={},
                        total_rows=len(cases),
                        successful_rows=len(cases),
                        failed_rows=0,
                        duplicate_rows=0,
                        checkpoint_row=len(cases),
                        status="completed",
                    )
                )
                work_orders: list[WorkOrder] = []
                for index, (title, content, _event_type, _location, reported_at) in enumerate(
                    cases, 1
                ):
                    work_order = WorkOrder(
                        id=uuid4(),
                        import_batch_id=batch_id,
                        source_row_number=index,
                        raw_title=title,
                        raw_content=content,
                        raw_fields={},
                        raw_sha256=uuid4().hex + uuid4().hex,
                        reported_at=reported_at,
                    )
                    work_orders.append(work_order)
                    session.add(work_order)
                await session.flush()
                session.add_all(
                    EventInstance(
                        id=uuid4(),
                        work_order_id=work_order.id,
                        ordinal=0,
                        event_type=event_type,
                        behavior=None,
                        normalized_summary=content,
                        entity_ids=[],
                        location_signals=[location],
                        time_signals=[],
                        evidence={},
                        model_id="test-agent",
                        model_config_hash=None,
                        schema_version="understanding.v2",
                        knowledge_snapshot_id=None,
                        pipeline_version="understanding.v2",
                    )
                    for work_order, (_, content, event_type, location, _) in zip(
                        work_orders, cases, strict=True
                    )
                )
        except (OSError, SQLAlchemyError) as error:
            pytest.skip(f"PostgreSQL not available; Agent retrieval contract deferred: {error}")

        repository = AgentRepository(sessions)
        result = await repository.retrieve(
            keywords=("工资", "欠薪", "薪资", "劳务费", "拖欠", "结清", "未支付", "劳动报酬"),
            issue_terms=("工资", "欠薪", "薪资", "劳务费", "拖欠", "结清", "未支付", "劳动报酬"),
            issue_required=True,
            entity=None,
            location="测试大良甲",
            event_type=None,
            title_tag=None,
            work_order_ids=(),
            handling_status=None,
            reported_after=None,
            reported_before=None,
            limit=20,
            semantic_vector=None,
            semantic_model_id=None,
        )
        assert len(result) == 1
        assert result[0]["title"] == "测试大良甲拖欠工资"

        broad = await repository.retrieve(
            keywords=(),
            issue_terms=(),
            issue_required=False,
            entity=None,
            location="测试大良甲",
            event_type=None,
            title_tag=None,
            work_order_ids=(),
            handling_status=None,
            reported_after=None,
            reported_before=None,
            limit=20,
            semantic_vector=None,
            semantic_model_id=None,
        )
        assert {item["title"] for item in broad} == {
            "测试大良甲拖欠工资",
            "【急】测试大良甲噪声",
            "测试大良甲垃圾",
            "测试大良甲占道",
            "测试大良甲时间未知",
        }

        cross_location = await repository.retrieve(
            keywords=("工资", "欠薪", "薪资", "劳务费", "拖欠", "结清", "未支付", "劳动报酬"),
            issue_terms=("工资", "欠薪", "薪资", "劳务费", "拖欠", "结清", "未支付", "劳动报酬"),
            issue_required=True,
            entity=None,
            location=None,
            event_type=None,
            title_tag=None,
            work_order_ids=tuple(work_order.id for work_order in work_orders),
            handling_status=None,
            reported_after=None,
            reported_before=None,
            limit=20,
            semantic_vector=None,
            semantic_model_id=None,
        )
        assert {item["title"] for item in cross_location} == {
            "测试大良甲拖欠工资",
            "测试容桂乙欠薪",
        }

        recent = await repository.retrieve(
            keywords=(),
            issue_terms=(),
            issue_required=False,
            entity=None,
            location="测试大良甲",
            event_type=None,
            title_tag=None,
            work_order_ids=(),
            handling_status=None,
            reported_after=now - timedelta(days=1),
            reported_before=now + timedelta(days=1),
            limit=20,
            semantic_vector=None,
            semantic_model_id=None,
        )
        assert len(recent) == 4

        urgent = await repository.retrieve(
            keywords=(),
            issue_terms=(),
            issue_required=False,
            entity=None,
            location="测试大良甲",
            event_type=None,
            title_tag="急",
            work_order_ids=(),
            handling_status=None,
            reported_after=None,
            reported_before=None,
            limit=None,
            semantic_vector=None,
            semantic_model_id=None,
            complete_scope=True,
        )
        assert [item["title"] for item in urgent] == ["【急】测试大良甲噪声"]
    finally:
        try:
            async with sessions() as session, session.begin():
                await session.execute(delete(ImportBatch).where(ImportBatch.id == batch_id))
        except (OSError, SQLAlchemyError):
            pass
        await engine.dispose()
