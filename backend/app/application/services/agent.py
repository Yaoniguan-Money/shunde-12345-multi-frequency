"""Application orchestration for the evidence-first intelligent assessment Agent."""

import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.domain.ports.analysis import LLMProvider
from backend.app.domain.types import EmbeddingRequest, LLMRequest, ProviderRoute
from backend.app.infrastructure.ai.factory import AIProviderBundle, build_provider_bundle
from backend.app.infrastructure.ai.remote import RemoteOpenAICompatibleLLMProvider
from backend.app.infrastructure.db.agent import AgentDashboardValues, AgentRecord, AgentRepository
from backend.app.schemas.agent import (
    AgentQueryDSL,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentTimeRange,
    AgentTopicGroup,
    AgentWorkOrderResult,
    BatchActionPayload,
    BatchActionPreviewResponse,
    DynamicDashboardResponse,
    WorksetCreateRequest,
    WorksetResponse,
)


class AgentCommandError(ValueError):
    """A bounded Agent command cannot be executed safely."""


class WorksetView(Protocol):
    id: UUID
    name: str
    original_query: str
    created_at: datetime
    created_by: str
    metadata_json: dict[str, object]


class AgentOrchestrator:
    """Turns natural language into a controlled DSL, never free-form SQL."""

    def __init__(
        self,
        repository: AgentRepository,
        settings: Settings,
        providers: AIProviderBundle | None,
        planner_llm: LLMProvider | None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._providers = providers
        self._planner_llm = planner_llm

    @classmethod
    def create(cls, repository: AgentRepository, settings: Settings) -> "AgentOrchestrator":
        try:
            providers = build_provider_bundle(settings)
        except Exception:
            # An unavailable configured model does not become a cloud fallback.  The
            # deterministic planner remains explicit in the response as `rules`.
            providers = None
        planner_llm: LLMProvider | None = providers.llm if providers is not None else None
        if settings.agent_deepseek_base_url and settings.agent_deepseek_api_key:
            planner_llm = RemoteOpenAICompatibleLLMProvider(
                str(settings.agent_deepseek_base_url),
                settings.agent_deepseek_model_id,
                settings.agent_deepseek_api_key,
                timeout_seconds=settings.model_timeout_seconds,
                concurrency=1,
            )
        return cls(repository, settings, providers, planner_llm)

    async def query(self, request: AgentQueryRequest) -> AgentQueryResponse:
        rules_plan = self._rules_plan(request)
        compiled, planner_mode = await self._plan_with_llm(request.query, rules_plan)
        created_after, created_before = _compile_time_range(compiled.time_range)
        vector, embedding_model_id = await self._semantic_vector(request.query)
        records = await self._repository.retrieve(
            keywords=_retrieval_terms(compiled),
            entity=compiled.entity,
            location=compiled.location,
            event_type=compiled.event_type,
            work_order_ids=tuple(compiled.work_order_ids),
            created_after=created_after,
            created_before=created_before,
            limit=compiled.limit,
            semantic_vector=vector,
            semantic_model_id=embedding_model_id,
        )
        work_orders = [_work_order_result(item) for item in records]
        topic_groups = _groups(item.event_type or "未归类" for item in work_orders)
        handling_groups = _groups(item.handling_status for item in work_orders)
        cluster_ids = list(
            dict.fromkeys(cluster_id for item in work_orders for cluster_id in item.cluster_ids)
        )
        answer = _evidence_answer(len(work_orders), topic_groups, cluster_ids)
        return AgentQueryResponse(
            original_query=request.query,
            compiled_query=compiled,
            planner_mode=planner_mode,
            answer=answer,
            disclaimer="结果来自当前工单与 V2 事件记录；群众投诉内容不等同于行政事实认定。",
            total=len(work_orders),
            topic_groups=topic_groups,
            handling_groups=handling_groups,
            work_orders=work_orders,
            cluster_ids=cluster_ids,
        )

    async def create_workset(self, request: WorksetCreateRequest) -> WorksetResponse:
        workset = await self._repository.create_workset(
            name=request.name,
            original_query=request.original_query,
            query_snapshot=request.query_snapshot.model_dump(mode="json"),
            work_order_ids=tuple(request.work_order_ids),
            cluster_ids=tuple(request.cluster_ids),
            created_by=request.created_by,
        )
        return _workset_response(
            cast(WorksetView, workset),
            request.query_snapshot,
            request.work_order_ids,
            request.cluster_ids,
        )

    async def get_workset(self, workset_id: UUID) -> WorksetResponse | None:
        record = await self._repository.get_workset(workset_id)
        if record is None:
            return None
        workset, work_order_ids, cluster_ids = record
        return _workset_response(
            cast(WorksetView, workset),
            AgentQueryDSL.model_validate(workset.query_snapshot),
            work_order_ids,
            cluster_ids,
        )

    async def preview_action(
        self, workset_id: UUID, payload: BatchActionPayload
    ) -> BatchActionPreviewResponse:
        if payload.action_type != "export_csv" and payload.new_status is None:
            raise AgentCommandError("批量状态或处理记录必须指定新的处理状态")
        preview, snapshot = await self._repository.create_preview(
            workset_id=workset_id,
            action_type=payload.action_type,
            payload=payload.model_dump(mode="json"),
            actor_id=payload.actor_id,
        )
        count = snapshot["affected_work_order_count"]
        return BatchActionPreviewResponse(
            preview_id=preview.id,
            action_type=payload.action_type,
            affected_work_order_count=count,
            affected_cluster_count=snapshot["affected_cluster_count"],
            skipped_work_order_count=snapshot["skipped_work_order_count"],
            before_status_counts=snapshot["before_status_counts"],
            after_status=payload.new_status,
            message=_preview_message(payload.action_type, count, payload.new_status),
        )

    async def execute_action(self, preview_id: UUID, actor_id: str) -> tuple[str, int, str | None]:
        return await self._repository.execute_preview(preview_id, actor_id)

    async def dashboard(
        self, *, title: str, work_order_ids: tuple[UUID, ...], cluster_ids: tuple[UUID, ...]
    ) -> DynamicDashboardResponse:
        values: AgentDashboardValues = await self._repository.dashboard(work_order_ids, cluster_ids)
        return DynamicDashboardResponse(
            title=title,
            work_order_count=values["work_order_count"],
            multi_frequency_event_count=values["multi_frequency_event_count"],
            topic_groups=[AgentTopicGroup.model_validate(item) for item in values["topic_groups"]],
            handling_groups=[
                AgentTopicGroup.model_validate(item) for item in values["handling_groups"]
            ],
            location_groups=[
                AgentTopicGroup.model_validate(item) for item in values["location_groups"]
            ],
            focus_cluster_ids=values["focus_cluster_ids"],
            disclaimer="所有统计均基于当前查询或工作集的真实工单范围，不代表行政事实认定。",
        )

    def _rules_plan(self, request: AgentQueryRequest) -> AgentQueryDSL:
        text = request.query.strip()
        prior = request.previous_query_snapshot
        keywords = _keywords(text)
        plan = AgentQueryDSL(
            intent="refine_previous"
            if _is_follow_up(text) and request.previous_work_order_ids
            else "search_work_orders",
            time_range=_time_range(text)
            or (prior.time_range if prior and _is_follow_up(text) else None),
            keywords=keywords or (prior.keywords if prior and _is_follow_up(text) else []),
            topic=_topic(text) or (prior.topic if prior and _is_follow_up(text) else None),
            entity=prior.entity if prior and _is_follow_up(text) else None,
            location=_location(text) or (prior.location if prior and _is_follow_up(text) else None),
            event_type=prior.event_type if prior and _is_follow_up(text) else None,
            handling_status=_handling_status(text)
            or (prior.handling_status if prior and _is_follow_up(text) else None),
            sort="newest" if "最新" in text else "relevance",
            limit=request.limit,
            work_order_ids=request.previous_work_order_ids if _is_follow_up(text) else [],
        )
        return plan

    async def _plan_with_llm(
        self, query: str, rules_plan: AgentQueryDSL
    ) -> tuple[AgentQueryDSL, Literal["llm", "rules"]]:
        if self._planner_llm is None:
            return rules_plan, "rules"
        prompt = (
            "将用户问题解析为受控 12345 工单查询 DSL。只能填写给定字段，绝不生成 SQL。"
            "不确定则保留 null 或空数组。时间相对值使用 last_7_days、last_30_days。\n"
            f"用户问题：{query}\n规则初稿：{rules_plan.model_dump_json()}"
        )
        schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "topic": {"type": ["string", "null"]},
                "entity": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "event_type": {"type": ["string", "null"]},
                "handling_status": {"type": ["string", "null"]},
                "sort": {"type": "string"},
                "time_range": {"type": ["object", "null"]},
            },
        }
        try:
            result = await self._planner_llm.generate_batch(
                (
                    LLMRequest(
                        request_id=str(uuid4()),
                        prompt=prompt,
                        output_schema=schema,
                        schema_version="agent-query-dsl.v1",
                        pipeline_version="agent-demo-v2",
                        route=ProviderRoute.REMOTE,
                    ),
                )
            )
            candidate = _merge_llm_plan(rules_plan, result[0].structured_output)
            return candidate, "llm"
        except Exception:
            return rules_plan, "rules"

    async def _semantic_vector(self, query: str) -> tuple[list[float] | None, str | None]:
        if self._providers is None or self._providers.plan.remote_embedding is None:
            return None, None
        try:
            result = await self._providers.embeddings.embed_batch(
                (
                    EmbeddingRequest(
                        item_id="agent-query",
                        text=query,
                        schema_version="agent-retrieval.v1",
                        pipeline_version="agent-demo-v2",
                        route=ProviderRoute.REMOTE,
                    ),
                )
            )
            return list(result[0].vector), result[0].model_id
        except Exception:
            return None, None


