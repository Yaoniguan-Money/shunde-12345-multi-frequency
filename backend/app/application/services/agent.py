"""Application orchestration for the evidence-first intelligent assessment Agent."""

import logging
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from backend.app.application.services.agent_composer import compose_evidence_answer
from backend.app.config import Settings
from backend.app.domain.ports.analysis import LLMProvider
from backend.app.domain.title_tags import TITLE_TAG_WHITELIST
from backend.app.domain.types import EmbeddingRequest, LLMRequest, ProviderRoute
from backend.app.infrastructure.ai.factory import AIProviderBundle, build_provider_bundle
from backend.app.infrastructure.ai.remote import RemoteOpenAICompatibleLLMProvider
from backend.app.infrastructure.db.agent import AgentDashboardValues, AgentRecord, AgentRepository
from backend.app.schemas.agent import (
    AgentDrilldown,
    AgentQueryDSL,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentQueryResultsRequest,
    AgentQueryResultsResponse,
    AgentTimeRange,
    AgentTopicGroup,
    AgentTreeChild,
    AgentTreeGroup,
    AgentWorkOrderResult,
    BatchActionPayload,
    BatchActionPreviewResponse,
    DynamicDashboardResponse,
    WorksetCreateRequest,
    WorksetListResponse,
    WorksetResponse,
    WorksetWorkspaceResponse,
)

