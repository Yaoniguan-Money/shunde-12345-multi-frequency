"""Generate a human-reviewable AI quality artifact from real imported work orders.

This script deliberately does not create a Gold Set or calculate quality metrics. It
selects a deterministic, weak-label stratified sample, runs the real local/remote/
hybrid provider seam, and writes raw input plus every derived result and trace to a
local JSONL artifact under ``data/runtime`` (which is gitignored).
"""

import argparse
import asyncio
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select, text

from backend.app.application.services.understanding import WorkOrderUnderstandingService
from backend.app.config import get_settings
from backend.app.domain.analysis import ExtractedEvent, ExtractedMention, TextSegment
from backend.app.domain.services.segmentation import RuleBasedWorkOrderSegmenter
from backend.app.domain.types import (
    EmbeddingRequest,
    EmbeddingResult,
    EventInstanceId,
    ProviderMode,
    RetrievalQuery,
    VersionTrace,
    WorkOrderId,
)
from backend.app.infrastructure.ai.factory import AIProviderBundle, build_provider_bundle
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository
from backend.app.infrastructure.db.models import (
    EventInstance,
    ImportBatch,
    WorkOrder,
    WorkOrderEmbedding,
)
from backend.app.infrastructure.db.retrieval import PostgresCandidateRetriever
from backend.app.infrastructure.db.session import create_engine, create_session_factory
from backend.app.infrastructure.knowledge.gazetteer import GazetteerHttpAdapter
from backend.app.infrastructure.knowledge.resolver import RuntimeEntityResolver
from backend.app.infrastructure.knowledge.snapshot import (
    GazetteerSnapshotBuilder,
    RuntimeSnapshotStore,
)


@dataclass(frozen=True, slots=True)
class ReviewSample:
    work_order_id: UUID
    source_row_number: int
    raw_title: str | None
    raw_content: str
    selection_stratum: str


_STRATA: tuple[tuple[str, str | None], ...] = (
    ("recurrence", r"(曾反映|再次反映|多次投诉|重复反映)"),
    ("multi_event_signal", r"(另有|同时|此外|另外|一是|二是|还反映|并且)"),
    (
        "mixed_history_reply",
        r"(历史|此前|之前).{0,80}(部门回复|处理意见|答复).{0,120}(诉求|希望|要求)",
    ),
    ("alias_signal", r"(简称|别名|俗称|又名|旧称)"),
    ("identifier_signal", r"(原工单|工单号|工单编号|诉求编号)"),
    ("general", None),
)
_WEAK_LABEL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("recurrence_language", r"曾反映|再次反映|多次投诉|重复反映"),
    ("history_language", r"历史|此前|之前|原工单"),
    ("department_reply_language", r"部门回复|处理意见|答复"),
    ("multi_event_language", r"另有|同时|此外|另外|一是|二是|还反映|并且"),
    ("alias_language", r"简称|别名|俗称|又名|旧称"),
    ("identifier_language", r"工单号|工单编号|诉求编号"),
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", type=UUID)
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--candidate-limit", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--llm-model")
    parser.add_argument("--embedding-model")
    return parser.parse_args()


async def _latest_batch(session_factory: Any, batch_id: UUID | None) -> ImportBatch:
    async with session_factory() as session:
        if batch_id is not None:
            batch = await session.get(ImportBatch, batch_id)
        else:
            batch = await session.scalar(
                select(ImportBatch)
                .where(ImportBatch.status.in_(("completed", "partial")))
                .order_by(ImportBatch.created_at.desc())
                .limit(1)
            )
        if batch is None:
            raise RuntimeError("no completed import batch found")
        return batch


