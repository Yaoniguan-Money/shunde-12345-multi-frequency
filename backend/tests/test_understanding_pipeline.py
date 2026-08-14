from uuid import NAMESPACE_URL, uuid5

from backend.app.application.services.understanding import WorkOrderUnderstandingService
from backend.app.domain.services.segmentation import RuleBasedWorkOrderSegmenter
from backend.app.domain.types import (
    CanonicalEntity,
    EntityCandidate,
    EntityCandidateSet,
    GazetteerHealth,
    GazetteerSnapshot,
    LLMResult,
    ResolutionState,
    VersionTrace,
)
from backend.app.schemas.ai import MentionType, WorkOrderUnderstanding


def test_segmenter_preserves_order_and_offsets() -> None:
    content = "问题：夜间施工扰民。历史：此前已投诉。诉求：请处理。"
    segments = RuleBasedWorkOrderSegmenter().segment(None, content)

    assert [segment.segment_type.value for segment in segments] == [
        "complaint",
        "history",
        "current_request",
    ]
    assert [content[segment.start_offset : segment.end_offset].strip() for segment in segments] == [
        "夜间施工扰民。",
        "此前已投诉。",
        "请处理。",
    ]


async def test_understanding_batches_llm_and_gazetteer_calls() -> None:
    entity = CanonicalEntity(uuid5(NAMESPACE_URL, "test:place"), "大良街道", "街道", ("凤城",))

    class TestLLM:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        async def generate_batch(self, requests):
            self.calls.append(tuple(request.request_id for request in requests))
            trace = VersionTrace("test-local", "config", "understanding.v1", None, "test.v1")
            return tuple(
                LLMResult(
                    request.request_id,
                    WorkOrderUnderstanding(
                        current_complaint="夜间施工扰民",
                        historical_context=None,
                        department_reply=None,
                        current_request="请处理",
                        mentions=[{"text": "凤城", "mention_type": MentionType.PLACE}],
                        events=[
                            {
                                "normalized_summary": "夜间施工扰民",
                                "location_signals": ["凤城"],
                                "mention_indexes": [0],
                            }
                        ],
                    ).model_dump(mode="json"),
                    trace,
                )
                for request in requests
            )

    class TestGazetteer:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        async def health(self) -> GazetteerHealth:
            return GazetteerHealth(True, "test")

        async def snapshot(self) -> GazetteerSnapshot:
            raise AssertionError("snapshot is not needed for this test")

        async def resolve_many(self, mentions):
            self.calls.append(mentions)
            return tuple(
                EntityCandidateSet(
                    mention,
                    ResolutionState.RESOLVED,
                    (EntityCandidate(entity, 0.98, ("test",)),),
                )
                for mention in mentions
            )

    llm = TestLLM()
    gazetteer = TestGazetteer()
    service = WorkOrderUnderstandingService(RuleBasedWorkOrderSegmenter(), llm, gazetteer=gazetteer)
    results = await service.understand_batch(
        (
            (uuid5(NAMESPACE_URL, "test:one"), None, "问题：凤城夜间施工。"),
            (uuid5(NAMESPACE_URL, "test:two"), None, "问题：凤城道路破损。"),
        )
    )

    assert len(results) == 2
    assert len(llm.calls) == 1
    assert len(llm.calls[0]) == 2
    assert gazetteer.calls == [("凤城", "凤城")]
    assert results[0].understanding.mentions[0].canonical_entity_id == entity.entity_id
    assert results[0].trace.model_id == "test-local"
