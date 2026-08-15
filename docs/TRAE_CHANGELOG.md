# TRAE_CHANGELOG.md

TRAE appends entries; do not rewrite history.

## 2026-08-15 — Demo Core read contracts

- 改动目标：为真实 cloud-first Demo Core 提供只读工单、事件和多频事件列表/详情接口。
- 修改文件：`backend/app/api/catalog.py`、`backend/app/schemas/catalog.py`、`backend/app/application/services/catalog.py`、`backend/app/infrastructure/db/catalog.py`、`docs/TRAE_HANDOFF.md`。
- API 变更：新增 `GET /work-orders`、`GET /work-orders/{id}`、`GET /events`、`GET /events/{id}`、`GET /multi-frequency-events`、`GET /multi-frequency-events/{id}`。详情保留原始工单与 v2 evidence/trace；列表使用 `items/offset/limit/total`。
- 本地验证：真实 uvicorn smoke 调用六个端点均 HTTP 200；`uv run pytest -q` 通过。
- 已知问题：当前接口展示的是小样本 Demo Core；全量 128,278 条 AI 理解和正式 Gold Set 仍未完成。

## 2026-08-15 — Demo product review loop

- 改动目标：把多频事件从只读 Demo 详情补齐到可核查、可纠错、可记录处理过程并可导出的后端闭环。
- 修改文件：`backend/app/api/review.py`、`backend/app/application/services/review.py`、`backend/app/domain/catalog.py`、`backend/app/domain/ports/review.py`、`backend/app/infrastructure/db/review.py`、`backend/app/infrastructure/export/csv.py`、`backend/app/api/catalog.py`、`backend/app/schemas/catalog.py`。
- API 变更：新增 handling-records 读写、corrections 读写和 `GET /multi-frequency-events/export.csv`；`GET /multi-frequency-events/{id}` 增加 `handling_history` 与 `human_corrections`，成员工单、SameEvent evidence、AI trace 保持可读。
- 语义修复：cluster consistency 不再把不同 `event_type` 字符串当硬冲突；只依据实体/地点明确冲突或 SameEvent evidence contradiction 拒绝合并，并增加同义 event type 回归测试。
- 审计与数据边界：复用既有 `EventHandlingRecord`、`HumanCorrection`、`AuditLog`；raw work order 不变。当前人工纠错只支持 `remove_member` / `confirm_member`，不虚构 merge/split。
- 本地验证：API 合同测试、真实 uvicorn/PostgreSQL smoke、CSV 200 响应通过；真实 smoke 写入 1 条处理记录、2 条纠错和 3 条审计记录，成员移除后确认恢复为 2。
- 已知边界：Demo 仍是真实数据库小样本，不是 128,278 条全量 AI 结果；没有 Gold Set，不报告 Recall/Precision/F1；TRAE 仍不得绕过 backend 或改变 Provider routing。

## 2026-08-15 — Bounded AI analysis job HTTP contract

- 改动目标：让 TRAE 可以从导入后的页面通过 HTTP 启动、轮询真实 AI 研判，不再依赖终端脚本。
- API 变更：新增 `POST /analysis-jobs`（`import_batch_id` + 必填 `max_work_orders`，1–300）和 `GET /analysis-jobs/{job_id}`；状态为 `queued/running/completed/failed`，返回处理进度、event/edge/cluster 计数、错误和 provider/model/config/schema/pipeline trace。
- 架构边界：单机 asyncio 后台 task；复用既有 analysis job/run/checkpoint、`UnderstandingAndIndexingPipeline` 与 `EventGraphService`。`scripts/demo_core.py` 已改为调用同一 `DemoAnalysisOrchestrator` application seam。
- Provider/安全：当前 Demo 强制显式 remote provider（`qwen-plus` + `qwen3.7-text-embedding`）；不会自动 fallback 到 local，API key 不进请求/响应/日志。
- 验证：API 合同、bounded chunk 上限、完成计数、失败状态测试通过；真实 HTTP bounded smoke 为 total `128278`、selected/processed `1`、event `1`、remote trace `qwen-plus`，未触发全量。