async def _select_sample(
    session_factory: Any, batch_id: UUID, sample_size: int
) -> tuple[ReviewSample, ...]:
    quota = max(1, (sample_size + len(_STRATA) - 1) // len(_STRATA))
    selected: dict[UUID, ReviewSample] = {}
    async with session_factory() as session:
        for stratum, pattern in _STRATA:
            predicate = "" if pattern is None else "AND raw_content ~ :pattern"
            rows = (
                await session.execute(
                    text(
                        """
                        SELECT id, source_row_number, raw_title, raw_content
                        FROM work_orders
                        WHERE import_batch_id = :batch_id
                        """
                        + predicate
                        + " ORDER BY md5(id::text) LIMIT :limit"
                    ),
                    {
                        "batch_id": batch_id,
                        "pattern": pattern,
                        "limit": min(sample_size * 2, quota * 4),
                    },
                )
            ).mappings()
            for row in rows:
                work_order_id = UUID(str(row["id"]))
                if work_order_id in selected:
                    continue
                selected[work_order_id] = ReviewSample(
                    work_order_id=work_order_id,
                    source_row_number=int(row["source_row_number"]),
                    raw_title=str(row["raw_title"]) if row["raw_title"] is not None else None,
                    raw_content=str(row["raw_content"]),
                    selection_stratum=stratum,
                )
                if (
                    len(selected) >= sample_size
                    or sum(1 for item in selected.values() if item.selection_stratum == stratum)
                    >= quota
                ):
                    break
            if len(selected) >= sample_size:
                break
        if len(selected) < sample_size:
            rows = (
                await session.execute(
                    text(
                        """
                        SELECT id, source_row_number, raw_title, raw_content
                        FROM work_orders
                        WHERE import_batch_id = :batch_id
                        ORDER BY md5(id::text) LIMIT :limit
                        """
                    ),
                    {"batch_id": batch_id, "limit": sample_size * 3},
                )
            ).mappings()
            for row in rows:
                work_order_id = UUID(str(row["id"]))
                if work_order_id in selected:
                    continue
                selected[work_order_id] = ReviewSample(
                    work_order_id=work_order_id,
                    source_row_number=int(row["source_row_number"]),
                    raw_title=str(row["raw_title"]) if row["raw_title"] is not None else None,
                    raw_content=str(row["raw_content"]),
                    selection_stratum="general",
                )
                if len(selected) >= sample_size:
                    break
    if len(selected) < sample_size:
        raise RuntimeError(
            f"requested {sample_size} samples but only {len(selected)} work orders were selected"
        )
    return tuple(sorted(selected.values(), key=lambda item: item.source_row_number))


def _weak_labels(content: str) -> list[str]:
    return [label for label, pattern in _WEAK_LABEL_PATTERNS if re.search(pattern, content)]


def _trace(trace: VersionTrace | None) -> dict[str, object] | None:
    if trace is None:
        return None
    return {
        "provider": trace.provider,
        "model_id": trace.model_id,
        "model_config_hash": trace.model_config_hash,
        "schema_version": trace.schema_version,
        "knowledge_snapshot_id": str(trace.knowledge_snapshot_id)
        if trace.knowledge_snapshot_id is not None
        else None,
        "pipeline_version": trace.pipeline_version,
    }


def _segment(segment: TextSegment) -> dict[str, object]:
    return {
        "segment_type": segment.segment_type.value,
        "text": segment.text,
        "ordinal": segment.ordinal,
        "start_offset": segment.start_offset,
        "end_offset": segment.end_offset,
    }


def _mention(mention: ExtractedMention) -> dict[str, object]:
    return {
        "text": mention.text,
        "mention_type": mention.mention_type,
        "start_offset": mention.start_offset,
        "end_offset": mention.end_offset,
        "canonical_entity_id": str(mention.canonical_entity_id)
        if mention.canonical_entity_id is not None
        else None,
        "resolution_state": mention.resolution_state,
        "confidence": mention.confidence,
        "evidence": list(mention.evidence),
    }


def _event(event: ExtractedEvent, ordinal: int) -> dict[str, object]:
    return {
        "ordinal": ordinal,
        "event_type": event.event_type,
        "normalized_summary": event.normalized_summary,
        "location_signals": list(event.location_signals),
        "mention_indexes": list(event.mention_indexes),
    }


async def _candidate_details(
    session_factory: Any, candidate_ids: tuple[EventInstanceId, ...]
) -> dict[UUID, dict[str, object]]:
    if not candidate_ids:
        return {}
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    EventInstance.id,
                    EventInstance.work_order_id,
                    EventInstance.ordinal,
                    EventInstance.event_type,
                    EventInstance.normalized_summary,
                    EventInstance.entity_ids,
                    EventInstance.location_signals,
                    WorkOrder.source_row_number,
                    WorkOrder.raw_title,
                )
                .join(WorkOrder, WorkOrder.id == EventInstance.work_order_id)
                .where(EventInstance.id.in_(candidate_ids))
            )
        ).all()
    return {
        UUID(str(row.id)): {
            "event_id": str(row.id),
            "work_order_id": str(row.work_order_id),
            "source_row_number": row.source_row_number,
            "raw_title": row.raw_title,
            "ordinal": row.ordinal,
            "event_type": row.event_type,
            "normalized_summary": row.normalized_summary,
            "entity_ids": list(row.entity_ids or []),
            "location_signals": list(row.location_signals or []),
        }
        for row in rows
    }


