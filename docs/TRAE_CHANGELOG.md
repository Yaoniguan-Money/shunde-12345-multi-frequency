# TRAE_CHANGELOG.md

TRAE appends entries; do not rewrite history.

## 2026-08-18 — WP2→WP7 contracts and provider/task binding

- 改动目标：将 `understanding.v3`、冻结 AnalysisScope、已验证 Provider Profile、V3 证据投影和数据库 overview/facets 接入真实产品合同。
- API 变更：新增 `/ai/provider-profiles`、`/ai/provider-profiles/{profile_id}/validate`、`/work-orders/overview`、`/work-orders/facets`；分析任务响应增加 Provider Profile/Execution Policy snapshot；事件详情增加分类、当前问题/诉求、history、evidence spans、unknown 字段。
- 前端变更：导入页选择并验证 Provider，创建任务前强制已验证；删除旧 `max_work_orders` 测试契约；高频页显示后端 reported_at 三日窗口语义。
- 数据库：新增 `provider_profiles` Alembic migration `d3e4f5a6b7c8`；候选记录保存召回路线、结构化锚点和版本；SameEvent ambiguous 不生成正向边。
- 验证：后端 89 tests、前端 33 tests、Ruff、format、Pyright、ESLint、Vite build 通过；尚未执行真实 100 条 WP8 回放。
- 已知问题：完整 ScopeFilter 级联筛选、Gold Set、真实 local/cloud provider 回放和 Playwright 主流程仍待 WP8 验收，不能由本条视为完成。

## 2026-08-18 — DS Flash provider switch validation

- 新增 `SHUNDE_AI_REMOTE_FLASH_LLM_MODEL_ID` 显式配置；`cloud-qwen` Profile、任务快照和幂等键会绑定实际 Flash 模型，配置版本变化会使旧验证状态失效。
- 真实合成验证使用 `qwen-flash`：health 通过，结构化推理被 DashScope 返回 HTTP 400 `overdue-payment`。这证明切换已经生效，但当前账户仍欠费，未启动新的 100 条云端回放。
- 状态：WP8 `BLOCKED`，等待可用 DashScope 账户/额度；不使用同一账户 fallback、不用 mock 替代真实验证。

## 2026-08-15 — 非技术用户详情页重构

- 多频事件详情改为业务概览、关联工单、关联判断、处理记录、人工纠错的卡片式层级；原文与智能研判结果分区显示。
- 状态增加由真实后端值驱动的绿/橙/红信号点；归属调整和新增办理记录默认收起，减少首屏操作噪声。
- 客户页移除源行号、原始扩展字段、UUID、模型追踪和英文内部值；`complete_link_guard`、SameEvent evidence 键及旧 `demo-operator` 均使用中文业务表达。
- 工单详情同步使用同一套中文详情样式和字段边界；API、数据库、原始工单与审计记录均未改变。
- 验证：前端 33 tests、lint、build 通过；真实本地 cluster 页面可见文本扫描未发现约定禁用技术术语。

## 2026-08-15 — 客户界面中文化与技术字段收敛

- 多频事件详情、工单详情、判断依据卡和导入研判状态统一使用中文业务标签。
- 默认隐藏 UUID、原始 evidence JSON、模型/供应商追踪和内部枚举；扩展原始字段仅在“工作人员查看”折叠区保留。
- 未知事件类型和状态分别显示“其他问题”“状态待同步”，不伪造后端含义；API、数据库、原始工单和审计记录不变。
- 验证：前端 32 tests、lint、build 通过。

## 2026-08-15 — Frontend traffic-light status layer

- 改动目标：参考政务看板的红/黄/绿信号灯风格，提升状态识别和多频事件浏览效率，同时保持后端真实数据约束。
- 修改文件：`frontend/src/components/SignalLight.tsx`、`frontend/src/components/signalState.ts`、
  `frontend/src/App.tsx`、`frontend/src/pages/DashboardPage.tsx`、`frontend/src/pages/EventsPage.tsx`、
  `frontend/src/pages/WorkOrdersPage.tsx`、`frontend/src/pages/ImportsPage.tsx`、`frontend/src/styles.css`。
