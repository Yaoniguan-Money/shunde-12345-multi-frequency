"""Stable query semantics for the Agent retrieval core.

Runtime diagnostics deliberately do not live here: this value is persisted in
workset snapshots and must stay portable between demo environments.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID


@dataclass(frozen=True)
class AgentSearchPlan:
    """One compiled scope shared by result, aggregate and tree executions."""

    semantic_query: str
    keywords: tuple[str, ...]
    issue_terms: tuple[str, ...]
    issue_required: bool
    entity: str | None
    location: str | None
    event_type: str | None
    title_tag: str | None
    work_order_ids: tuple[UUID, ...]
    handling_status: str | None
    reported_after: datetime | None
    reported_before: datetime | None
    sort: Literal["relevance", "newest", "oldest"]


AgentRecordT = TypeVar("AgentRecordT")


@dataclass(frozen=True)
class AgentPage(Generic[AgentRecordT]):  # noqa: UP046 - Python 3.11 support.
    matched_total: int
    records: list[AgentRecordT]
    semantic_candidate_count: int
