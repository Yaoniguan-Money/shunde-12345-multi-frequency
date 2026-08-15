# TRAE_HANDOFF.md

# 角色定义

**Codex = 硬装**：架构、数据、API、数据库、模型/知识库 adapter、任务恢复、测试、Git、性能门禁。  
**TRAE = 软装**：视觉、交互、文案、内容呈现、空/错/加载状态、Demo 体验。

TRAE 的目标不是重新设计后端，而是在不破坏硬装的前提下让产品更好用、更好看、更好演示。

# 开工前必读

1. 根目录 `AGENTS.md`
2. `docs/PRODUCT_SCOPE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/CURRENT_STATE.md`
5. OpenAPI / 前端 typed API client

# 真实数据位置（不要移动或修改）

政府 Excel 的完整路径：

当前验收请使用：`C:\Users\Lenovo\Desktop\顺德12345热线精选工单数据集（含重复工单）.xlsx`（100 条精选工单，含重复工单字段/明细）。原 128,278 条 Excel 不作为当前验收库。

地名库交接包：

`C:\Users\Lenovo\Desktop\顺德地名库交接包`

TRAE 不得把这两个目录复制进 Git，不得修改原 Excel，也不得为了页面演示制造替代数据。当前已提供真实 Phase 2 导入 API；Excel 仍只从上述绝对路径读取。

# Phase 1 已稳定的运行合同

- Backend：`http://127.0.0.1:8080`
- Frontend dev：`http://127.0.0.1:5173`
- Gazetteer（只允许 backend adapter 调用）：`http://127.0.0.1:8000`
- PostgreSQL：`127.0.0.1:5432`
- Health：`/health/live`、`/health/ready`、`/health/dependencies`
- Import preview：`POST /imports/preview`（multipart，真实表头预览）
- Import：`POST /imports`（multipart + mapping JSON；批次幂等、checkpoint 可恢复）
- Entity resolve：`POST /entities/resolve`（快照优先，剩余 mention 单次批量查询）
- 当前前端只是 health 工程骨架，不是业务页面完成态。
- 当前没有生产 mock/fake 数据；测试 fake 只在 `backend/tests`。

## AI understanding / retrieval（当前为可运行的后端合同）

- 未配置环境时默认模型运行时仍是 Ollama `http://127.0.0.1:11434`；结构化抽取使用 `qwen2.5:3b`，向量使用 `nomic-embed-text`（768 维）。比赛 Demo 显式设置 `SHUNDE_AI_PROVIDER_MODE=remote` 后使用 Qwen `qwen-plus` + `qwen3.7-text-embedding`（1024 维）。生产 local adapter 拒绝云端 URL，不做隐式云回退。
- Provider 模式由 `SHUNDE_AI_PROVIDER_MODE=local|remote|hybrid` 显式选择，默认 `local`。remote 使用通用 OpenAI-compatible adapter，API key 只来自环境变量；hybrid 的 `AUTO`/`LOCAL` 走本地，只有显式 `REMOTE` route 才走远端。AI trace 包含 `provider / model_id / model_config_hash / schema_version / pipeline_version`。
- 远端验证命令：`uv run python scripts/remote_provider_smoke.py`。该命令只发送合成 JSON，不发送政府工单；未配置 key 时状态为 `BLOCKED`。2026-08-15 已用 Qwen `qwen-plus` 实际通过 health 与结构化 JSON，provider trace 为 `remote-openai-compatible`。
- `uv run python scripts/run_understanding.py --limit N --chunk-size K`：从真实导入批次 checkpoint 继续执行“规则分段 → 批量结构化抽取 → 批量地名解析 → event/mention/segment 持久化 → embedding 写入”。省略 `--limit` 才会继续到全量，当前只实测了前 11 条，不要在演示环境无意触发全量。
- Demo 前端不再需要手工运行 Python：使用下方 `POST /analysis-jobs` 创建 bounded 后台任务，再轮询 `GET /analysis-jobs/{job_id}`。`max_work_orders` 必填且当前限制为 1–300；没有“默认全量”按钮。
- `uv run python scripts/retrieval_benchmark.py --profile 1000 --embedding-model nomic-embed-text`：运行 pgvector candidate retrieval 性能测试；没有业务 Gold Set 时 `quality` 必须保持 `null`。
- 原始 `work_orders.raw_*` 永不被 AI 改写。AI 结果存放在 `complaint_segments`、`entity_mentions`、`event_instances`、`work_order_embeddings`，并带 `model_id / schema_version / pipeline_version / knowledge_snapshot_id` 等 trace 字段。
- Demo Core 已提供真实事件聚类、同事件判定、详情和产品处理闭环 API；TRAE 不应为不存在的全量能力制作静态“已完成”页面。当前 Demo 只覆盖真实数据库动态抽出的少量工单，列表必须显示分页总数和当前状态，未知/未解析状态必须原样显示。
- **锁定语义：多频按 distinct WorkOrder 计算，不按 EventInstance 数计算。** 一张工单可以有多个真实 AI 事件，但不能自己构成多频；同工单事件不会进入跨工单 retrieval / SameEvent / cluster。
- 质量 review：`uv run python scripts/quality_review.py --sample-size 300 --chunk-size 8 --candidate-limit 5`。输出在 `data/runtime/quality/`，逐条展示原始工单→分段→v2 事件→实体解析→embedding/pgvector 候选→SameEvent evidence→版本 trace；弱标签只是待人工确认候选，不能显示为 Gold Label，也不能显示 Recall/Precision/F1。

