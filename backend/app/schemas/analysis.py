"""HTTP contracts for bounded background AI analysis jobs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.schemas.catalog import TraceResponse

AnalysisJobStatus = Literal["queued", "running", "completed", "failed"]
AnalysisSelectionMode = Literal["sequential", "recurrence_candidates"]
AnalysisJobStage = Literal[
    "queued",
    "understanding",
    "embedding",
    "retrieval",
    "matching",
    "clustering",
    "completed",
]


class AnalysisJobCreate(BaseModel):
    import_batch_id: UUID
    max_work_orders: int = Field(ge=1, le=300)
    selection_mode: AnalysisSelectionMode = "sequential"


class AnalysisJobResponse(BaseModel):
    job_id: UUID
    status: AnalysisJobStatus
    current_stage: AnalysisJobStage
    total_rows: int
    selected_rows: int
    processed_rows: int
    event_count: int
    match_edge_count: int
    cluster_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    trace: TraceResponse | None
    selection_mode: AnalysisSelectionMode
