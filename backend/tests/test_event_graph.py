from uuid import uuid4

import pytest

from backend.app.application.services.event_graph import EventGraphService
from backend.app.application.services.understanding import WorkOrderUnderstandingService
from backend.app.domain.analysis import SegmentType
from backend.app.domain.services.clustering import EventClusterBuilder
from backend.app.domain.services.segmentation import RuleBasedWorkOrderSegmenter
from backend.app.domain.types import (
    EntityId,
    EventCandidate,
    EventForMatching,
    EventInstanceId,
    EventMatchEdgeRecord,
    LLMResult,
    ProviderRoute,
    SameEventEvidence,
    VersionTrace,
    WorkOrderId,
)
from backend.app.infrastructure.ai.same_event import RemoteSameEventMatcher
from backend.app.schemas.ai import MentionType, WorkOrderUnderstanding


def _remote_trace() -> VersionTrace:
    return VersionTrace(
        "remote-model",
        "config-hash",
        "same-event.v1",
        None,
        "same-event.v1",
        "remote-openai-compatible",
    )


@pytest.mark.asyncio
async def test_understanding_v2_validates_verbatim_event_evidence() -> None:
    class FakeLLM:
        async def generate_batch(self, requests):
            return tuple(
                LLMResult(
                    request.request_id,
                    WorkOrderUnderstanding(
                        current_complaint="夜间噪声",
                        mentions=[{"text": "凤城", "mention_type": MentionType.PLACE}],
                        events=[
                            {
                                "event_type": "noise",
                                "behavior": "要求停止噪声",
                                "normalized_summary": "凤城夜间噪声扰民",
                                "time_signals": ["夜间", "不存在的时间"],
                                "evidence": [
                                    {"segment_ordinal": 0, "quote": "凤城夜间噪声"},
                                    {"segment_ordinal": 0, "quote": "模型编造的证据"},
                                ],
                            }
                        ],
                    ).model_dump(mode="json"),
                    VersionTrace(
                        "remote-model",
                        "config",
                        "understanding.v2",
                        None,
                        "understanding.v2",
                        "remote-openai-compatible",
                    ),
                )
                for request in requests
            )

    result = await WorkOrderUnderstandingService(
        RuleBasedWorkOrderSegmenter(),
        FakeLLM(),
        pipeline_version="understanding.v2",
        schema_version="understanding.v2",
    ).understand(uuid4(), None, "凤城夜间噪声扰民。")

    event = result.understanding.events[0]
    assert event.behavior == "要求停止噪声"
    assert event.time_signals == ("夜间",)
    assert len(event.evidence) == 1
    assert event.evidence[0].quote == "凤城夜间噪声"
    assert event.evidence[0].segment_type == SegmentType.COMPLAINT.value


def _event(
    *,
    event_id: EventInstanceId,
    entity: EntityId,
    location: str,
    summary: str,
    event_type: str = "noise",
    work_order_id: WorkOrderId | None = None,
) -> EventForMatching:
    return EventForMatching(
        event_id=event_id,
        work_order_id=work_order_id or WorkOrderId(uuid4()),
        event_type=event_type,
        behavior="要求处理",
        normalized_summary=summary,
        entity_ids=(entity,),
        location_signals=(location,),
        time_signals=(),
        evidence=({"segment_type": "complaint", "quote": summary},),
        raw_title=None,
        raw_content=summary,
    )


@pytest.mark.asyncio
async def test_event_graph_never_matches_events_from_the_same_work_order() -> None:
    work_order_id = WorkOrderId(uuid4())
    entity = EntityId(uuid4())
    left = _event(
        event_id=EventInstanceId(uuid4()),
        work_order_id=work_order_id,
        entity=entity,
        location="同一地点",
        summary="商业噪声投诉",
    )
    right = _event(
        event_id=EventInstanceId(uuid4()),
        work_order_id=work_order_id,
        entity=entity,
        location="同一地点",
        summary="要求关停音响",
    )

    class Events:
        async def get_for_matching(self, event_id):
            return {left.event_id: left, right.event_id: right}[event_id]

    class Retriever:
        async def retrieve(self, query):
            other = right.event_id if query.event_id == left.event_id else left.event_id
            return (EventCandidate(other, 0.99),)

    class Matcher:
        async def match(self, _left_event_id, _right_event_id):
            raise AssertionError("same-work-order events must not reach SameEventMatcher")

    class Graph:
        async def start_run(self, **_kwargs):
            return uuid4(), uuid4()

        async def save_match_edge(self, *_args, **_kwargs):
            raise AssertionError("same-work-order events must not persist a match edge")

        async def save_cluster(self, *_args, **_kwargs):
            raise AssertionError("same-work-order events must not persist a cluster")

        async def finish_run(self, _run_id, _metrics):
            return None

    result = await EventGraphService(Events(), Graph(), Retriever(), Matcher()).run(
        (left.event_id, right.event_id)
    )

    assert result.decisions == ()
    assert result.cluster_ids == ()


