from typing import cast
from uuid import UUID

from backend.app.application.services.agent import AgentOrchestrator
from backend.app.config import Settings
from backend.app.infrastructure.db.agent import AgentRepository
from backend.app.schemas.agent import AgentQueryRequest


def _service() -> AgentOrchestrator:
    return AgentOrchestrator(cast(AgentRepository, object()), Settings(), None, None)


def test_existing_deepseek_environment_aliases_configure_the_agent() -> None:
    settings = Settings(
        SHUNDE_AI_DEEPSEEK_BASE_URL="https://deepseek.example.test",
        SHUNDE_AI_DEEPSEEK_API_KEY="test-key",
        SHUNDE_AI_DEEPSEEK_LLM_MODEL_ID="deepseek-chat",
    )

    assert settings.agent_deepseek_base_url is not None
    assert settings.agent_deepseek_api_key is not None
    assert settings.agent_deepseek_model_id == "deepseek-chat"


def test_engineering_payment_query_is_compiled_to_controlled_dsl() -> None:
    plan = _service()._rules_plan(  # noqa: SLF001 - validates the controlled planner boundary.
        AgentQueryRequest(query="最近一个月有哪些工程款投诉？")
    )

    assert plan.intent == "search_work_orders"
    assert plan.topic == "工程款"
    assert plan.time_range is not None
    assert plan.time_range.value == "last_30_days"
    assert "工程款" in plan.keywords
    assert plan.issue_required is True


def test_constraint_follow_up_inherits_scope_without_locking_prior_result_ids() -> None:
    previous = _service()._rules_plan(  # noqa: SLF001 - validates the controlled planner boundary.
        AgentQueryRequest(query="最近一个月有哪些工程款投诉？")
    )
    plan = _service()._rules_plan(  # noqa: SLF001 - validates the controlled planner boundary.
        AgentQueryRequest(
            query="那最近一个月呢？",
            previous_query_snapshot=previous,
            previous_work_order_ids=["51dee877-ba24-4834-aa61-39978bb2d480"],
        )
    )

    assert plan.intent == "refine_previous"
    assert plan.time_range is not None
    assert plan.time_range.value == "last_30_days"
    assert plan.topic == "工程款"
    assert plan.issue_required is True
    assert plan.work_order_ids == []


def test_location_and_explicit_issue_are_both_constraints() -> None:
    plan = _service()._rules_plan(  # noqa: SLF001 - controlled planner contract.
        AgentQueryRequest(query="大良有没有拖欠工资的情况")
    )

    assert plan.location == "大良"
    assert plan.topic == "工资"
    assert plan.issue_required is True


def test_result_reference_follow_up_keeps_prior_evidence_ids() -> None:
    prior = _service()._rules_plan(AgentQueryRequest(query="大良有没有拖欠工资"))
    result_id = UUID("51dee877-ba24-4834-aa61-39978bb2d480")
    plan = _service()._rules_plan(
        AgentQueryRequest(
            query="这几单处理了吗？",
            previous_query_snapshot=prior,
            previous_work_order_ids=[result_id],
        )
    )

    assert plan.intent == "refine_previous"
    assert plan.work_order_ids == [result_id]


def test_urgent_count_refines_the_active_location_scope() -> None:
    first = _service()._rules_plan(AgentQueryRequest(query="容桂有什么事情"))
    second = _service()._rules_plan(
        AgentQueryRequest(query="有几条急单", previous_query_snapshot=first)
    )

    assert first.location == "容桂"
    assert second.context_mode == "refine_scope"
    assert second.location == "容桂"
    assert second.title_tag == "急"
    assert second.aggregation == "count"
    assert second.work_order_ids == []


def test_urgent_result_reference_uses_previous_evidence_and_groups_status() -> None:
    prior = _service()._rules_plan(AgentQueryRequest(query="容桂有几条急单"))
    result_id = UUID("51dee877-ba24-4834-aa61-39978bb2d480")

    plan = _service()._rules_plan(
        AgentQueryRequest(
            query="这些急单处理了吗",
            previous_query_snapshot=prior,
            previous_work_order_ids=[result_id],
        )
    )

    assert plan.context_mode == "reference_results"
    assert plan.title_tag == "急"
    assert plan.aggregation == "group_by_status"
    assert plan.work_order_ids == [result_id]


def test_time_refinement_keeps_active_urgent_scope() -> None:
    prior = _service()._rules_plan(AgentQueryRequest(query="容桂有几条急单"))
    plan = _service()._rules_plan(
        AgentQueryRequest(query="那最近一个月呢", previous_query_snapshot=prior)
    )

    assert plan.context_mode == "refine_scope"
    assert plan.location == "容桂"
    assert plan.title_tag == "急"
    assert plan.time_range is not None
    assert plan.time_range.value == "last_30_days"


def test_global_scope_explicitly_resets_previous_location() -> None:
    prior = _service()._rules_plan(AgentQueryRequest(query="容桂有什么事情"))
    plan = _service()._rules_plan(
        AgentQueryRequest(query="全区有几条急单", previous_query_snapshot=prior)
    )

    assert plan.context_mode == "new_scope"
    assert plan.location is None
    assert plan.title_tag == "急"
    assert plan.aggregation == "count"


def test_direct_location_urgent_count_needs_no_history() -> None:
    plan = _service()._rules_plan(AgentQueryRequest(query="大良有几条急单"))

    assert plan.location == "大良"
    assert plan.title_tag == "急"
    assert plan.aggregation == "count"