def _merge_llm_plan(base: AgentQueryDSL, values: dict[str, object]) -> AgentQueryDSL:
    allowed = {
        "intent",
        "keywords",
        "topic",
        "entity",
        "location",
        "event_type",
        "handling_status",
        "sort",
        "time_range",
    }
    patch = {key: value for key, value in values.items() if key in allowed}
    if "time_range" in patch and isinstance(patch["time_range"], dict):
        raw_time = cast(dict[str, object], patch["time_range"])
        if raw_time.get("value") not in {"last_7_days", "last_30_days"}:
            patch.pop("time_range")
    try:
        return AgentQueryDSL.model_validate({**base.model_dump(), **patch})
    except ValidationError:
        return base


def _compile_time_range(value: AgentTimeRange | None) -> tuple[datetime | None, datetime | None]:
    if value is None:
        return None, None
    now = datetime.now(UTC)
    if value.kind == "relative":
        if value.value == "last_7_days":
            return now - timedelta(days=7), now
        if value.value == "last_30_days":
            return now - timedelta(days=30), now
    return value.start, value.end


def _time_range(text: str) -> AgentTimeRange | None:
    if any(token in text for token in ("这一周", "最近一周", "近一周", "7天")):
        return AgentTimeRange(kind="relative", value="last_7_days")
    if any(token in text for token in ("最近一个月", "近一个月", "30天")):
        return AgentTimeRange(kind="relative", value="last_30_days")
    return None


