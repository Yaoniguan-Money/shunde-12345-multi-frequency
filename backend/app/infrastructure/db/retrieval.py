from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.domain.ports.analysis import CandidateRetriever, EmbeddingProvider
from backend.app.domain.types import (
    EmbeddingRequest,
    EventCandidate,
    EventInstanceId,
    RetrievalQuery,
)
from backend.app.infrastructure.db.models import EventInstance, WorkOrderEmbedding


class PostgresCandidateRetriever(CandidateRetriever):
    """Use bounded vector and deterministic anchors for candidate recall."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
        *,
        model_id: str,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider
        self._model_id = model_id

    async def retrieve(self, query: RetrievalQuery) -> tuple[EventCandidate, ...]:
        if not query.text.strip() or query.limit < 1:
            return ()
        anchored = await self._anchor_candidates(query)
        vector = await self._stored_vector(query.event_id)
        if vector is None:
            embedded = await self._embedding_provider.embed_batch(
                (EmbeddingRequest(str(query.event_id), query.text),)
            )
            if len(embedded) != 1:
                raise RuntimeError("embedding provider returned an unexpected result count")
            vector = list(embedded[0].vector)
        distance = WorkOrderEmbedding.embedding.cosine_distance(vector).label("distance")
        statement = (
            select(EventInstance.id, distance)
            .join(
                WorkOrderEmbedding,
                WorkOrderEmbedding.event_instance_id == EventInstance.id,
            )
            .where(
                WorkOrderEmbedding.model_id == self._model_id,
                WorkOrderEmbedding.dimensions == len(vector),
                EventInstance.id != query.event_id,
                EventInstance.work_order_id != query.work_order_id,
            )
            .order_by(distance)
            .limit(query.limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        vector_candidates = tuple(
            EventCandidate(
                event_id=EventInstanceId(event_id),
                score=max(0.0, min(1.0, 1.0 - float(raw_distance))),
                evidence=("pgvector_cosine_distance", f"embedding_model:{self._model_id}"),
            )
            for event_id, raw_distance in rows
        )
        merged: dict[EventInstanceId, EventCandidate] = {
            candidate.event_id: candidate for candidate in anchored
        }
        for candidate in vector_candidates:
            merged.setdefault(candidate.event_id, candidate)
        return tuple(merged.values())[: query.limit]

    async def _anchor_candidates(self, query: RetrievalQuery) -> tuple[EventCandidate, ...]:
        """Recall same-entity and project/location anchors before vector ranking.

        These are evidence-routing candidates, not SameEvent conclusions.  The
        bounded result still requires the remote matcher and cluster consistency
        checks before it can affect a frequency projection.
        """

        conditions = [
            EventInstance.entity_ids.contains([str(entity_id)]) for entity_id in query.entity_ids
        ]
        location_anchors = _strong_location_anchors(query.location_signals)
        conditions.extend(
            EventInstance.location_signals.contains([location]) for location in location_anchors
        )
        conditions.extend(
            EventInstance.normalized_summary.contains(location) for location in location_anchors
        )
        if not conditions:
            return ()
        statement = (
            select(EventInstance.id)
            .where(
                EventInstance.id != query.event_id,
                EventInstance.work_order_id != query.work_order_id,
                or_(*conditions),
            )
            .order_by(EventInstance.created_at.desc(), EventInstance.id)
            .limit(query.limit)
        )
        async with self._session_factory() as session:
            event_ids = (await session.scalars(statement)).all()
        return tuple(
            EventCandidate(
                event_id=EventInstanceId(event_id),
                score=1.0,
                evidence=("hybrid_anchor", "same_entity_or_project_location"),
            )
            for event_id in event_ids
        )

    async def _stored_vector(self, event_id: EventInstanceId) -> list[float] | None:
        statement = (
            select(WorkOrderEmbedding.embedding)
            .where(
                WorkOrderEmbedding.event_instance_id == event_id,
                WorkOrderEmbedding.model_id == self._model_id,
            )
            .order_by(WorkOrderEmbedding.created_at.desc())
            .limit(1)
        )
        async with self._session_factory() as session:
            vector = (await session.execute(statement)).scalar_one_or_none()
        return list(vector) if vector is not None else None


def _strong_location_anchors(signals: tuple[str, ...]) -> tuple[str, ...]:
    """Keep only sufficiently specific project/location strings for SQL anchors."""

    normalized = ("".join(signal.split()) for signal in signals)
    return tuple(dict.fromkeys(signal for signal in normalized if len(signal) >= 4))
