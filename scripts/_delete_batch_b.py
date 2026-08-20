# This is a user-owned, manually reviewed maintenance helper; its synchronous
# backup operations intentionally run inside an async database workflow.
# ruff: noqa: ASYNC230, ASYNC240, E501
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.infrastructure.db.session import create_engine, create_session_factory

FAIL_BATCH = "224a3f34-408e-442e-b8bf-d766ed3aedbf"
CHILD_TABLES = [
    "work_order_analysis_results",
    "complaint_segments",
    "event_instances",
    "human_corrections",
    "entity_mentions",
    "work_order_embeddings",
]


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    backup_dir = Path("./data/runtime")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_csv = backup_dir / f"batch_b_backup_{FAIL_BATCH[:8]}.csv"

    async with factory() as s:
        # 1. 核查工单数
        n = await s.scalar(
            text("select count(*) from work_orders where import_batch_id=:b"), {"b": FAIL_BATCH}
        )
        print(f"target work orders: {n}")

        # 2. 核查子表引用（work_order_analysis_results 会随工单一并删除，不作为中止条件）
        total_refs = 0
        for t in CHILD_TABLES:
            try:
                c = await s.scalar(
                    text(
                        f"select count(*) from {t} e join work_orders w on e.work_order_id=w.id "
                        "where w.import_batch_id=:b"
                    ),
                    {"b": FAIL_BATCH},
                )
                print(f"  {t}: {c} refs")
                if t != "work_order_analysis_results":
                    total_refs += c
            except Exception as ex:
                print(f"  {t}: ERROR {ex}")
                sys.exit(2)

        if total_refs > 0:
            print(f"ABORT: {total_refs} child refs found; refusing to delete")
            sys.exit(3)

        # 3. 备份（工单关键字段）
        rows = (
            await s.execute(
                text(
                    "select external_work_order_number, raw_sha256, raw_title from work_orders "
                    "where import_batch_id=:b order by source_row_number"
                ),
                {"b": FAIL_BATCH},
            )
        ).all()
        with open(backup_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["external_work_order_number", "raw_sha256", "raw_title"])
            w.writerows(r for r in rows)
        print(f"backup written: {backup_csv} ({len(rows)} rows)")

        # 4. 独立连接 + 事务内删除
        async with engine.begin() as conn:
            r = await conn.execute(
                text(
                    "delete from work_order_analysis_results where work_order_id in "
                    "(select id from work_orders where import_batch_id=:b)"
                ),
                {"b": FAIL_BATCH},
            )
            print(f"deleted work_order_analysis_results: {r.rowcount}")
            r = await conn.execute(
                text("delete from analysis_jobs where idempotency_key like :p"),
                {"p": f"analysis:{FAIL_BATCH}%"},
            )
            print(f"deleted analysis_jobs: {r.rowcount}")
            r = await conn.execute(
                text("delete from work_orders where import_batch_id=:b"), {"b": FAIL_BATCH}
            )
            print(f"deleted work_orders: {r.rowcount}")
            r = await conn.execute(
                text("delete from import_batches where id=:b"), {"b": FAIL_BATCH}
            )
            print(f"deleted import_batches: {r.rowcount}")

    # 5. 复核
    async with factory() as s:
        print("work_orders remaining:", await s.scalar(text("select count(*) from work_orders")))
        print(
            "import_batches remaining:", await s.scalar(text("select count(*) from import_batches"))
        )
        print(
            "analysis_jobs remaining:", await s.scalar(text("select count(*) from analysis_jobs"))
        )
        print(
            "event_instances remaining:",
            await s.scalar(text("select count(*) from event_instances")),
        )


asyncio.run(main())