def _keywords(text: str) -> list[str]:
    dictionary = (
        "工程款",
        "项目款",
        "拖欠",
        "工资",
        "噪音",
        "艾灸",
        "环境",
        "学校",
        "占道",
        "食品",
    )
    return [item for item in dictionary if item in text][:8]


def _topic(text: str) -> str | None:
    if any(item in text for item in ("工程款", "项目款", "施工费用", "尾款")):
        return "工程款"
    if "工资" in text or "欠薪" in text:
        return "工资"
    if "噪音" in text:
        return "噪音"
    return None


def _retrieval_terms(plan: AgentQueryDSL) -> tuple[str, ...]:
    expansions = {
        "工程款": ("工程款", "项目款", "施工费用", "尾款", "劳务费", "工资", "拖欠"),
        "工资": ("工资", "欠薪", "劳务费", "拖欠"),
        "噪音": ("噪音", "噪声", "扰民"),
    }
    terms = [*plan.keywords, *(expansions.get(plan.topic, ()) if plan.topic else ())]
    return tuple(dict.fromkeys(term for term in terms if term))


def _location(text: str) -> str | None:
    match = re.search(r"(金域滨江|龙江|大良|容桂|陈村|勒流|北滘|杏坛|均安)", text)
    return match.group(1) if match else None


