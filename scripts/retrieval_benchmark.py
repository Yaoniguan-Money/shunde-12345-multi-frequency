"""Benchmark pgvector retrieval without inventing quality labels."""

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.domain.types import RetrievalQuery, WorkOrderId
from backend.app.infrastructure.ai.factory import build_provider_bundle
from backend.app.infrastructure.db.models import EventInstance, WorkOrderEmbedding
from backend.app.infrastructure.db.retrieval import PostgresCandidateRetriever
from backend.app.infrastructure.db.session import create_engine, create_session_factory


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-model", default=os.environ.get("SHUNDE_EMBEDDING_MODEL_ID"))
    parser.add_argument("--profile", choices=("1000", "10000", "full"), default="1000")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--gold-set", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _hardware() -> dict[str, str]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        output = "unavailable"
    return {"gpu": output}


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(percentile) - 1]


def _quality(
    gold_path: Path | None,
    results: dict[str, tuple[UUID, ...]],
    k: int,
) -> dict[str, object] | None:
    if gold_path is None:
        return None
    payload = json.loads(gold_path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not cases:
        raise ValueError("gold set must contain at least one case")
    hits = 0
    relevant = 0
    retrieved = 0
    for case in cases:
        query_id = str(case["query_event_id"])
        relevant_ids = {str(value) for value in case["relevant_event_ids"]}
        candidates = {str(value) for value in results.get(query_id, ())[:k]}
        hits += len(candidates & relevant_ids)
        relevant += len(relevant_ids)
        retrieved += len(candidates)
    return {
        "gold_set": str(gold_path),
        "cases": len(cases),
        "recall_at_k": hits / relevant if relevant else None,
        "precision_at_k": hits / retrieved if retrieved else None,
    }


async def main() -> None:
    args = _args()
    settings = get_settings()
    providers = build_provider_bundle(
        settings,
        embedding_model_override=args.embedding_model,
    )
    await providers.embeddings.health()
    active_embedding = (
        providers.plan.remote_embedding
        if providers.mode.value == "remote"
        else providers.plan.local_embedding
    )
    if active_embedding is None:
        raise RuntimeError("active embedding provider is not configured")
    provider = providers.embeddings
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            statement = (
                select(
                    EventInstance.id,
                    EventInstance.work_order_id,
                    EventInstance.normalized_summary,
                )
                .join(
                    WorkOrderEmbedding,
                    WorkOrderEmbedding.event_instance_id == EventInstance.id,
                )
                .where(WorkOrderEmbedding.model_id == active_embedding.model_id)
                .order_by(EventInstance.created_at, EventInstance.id)
            )
            if args.profile != "full":
                statement = statement.limit(int(args.profile))
            rows = (await session.execute(statement)).all()
        retriever = PostgresCandidateRetriever(
            session_factory, provider, model_id=active_embedding.model_id
        )
        latencies: list[float] = []
        retrieval_results: dict[str, tuple[UUID, ...]] = {}
        started = time.perf_counter()
        for event_id, work_order_id, summary in rows:
            query_started = time.perf_counter()
            candidates = await retriever.retrieve(
                RetrievalQuery(
                    event_id,
                    WorkOrderId(work_order_id),
                    (),
                    (),
                    None,
                    summary,
                    args.k,
                )
            )
            latencies.append((time.perf_counter() - query_started) * 1000)
            retrieval_results[str(event_id)] = tuple(candidate.event_id for candidate in candidates)
        elapsed = time.perf_counter() - started
        output = {
            "created_at": datetime.now(UTC).isoformat(),
            "profile": args.profile,
            "rows": len(rows),
            "k": args.k,
            "embedding_model": active_embedding.model_id,
            "hardware": _hardware(),
            "throughput_queries_per_second": len(rows) / elapsed if elapsed else 0.0,
            "latency_ms": {
                "p50": _percentile(latencies, 50),
                "p95": _percentile(latencies, 95),
                "max": max(latencies) if latencies else 0.0,
            },
            "quality": _quality(args.gold_set, retrieval_results, args.k),
            "quality_note": (
                "quality is omitted unless a named business-approved Gold Set is supplied"
            ),
        }
        output_path = args.output or Path(
            f"data/runtime/benchmarks/retrieval-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(output, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
