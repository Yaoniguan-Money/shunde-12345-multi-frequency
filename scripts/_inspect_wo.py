# This is a user-owned, read-only maintenance helper.
# ruff: noqa: E501
import asyncio

from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.infrastructure.db.session import create_engine, create_session_factory

FAIL_BATCH = "224a3f34-408e-442e-b8bf-d766ed3aedbf"


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as s:
        # 引用 work_orders 的外键
        res = await s.execute(
            text(
                "select tc.table_name, kcu.column_name, ccu.table_name as ref_table, ccu.column_name as ref_col "
                "from information_schema.table_constraints tc "
                "join information_schema.key_column_usage kcu on tc.constraint_name=kcu.constraint_name "
                "join information_schema.constraint_column_usage ccu on tc.constraint_name=ccu.constraint_name "
                "where tc.constraint_type='FOREIGN KEY' and ccu.table_name='work_orders'"
            )
        )
        print("FKs referencing work_orders:", [tuple(r) for r in res.all()])

        # import_batches 表
        try:
            res = await s.execute(text("select count(*) from import_batches"))
            print("import_batches total:", res.scalar())
        except Exception as ex:
            print("import_batches ERROR:", ex)

        # failed batch 内工单是否被 event_instances 引用
        res = await s.execute(
            text(
                "select count(*) from event_instances e join work_orders w on e.work_order_id=w.id "
                "where w.import_batch_id=:b"
            ),
            {"b": FAIL_BATCH},
        )
        print("event_instances referencing failed-batch work orders:", res.scalar())

        # failed batch 工单数
        res = await s.execute(
            text("select count(*) from work_orders where import_batch_id=:b"), {"b": FAIL_BATCH}
        )
        print("failed-batch work orders:", res.scalar())

        # work_orders 自身被引用自 import_batches 的情况
        res = await s.execute(
            text(
                "select column_name, data_type from information_schema.columns where table_name='import_batches' order by ordinal_position"
            )
        )
        print("import_batches columns:", [tuple(r) for r in res.all()])


asyncio.run(main())