def _handling_status(text: str) -> Literal["unhandled", "investigating", "resolved"] | None:
    if any(item in text for item in ("未处理", "还没处理", "未办")):
        return "unhandled"
    if any(item in text for item in ("跟进", "处理中", "正在处理")):
        return "investigating"
    if any(item in text for item in ("已处理", "已解决", "办结")):
        return "resolved"
    return None


def _is_follow_up(text: str) -> bool:
    return any(item in text for item in ("这些", "刚才", "只看", "其中", "上一步"))


def _work_order_result(value: AgentRecord) -> AgentWorkOrderResult:
    return AgentWorkOrderResult(
        work_order_id=value["work_order_id"],
        external_work_order_number=value["external_work_order_number"],
        title=value["title"],
        reported_at=None,
        time_label="系统入库时间",
        normalized_summary=value["normalized_summary"],
        location=value["location"],
        event_type=value["event_type"],
        handling_status=str(value["handling_status"]),
        cluster_ids=value["cluster_ids"],
        is_multi_frequency=bool(value["is_multi_frequency"]),
        retrieval_evidence=value["retrieval_evidence"],
    )


def _groups(values: Iterable[str]) -> list[AgentTopicGroup]:
    return [
        AgentTopicGroup(label=label, count=count) for label, count in Counter(values).most_common(8)
    ]


def _evidence_answer(total: int, topics: list[AgentTopicGroup], cluster_ids: list[UUID]) -> str:
    if total == 0:
        return "当前条件下未检索到可追溯的工单记录；可尝试放宽时间、地点或关键词。"
    topic_text = "、".join(f"{item.label} {item.count} 条" for item in topics[:3]) or "待归类"
    cluster_text = f"，其中关联多频事件 {len(cluster_ids)} 个" if cluster_ids else ""
    return (
        f"系统检索到 {total} 条相关投诉记录，主要涉及：{topic_text}{cluster_text}。"
        "以下每条均可回到真实工单核查。"
    )


def _workset_response(
    workset: WorksetView,
    query_snapshot: AgentQueryDSL,
    work_order_ids: list[UUID],
    cluster_ids: list[UUID],
) -> WorksetResponse:
    return WorksetResponse(
        id=workset.id,
        name=workset.name,
        original_query=workset.original_query,
        query_snapshot=query_snapshot,
        work_order_ids=work_order_ids,
        cluster_ids=cluster_ids,
        created_at=workset.created_at,
        created_by=workset.created_by,
        result_count=len(work_order_ids),
        metadata=workset.metadata_json,
    )


def _preview_message(action_type: str, count: int, status: str | None) -> str:
    if action_type == "export_csv":
        return f"准备导出 {count} 条工单，确认后生成 CSV。"
    label = {"unhandled": "未处理", "investigating": "正在跟进", "resolved": "已解决"}.get(
        status or "", status or ""
    )
    return f"准备处理 {count} 条工单，确认后统一记录为“{label}”。"
