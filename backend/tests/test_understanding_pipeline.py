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


async def test_understanding_attaches_reply_and_request_actions_to_the_complaint_event() -> None:
    class TestLLM:
        async def generate_batch(self, requests):
            trace = VersionTrace(
                "qwen-plus",
                "config",
                "understanding.v2",
                None,
                "understanding.v2",
                "remote-openai-compatible",
            )
            return tuple(
                LLMResult(
                    request.request_id,
                    WorkOrderUnderstanding(
                        current_complaint="某KTV存在商业噪声",
                        department_reply="执法人员已到场并约谈负责人",
                        current_request="要求再次到场并关闭音响",
                        mentions=[{"text": "某KTV", "mention_type": MentionType.ORGANIZATION}],
                        events=[
                            {
                                "event_type": "commercial_noise",
                                "behavior": "商业噪声扰民",
                                "normalized_summary": "某KTV商业噪声扰民",
                                "location_signals": ["新桂北路29号116号铺"],
                                "mention_indexes": [0],
                                "evidence": [{"segment_ordinal": 0, "quote": "某KTV存在商业噪声"}],
                            },
                            {
                                "event_type": "enforcement_action",
                                "behavior": "约谈负责人",
                                "normalized_summary": "执法人员约谈KTV负责人",
                                "location_signals": ["新桂北路29号116号铺"],
                                "mention_indexes": [0],
                                "evidence": [
                                    {"segment_ordinal": 1, "quote": "执法人员已到场并约谈负责人"}
                                ],
                            },
                            {
                                "event_type": "handling_request",
                                "behavior": "再次到场并关闭音响",
                                "normalized_summary": "要求再次关停KTV音响",
                                "location_signals": ["新桂北路29号116号铺"],
                                "mention_indexes": [0],
                                "evidence": [
                                    {"segment_ordinal": 2, "quote": "要求再次到场并关闭音响"}
                                ],
                            },
                        ],
                    ).model_dump(mode="json"),
                    trace,
                )
                for request in requests
            )

    content = (
        "投诉：某KTV存在商业噪声。"
        "部门回复：执法人员已到场并约谈负责人。"
        "诉求：要求再次到场并关闭音响。"
    )
    result = await WorkOrderUnderstandingService(
        RuleBasedWorkOrderSegmenter(), TestLLM()
    ).understand(uuid5(NAMESPACE_URL, "test:handling-context"), None, content)

    assert result.understanding.department_reply == "执法人员已到场并约谈负责人"
    assert result.understanding.current_request == "要求再次到场并关闭音响"
    assert len(result.understanding.events) == 1
    assert result.understanding.events[0].event_type == "commercial_noise"
    assert {item.segment_type for item in result.understanding.events[0].evidence} == {
        "complaint",
        "department_reply",
        "current_request",
    }


async def test_understanding_preserves_distinct_issues_inside_one_work_order() -> None:
    class TestLLM:
        async def generate_batch(self, requests):
            trace = VersionTrace(
                "qwen-plus",
                "config",
                "understanding.v2",
                None,
                "understanding.v2",
                "remote-openai-compatible",
            )
            output = WorkOrderUnderstanding(
                current_complaint="某KTV存在商业噪声，且消防设施故障",
                mentions=[{"text": "某KTV", "mention_type": MentionType.ORGANIZATION}],
                events=[
                    {
                        "event_type": "commercial_noise",
                        "normalized_summary": "某KTV商业噪声扰民",
                        "location_signals": ["新桂北路29号116号铺"],
                        "mention_indexes": [0],
                        "evidence": [{"segment_ordinal": 0, "quote": "商业噪声"}],
                    },
                    {
                        "event_type": "fire_safety_fault",
                        "normalized_summary": "某KTV消防设施故障",
                        "location_signals": ["新桂北路29号116号铺"],
                        "mention_indexes": [0],
                        "evidence": [{"segment_ordinal": 0, "quote": "消防设施故障"}],
                    },
                ],
            ).model_dump(mode="json")
            return tuple(LLMResult(request.request_id, output, trace) for request in requests)

    result = await WorkOrderUnderstandingService(
        RuleBasedWorkOrderSegmenter(), TestLLM()
    ).understand(
        uuid5(NAMESPACE_URL, "test:multiple-issues"),
        None,
        "投诉：某KTV存在商业噪声，且消防设施故障。",
    )

    assert [event.event_type for event in result.understanding.events] == [
        "commercial_noise",
        "fire_safety_fault",
    ]


def test_understanding_discards_non_string_object_mentions() -> None:
    understanding = WorkOrderUnderstanding.model_validate(
        {
            "events": [
                {
                    "normalized_summary": "测试事项",
                    "focal_object_mentions": [1, "项目A"],
                    "location_mentions": [0, "地点B"],
                }
            ]
        }
    )

    assert understanding.events[0].focal_object_mentions == ["项目A"]
    assert understanding.events[0].location_mentions == ["地点B"]
