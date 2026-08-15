from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from backend.app.domain.analysis import (
    EventEvidence,
    ExtractedEvent,
    ExtractedMention,
    StructuredUnderstanding,
    TextSegment,
)
from backend.app.domain.ports.analysis import LLMProvider, WorkOrderSegmenter
from backend.app.domain.ports.gazetteer import MentionResolver
from backend.app.domain.types import LLMRequest, VersionTrace
from backend.app.schemas.ai import (
    EventEvidenceItem,
    UnderstandingTrace,
    WorkOrderUnderstanding,
)


@dataclass(frozen=True, slots=True)
class UnderstandingResult:
    work_order_id: UUID
    segments: tuple[TextSegment, ...]
    understanding: StructuredUnderstanding
    trace: VersionTrace


class WorkOrderUnderstandingService:
    """Segment, extract and resolve one or more work orders through typed seams."""

    def __init__(
        self,
        segmenter: WorkOrderSegmenter,
        llm_provider: LLMProvider,
        *,
        gazetteer: MentionResolver | None = None,
        pipeline_version: str = "understanding.v2",
        schema_version: str = "understanding.v2",
        knowledge_snapshot_id: UUID | None = None,
    ) -> None:
        self._segmenter = segmenter
        self._llm = llm_provider
        self._gazetteer = gazetteer
        self._pipeline_version = pipeline_version
        self._schema_version = schema_version
        self._knowledge_snapshot_id = knowledge_snapshot_id

    async def understand(
        self,
        work_order_id: UUID,
        title: str | None,
        content: str,
    ) -> UnderstandingResult:
        results = await self.understand_batch(((work_order_id, title, content),))
        return results[0]

    async def understand_batch(
        self, items: tuple[tuple[UUID, str | None, str], ...]
    ) -> tuple[UnderstandingResult, ...]:
        if not items:
            return ()
        segmented = tuple(
            (work_order_id, title, self._segmenter.segment(title, content))
            for work_order_id, title, content in items
        )
        requests = tuple(
            LLMRequest(
                request_id=str(work_order_id),
                prompt=self._prompt(title, segments),
                output_schema=WorkOrderUnderstanding.model_json_schema(),
                schema_version=self._schema_version,
                pipeline_version=self._pipeline_version,
            )
            for work_order_id, title, segments in segmented
        )
        llm_results = await self._llm.generate_batch(requests)
        if len(llm_results) != len(items):
            raise RuntimeError("LLM provider returned an unexpected result count")
        understandings: list[WorkOrderUnderstanding] = []
        traces: list[VersionTrace] = []
        for llm_result in llm_results:
            trace = llm_result.trace
            if trace.knowledge_snapshot_id is None and self._knowledge_snapshot_id is not None:
                trace = VersionTrace(
                    model_id=trace.model_id,
                    model_config_hash=trace.model_config_hash,
                    schema_version=trace.schema_version,
                    knowledge_snapshot_id=self._knowledge_snapshot_id,
                    pipeline_version=trace.pipeline_version,
                    provider=trace.provider,
                )
            understanding = WorkOrderUnderstanding.model_validate(llm_result.structured_output)
            if understanding.trace is None:
                understanding = understanding.model_copy(
                    update={
                        "trace": UnderstandingTrace(
                            provider=trace.provider,
                            model_id=trace.model_id,
                            model_config_hash=trace.model_config_hash,
                            schema_version=trace.schema_version,
                            knowledge_snapshot_id=trace.knowledge_snapshot_id,
                            pipeline_version=trace.pipeline_version,
                        )
                    }
                )
            if self._gazetteer is None and any(
                mention.canonical_entity_id is not None for mention in understanding.mentions
            ):
                understanding = understanding.model_copy(
                    update={
                        "mentions": [
                            mention.model_copy(
                                update={
                                    "canonical_entity_id": None,
                                    "resolution_state": "unresolved",
                                    "confidence": None,
                                    "evidence": [],
                                }
                            )
                            for mention in understanding.mentions
                        ]
                    }
                )
            understandings.append(understanding)
            traces.append(trace)
        if self._gazetteer is not None:
            mention_locations = [
                (result_index, mention_index)
                for result_index, understanding in enumerate(understandings)
                for mention_index, _mention in enumerate(understanding.mentions)
            ]
            if mention_locations:
                candidates = await self._gazetteer.resolve_many(
                    tuple(
                        understandings[result_index].mentions[mention_index].text
                        for result_index, mention_index in mention_locations
                    )
                )
                if len(candidates) != len(mention_locations):
                    raise RuntimeError("gazetteer returned an unexpected result count")
                mutable_mentions = [
                    list(understanding.mentions) for understanding in understandings
                ]
                for (result_index, mention_index), candidate_set in zip(
                    mention_locations, candidates, strict=True
                ):
                    mention = mutable_mentions[result_index][mention_index]
                    best = candidate_set.candidates[0] if candidate_set.candidates else None
                    mutable_mentions[result_index][mention_index] = mention.model_copy(
                        update={
                            "canonical_entity_id": best.entity.entity_id if best else None,
                            "resolution_state": candidate_set.state.value,
                            "confidence": best.confidence if best else None,
                            "evidence": list(best.evidence) if best else [],
                        }
                    )
                understandings = [
                    understanding.model_copy(update={"mentions": mutable_mentions[index]})
                    for index, understanding in enumerate(understandings)
                ]
        return tuple(
            UnderstandingResult(
                items[index][0],
                segmented[index][2],
                self._to_domain(understandings[index], segmented[index][2]),
                traces[index],
            )
            for index in range(len(items))
        )

    @staticmethod
    def _to_domain(
        understanding: WorkOrderUnderstanding,
        segments: tuple[TextSegment, ...],
    ) -> StructuredUnderstanding:
        segments_by_ordinal = {segment.ordinal: segment for segment in segments}
        return StructuredUnderstanding(
            current_complaint=understanding.current_complaint,
            historical_context=understanding.historical_context,
            department_reply=understanding.department_reply,
            current_request=understanding.current_request,
            mentions=tuple(
                ExtractedMention(
                    text=mention.text,
                    mention_type=mention.mention_type.value,
                    start_offset=mention.start_offset,
                    end_offset=mention.end_offset,
                    canonical_entity_id=mention.canonical_entity_id,
                    resolution_state=mention.resolution_state,
                    confidence=mention.confidence,
                    evidence=tuple(mention.evidence),
                )
                for mention in understanding.mentions
            ),
            events=tuple(
                ExtractedEvent(
                    event_type=event.event_type,
                    behavior=event.behavior,
                    normalized_summary=event.normalized_summary,
                    location_signals=tuple(event.location_signals),
                    time_signals=tuple(
                        signal.strip()
                        for signal in event.time_signals
                        if signal.strip()
                        and any(signal.strip() in segment.text for segment in segments)
                    ),
                    mention_indexes=tuple(event.mention_indexes),
                    evidence=WorkOrderUnderstandingService._validated_event_evidence(
                        event.evidence, segments_by_ordinal
                    ),
                )
                for event in understanding.events
            ),
        )

    @staticmethod
    def _validated_event_evidence(
        evidence: Sequence[EventEvidenceItem], segments_by_ordinal: dict[int, TextSegment]
    ) -> tuple[EventEvidence, ...]:
        validated: list[EventEvidence] = []
        for item in evidence:
            segment_ordinal = getattr(item, "segment_ordinal", None)
            quote = getattr(item, "quote", None)
            if not isinstance(segment_ordinal, int) or not isinstance(quote, str):
                continue
            segment = segments_by_ordinal.get(segment_ordinal)
            normalized_quote = quote.strip()
            if segment is None or not normalized_quote:
                continue
            relative_start = segment.text.find(normalized_quote)
            if relative_start < 0:
                continue
            validated.append(
                EventEvidence(
                    segment_ordinal=segment.ordinal,
                    segment_type=segment.segment_type.value,
                    quote=normalized_quote,
                    start_offset=segment.start_offset + relative_start,
                    end_offset=segment.start_offset + relative_start + len(normalized_quote),
                )
            )
        return tuple(validated)

    @staticmethod
    def _prompt(title: str | None, segments: tuple[TextSegment, ...]) -> str:
        title_line = f"标题：{title.strip()}\n" if title and title.strip() else ""
        segment_lines = "\n".join(
            f"[{segment.ordinal}|{segment.segment_type.value}] {segment.text}"
            for segment in segments
        )
        return (
            f"{title_line}请从以下已分段工单中抽取当前投诉、历史背景、部门回复、当前诉求、"
            f"地点/机构 mention 和一个或多个独立事件。每个事件必须单独填写 behavior（该事件的"
            f"处理/诉求动作，不要把整张工单 current_request 原样复制）、time_signals（原文中出现的"
            f"时间词或时间表达）和 evidence。evidence 只能引用下面输入中连续出现的原文，填写准确的"
            f"segment_ordinal 与 quote；不能改写或编造证据。mention 的 offset 相对于对应原文段落"
            f"不可臆造；每个文本字段只写简洁摘要（建议不超过120个汉字），部门回复只保留"
            f"处理结论，不要复制整段回复；每个事件摘要不超过100个汉字。"
            f"无法确认时使用 unresolved。\n{segment_lines}"
        )
