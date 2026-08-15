"""Safely repair derived entity references and explicit occurrence dates; never raw work orders."""

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.config import get_settings
from backend.app.domain.time_normalization import occurrence_date_from_signals
from backend.app.infrastructure.db.models import (
    AnalysisRun,
    CanonicalEntity,
    EventInstance,
    WorkOrderAnalysisResult,
)
from backend.app.infrastructure.db.session import create_engine, create_session_factory


async def main() -> None:
    engine = create_engine(get_settings())
    sessions = create_session_factory(engine)
    repaired_entities = 0
    repaired_dates = 0
    backfilled_outcomes = 0
    try:
        async with sessions() as session, session.begin():
            valid_ids = set((await session.scalars(select(CanonicalEntity.id))).all())
            events = (await session.scalars(select(EventInstance))).all()
            run_ids = set((await session.scalars(select(AnalysisRun.id))).all())
            outcome_counts: dict[tuple[UUID, UUID, str], int] = {}
            for event in events:
                raw_entity_ids = cast(list[object], event.entity_ids or [])
                filtered = [
                    str(entity_id)
                    for value in raw_entity_ids
                    if (entity_id := _uuid(value)) is not None and entity_id in valid_ids
                ]
                if filtered != raw_entity_ids:
                    event.entity_ids = filtered
                    repaired_entities += 1
                signals = tuple(
                    str(value) for value in cast(list[object], event.time_signals or [])
                )
                occurrence_date = occurrence_date_from_signals(signals)
                if event.occurrence_date != occurrence_date:
                    event.occurrence_date = occurrence_date
                    repaired_dates += 1
                evidence = cast(dict[str, object], event.evidence or {})
                run_id = _uuid(evidence.get("analysis_run_id"))
                if run_id is not None and run_id in run_ids:
                    key = (event.work_order_id, run_id, event.pipeline_version)
                    outcome_counts[key] = outcome_counts.get(key, 0) + 1
            for (work_order_id, run_id, pipeline_version), event_count in outcome_counts.items():
                result = await session.execute(
                    pg_insert(WorkOrderAnalysisResult)
                    .values(
                        work_order_id=work_order_id,
                        analysis_run_id=run_id,
                        pipeline_version=pipeline_version,
                        status="analyzed",
                        event_count=event_count,
                        analyzed_at=datetime.now(UTC),
                    )
                    .on_conflict_do_nothing(constraint="uq_work_order_analysis_result_run")
                )
                backfilled_outcomes += result.rowcount or 0
        print(
            f"event semantic repair complete: entity_rows={repaired_entities}, "
            f"occurrence_dates={repaired_dates}, outcomes={backfilled_outcomes}"
        )
    finally:
        await engine.dispose()


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    asyncio.run(main())
