from dataclasses import dataclass
from uuid import UUID

from backend.app.domain.analysis import (
    ExtractedEvent,
    ExtractedMention,
    StructuredUnderstanding,
    TextSegment,
)
from backend.app.domain.ports.analysis import LLMProvider, WorkOrderSegmenter
from backend.app.domain.ports.gazetteer import MentionResolver
from backend.app.domain.types import LLMRequest, VersionTrace
from backend.app.schemas.ai import (
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
        pipeline_version: str = "understanding.v1",
        schema_version: str = "understanding.v1",
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
                )
            understanding = WorkOrderUnderstanding.model_validate(llm_result.structured_output)
            if understanding.trace is None:
                understanding = understanding.model_copy(
                    update={
                        "trace": UnderstandingTrace(
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
                self._to_domain(understandings[index]),
                traces[index],
            )
            for index in range(len(items))
        )

    @staticmethod
    def _to_domain(understanding: WorkOrderUnderstanding) -> StructuredUnderstanding:
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
                    normalized_summary=event.normalized_summary,
                    location_signals=tuple(event.location_signals),
                    mention_indexes=tuple(event.mention_indexes),
                )
                for event in understanding.events
            ),
        )

    @staticmethod
    def _prompt(title: str | None, segments: tuple[TextSegment, ...]) -> str:
        title_line = f"标题：{title.strip()}\n" if title and title.strip() else ""
        segment_lines = "\n".join(
            f"[{segment.ordinal}|{segment.segment_type.value}] {segment.text}"
            for segment in segments
        )
        return (
            f"{title_line}请从以下已分段工单中抽取当前投诉、历史背景、部门回复、当前诉求、"
            f"地点/机构 mention 和一个或多个独立事件。mention 的 offset 相对于对应原文段落"
            f"不可臆造；"
            f"无法确认时使用 unresolved。\n{segment_lines}"
        )
