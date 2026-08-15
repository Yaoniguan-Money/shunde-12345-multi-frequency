"""Remote, evidence-aware SameEventMatcher adapter."""

import json

from backend.app.domain.ports.analysis import LLMProvider, SameEventMatcher
from backend.app.domain.ports.repositories import EventRepository
from backend.app.domain.types import (
    EventForMatching,
    EventInstanceId,
    LLMRequest,
    ProviderRoute,
    SameEventDecision,
    SameEventEvidence,
)
from backend.app.schemas.ai import SameEventResponse


class RemoteSameEventMatcher(SameEventMatcher):
    """Use a configured remote LLM after retrieval, never cosine alone."""

    def __init__(
        self,
        events: EventRepository,
        llm: LLMProvider,
        *,
        pipeline_version: str = "same-event.v1",
        schema_version: str = "same-event.v1",
    ) -> None:
        self._events = events
        self._llm = llm
        self._pipeline_version = pipeline_version
        self._schema_version = schema_version

    async def match(
        self, left_event_id: EventInstanceId, right_event_id: EventInstanceId
    ) -> SameEventDecision:
        left = await self._events.get_for_matching(left_event_id)
        right = await self._events.get_for_matching(right_event_id)
        if left is None or right is None:
            raise LookupError("both events must exist before SameEventMatcher evaluation")
        request = LLMRequest(
            request_id=f"same-event:{left_event_id}:{right_event_id}",
            prompt=self._prompt(left, right),
            output_schema=SameEventResponse.model_json_schema(),
            schema_version=self._schema_version,
            pipeline_version=self._pipeline_version,
            route=ProviderRoute.REMOTE,
        )
        result = (await self._llm.generate_batch((request,)))[0]
        parsed = SameEventResponse.model_validate(result.structured_output)
        evidence = SameEventEvidence(
            same_entity=parsed.evidence.same_entity,
            same_location=parsed.evidence.same_location,
            same_issue=parsed.evidence.same_issue,
            time_compatible=parsed.evidence.time_compatible,
            contradictions=tuple(parsed.evidence.contradictions),
        )
        decision = SameEventDecision(parsed.same_event, parsed.confidence, evidence, result.trace)
        return self._apply_hard_contradictions(left, right, decision)

    @staticmethod
    def _prompt(left: EventForMatching, right: EventForMatching) -> str:
        payload = {
            "left": RemoteSameEventMatcher._event_payload(left),
            "right": RemoteSameEventMatcher._event_payload(right),
        }
        return (
            "判断两条工单事件是否指向同一个现实世界问题/处置链，而不是判断文本是否相似。"
            "优先比较 canonical entity、规范化地点、问题/行为和当前诉求；事件类型字符串可以是"
            "同义标签，不要求字面相等。对同一地点、同一主体、同一问题的‘再次反映/多次投诉/"
            "仍未解决’：日期不同表示重复或持续投诉，不能仅因时间不同就判为不同事件，此时"
            "time_compatible 可为 true。只有明确是互不相关的一次性事件，或问题、主体、地点相冲突，"
            "才判 same_event=false。注意：同一主体/同一地点不等于同一问题；例如消防设施机械杂音"
            "与商铺KTV商业噪音、物业维修与商户扰民属于不同事件，即使出现在同一工单也必须判 false。"
            "历史部门回复的复制文本不能单独证明同事件，但可作为处置链证据。"
            "若主体不同、地点明显不同或问题冲突，必须返回 same_event=false，并在 contradictions "
            "中说明。confidence 是对 same_event 判断的置信度，不是 cosine similarity。只输出 JSON，"
            "不要补充解释。\n" + json.dumps(payload, ensure_ascii=False)
        )

    @staticmethod
    def _event_payload(event: EventForMatching) -> dict[str, object]:
        return {
            "event_id": str(event.event_id),
            "raw_title": event.raw_title,
            "event_type": event.event_type,
            "behavior": event.behavior,
            "normalized_summary": event.normalized_summary,
            "canonical_entity_ids": [str(value) for value in event.entity_ids],
            "location_signals": list(event.location_signals),
            "time_signals": list(event.time_signals),
            "evidence": list(event.evidence),
        }

    @staticmethod
    def _apply_hard_contradictions(
        left: EventForMatching,
        right: EventForMatching,
        decision: SameEventDecision,
    ) -> SameEventDecision:
        contradictions = list(decision.evidence.contradictions)
        same_entity = decision.evidence.same_entity
        same_location = decision.evidence.same_location
        same_issue = decision.evidence.same_issue
        left_entities = {str(value) for value in left.entity_ids}
        right_entities = {str(value) for value in right.entity_ids}
        if left_entities and right_entities and left_entities.isdisjoint(right_entities):
            same_entity = False
            contradictions.append("canonical_entity_conflict")
        unique_contradictions = tuple(dict.fromkeys(contradictions))
        if not unique_contradictions:
            return decision
        return SameEventDecision(
            same_event=False,
            confidence=min(decision.confidence, 0.99),
            evidence=SameEventEvidence(
                same_entity=same_entity,
                same_location=same_location,
                same_issue=same_issue,
                time_compatible=decision.evidence.time_compatible,
                contradictions=unique_contradictions,
            ),
            trace=decision.trace,
        )