## Demo Core 云端路径与 API

当前可演示的真实链路是：

```text
真实工单小样本 → understanding.v2 → remote embedding 1024d
→ pgvector candidates → remote SameEventMatcher → 一致性 cluster → API
```

演示前运行 `docs/DEVELOPMENT.md` 中的环境加载和 `scripts/demo_core.py` 命令。脚本会生成 `data/runtime/demo/demo-core-*.json`（runtime ignored），artifact 不复制正文；正文和完整证据由 API 详情按 ID 读取。

TRAE 只调用以下 HTTP contract，不直接访问数据库或模型：

```text
GET /work-orders?offset=0&limit=20&query=
GET /work-orders/{work_order_id}
GET /events?offset=0&limit=20&pipeline_version=understanding.v2&work_order_id=
GET /events/{event_id}
GET /multi-frequency-events?offset=0&limit=20
GET /multi-frequency-events/{cluster_id}
POST /analysis-jobs
GET /analysis-jobs/{job_id}
POST /attachments
GET /attachments/{attachment_id}
POST /multi-frequency-events/{cluster_id}/review
POST /multi-frequency-events/{cluster_id}/handling-records
GET /multi-frequency-events/{cluster_id}/handling-records
POST /multi-frequency-events/{cluster_id}/corrections
GET /multi-frequency-events/{cluster_id}/corrections
GET /multi-frequency-events/export.csv?cluster_id={cluster_id}
```

### Analysis job HTTP contract

```text
POST /analysis-jobs
{
  "import_batch_id": "<completed-or-partial-import-batch-id>",
  "max_work_orders": 50
}

GET /analysis-jobs/{job_id}
```

创建响应为 HTTP 202，状态从 `queued` → `running` → `completed|failed`。响应字段包含
`total_rows`、`selected_rows`、`processed_rows`、`event_count`、`match_edge_count`、
`cluster_count`、`started_at`、`finished_at`、`error` 和 `trace`（provider/model/config
hash/schema/pipeline）。API 后台复用 understanding.v2、remote embedding、pgvector、
RemoteSameEventMatcher 与 EventGraphService；请求不会同步等待整批模型推理。当前 Demo
必须显式使用 `SHUNDE_AI_PROVIDER_MODE=remote`、`qwen-plus` 和
`qwen3.7-text-embedding`，不会自动回退本地，API key 永不进入响应。

