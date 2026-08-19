"""Bounded DeepSeek composition over already-scoped Agent evidence."""

import json
import logging
from uuid import uuid4

from backend.app.domain.ports.analysis import LLMProvider
from backend.app.domain.types import LLMRequest, ProviderRoute
from backend.app.infrastructure.db.agent import AgentRecord

logger = logging.getLogger(__name__)

_MAX_EVIDENCE_ITEMS = 20
_MAX_RAW_EXCERPT = 240
_MAX_COMPOSER_TEXT = 600


async def compose_evidence_answer(
    *,
    planner_llm: LLMProvider | None,
    query: str,
    records: list[AgentRecord],
    factual_summary: str,
) -> str:
    """Add clearly-labelled AI analysis without changing evidence-backed facts."""
    if planner_llm is None or not records:
        return factual_summary
    evidence = [_evidence_item(record) for record in records[:_MAX_EVIDENCE_ITEMS]]
    prompt = (
        "你是12345工单研判助手。只依据给出的真实工单证据写简洁中文研判。"
        "不得增加不存在的地点、工单、数量、因果或政府处置事实。"
        "可能原因必须是推测，建议必须标注为 AI 建议；不能把投诉内容表述为行政事实认定。\n"
        f"用户问题：{query}\n"
        f"真实证据（最多{_MAX_EVIDENCE_ITEMS}条）：{json.dumps(evidence, ensure_ascii=False)}"
    )
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "analysis": {"type": "string"},
            "possible_reason": {"type": "string"},
            "recommendation": {"type": "string"},
        },
    }
    try:
        result = await planner_llm.generate_batch(
            (
                LLMRequest(
                    request_id=str(uuid4()),
                    prompt=prompt,
                    output_schema=schema,
                    schema_version="agent-analysis-composer.v1",
                    pipeline_version="agent-demo-v2",
                    route=ProviderRoute.REMOTE,
                ),
            )
        )
    except Exception as error:
        logger.warning(
            "Agent analysis composer fell back to factual summary",
            extra={
                "composer_provider": "deepseek",
                "error_type": type(error).__name__,
                "pipeline_version": "agent-demo-v2",
            },
        )
        return factual_summary
    payload = result[0].structured_output
    analysis = _text(payload.get("analysis"))
    if not analysis:
        return factual_summary
    sections = [factual_summary, f"AI研判（非行政事实认定）：{analysis}"]
    possible_reason = _text(payload.get("possible_reason"))
    if possible_reason:
        sections.append(f"可能原因（AI推测）：{possible_reason}")
    recommendation = _text(payload.get("recommendation"))
    if recommendation:
        sections.append(f"建议首先核查（AI建议）：{recommendation}")
    return "\n\n".join(sections)


def _evidence_item(record: AgentRecord) -> dict[str, object]:
    return {
        "工单号": record["external_work_order_number"] or str(record["work_order_id"]),
        "原始标题": record["title"] or "",
        "原文摘录": record["raw_content"][:_MAX_RAW_EXCERPT],
        "V2摘要": record["normalized_summary"] or "",
        "V2地点信号": record["location_signals"],
        "事件类型": record["event_type"] or "",
        "办理状态": record["handling_status"],
        "关联多频簇": [str(item) for item in record["cluster_ids"]],
    }


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())[:_MAX_COMPOSER_TEXT]
    return cleaned or None