logger = logging.getLogger(__name__)


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
        # V2 may have a different remote chat model configured.  The Agent
        # planner is intentionally DeepSeek-only; absence is explicit rules
        # mode, never a silent Qwen (or other provider) substitution.
        planner_llm: LLMProvider | None = None
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
        compiled, planner_mode = await self._plan_with_llm(request, rules_plan)
        records = await self._scope_records(compiled)
        total = len(records)
        page_records = records[: request.limit]
        work_orders = [_work_order_result(item) for item in page_records]
        topic_groups = _groups(item["event_type"] or "未归类" for item in records)
        handling_groups = _groups(item["handling_status"] for item in records)
        cluster_ids = list(
            dict.fromkeys(cluster_id for item in records for cluster_id in item["cluster_ids"])
        )
        factual_summary = _evidence_answer(
            compiled,
            request.query,
            total,
            records,
            topic_groups,
            handling_groups,
            cluster_ids,
        )
        answer = await compose_evidence_answer(
            planner_llm=self._planner_llm,
            query=request.query,
            records=records,
            factual_summary=factual_summary,
        )
        return AgentQueryResponse(
            original_query=request.query,
            compiled_query=compiled,
            planner_mode=planner_mode,
            answer=answer,
            disclaimer="结果来自当前工单与 V2 事件记录；群众投诉内容不等同于行政事实认定。",
            total=total,
            topic_groups=topic_groups,
            handling_groups=handling_groups,
            work_orders=work_orders,
            cluster_ids=cluster_ids,
            matched_total=total,
            page=1,
            page_size=request.limit,
            retrieval_trace=[item["retrieval_trace"] for item in page_records]
            if self._settings.environment != "production"
            else [],
        )

    async def query_results(self, request: AgentQueryResultsRequest) -> AgentQueryResultsResponse:
        records = _apply_drilldown(
            await self._scope_records(request.compiled_query), request.drilldown
        )
        start = (request.page - 1) * request.page_size
        return AgentQueryResultsResponse(
            matched_total=len(records),
            page=request.page,
            page_size=request.page_size,
            items=[_work_order_result(item) for item in records[start : start + request.page_size]],
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

    async def list_worksets(self) -> WorksetListResponse:
        records = await self._repository.list_worksets()
        items = [
            _workset_response(
                cast(WorksetView, workset),
                AgentQueryDSL.model_validate(workset.query_snapshot),
                work_order_ids,
                cluster_ids,
            )
            for workset, work_order_ids, cluster_ids in records
        ]
        return WorksetListResponse(items=items, total=len(items))

    async def workspace(self, workset_id: UUID) -> WorksetWorkspaceResponse | None:
        record = await self._repository.get_workset(workset_id)
        if record is None:
            return None
        workset, work_order_ids, cluster_ids = record
        members = await self._repository.retrieve(
            keywords=(),
            issue_terms=(),
            issue_required=False,
            entity=None,
            location=None,
            event_type=None,
            title_tag=None,
            work_order_ids=tuple(work_order_ids),
            handling_status=None,
            reported_after=None,
            reported_before=None,
            limit=None,
            semantic_vector=None,
            semantic_model_id=None,
            complete_scope=True,
        )
        dashboard = await self.dashboard(
            title=workset.name,
            work_order_ids=tuple(work_order_ids),
            cluster_ids=tuple(cluster_ids),
        )
        return WorksetWorkspaceResponse(
            workset=_workset_response(
                cast(WorksetView, workset),
                AgentQueryDSL.model_validate(workset.query_snapshot),
                work_order_ids,
                cluster_ids,
            ),
            work_orders=[_work_order_result(item) for item in members],
            dashboard=dashboard,
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

    async def execute_action(
        self, workset_id: UUID, preview_id: UUID, actor_id: str
    ) -> tuple[str, int, str | None]:
        return await self._repository.execute_preview(workset_id, preview_id, actor_id)

    async def dashboard(
        self,
        *,
        title: str,
        work_order_ids: tuple[UUID, ...],
        cluster_ids: tuple[UUID, ...],
        compiled_query: AgentQueryDSL | None = None,
        drilldown: AgentDrilldown | None = None,
    ) -> DynamicDashboardResponse:
        if compiled_query is not None:
            return _dashboard_response(
                title, _apply_drilldown(await self._scope_records(compiled_query), drilldown)
            )
        values: AgentDashboardValues = await self._repository.dashboard(work_order_ids, cluster_ids)
        return DynamicDashboardResponse(
            title=title,
            work_order_count=values["work_order_count"],
            multi_frequency_event_count=values["multi_frequency_event_count"],
            multi_frequency_work_order_count=values["multi_frequency_work_order_count"],
            high_frequency_event_count=values["high_frequency_event_count"],
            urgent_count=values["urgent_count"],
            topic_groups=[AgentTopicGroup.model_validate(item) for item in values["topic_groups"]],
            handling_groups=[
                AgentTopicGroup.model_validate(item) for item in values["handling_groups"]
            ],
            location_groups=[
                AgentTopicGroup.model_validate(item) for item in values["location_groups"]
            ],
            topic_tree=[],
            location_tree=[],
            status_tree=[],
            focus_cluster_ids=values["focus_cluster_ids"],
            disclaimer="所有统计均基于当前查询或工作集的真实工单范围，不代表行政事实认定。",
        )

    async def _scope_records(self, compiled: AgentQueryDSL) -> list[AgentRecord]:
        """The durable scope never inherits a page limit from the UI."""
        reported_after, reported_before = _compile_time_range(compiled.time_range)
        vector, embedding_model_id = await self._semantic_vector(_scope_query_text(compiled))
        return await self._repository.retrieve(
            keywords=_retrieval_terms(compiled),
            issue_terms=_issue_terms(compiled),
            issue_required=compiled.issue_required,
            entity=compiled.entity,
            location=compiled.location,
            event_type=compiled.event_type,
            title_tag=compiled.title_tag,
            work_order_ids=tuple(compiled.work_order_ids),
            handling_status=compiled.handling_status,
            reported_after=reported_after,
            reported_before=reported_before,
            limit=None,
            semantic_vector=vector,
            semantic_model_id=embedding_model_id,
            complete_scope=True,
        )

    def _rules_plan(self, request: AgentQueryRequest) -> AgentQueryDSL:
        text = request.query.strip()
        prior = request.previous_query_snapshot
        context_mode = _context_mode(text, prior)
        inherited = prior if context_mode != "new_scope" and prior is not None else AgentQueryDSL()
        explicit_topic = _topic(text)
        plan = AgentQueryDSL(
            intent="refine_previous" if context_mode != "new_scope" else "search_work_orders",
            time_range=_time_range(text) or inherited.time_range,
            keywords=_keywords(text) or inherited.keywords,
            topic=explicit_topic or inherited.topic,
            title_tag=_title_tag(text) or inherited.title_tag,
            # Aggregation describes this utterance's answer shape, not the
            # durable active scope. A later time/status refinement starts with
            # a fresh answer intent unless it asks to count/group again.
            aggregation=_aggregation(text) or "none",
            context_mode=context_mode,
            issue_required=bool(explicit_topic) or inherited.issue_required,
            entity=inherited.entity,
            location=_location(text) or inherited.location,
            event_type=inherited.event_type,
            handling_status=_handling_status(text) or inherited.handling_status,
            sort="newest" if "最新" in text else "relevance",
            limit=request.limit,
            # Only a result reference is bound to the prior evidence set.
            # Scope refinements must rerun on the complete legal scope.
            work_order_ids=(
                request.previous_work_order_ids if context_mode == "reference_results" else []
            ),
        )
        return plan

    async def _plan_with_llm(
        self, request: AgentQueryRequest, rules_plan: AgentQueryDSL
    ) -> tuple[AgentQueryDSL, Literal["llm", "rules"]]:
        if self._planner_llm is None:
            return rules_plan, "rules"
        prior_dsl = (
            request.previous_query_snapshot.model_dump_json()
            if request.previous_query_snapshot
            else "无"
        )
        prompt = (
            "将用户问题解析为受控 12345 工单查询 DSL。只能填写给定字段，绝不生成 SQL。"
            "用户明确提及的地点、主体、工单号、办理状态、时间和问题类别都是硬筛选条件。"
            "例如“大良有没有拖欠工资”是大良范围内的欠薪问题，不是先查大良再按欠薪排序。"
            "location 应保留用户的开放文本地点原样（道路、小区、学校、园区、项目等均可），"
            "不得将地点写入 topic 或 keywords。"
            "不确定则保留 null 或空数组。时间相对值使用 last_7_days、last_30_days。"
            "title_tag=急 仅表示标题的确定性急标签；aggregation 表示统计方式。"
            "必须判断 context_mode：新范围、继续收窄范围、或引用上一轮结果。\n"
            f"上一轮用户问题：{request.previous_query or '无'}\n"
            f"上一轮 DSL：{prior_dsl}\n"
            f"上一轮证据工单 IDs：{[str(item) for item in request.previous_work_order_ids]}\n"
            f"当前用户问题：{request.query}\n规则初稿：{rules_plan.model_dump_json()}"
        )
        schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "topic": {"type": ["string", "null"]},
                "title_tag": {"type": ["string", "null"]},
                "aggregation": {"type": "string"},
                "context_mode": {"type": "string"},
                "issue_required": {"type": "boolean"},
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
        except Exception as error:
            logger.warning(
                "Agent planner fell back to controlled rules",
                extra={
                    "planner_provider": "deepseek",
                    "error_type": type(error).__name__,
                    "pipeline_version": "agent-demo-v2",
                },
            )
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
        except Exception as error:
            logger.warning(
                "Agent semantic retrieval is unavailable; continuing with structured evidence",
                extra={
                    "error_type": type(error).__name__,
                    "pipeline_version": "agent-demo-v2",
                },
            )
            return None, None


def _merge_llm_plan(base: AgentQueryDSL, values: dict[str, object]) -> AgentQueryDSL:
    allowed = {
        "intent",
        "keywords",
        "topic",
        "title_tag",
        "aggregation",
        "context_mode",
        "issue_required",
        "entity",
        "location",
        "event_type",
        "handling_status",
        "sort",
        "time_range",
    }
    patch = {key: value for key, value in values.items() if key in allowed}
    if base.issue_required:
        # The model may refine vocabulary but cannot relax an issue that the
        # deterministic parser identified as an explicit user constraint.
        patch["issue_required"] = True
    # Deterministic parsing owns hard title tags, aggregation phrases and
    # context inheritance. The model sees the full turn context to help with
    # underspecified language, but cannot relax these safe boundaries.
    if base.title_tag:
        patch["title_tag"] = base.title_tag
    if base.aggregation != "none":
        patch["aggregation"] = base.aggregation
    patch["context_mode"] = base.context_mode
    if base.context_mode == "reference_results":
        patch["work_order_ids"] = [str(item) for item in base.work_order_ids]
    if "location" in patch and not _is_location_candidate(patch["location"]):
        patch.pop("location")
    if base.location and not patch.get("location"):
        patch.pop("location", None)
    if base.entity and not patch.get("entity"):
        patch.pop("entity", None)
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
    if any(token in text for token in ("最近一个月", "近一个月", "30天", "最近", "近来")):
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
    if any(item in text for item in ("工资", "欠薪", "薪资", "劳动报酬", "结清")):
        return "工资"
    if "噪音" in text:
        return "噪音"
    return None


def _retrieval_terms(plan: AgentQueryDSL) -> tuple[str, ...]:
    expansions = {
        "工程款": ("工程款", "项目款", "施工费用", "尾款", "劳务费", "工资", "拖欠"),
        "工资": ("工资", "欠薪", "薪资", "劳务费", "拖欠", "结清", "未支付", "劳动报酬"),
        "噪音": ("噪音", "噪声", "扰民"),
    }
    terms = [*plan.keywords, *(expansions.get(plan.topic, ()) if plan.topic else ())]
    return tuple(dict.fromkeys(term for term in terms if term))


def _issue_terms(plan: AgentQueryDSL) -> tuple[str, ...]:
    if not plan.issue_required:
        return ()
    return _retrieval_terms(plan)


def _location(text: str) -> str | None:
    if any(item in text for item in ("全区", "全市", "全镇", "全域")):
        return None
    normalized = re.sub(r"[，。！？、,.!?]", " ", text).strip()
    prefix_match = re.match(
        r"(?:请问|帮我看看|查询|了解)?(?P<location>[\u4e00-\u9fffA-Za-z0-9·]{2,40}?)"
        r"(?:最近|近来|这段时间|有什么|有没有|是否有|有几条|有多少|多少条|发生了什么|相关工单|的情况)",
        normalized,
    )
    if prefix_match:
        candidate = prefix_match.group("location").strip(" 的在关于")
        if _is_location_candidate(candidate):
            return candidate
    suffix_match = re.search(
        r"(?P<location>[\u4e00-\u9fffA-Za-z0-9·]{1,24}"
        r"(?:大道|中路|东路|西路|南路|北路|路|街|巷|桥|学校|小区|园区|工业园|项目|广场|社区|村|苑))",
        normalized,
    )
    if suffix_match:
        candidate = suffix_match.group("location")
        if _is_location_candidate(candidate):
            return candidate
    return None


def _is_location_candidate(value: object) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if len(candidate) < 2 or len(candidate) > 128:
        return False
    if candidate in {"最近", "近来", "这段时间", "有什么", "发生了什么", "相关工单"}:
        return False
    return _topic(candidate) is None and not any(
        token in candidate for token in ("拖欠", "欠薪", "工程款", "项目款", "工资")
    )


def _handling_status(text: str) -> Literal["unhandled", "investigating", "resolved"] | None:
    if any(item in text for item in ("未处理", "还没处理", "未办")):
        return "unhandled"
    if any(item in text for item in ("跟进", "处理中", "正在处理")):
        return "investigating"
    if any(item in text for item in ("已处理", "已解决", "办结")):
        return "resolved"
    return None


def _context_mode(
    text: str, prior: AgentQueryDSL | None
) -> Literal["new_scope", "refine_scope", "reference_results"]:
    """Classify a turn by scope semantics, with old phrase rules only as fallback."""
    if prior is None:
        return "new_scope"
    if any(item in text for item in ("全区", "全市", "全镇", "全域")):
        return "new_scope"
    if _explicit_result_reference(text):
        return "reference_results"
    # A newly named location creates a new scope. Otherwise a deterministic
    # filter/aggregation modifier refines the active scope.
    if _location(text):
        return "new_scope"
    if any(
        (
            _time_range(text) is not None,
            _title_tag(text) is not None,
            _topic(text) is not None,
            _handling_status(text) is not None,
            _aggregation(text) is not None,
            _follow_up_kind(text) == "constraints",
        )
    ):
        return "refine_scope"
    return "new_scope"


def _explicit_result_reference(text: str) -> bool:
    return any(item in text for item in ("这几单", "这些工单", "这些急单", "它们", "其中这些"))


def _follow_up_kind(text: str) -> Literal["none", "constraints"]:
    """Legacy phrase fallback; primary planning uses `_context_mode` above."""
    if any(item in text for item in ("这些", "刚才", "只看", "其中", "上一步", "那最近", "那近")):
        return "constraints"
    return "none"


def _title_tag(text: str) -> str | None:
    if any(token in text for token in ("急单", "急件", "紧急工单", "【急】", "（急）", "(急)")):
        return "急" if "急" in TITLE_TAG_WHITELIST else None
    return None


def _aggregation(
    text: str,
) -> Literal["count", "group_by_topic", "group_by_status", "group_by_location"] | None:
    if any(token in text for token in ("哪类最多", "什么问题最多", "哪种投诉最多")):
        return "group_by_topic"
    if any(token in text for token in ("处理了吗", "办理情况", "处理情况", "哪些已处理")):
        return "group_by_status"
    if any(token in text for token in ("几条", "多少条", "有多少", "总共有多少")):
        return "count"
    if any(token in text for token in ("哪个地方最多", "哪里最多")):
        return "group_by_location"
    return None


def _work_order_result(value: AgentRecord) -> AgentWorkOrderResult:
    return AgentWorkOrderResult(
        work_order_id=value["work_order_id"],
        external_work_order_number=value["external_work_order_number"],
        title=value["title"],
        title_tags=value["title_tags"],
        is_urgent=value["is_urgent"],
        reported_at=value["reported_at"],
        time_label="业务受理时间" if value["reported_at"] is not None else "业务时间未知",
        normalized_summary=value["normalized_summary"],
        location=value["location"],
        event_type=value["event_type"],
        handling_status=str(value["handling_status"]),
        cluster_ids=value["cluster_ids"],
        is_multi_frequency=bool(value["is_multi_frequency"]),
        is_high_frequency=bool(value["is_high_frequency"]),
        retrieval_evidence=value["retrieval_evidence"],
    )


def _groups(values: Iterable[str]) -> list[AgentTopicGroup]:
    return [
        AgentTopicGroup(label=label, count=count) for label, count in Counter(values).most_common()
    ]


def _unique_ids(values: Iterable[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))


def _scope_query_text(compiled: AgentQueryDSL) -> str:
    """Stable semantic-ranking input reconstructed solely from the controlled DSL."""
    return " ".join(
        value
        for value in (
            compiled.topic,
            compiled.event_type,
            compiled.entity,
            compiled.location,
            *compiled.keywords,
        )
        if value
    )


def _apply_drilldown(
    records: list[AgentRecord], drilldown: AgentDrilldown | None
) -> list[AgentRecord]:
    if drilldown is None:
        return records
    return [
        record
        for record in records
        if (drilldown.topic is None or (record["event_type"] or "未归类") == drilldown.topic)
        and (
            drilldown.location is None or (record["location"] or "未提供地点") == drilldown.location
        )
        and (
            drilldown.handling_status is None
            or record["handling_status"] == drilldown.handling_status
        )
        and (
            drilldown.frequency == "all"
            or (drilldown.frequency == "multi_frequency" and record["is_multi_frequency"])
            or (drilldown.frequency == "high_frequency" and record["is_high_frequency"])
        )
    ]


def _dashboard_response(title: str, records: list[AgentRecord]) -> DynamicDashboardResponse:
    cluster_ids = _unique_ids(cluster_id for item in records for cluster_id in item["cluster_ids"])
    high_cluster_ids = _unique_ids(
        cluster_id for item in records for cluster_id in item["high_frequency_cluster_ids"]
    )
    return DynamicDashboardResponse(
        title=title,
        work_order_count=len(records),
        multi_frequency_event_count=len(cluster_ids),
        multi_frequency_work_order_count=sum(1 for item in records if item["is_multi_frequency"]),
        high_frequency_event_count=len(high_cluster_ids),
        urgent_count=sum(1 for item in records if item["is_urgent"]),
        topic_groups=_groups(item["event_type"] or "未归类" for item in records),
        handling_groups=_groups(item["handling_status"] for item in records),
        location_groups=_groups(item["location"] or "未提供地点" for item in records),
        topic_tree=_tree_groups(records, "topic"),
        location_tree=_tree_groups(records, "location"),
        status_tree=_tree_groups(records, "status"),
        focus_cluster_ids=cluster_ids,
        disclaimer="所有统计均基于完整查询范围，不代表行政事实认定。",
    )


def _tree_groups(
    records: list[AgentRecord], mode: Literal["topic", "location", "status"]
) -> list[AgentTreeGroup]:
    """Build complete scope aggregates; only leaf examples are intentionally capped."""
    grouped: dict[str, dict[str, list[AgentRecord]]] = {}
    for record in records:
        topic = record["event_type"] or "未归类"
        location = record["location"] or "未提供地点"
        status = _handling_label(record["handling_status"])
        primary, child = (
            (topic, location)
            if mode == "topic"
            else (location, topic)
            if mode == "location"
            else (status, topic)
        )
        grouped.setdefault(primary, {}).setdefault(child, []).append(record)

    groups: list[AgentTreeGroup] = []
    for label, children in grouped.items():
        all_records = [record for values in children.values() for record in values]
        groups.append(
            AgentTreeGroup(
                label=label,
                count=len(all_records),
                urgent_count=sum(1 for record in all_records if record["is_urgent"]),
                multi_frequency_count=sum(
                    1 for record in all_records if record["is_multi_frequency"]
                ),
                children=[
                    AgentTreeChild(
                        label=child_label,
                        count=len(child_records),
                        work_orders=[_work_order_result(record) for record in child_records[:3]],
                    )
                    for child_label, child_records in sorted(
                        children.items(), key=lambda item: (-len(item[1]), item[0])
                    )
                ],
            )
        )
    return sorted(groups, key=lambda group: (-group.count, group.label))


def _evidence_answer(
    plan: AgentQueryDSL,
    query: str,
    total: int,
    records: list[AgentRecord],
    topics: list[AgentTopicGroup],
    handling_groups: list[AgentTopicGroup],
    cluster_ids: list[UUID],
) -> str:
    scope = plan.location or "当前检索范围"
    label = "急单" if plan.title_tag == "急" else "工单"
    if plan.aggregation == "count":
        if total == 0:
            return f"{scope}内没有发现{label}。"
        return f"{scope}当前检索范围内共有 {total} 条{label}。"
    if plan.aggregation == "group_by_status":
        if total == 0:
            return "引用的工单范围内没有记录。"
        summary = "、".join(
            f"{_handling_label(item.label)} {item.count} 条" for item in handling_groups
        )
        prefix = "这些" if plan.context_mode == "reference_results" else scope
        return f"{prefix}{label}共 {total} 条，办理状态为：{summary}。"
    if plan.aggregation in {"group_by_topic", "group_by_location"}:
        groups = (
            _groups(item["location"] or "未提供地点" for item in records)
            if plan.aggregation == "group_by_location"
            else topics
        )
        if total == 0:
            return f"{scope}内没有可统计的{label}。"
        primary = groups[0] if groups else None
        if primary is None:
            return f"{scope}内共有 {total} 条{label}，暂未形成可用分类。"
        return f"{scope}内共有 {total} 条{label}，最多的是“{primary.label}”{primary.count} 条。"
    if total == 0:
        return "该条件下未检索到记录；可尝试放宽时间、地点或关键词。"
    if any(token in query for token in ("有没有", "是否有", "有无")):
        return f"有，目前找到 {total} 条{label}。"
    topic_text = "、".join(f"{item.label} {item.count} 条" for item in topics[:3]) or "待归类"
    cluster_text = f"，其中关联多频事件 {len(cluster_ids)} 个" if cluster_ids else ""
    first = records[0]
    core = first["title"] or first["normalized_summary"] or "一条可核查工单"
    return (
        f"有。当前检索范围内找到 {total} 条直接相关工单，主要涉及：{topic_text}{cluster_text}。\n\n"
        f"核心工单：{core}\n"
        "当前数据只能确认上述投诉记录，不能据此认定该问题具有普遍性。"
    )


def _handling_label(value: str) -> str:
    return {"unhandled": "未处理", "investigating": "正在跟进", "resolved": "已解决"}.get(
        value, value
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