响应还包含 `current_stage=queued|understanding|embedding|retrieval|matching|clustering|completed`。
TRAE 必须在 `status` 仍为 queued/running 时继续轮询；即使 `processed_rows == selected_rows`，
matching/clustering 尚未结束也不得显示“研判完成”。只有后端返回 `status=completed` 才刷新
多频事件列表。一次研判的事件、匹配边、cluster 都属于同一个 analysis run，前端不得自行
拼接历史 run 或以 0 个 cluster 推断接口没有执行。

`POST /analysis-jobs` 新增可选 `selection_mode=sequential|recurrence_candidates`，默认 `sequential` 保持兼容。Demo 建议显式选择 `recurrence_candidates` 且按操作者当前要求使用 `max_work_orders=100`。页面必须同时显示 `total_rows=128278`、`selected_rows=100`和真实 `processed_rows`，不得写成“13 万条已全部 AI 研判”。候选规则仅路由工单，不是 SameEvent 结论。

### Product semantics contracts

- `GET /work-orders` 支持 `analysis_state / event_type / title_tag`；summary 新增 `analysis_state`、`title_tags[]`、`is_urgent`。`analysis_state` 只能是 `unprocessed / analyzed_no_event / analyzed / failed`。
- `GET /work-orders/{id}` 默认只包含当前 `understanding.v2` events，不混合 v1；`cluster_refs[]` 提供真实 cluster ID/name/review/handling status 供跳转。
- Event 新增 `occurrence_date`；只有 time_signals 可确定完整年月日时才有值。`GET /events` 额外返回 `occurrence_dated_total / occurrence_unknown_total`，严禁用 `created_at` 补空。
- Entity reference 新增 `resolution_state`；`unresolved` 时页面显示“未解析”，不能把 UUID 前 8 位当业务名称。
- Cluster summary 新增 `review_status` 和 `is_multi_frequency`。多频列表仍只返回 `is_multi_frequency=true`；人工 remove 导致失效后，用 cluster_id 直访详情仍可返回审计/处理/纠错历史，前端必须保留 confirm_member 恢复入口。
- `POST /multi-frequency-events/{id}/review` 请求为 `review_status / actor_id / reason`；支持 pending/confirmed/rejected，不得用 handling status 替代。
- `POST /attachments` 是 multipart `file`，返回 `attachment_id/reference/original_filename/size/content_type`；将 `reference` 写入 handling record 的 `attachment_references`，下载调用 `GET /attachments/{attachment_id}`，不传绝对路径。

事件详情字段：`event_type`、`behavior`、`normalized_summary`、`entities`（canonical ID/name/type）、`location_signals`、`time_signals`、`evidence`（原文 quote/offset/segment）、`trace`。多频列表的 `work_order_count` 是不同原始工单数，`event_count` 是 AI 事件成员数，兼容字段 `member_count` 也表示 `work_order_count`，不得将其当成 event 数。详情页优先遍历 `work_orders`：每张原始工单只渲染一张 raw card，其下遍历该工单的 `events`；`members` 仅为 event-level 旧合同兼容。

多频详情还包含 `same_event` edge、`same_entity/same_location/same_issue/time_compatible/contradictions`、cluster `handling_status` 和 trace，以及 `handling_history`、`human_corrections`。处理记录写入 `handling_status`、说明、结果和附件引用；纠错当前支持 `remove_member` / `confirm_member`，两者均写入 HumanCorrection 与 AuditLog，原始工单不变。CSV 至少包含 cluster、工单编号、标题、事件摘要、主体/地点、AI 依据、处理状态和处理结果。不要把 `confidence` 或 embedding 分数单独渲染成事实结论。

移出成员恢复：`GET /multi-frequency-events/{cluster_id}` 现在额外返回 `removed_members[]`。该数组不是软删除表，而是按纠错历史投影的最新状态；最新为 `remove_member` 且没有后续 `confirm_member` 的事件显示在这里，active `work_orders[].events` 不再重复显示。每项包含 `event_instance_id`、`event`（含原 AI trace）/`work_order`（可解析时）、`raw_title`、`raw_content`、`correction_id`、`actor_id`、`reason`、`removed_at`、`can_restore`。即使事件无法解析，也保留 ID 和纠错记录并将 `can_restore=false`。恢复仍使用：

