from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import get_settings
from backend.app.domain.types import (
    EmbeddingRequest,
    EmbeddingResult,
    EventInstanceId,
    RetrievalQuery,
    WorkOrderId,
)
from backend.app.infrastructure.db.models import (
    EventInstance,
    ImportBatch,
    WorkOrder,
    WorkOrderEmbedding,
)
from backend.app.infrastructure.db.retrieval import PostgresCandidateRetriever
from backend.app.infrastructure.db.session import create_engine, create_session_factory


class QueryEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def embed_batch(
        self, requests: tuple[EmbeddingRequest, ...]
    ) -> tuple[EmbeddingResult, ...]:
        self.calls += 1
        return tuple(
            EmbeddingResult(request.item_id, (1.0, 0.0, 0.0), "test-embedding")
            for request in requests
        )


async def test_pgvector_retrieval_excludes_self_and_ranks_hard_negative() -> None:
    """A close vector wins while the query event itself is never a candidate."""
    engine = create_engine(get_settings())
    session_factory = create_session_factory(engine)
    batch_id = uuid4()
    work_order_ids = (uuid4(), uuid4(), uuid4())
    event_ids = (uuid4(), uuid4(), uuid4(), uuid4())
    try:
        try:
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        ImportBatch(
                            id=batch_id,
                            source_filename="retrieval-contract-test.xlsx",
                            source_sha256=uuid4().hex + uuid4().hex,
                            source_size_bytes=1,
                            field_mapping={},
                            total_rows=3,
                            successful_rows=3,
                            failed_rows=0,
                            duplicate_rows=0,
                            checkpoint_row=3,
                            status="completed",
                        )
                    )
                    session.add_all(
                        WorkOrder(
                            id=work_order_id,
                            import_batch_id=batch_id,
                            source_row_number=index,
                            raw_title=None,
                            raw_content=f"retrieval test {index}",
                            raw_fields={},
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
                            event_type="test",
                            behavior=None,
                            normalized_summary=f"event {index}",
                            entity_ids=[],
                            location_signals=[],
                            time_signals=[],
                            evidence={"test": True},
                            model_id="test-model",
                            model_config_hash=None,
                            schema_version="test.v1",
                            knowledge_snapshot_id=None,
                            pipeline_version="test.v1",
                        )
                        for index, (event_id, work_order_id, ordinal) in enumerate(
                            (
                                (event_ids[0], work_order_ids[0], 0),
                                (event_ids[1], work_order_ids[0], 1),
                                (event_ids[2], work_order_ids[1], 0),
                                (event_ids[3], work_order_ids[2], 0),
                            ),
                            start=1,
                        )
                    )
                    await session.flush()
                    session.add_all(
                        WorkOrderEmbedding(
                            id=uuid4(),
                            work_order_id=work_order_id,
                            event_instance_id=event_id,
                            content_hash=uuid4().hex + uuid4().hex,
                            dimensions=3,
                            embedding=vector,
                            model_id="test-embedding",
                            model_config_hash=None,
                            schema_version="test.v1",
                            knowledge_snapshot_id=None,
                            pipeline_version="test.v1",
                        )
                        for work_order_id, event_id, vector in (
                            (work_order_ids[0], event_ids[0], [1.0, 0.0, 0.0]),
                            (work_order_ids[0], event_ids[1], [0.999, 0.001, 0.0]),
                            (work_order_ids[1], event_ids[2], [0.99, 0.01, 0.0]),
                            (work_order_ids[2], event_ids[3], [0.0, 1.0, 0.0]),
                        )
                    )
        except (OSError, SQLAlchemyError) as error:
            pytest.skip(f"PostgreSQL not available; pgvector contract deferred: {error}")

        embedding_provider = QueryEmbeddingProvider()
        retriever = PostgresCandidateRetriever(
            session_factory, embedding_provider, model_id="test-embedding"
        )
        candidates = await retriever.retrieve(
            RetrievalQuery(
                event_id=EventInstanceId(event_ids[0]),
                work_order_id=WorkOrderId(work_order_ids[0]),
                entity_ids=(),
                location_signals=(),
                event_type="test",
                text="query",
                limit=2,
            )
        )

        assert candidates
        assert candidates[0].event_id == EventInstanceId(event_ids[2])
        assert all(candidate.event_id != EventInstanceId(event_ids[0]) for candidate in candidates)
        assert all(candidate.event_id != EventInstanceId(event_ids[1]) for candidate in candidates)
        assert candidates[0].score > candidates[-1].score
        assert embedding_provider.calls == 0
    finally:
        try:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(delete(ImportBatch).where(ImportBatch.id == batch_id))
        except (OSError, SQLAlchemyError):
            pass
        await engine.dispose()
