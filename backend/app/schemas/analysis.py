"""HTTP contracts for full-batch AI analysis jobs.

WP2: 删除 max_work_orders 和 selection_mode；研判范围等于导入批次全部成功工单。
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from backend.app.schemas.catalog import TraceResponse

AnalysisJobStatus = Literal[
    "queued",
    "running",
    "completed",
    "completed_with_failures",
    "failed",
]
AnalysisJobStage = Literal[
    "queued",
    "understanding",
    "classification",
    "embedding",
    "retrieval",
    "matching",
    "clustering",
    "completed",
]


class AnalysisJobCreate(BaseModel):
    """创建研判任务。

    请求体不存在 max_work_orders、selection_mode 或前端并发参数。
    研判范围等于导入批次全部成功工单。
    provider_profile_id 在 WP5 实现后必填；当前可选，为 None 时使用环境配置。
    """

    import_batch_id: UUID
    provider_profile_id: str | None = None


class AnalysisJobResponse(BaseModel):
    job_id: UUID
    status: AnalysisJobStatus
    current_stage: AnalysisJobStage
    total_rows: int
    target_work_order_count: int
    processed_work_order_count: int
    failed_work_order_count: int
    produced_event_instance_count: int
    match_edge_count: int
    cluster_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    trace: TraceResponse | None
    # 旧字段兼容（从 metrics 投影）
    selected_rows: int
    processed_rows: int
    event_count: int
