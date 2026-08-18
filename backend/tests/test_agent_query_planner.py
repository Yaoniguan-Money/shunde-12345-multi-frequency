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


def test_follow_up_preserves_result_scope_and_applies_status_filter() -> None:
    previous = _service()._rules_plan(  # noqa: SLF001 - validates the controlled planner boundary.
        AgentQueryRequest(query="最近一个月有哪些工程款投诉？")
    )
    plan = _service()._rules_plan(  # noqa: SLF001 - validates the controlled planner boundary.
        AgentQueryRequest(
            query="只看还没处理的",
            previous_query_snapshot=previous,
            previous_work_order_ids=["51dee877-ba24-4834-aa61-39978bb2d480"],
        )
    )

    assert plan.intent == "refine_previous"
    assert plan.handling_status == "unhandled"
    assert plan.work_order_ids == [UUID("51dee877-ba24-4834-aa61-39978bb2d480")]
