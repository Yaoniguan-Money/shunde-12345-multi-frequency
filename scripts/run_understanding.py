"""Run the real local understanding + embedding pipeline.

Use ``--limit N`` for a bounded real smoke; omit it (or pass 0) to resume until
the imported batch is complete. A paused smoke leaves a durable job checkpoint.
"""

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select

from backend.app.application.services.indexing import UnderstandingAndIndexingPipeline
from backend.app.application.services.understanding import WorkOrderUnderstandingService
from backend.app.config import get_settings
from backend.app.domain.services.segmentation import RuleBasedWorkOrderSegmenter
from backend.app.infrastructure.ai.factory import build_provider_bundle
from backend.app.infrastructure.db.analysis import SQLAlchemyUnderstandingRepository
from backend.app.infrastructure.db.models import ImportBatch
from backend.app.infrastructure.db.session import create_engine, create_session_factory
from backend.app.infrastructure.knowledge.gazetteer import GazetteerHttpAdapter
from backend.app.infrastructure.knowledge.resolver import RuntimeEntityResolver
from backend.app.infrastructure.knowledge.snapshot import (
    GazetteerSnapshotBuilder,
    RuntimeSnapshotStore,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", type=UUID)
    parser.add_argument("--llm-model", default=os.environ.get("SHUNDE_LLM_MODEL_ID"))
    parser.add_argument("--embedding-model", default=os.environ.get("SHUNDE_EMBEDDING_MODEL_ID"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=4)
    return parser.parse_args()


async def _latest_batch(session_factory, batch_id: UUID | None) -> ImportBatch:
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


async def main() -> None:
    args = _args()
    settings = get_settings()
    providers = build_provider_bundle(
        settings,
        llm_model_override=args.llm_model,
        embedding_model_override=args.embedding_model,
    )
    await providers.health()
    active_llm = (
        providers.plan.remote_llm if providers.mode.value == "remote" else providers.plan.local_llm
    )
    active_embedding = (
        providers.plan.remote_embedding
        if providers.mode.value == "remote"
        else providers.plan.local_embedding
    )
    if active_llm is None or active_embedding is None:
        raise RuntimeError("active provider plan is missing model endpoints")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        batch = await _latest_batch(session_factory, args.batch_id)
        repository = SQLAlchemyUnderstandingRepository(session_factory)
        gazetteer = None
        knowledge_snapshot_id = None
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
            gazetteer = RuntimeEntityResolver(
                snapshot,
                GazetteerHttpAdapter(
                    str(settings.gazetteer_api_base_url), settings.dependency_timeout_seconds
                ),
            )
        understanding = WorkOrderUnderstandingService(
            RuleBasedWorkOrderSegmenter(),
            providers.llm,
            gazetteer=gazetteer,
            pipeline_version=settings.analysis_pipeline_version,
            schema_version=settings.analysis_schema_version,
            knowledge_snapshot_id=knowledge_snapshot_id,
        )
        pipeline = UnderstandingAndIndexingPipeline(
            repository,
            understanding,
            providers.embeddings,
            pipeline_version=settings.analysis_pipeline_version,
            schema_version=settings.analysis_schema_version,
            model_id=active_llm.model_id,
            embedding_model_id=active_embedding.model_id,
            provider=providers.mode.value,
            chunk_size=args.chunk_size,
        )
        summary = await pipeline.run(
            batch.id,
            batch.total_rows,
            max_rows=args.limit or None,
        )
        print(json.dumps(asdict(summary), ensure_ascii=False, default=str))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