- 数据口径：系统灯来自 health/dependencies；事件灯来自 `handling_status`、`review_status` 和
  `is_high_frequency`；工单灯来自 `analysis_state`；研判灯来自 `AnalysisJob.status/current_stage`。
  状态统计限定当前页/当前加载数据，不冒充全量。
- 兼容修复：多频卡片“查看详情”链接不再因窄宽度被逐字竖排。
- 验证：前端 32 tests、lint、build 通过；无 API、数据库或原始数据改动。

## 2026-08-15 — Backend high-frequency window contract

- 改动目标：落实“ 三天内三条及以上 ”的高频口径，避免前端用模糊相似度或本地日期推断。
- API 变更：`ClusterSummaryResponse` / `ClusterDetailResponse.summary` 新增 `is_high_frequency`、
  `frequency_window_days`、`frequency_work_order_count`。
- 判定：active cluster 任意滚动 3 个日历日窗口内至少 3 条不同真实 WorkOrder；同工单多个
  EventInstance 只计一条，缺少 `occurrence_date` 的记录不计入。没有满足条件时返回 false，不制造高频标签。
- 前端：多频事件卡片仅在 `is_high_frequency=true` 时展示“高频 · 3天内N条工单”；不重新计算。
- 验证：新增 rolling-window domain tests 和 EventsPage contract test；无数据库迁移。

## 2026-08-15 — Frontend backend-only rendering

- 改动目标：修复前端展示与后端记录无法匹配的问题；没有后端字段的内容不再显示。
- 修改文件：`frontend/src/App.tsx`、`frontend/src/pages/DashboardPage.tsx`、`frontend/src/pages/EventsPage.tsx`、`frontend/src/pages/WorkOrdersPage.tsx`、`frontend/src/pages/ImportsPage.tsx`、`frontend/src/styles.css`、`frontend/src/pages/DashboardPage.test.tsx`。
- API 变更：无。页面只消费既有目录、导入预览、导入、分析任务和复核合同。
- 行为：移除静态雷达/活动/趋势/随机数/固定兜底统计、模拟工单、模拟导入历史、假预览行和模拟匹配边；空数组显示空状态，接口失败显示错误和重试；多频/工单/批次/任务必须带真实后端 ID。
- 高频边界（历史）：当时后端没有三天窗口；后续已接入顶部条目定义的后端合同。
- 本地验证：`pnpm test --run`（6 files、31 passed）、`pnpm lint`（passed）、`pnpm build`（passed）。
- 历史边界：该时点后端尚未提供三天窗口；已由本文件顶部的“Backend high-frequency window contract”条目 supersede。

## 2026-08-15 — Removed member restore contract

- 改动目标：修复成员移出多频事件后因 active 详情不再包含该事件而无法恢复的问题。
- API 变更：`GET /multi-frequency-events/{cluster_id}` 增加 `removed_members[]`，返回事件/工单、原始内容、AI trace、`event_instance_id`、纠错元数据与 `can_restore`；无法解析的事件保留 ID 但不可恢复。
- 纠错语义：保留既有 `POST /multi-frequency-events/{cluster_id}/corrections`；`confirm_member` 只允许恢复此前确实 `remove_member` 的事件，active member 重复恢复返回 409。所有操作继续写 `HumanCorrection` 与 `AuditLog`。
- 前端交互：详情页独立展示“已移出事件”，显式填写操作员 ID（默认 `demo-operator`）和恢复理由，二次确认后恢复并重新读取详情。
- 验证：后端 `48 passed`；前端 `29 passed`、lint/build 通过；`scripts/check.ps1` 全部通过。

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

## 2026-08-15 — Distinct-WorkOrder multi-frequency invariant