def _candidate_review_flags(
    event: ExtractedEvent,
    mentions: tuple[ExtractedMention, ...],
    candidate: dict[str, object],
    score: float,
) -> list[str]:
    flags: list[str] = []
    query_locations = set(event.location_signals)
    candidate_locations = set(str(value) for value in candidate.get("location_signals", []))
    if (
        score >= 0.75
        and query_locations
        and candidate_locations
        and not (query_locations & candidate_locations)
    ):
        flags.append("hard_negative_possible_different_location")
    query_entities = {
        str(mentions[index].canonical_entity_id)
        for index in event.mention_indexes
        if 0 <= index < len(mentions) and mentions[index].canonical_entity_id is not None
    }
    candidate_entities = {str(value) for value in candidate.get("entity_ids", [])}
    if query_entities & candidate_entities and event.event_type != candidate.get("event_type"):
        flags.append("same_entity_possible_different_issue")
    if score >= 0.75:
        flags.append("high_similarity_requires_human_judgement")
    return flags


async def _embedding_count(session_factory: Any, model_id: str) -> int:
    async with session_factory() as session:
        value = await session.scalar(
            select(text("count(*)"))
            .select_from(WorkOrderEmbedding)
            .where(WorkOrderEmbedding.model_id == model_id)
        )
    return int(value or 0)


def _endpoint_manifest(endpoint: Any) -> dict[str, object] | None:
    if endpoint is None:
        return None
    return {
        "provider": endpoint.provider,
        "base_url": endpoint.base_url,
        "model_id": endpoint.model_id,
        "timeout_seconds": endpoint.timeout_seconds,
        "concurrency": endpoint.concurrency,
        "api_key_configured": endpoint.api_key is not None,
    }