@pytest.mark.asyncio
async def test_remote_same_event_forces_disjoint_entities_false_and_routes_remote() -> None:
    left_id = EventInstanceId(uuid4())
    right_id = EventInstanceId(uuid4())
    left = _event(event_id=left_id, entity=EntityId(uuid4()), location="大良", summary="噪声投诉")
    right = _event(event_id=right_id, entity=EntityId(uuid4()), location="大良", summary="噪声投诉")

    class Events:
        async def get_for_matching(self, event_id):
            return {left_id: left, right_id: right}[event_id]

    class LLM:
        def __init__(self) -> None:
            self.routes: list[ProviderRoute] = []

        async def generate_batch(self, requests):
            self.routes.extend(request.route for request in requests)
            return tuple(
                LLMResult(
                    request.request_id,
                    {
                        "same_event": True,
                        "confidence": 0.95,
                        "evidence": {
                            "same_entity": True,
                            "same_location": True,
                            "same_issue": True,
                            "time_compatible": True,
                            "contradictions": [],
                        },
                    },
                    _remote_trace(),
                )
                for request in requests
            )

    llm = LLM()
    decision = await RemoteSameEventMatcher(Events(), llm).match(left_id, right_id)
    assert decision.same_event is False
    assert "canonical_entity_conflict" in decision.evidence.contradictions
    assert llm.routes == [ProviderRoute.REMOTE]


@pytest.mark.asyncio
async def test_remote_same_event_rejects_events_from_the_same_work_order() -> None:
    work_order_id = WorkOrderId(uuid4())
    entity = EntityId(uuid4())
    left = _event(
        event_id=EventInstanceId(uuid4()),
        work_order_id=work_order_id,
        entity=entity,
        location="同一地点",
        summary="商业噪声投诉",
    )
    right = _event(
        event_id=EventInstanceId(uuid4()),
        work_order_id=work_order_id,
        entity=entity,
        location="同一地点",
        summary="部门已约谈",
    )

    class Events:
        async def get_for_matching(self, event_id):
            return {left.event_id: left, right.event_id: right}[event_id]

    class LLM:
        async def generate_batch(self, _requests):
            raise AssertionError("same-work-order events must be rejected before the LLM")

    with pytest.raises(ValueError, match="different work orders"):
        await RemoteSameEventMatcher(Events(), LLM()).match(left.event_id, right.event_id)


def test_cluster_builder_rejects_contradictory_transitive_merge() -> None:
    entity = EntityId(uuid4())
    a = _event(event_id=EventInstanceId(uuid4()), entity=entity, location="同一地点", summary="A")
    b = _event(event_id=EventInstanceId(uuid4()), entity=entity, location="同一地点", summary="B")
    c = _event(
        event_id=EventInstanceId(uuid4()),
        entity=EntityId(uuid4()),
        location="另一地点",
        summary="C",
    )
    trace = _remote_trace()
    edge_ab = EventMatchEdgeRecord(
        a.event_id, b.event_id, True, 0.95, SameEventEvidence(True, True, True, True), trace
    )
    edge_bc = EventMatchEdgeRecord(
        b.event_id, c.event_id, True, 0.90, SameEventEvidence(True, True, True, True), trace
    )

    proposals = EventClusterBuilder().build((a, b, c), (edge_ab, edge_bc))

    assert len(proposals) == 1
    assert set(proposals[0].members) == {a.event_id, b.event_id}
    assert (b.event_id, c.event_id) in proposals[0].rejected_edges


def test_cluster_builder_never_creates_multi_frequency_from_one_work_order() -> None:
    work_order_id = WorkOrderId(uuid4())
    entity = EntityId(uuid4())
    events = tuple(
        _event(
            event_id=EventInstanceId(uuid4()),
            work_order_id=work_order_id,
            entity=entity,
            location="同一地点",
            summary=summary,
        )
        for summary in ("商业噪声", "部门已约谈", "要求关停音响")
    )
    edges = (
        EventMatchEdgeRecord(
            events[0].event_id,
            events[1].event_id,
            True,
            0.96,
            SameEventEvidence(True, True, True, True),
            _remote_trace(),
        ),
        EventMatchEdgeRecord(
            events[1].event_id,
            events[2].event_id,
            True,
            0.95,
            SameEventEvidence(True, True, True, True),
            _remote_trace(),
        ),
    )

    assert EventClusterBuilder().build(events, edges) == ()


def test_cluster_builder_keeps_semantic_event_type_synonyms_together() -> None:
    entity = EntityId(uuid4())
    left = _event(
        event_id=EventInstanceId(uuid4()),
        entity=entity,
        location="新桂北路29号116号铺",
        summary="恒艺工作室商业噪音",
        event_type="commercial_noise",
    )
    right = _event(
        event_id=EventInstanceId(uuid4()),
        entity=entity,
        location="新桂北路29号116号铺",
        summary="恒艺工作室噪声扰民",
        event_type="noise_disturbance",
    )
    edge = EventMatchEdgeRecord(
        left.event_id,
        right.event_id,
        True,
        0.95,
        SameEventEvidence(True, True, True, True),
        _remote_trace(),
    )

    proposals = EventClusterBuilder().build((left, right), (edge,))

    assert len(proposals) == 1
    assert set(proposals[0].members) == {left.event_id, right.event_id}