- 改动目标：修复“单张工单被 AI 拆成多个 EventInstance，却被计成多频”的领域语义错误。
- 后端合同：retrieval / SameEvent / graph 只允许不同 WorkOrder 的事件对；cluster 必须至少覆盖 2 个 distinct WorkOrder。旧的无效存量簇保留审计，但不再由 Catalog API 返回。
- API 变更：cluster 列表/详情新增 `work_order_count` 和 `event_count`；兼容字段 `member_count` 改为 distinct WorkOrder 数。详情新增按原始工单聚合的 `work_orders`，保留 event-level `members` 供旧客户端兼容。
- 前端变更：列表分开显示“关联工单”和“AI 事件”；详情按 `work_orders` 渲染，同一原始工单只显示一张 raw card，其下可有多个 AI 事件。
- 理解纠偏：部门回复/历史处置/当前请求在主体或地点锚点唯一时并入投诉事件上下文；真实的噪音+消防等多问题仍保留为多事件。

## 2026-08-15 — Frontend soft-install: real API integration across all pages

- 改动目标：在不改后端、不用 mock、不引入 merge/split 的前提下，完成前端全部页面的真实 API 软装，形成可路演的 12345 工作台。
- 修改文件（前端）：
  - `frontend/vite.config.ts`：`server.host=127.0.0.1`、`port=5173`、`strictPort=true`，并加注释说明后端 CORS allow_origins 默认只含 5173，前端 dev server 必须跑在 5173 才能通过 preflight（不改后端）。
  - `frontend/src/api/client.ts`：重写为统一 fetch wrapper，支持 GET/POST JSON、POST FormData/multipart（不手工设 Content-Type 让浏览器生成 boundary）、Blob/CSV 下载（单次 fetch 取 blob + 从 Content-Disposition 解析 filename）；非 2xx 抛 `ApiError` 含 `status/detail`；`describeApiError` 解析 FastAPI ValidationError 与 `{message}` 结构；`triggerBlobDownload` 用 `URL.createObjectURL` 触发浏览器下载。
  - `frontend/src/api/imports.ts`：新增 `previewImport`/`executeImport`，定义 `ImportPreviewResponse`/`ImportMapping`/`ImportResultResponse` 类型。
  - `frontend/src/api/analysis.ts`：新增 `createAnalysisJob`/`getAnalysisJob`，定义 `AnalysisJobResponse`/`AnalysisJobTrace` 类型。
  - `frontend/src/api/review.ts`：新增 `addHandlingRecord`/`listHandlingRecords`/`addCorrection`/`listCorrections`/`exportClusterCsv`，覆盖处理记录、人工纠错、CSV 导出。
  - `frontend/src/api/catalog.ts`：cluster 列表/详情、work-orders 列表/详情、events 列表/详情全部走真实后端。
  - `frontend/src/api/health.ts`：liveness/readiness/dependencies 走真实后端。
  - `frontend/src/types/api.ts`：`ClusterDetailResponse` 含 `summary/members/work_orders/edges/handling_history/human_corrections`；`ClusterSummaryResponse` 含 `work_order_count/event_count`。
- 页面实现：
  - `frontend/src/pages/EventsListPage.tsx`：卡片化多频事件列表，分开显示 `work_order_count`（关联工单）和 `event_count`（AI 事件）；当前页筛选明确标注“仅当前页”，非全局搜索；点卡片跳详情。
  - `frontend/src/pages/ClusterDetailPage.tsx`：完整事件详情操作页，含处理记录区（新增/列表）、人工纠错区（`remove_member`/`confirm_member`）、CSV 导出区；删 placeholder；`work_orders` 按原始工单聚合，同一原始工单只显示一张 raw card，其下可有多个 AI 事件成员；AI evidence 左侧色条 + 浅色背景，`TraceTag` 折叠到“技术追踪”details/summary，不抢主业务信息中心。
  - `frontend/src/pages/WorkOrdersPage.tsx`：真实工单列表，分页 + 当前页筛选，`StatusBadge` 中文映射。
  - `frontend/src/pages/WorkOrderDetailPage.tsx`：工单详情，含 raw 字段、AI evidence、trace 折叠。
  - `frontend/src/pages/ImportsPage.tsx`：四阶段状态机——选文件→预览/映射→导入→AI 研判轮询；预览用后端 `suggested_mapping` 预填；`content` 必须映射才能导入；导入成功显示真实 `batch_id` 并识别幂等命中；研判阶段 `max_work_orders` 1–300 限制，2 秒轮询 `GET /analysis-jobs/{job_id}`，`queued→running→completed` 显示状态徽章 + 进度计数 + trace；完成后 CTA 跳 `/events`；无“全量研判”按钮。
  - `frontend/src/App.tsx`：左侧导航仅三项（多频事件/工单中心/数据导入与AI研判），无 tag；顶栏 `HealthIndicator` 调 `/health/live`。
