"""Compare bounded deterministic selection modes without calling any model."""

import argparse
import asyncio
import json
import re
from collections import Counter

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository
from backend.app.infrastructure.db.models import ImportBatch
from backend.app.infrastructure.db.session import create_engine, create_session_factory

_RECURRENCE = re.compile(r"曾反映|再次反映|多次反映|重复反映")
_REFERENCE = re.compile(r"工单号|诉求编号")


async def main(limit: int) -> None:
    engine = create_engine(get_settings())
    sessions = create_session_factory(engine)
    repository = SQLAlchemyUnderstandingRepository(sessions)
    try:
        async with sessions() as session:
            batch = await session.scalar(
                select(ImportBatch)
                .where(ImportBatch.status.in_(("completed", "partial")))
                .order_by(ImportBatch.created_at.desc())
            )
        if batch is None:
            raise RuntimeError("no completed import batch")
        result: dict[str, object] = {
            "batch_id": str(batch.id),
            "batch_total_rows": batch.total_rows,
            "limit": limit,
        }
        for mode in ("sequential", "recurrence_candidates"):
            rows = await repository.select_work_orders(batch.id, limit, mode)
            titles = Counter(_title_key(row.raw_title) for row in rows if row.raw_title)
            result[mode] = {
                "selected_rows": len(rows),
                "recurrence_keyword_rows": sum(
                    bool(_RECURRENCE.search(row.raw_content)) for row in rows
                ),
                "referenced_number_rows": sum(
                    bool(_REFERENCE.search(row.raw_content)) for row in rows
                ),
                "rows_in_repeated_title_group": sum(
                    titles[_title_key(row.raw_title)] > 1 for row in rows if row.raw_title
                ),
                "source_row_min": min((row.source_row_number for row in rows), default=None),
                "source_row_max": max((row.source_row_number for row in rows), default=None),
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


def _title_key(value: str | None) -> str:
    return re.sub(r"[\s【】\[\]()（）:：,，.!！?？-]", "", (value or "").lower())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, choices=range(1, 301))
    args = parser.parse_args()
    asyncio.run(main(args.limit))