async def main() -> None:
    args = _args()
    if not 300 <= args.sample_size <= 1000:
        raise ValueError("sample-size must be between 300 and 1000 for a quality review run")
    if args.chunk_size < 1 or args.candidate_limit < 1:
        raise ValueError("chunk-size and candidate-limit must be positive")
    settings = get_settings()
    providers: AIProviderBundle = build_provider_bundle(
        settings, llm_model_override=args.llm_model, embedding_model_override=args.embedding_model
    )
    provider_health = await providers.health()
    active_embedding = (
        providers.plan.remote_embedding
        if providers.mode is ProviderMode.REMOTE
        else providers.plan.local_embedding
    )
    if active_embedding is None:
        raise RuntimeError("active embedding endpoint is not configured")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    started = time.perf_counter()
    output_path = args.output or (
        settings.runtime_dir
        / "quality"
        / f"ai-quality-review-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output_path.with_suffix(".summary.json")
    failed = 0
    event_count = 0
    candidate_count = 0
    strata_counts: Counter[str] = Counter()
    weak_label_counts: Counter[str] = Counter()
    review_flag_counts: Counter[str] = Counter()
    try:
        batch = await _latest_batch(session_factory, args.batch_id)
        samples = await _select_sample(session_factory, batch.id, args.sample_size)
        strata_counts.update(sample.selection_stratum for sample in samples)
        weak_label_counts.update(
            label for sample in samples for label in _weak_labels(sample.raw_content)
        )
        repository = SQLAlchemyUnderstandingRepository(session_factory)
        snapshot = None
        knowledge_snapshot_id = None
        gazetteer = None
        if settings.gazetteer_home is not None or settings.gazetteer_database_path is not None:
            database_path = settings.gazetteer_database_path or (
                settings.gazetteer_home / "地名服务" / "shunde_places.db"
                if settings.gazetteer_home is not None
                else None
            )
            if database_path is None:
                raise RuntimeError("gazetteer path configuration is incomplete")
            snapshot = GazetteerSnapshotBuilder(database_path).build()
            RuntimeSnapshotStore(settings.gazetteer_snapshot_path).save(snapshot)
            knowledge_snapshot_id = await repository.sync_snapshot(snapshot)
            gazetteer_remote = GazetteerHttpAdapter(
                str(settings.gazetteer_api_base_url), settings.dependency_timeout_seconds
            )
            gazetteer_health = await gazetteer_remote.health()
            if not gazetteer_health.available:
                raise RuntimeError("gazetteer live OpenAPI health check failed")
            gazetteer = RuntimeEntityResolver(snapshot, gazetteer_remote)
        understanding = WorkOrderUnderstandingService(
            RuleBasedWorkOrderSegmenter(),
            providers.llm,
            gazetteer=gazetteer,
            pipeline_version="quality-review.v1",
            schema_version="quality-review.v1",
            knowledge_snapshot_id=knowledge_snapshot_id,
        )
        retriever = PostgresCandidateRetriever(
            session_factory, providers.embeddings, model_id=active_embedding.model_id
        )
        with output_path.open("w", encoding="utf-8") as artifact:
            for start in range(0, len(samples), args.chunk_size):
                chunk = samples[start : start + args.chunk_size]
                try:
                    results = await understanding.understand_batch(
                        tuple(
                            (sample.work_order_id, sample.raw_title, sample.raw_content)
                            for sample in chunk
                        )
                    )
                except Exception as error:  # noqa: BLE001 - preserve failed samples in artifact
                    failed += len(chunk)
                    for sample in chunk:
                        artifact.write(
                            json.dumps(
                                {
                                    "review_state": "processing_error",
                                    "error_type": type(error).__name__,
                                    "error_message": str(error),
                                    "sample": {
                                        "work_order_id": str(sample.work_order_id),
                                        "source_row_number": sample.source_row_number,
                                        "selection_stratum": sample.selection_stratum,
                                        "weak_labels": _weak_labels(sample.raw_content),
                                        "raw_work_order": {
                                            "title": sample.raw_title,
                                            "content": sample.raw_content,
                                        },
                                    },
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        artifact.flush()
                    continue
                for sample, result in zip(chunk, results, strict=True):
                    understanding_domain = result.understanding
                    event_items = tuple(
                        (event_index, event)
                        for event_index, event in enumerate(understanding_domain.events)
                        if event.normalized_summary.strip()
                    )
                    event_requests = tuple(
                        EmbeddingRequest(
                            str(
                                uuid5(
                                    NAMESPACE_URL, f"quality-review:{sample.work_order_id}:{index}"
                                )
                            ),
                            event.normalized_summary,
                            schema_version="quality-review.v1",
                            pipeline_version="quality-review.v1",
                        )
                        for index, event in event_items
                    )
                    embedded: tuple[EmbeddingResult, ...] = ()
                    if event_requests:
                        embedded = await providers.embeddings.embed_batch(event_requests)
                    event_records: list[dict[str, object]] = []
                    for request_index, (event_index, event) in enumerate(event_items):
                        embedding = embedded[request_index]
                        synthetic_event_id = EventInstanceId(
                            UUID(event_requests[request_index].item_id)
                        )
                        query = RetrievalQuery(
                            event_id=synthetic_event_id,
                            work_order_id=WorkOrderId(sample.work_order_id),
                            entity_ids=tuple(
                                mention.canonical_entity_id
                                for mention_index in event.mention_indexes
                                if 0 <= mention_index < len(understanding_domain.mentions)
                                and (
                                    mention := understanding_domain.mentions[mention_index]
                                ).canonical_entity_id
                                is not None
                            ),
                            location_signals=event.location_signals,
                            event_type=event.event_type,
                            text=event.normalized_summary,
                            limit=args.candidate_limit,
                        )
                        candidates = await retriever.retrieve(query)
                        details = await _candidate_details(
                            session_factory, tuple(candidate.event_id for candidate in candidates)
                        )
                        candidate_records: list[dict[str, object]] = []
                        for candidate in candidates:
                            detail = details.get(UUID(str(candidate.event_id)), {})
                            flags = _candidate_review_flags(
                                event,
                                understanding_domain.mentions,
                                detail,
                                candidate.score,
                            )
                            review_flag_counts.update(flags)
                            candidate_records.append(
                                {
                                    **detail,
                                    "score": candidate.score,
                                    "evidence": list(candidate.evidence),
                                    "review_flags": flags,
                                }
                            )
                        candidate_count += len(candidate_records)
                        event_count += 1
                        event_records.append(
                            {
                                **_event(event, event_index),
                                "embedding": {
                                    "item_id": embedding.item_id,
                                    "model_id": embedding.model_id,
                                    "dimensions": len(embedding.vector),
                                    "trace": _trace(embedding.trace),
                                },
                                "retrieval_candidates": candidate_records,
                            }
                        )
                    artifact.write(
                        json.dumps(
                            {
                                "review_state": "pending_human_review",
                                "gold_set": None,
                                "weak_label_disclaimer": (
                                    "弱标签只用于抽样与人工复核排序，不是 ground truth；"
                                    "本 artifact 不计算准确率。"
                                ),
                                "sample": {
                                    "work_order_id": str(sample.work_order_id),
                                    "source_row_number": sample.source_row_number,
                                    "selection_stratum": sample.selection_stratum,
                                    "weak_labels": _weak_labels(sample.raw_content),
                                    "raw_work_order": {
                                        "title": sample.raw_title,
                                        "content": sample.raw_content,
                                    },
                                },
                                "segmentation": [_segment(segment) for segment in result.segments],
                                "understanding": {
                                    "current_complaint": understanding_domain.current_complaint,
                                    "historical_context": understanding_domain.historical_context,
                                    "department_reply": understanding_domain.department_reply,
                                    "current_request": understanding_domain.current_request,
                                    "mentions": [
                                        _mention(mention)
                                        for mention in understanding_domain.mentions
                                    ],
                                    "events": event_records,
                                },
                                "trace": {"llm": _trace(result.trace)},
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    artifact.flush()
        summary = {
            "status": "partial" if failed else "ready_for_human_review",
            "generated_at": datetime.now(UTC).isoformat(),
            "artifact": str(output_path),
            "source": {
                "batch_id": str(batch.id),
                "source_filename": batch.source_filename,
                "source_sha256": batch.source_sha256,
                "total_rows": batch.total_rows,
                "sample_size_requested": args.sample_size,
                "sample_size_written": len(samples),
            },
            "provider": {
                "mode": providers.mode.value,
                "health": provider_health,
                "local_llm": _endpoint_manifest(providers.plan.local_llm),
                "remote_llm": _endpoint_manifest(providers.plan.remote_llm),
                "local_embedding": _endpoint_manifest(providers.plan.local_embedding),
                "remote_embedding": _endpoint_manifest(providers.plan.remote_embedding),
            },
            "pipeline": {
                "pipeline_version": "quality-review.v1",
                "schema_version": "quality-review.v1",
                "retrieval_model_id": active_embedding.model_id,
                "indexed_embedding_rows_at_run": await _embedding_count(
                    session_factory, active_embedding.model_id
                ),
            },
            "counts": {
                "failed_samples": failed,
                "events": event_count,
                "retrieval_candidates": candidate_count,
                "selection_strata": dict(strata_counts),
                "weak_labels": dict(weak_label_counts),
                "review_flags": dict(review_flag_counts),
            },
            "metrics": {"precision": None, "recall": None, "f1": None},
            "event_schema_assessment": {
                "conclusion": "partial_not_ready_for_reliable_same_event_decision",
                "reason": (
                    "当前事件结构支持分段、事件摘要、地点信号和 mention 关联，足够做候选检索；"
                    "但缺少稳定的时间区间、主体/问题 facet、事件级证据 span 与冲突字段，"
                    "不能单凭当前 schema 可靠判定 same_event。"
                ),
                "next_step": "先完成人工 Gold Set 与 schema v2 评审，再实现 SameEventMatcher。",
            },
            "elapsed_seconds": time.perf_counter() - started,
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "artifact": str(output_path),
                    "summary": str(summary_path),
                    "counts": summary["counts"],
                },
                ensure_ascii=False,
            )
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