- 组件与样式：
  - `frontend/src/components/StatusBadge.tsx`：`STATUS_CN_MAP` 中文映射（queued→排队中/running→研判中/completed→已完成/failed→失败/active→有效/unhandled→未处理/investigating→处理中/resolved→已办结 等），未知状态仍展示原始值不擅自改意义；`analysis`/`handling`/`neutral` 三 variant。
  - `frontend/src/components/TraceTag.tsx`：改为 details/summary 折叠“技术追踪”区域，`trace-tag--foldable/trace-tag__summary/trace-tag__body` 样式追加到 `styles.css`。
- 测试（Vitest + @testing-library/react）：28 tests PASS（5 test files）——App 2、WorkOrderDetailPage 3、WorkOrdersPage 4、ClusterDetailPage 10、ImportsPage 9（含 `suggested_mapping` 预填、`content` 未映射禁用、真实 `batch_id`、幂等命中提示、`max_work_orders` 1–300 边界、`queued→running→completed` 轮询 + CTA 跳转、失败重试回表单）。
- 工程检查：`corepack pnpm lint`（eslint `--max-warnings 0`）PASS；`corepack pnpm test --run` 28/28 PASS；`corepack pnpm build` PASS（dist/index.html 0.42KB、index.css 31.08KB、index.js 460.14KB gzip 144.80KB，179ms）。
- 真实后端 API smoke（curl + Origin 5173）：`GET /health/live` 200 + `Access-Control-Allow-Origin=http://127.0.0.1:5173`；`GET /multi-frequency-events?limit=1` 200 + ACAO 5173 + 1 cluster（`work_order_count=3 event_count=3 handling_status=unhandled`）；`GET /multi-frequency-events/{id}` 200 + ACAO 5173 + 14971 bytes；`GET /work-orders?limit=3` 200 + 3 items + `total=128278`；OPTIONS preflight 从 5173 origin 返回 200 + `Access-Control-Allow-Methods=GET, POST, PUT, PATCH, DELETE` + `Access-Control-Allow-Headers=Accept, Accept-Language, Content-Language, Content-Type, X-Correlation-ID`。
- 尚未实现/未覆盖的真实后端能力（前端不绕过，等后端/数据就绪再接）：
  - 全量 128,278 条 AI 理解与正式 Gold Set 仍未完成，列表当前只展示 Demo Core 小样本（1 cluster）。
  - 无 Gold Set，不报告 Recall/Precision/F1。
  - 前端未实现 merge/split 人工纠错（后端当前只支持 `remove_member`/`confirm_member`，前端与之对齐）。
  - 无登录、无地图、无大屏（按用户明确约束不引入）。
  - GSAP 视觉打磨按 spec 改为 MAY/SHOULD，仅在有视觉收益明确时使用；当前 phase 以真实 API 联调与可路演链路为主，未做 GSAP 动效。
- 已知工具环境问题（非代码问题）：TRAE OpenPreview 预览浏览器在 5173 调后端 8080 时报 `net::ERR_ABORTED`，curl 验证后端 CORS preflight/简单请求均从 5173 origin 正常返回 200 + 正确 ACAO/ACAH，是预览工具自身浏览器 origin 非 5173 导致；真实浏览器访问 `http://127.0.0.1:5173/` 可正常加载所有页面与真实 API。