```text
POST /multi-frequency-events/{cluster_id}/corrections
{
  "correction_type": "confirm_member",
  "event_instance_id": "<removed event id>",
  "actor_id": "<editable operator id>",
  "reason": "<editable restore reason>"
}
```

详情页必须提供独立“已移出事件”区，操作员编号默认显示“演示操作员”但可编辑，恢复理由必填可编辑，点击恢复需二次确认；请求期间禁用按钮，成功后重新读取详情并刷新多频列表缓存。active member 重复恢复或未曾移出的事件由后端返回 409，不应伪装成功。

客户详情页面向非技术人员：只显示中文业务词汇，不展示 UUID、源行号、原始扩展字段、模型/供应商追踪、evidence 键名或英文状态枚举。多频详情先展示事件结论、关联工单数、研判事项数和可信度；工单原文与智能研判结果分区；“调整事件归属”和“新增办理记录”默认收起。绿/橙/红状态点只映射后端真实状态，不允许由前端创造业务结论。

# TRAE 可以改

- React 页面布局、组件、动效、图标、信息层级
- 事件列表/工单详情/证据详情的呈现
- loading / error / empty state
- 筛选器、表格体验、分页体验
- Demo 引导和说明文案
- 在 API 已提供数据的前提下新增展示组件

# TRAE 禁止改

- 不得从 UI 直接访问数据库、vLLM、Obsidian 地名服务。
- 不得绕过 backend handler。
- 不得删字段或降功能来适配页面。
- 不得把真实 API 换成静态 mock 作为正式路径。
- 不得私自改变 Entity/Event 数据语义。
- 不得将 EventInstance 数当成多频次数，不得在详情页重复渲染同一张原始工单。
- 不得把 AI 结果改回强制人工复核流程。
- 不得删除人工纠错与审计信息。
- 不得隐藏失败/未知状态以制造“全部成功”的观感。
- 首页和看板不得添加静态示例、随机数、固定比例或样本外兜底数字；没有后端字段就不展示该指标，接口空结果必须显示空状态。
- 不得把“多频 cluster”直接改名或自行推断成“高频”。后端已提供 `is_high_frequency`、
  `frequency_window_days`、`frequency_work_order_count`：含义是 active cluster 任意滚动三天日历窗口内
  至少三条不同真实 WorkOrder，缺少 `occurrence_date` 的记录不计入；前端只展示字段，不自行设置相似度阈值或重算。
- 不得擅自改变 Provider routing；不得写死商业模型厂商；不得绕过 backend 直接调用模型；不得修改 API key / secret 管理方式。当前 Demo 路径继续使用 `qwen-plus`、`qwen3.7-text-embedding` 和 remote OpenAI-compatible provider。
- `partial`、`failed`、`ambiguous`、`unresolved` 必须原样呈现，不能视觉上抹平。

# API 改动规则

需要新增/修改 API 时：

1. 在 `docs/TRAE_CHANGELOG.md` 写需求和原因。
2. 不要自己破坏 contract；交给 Codex 修改 schema/handler。
3. Codex 跑 migration/tests 后再更新前端 client。

# 如果 TRAE 没连接 Git

每个软装阶段至少更新：

```text
docs/TRAE_CHANGELOG.md
- 日期
- 改动目标
- 修改文件
- 是否需要 API 变更
- 本地验证命令
- 已知问题
```

不要删除 `.git` 目录，不要执行 `git init` 覆盖仓库，不要复制出第二套“最终版工程”。

交回 Codex 后由 Codex：review → checks → commit → push。

# TRAE 完成定义

- 页面没有假数据冒充真实结果。
- 真实接口异常时页面能正确显示失败。
- 原始工单与 AI 理解明确分区。
- 事件依据一眼可读，不能只显示一个相似度百分比。
- AI 未识别字段显示“未识别/不确定”，不美化成虚构内容。
- 不引入架构回退。
