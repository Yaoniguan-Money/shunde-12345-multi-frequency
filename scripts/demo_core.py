"""Run the small, real cloud-first Demo Core event graph.

The selector is intentionally query-driven: it discovers the known Shunde anchor
and hard-negative examples from PostgreSQL instead of embedding IDs in code. Only
the selected demo rows are sent to the explicitly configured remote providers.
"""

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import and_, not_, or_, select

from backend.app.application.services.analysis import DemoAnalysisOrchestrator
from backend.app.config import get_settings
from backend.app.domain.analysis_jobs import WorkOrderSource
from backend.app.domain.types import VersionTrace
from backend.app.infrastructure.db.models import WorkOrder
from backend.app.infrastructure.db.session import create_engine, create_session_factory


@dataclass(frozen=True, slots=True)
class DemoSample:
    work_order_id: UUID
    source_row_number: int
    raw_title: str | None
    label: str


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-limit", type=int, default=8)
    parser.add_argument("--candidate-limit", type=int, default=8)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


async def _select_samples(session_factory, anchor_limit: int) -> tuple[DemoSample, ...]:
    if anchor_limit < 3:
        raise ValueError("anchor-limit must be at least 3")
    selected: dict[UUID, DemoSample] = {}

    async with session_factory() as session:
        anchor_rows = (
            await session.scalars(
                select(WorkOrder)
                .where(
                    WorkOrder.raw_content.ilike("%新桂北路29号116号铺%"),
                    or_(
                        WorkOrder.raw_content.ilike("%恒艺工作室%"),
                        WorkOrder.raw_content.ilike("%恒艺音乐%"),
                    ),
                )
                .order_by(WorkOrder.source_row_number)
                .limit(anchor_limit)
            )
        ).all()
        if len(anchor_rows) < 3:
            raise RuntimeError("real Demo anchor has fewer than three matching work orders")
        for row in anchor_rows:
            selected[row.id] = DemoSample(
                row.id, row.source_row_number, row.raw_title, "恒艺_anchor"
            )

        negative_queries = (
            (
                "different_location_noise",
                and_(
                    WorkOrder.raw_content.ilike("%商业噪音%"),
                    not_(WorkOrder.raw_content.ilike("%新桂北路29号116号铺%")),
                ),
            ),
            (
                "same_subject_noise",
                and_(
                    WorkOrder.raw_content.ilike("%万民金海城%"),
                    WorkOrder.raw_title.ilike("%商业噪音%"),
                ),
            ),
            (
                "same_subject_different_issue",
                and_(
                    WorkOrder.raw_content.ilike("%万民金海城%"),
                    WorkOrder.raw_title.ilike("%消防设施%"),
                ),
            ),
        )
        for label, predicate in negative_queries:
            row = await session.scalar(
                select(WorkOrder).where(predicate).order_by(WorkOrder.source_row_number).limit(1)
            )
            if row is not None:
                selected.setdefault(
                    row.id,
                    DemoSample(row.id, row.source_row_number, row.raw_title, label),
                )
    return tuple(sorted(selected.values(), key=lambda item: item.source_row_number))


def _trace_dict(trace: VersionTrace) -> dict[str, object]:
    return {
        "provider": trace.provider,
        "model_id": trace.model_id,
        "model_config_hash": trace.model_config_hash,
        "schema_version": trace.schema_version,
        "pipeline_version": trace.pipeline_version,
    }


async def main() -> None:
    args = _args()
    settings = get_settings()
    if settings.ai_provider_mode.value != "remote":
        raise RuntimeError("Demo Core requires explicit SHUNDE_AI_PROVIDER_MODE=remote")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        samples = await _select_samples(session_factory, args.anchor_limit)
        orchestrator = await DemoAnalysisOrchestrator.create(settings, session_factory)
        async with session_factory() as session:
            work_orders = (
                await session.scalars(
                    select(WorkOrder).where(
                        WorkOrder.id.in_([sample.work_order_id for sample in samples])
                    )
                )
            ).all()
        by_id = {row.id: row for row in work_orders}
        if len(by_id) != len(samples):
            raise RuntimeError("selected demo work orders disappeared before processing")
        execution = await orchestrator.run_selected(
            tuple(
                WorkOrderSource(
                    sample.work_order_id,
                    sample.source_row_number,
                    by_id[sample.work_order_id].raw_title,
                    by_id[sample.work_order_id].raw_content,
                )
                for sample in samples
            ),
            candidate_limit=args.candidate_limit,
        )
        event_views = {
            event_id: await orchestrator.event_repository.get_for_matching(event_id)
            for event_id in execution.event_ids
        }
        labels = {sample.work_order_id: sample.label for sample in samples}
        decisions = []
        for edge in execution.decisions:
            left = event_views[edge.left_event_id]
            right = event_views[edge.right_event_id]
            if left is None or right is None:
                continue
            decisions.append(
                {
                    "left_event_id": str(edge.left_event_id),
                    "right_event_id": str(edge.right_event_id),
                    "left_work_order_id": str(left.work_order_id),
                    "right_work_order_id": str(right.work_order_id),
                    "left_label": labels.get(left.work_order_id),
                    "right_label": labels.get(right.work_order_id),
                    "same_event": edge.same_event,
                    "confidence": edge.confidence,
                    "evidence": asdict(edge.evidence),
                    "trace": _trace_dict(edge.trace),
                }
            )
        positive = [item for item in decisions if item["same_event"]]
        negative = [item for item in decisions if not item["same_event"]]
        if not execution.cluster_ids:
            raise RuntimeError("Demo Core produced no positive event cluster")
        output_path = args.output or Path(
            f"data/runtime/demo/demo-core-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "status": "ready",
            "created_at": datetime.now(UTC).isoformat(),
            "provider_health": orchestrator.provider_health,
            "pipeline": {
                "understanding": settings.analysis_pipeline_version,
                "embedding_model": orchestrator.providers.plan.remote_embedding.model_id
                if orchestrator.providers.plan.remote_embedding
                else None,
                "embedding_dimensions": execution.embedding_dimensions,
                "same_event": "demo-same-event.v1",
            },
            "selected_work_orders": [
                {
                    "work_order_id": str(sample.work_order_id),
                    "source_row_number": sample.source_row_number,
                    "raw_title": sample.raw_title,
                    "label": sample.label,
                }
                for sample in samples
            ],
            "event_ids": [str(event_id) for event_id in execution.event_ids],
            "decisions": decisions,
            "positive_edge_count": len(positive),
            "negative_edge_count": len(negative),
            "cluster_ids": [str(cluster_id) for cluster_id in execution.cluster_ids],
            "hard_negative_candidates": negative,
            "raw_text_note": "原始标题/正文保留在 PostgreSQL API；artifact 不复制正文。",
        }
        output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(artifact, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
