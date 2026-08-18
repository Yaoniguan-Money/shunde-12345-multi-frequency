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

## AI understanding / retrieval（演讲稿对齐后合同）

- 本轮（演讲稿对齐总升级计划）锁定：任务前在 UI 选择 Provider Profile，任务创建后冻结快照，不再依赖 `SHUNDE_AI_PROVIDER_MODE` 全局环境变量切换。
- 本地路径必须真实执行 LLM、Embedding、结构化输出和最小端到端研判；只做 `/health`、模型列表或单次 ping 不算完成。
- 云端 Provider 与本地 Provider 均通过 registry 选择；当前可用 `cloud-qwen` 和 `cloud-deepseek`。DeepSeek Profile 使用 `deepseek-v4-flash` LLM + 本地 Ollama `nomic-embed-text` Embedding，两个路由独立冻结；领域层不出现厂商分支，任一 provider 失败都明确可见且无 fallback。
- Provider 模式 API：`GET /ai/provider-profiles` 返回本地和云端可选 Profile（脱敏，不返回 API Key / Base URL）；`POST /ai/provider-profiles/{profile_id}/validate` 真实执行有界完整链路验证（LLM 结构化 EventFact、DB44 分类节点约束、Embedding 维度、SameEvent 结构化判断、最小导入夹具到聚类投影），不使用政府原文。前端只传 `profile_id`。
- 当前 DeepSeek 真实回放因账户余额阻塞：执行策略已降为 2 并发，等待 Provider 余额恢复后重新验证 `cloud-deepseek`，再恢复固定 Scope 的任务；不要在余额不足时改传本地 Profile 或把失败显示为完成。
- `understanding.v3` 替代 `understanding.v2` 成为 active projection；旧 v1/v2 数据保留审计可达。v3 文本分段固定为 `current_complaint / current_request / history_context / department_reply`，每个分段保留原文起止区间和分段依据；EventFact[] 只从 `current_complaint + current_request` 创建。
- 标准分类完整对齐 DB44/T 2479—2024 附录 A：14 一级、99 二级、515 三级；来源代码确定性映射，无代码时 AI 只能选 `classification_node_id`，不能生成自由文本类型。`090499` 两条不同父路径保留。Taxonomy API：`GET /taxonomies/active`、`GET /taxonomies/{version}/tree`。
- 原始 `work_orders.raw_*` 永不被 AI 改写。AI 结果存放在 `complaint_segments`、`entity_mentions`、`event_instances`（v3）、`work_order_embeddings`，并带 `model_id / schema_version / pipeline_version / knowledge_snapshot_id / classification_node_id / classification_source` 等 trace 字段。
- **锁定语义：多频按 distinct WorkOrder 计算，不按 EventInstance 数计算。** 一张工单可以有多个真实 AI 事件，但不能自己构成多频；同工单事件不进入跨工单 retrieval / SameEvent / cluster。100 张工单可产生 103 个事项，这是一对多合法结果。
- 高频规则：同一事件在任意连续 3 个自然日内达到 3 张及以上不同工单即 `high_frequency`；窗口使用 `reported_at`（受理时间），不使用 `occurrence_date` / `imported_at` / 历史回复日期。状态只有 `high_frequency / not_reached / insufficient_date_evidence`，禁止 `low_frequency`。
- 质量 review 脚本仅作为审计候选生成器，不能显示为 Gold Label，也不能显示 Recall/Precision/F1；无业务确认 Gold Set 前不报告质量指标。

## Demo Core 云端路径与 API

当前可演示的真实链路是：

```text
真实工单小样本 → understanding.v3 → remote embedding 1024d
→ pgvector candidates → SameEventJudgeV2 → 一致性 cluster → API
```

演示前运行 `docs/DEVELOPMENT.md` 中的环境加载和 `scripts/demo_core.py` 命令。脚本会生成 `data/runtime/demo/demo-core-*.json`（runtime ignored），artifact 不复制正文；正文和完整证据由 API 详情按 ID 读取。

TRAE 只调用以下 HTTP contract，不直接访问数据库或模型：

```text
GET /work-orders?offset=0&limit=20&query=
GET /work-orders/overview
GET /work-orders/facets
GET /work-orders/{work_order_id}
GET /events?offset=0&limit=20&pipeline_version=understanding.v3&work_order_id=
GET /events/{event_id}
GET /multi-frequency-events?offset=0&limit=20
GET /multi-frequency-events/{cluster_id}
GET /ai/provider-profiles
POST /ai/provider-profiles/{profile_id}/validate
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
GET /taxonomies/active
GET /taxonomies/{version}/tree
```

### Analysis job HTTP contract

```text
POST /analysis-jobs
{
  "import_batch_id": "<completed-or-partial-import-batch-id>",
  "provider_profile_id": "<chosen-profile-id>"
}
```

请求体不存在 `max_work_orders`、`selection_mode` 或前端并发参数。研判范围等于导入批次全部成功工单；后端可分块、限并发、断点续跑，但目标范围不可截断后伪装完成。

创建响应为 HTTP 202，状态从 `queued` → `running` → `completed | completed_with_failures | failed`。响应字段包含
`target_work_order_count`、`processed_work_order_count`、`failed_work_order_count`、
`produced_event_instance_count`、`provider_profile_snapshot`、`execution_policy_snapshot`、
`pipeline_version`、`taxonomy_version`、`current_stage`、checkpoint 和错误摘要。
API 后台复用 understanding.v3、taxonomy-constrained 分类、remote/local embedding、pgvector、
SameEventJudgeV2 与 ClusterAssembler；请求不会同步等待整批模型推理。

`current_stage=queued|understanding|classification|embedding|retrieval|matching|clustering|completed`。
TRAE 必须在 `status` 仍为 queued/running 时继续轮询；即使 `processed_work_order_count == target_work_order_count`，
matching/clustering 尚未结束也不得显示“研判完成”。只有后端返回 `status=completed` 才刷新
多频事件列表。一次研判的事件、匹配边、cluster 都属于同一个 analysis run，前端不得自行
拼接历史 run 或以 0 个 cluster 推断接口没有执行。

### Product semantics contracts

- `GET /work-orders` 支持 `analysis_state / classification_node_id / include_descendants / source_tag / urgency / frequency_status / pipeline_version`；summary 包含 `analysis_state`、`classifications[]`、`source_tags[]`、`is_urgent`、`frequency_statuses[]`、`event_instance_count`、`multi_frequency_membership_count`、`reported_at`、`reported_at_source`、`imported_at`。`analysis_state` 只能是 `unprocessed / analyzed_no_event / analyzed / failed`。
- `GET /work-orders/overview` 返回 `work_order_total / analysis_outcome_counts / event_instance_total / multi_frequency_cluster_total / frequency_status_counts / classification_facets / source_tag_facets / unknown_classification_work_order_count`，全部按同一 ScopeFilter 聚合；`analysis_outcome_counts` 之和等于 `work_order_total`。当前页 20 条只属于分页信息，不属于 overview。
- `GET /work-orders/{id}` 默认只包含当前 `understanding.v3` events，不混合 v1/v2；`cluster_refs[]` 提供真实 cluster ID/name/review/handling status 供跳转。
- Event 含 `reported_at` + 来源、`occurrence_interval`（可空/区间）；只有 time_signals 可确定完整年月日时才有 `occurrence_interval`。严禁用 `created_at` / `imported_at` 补 `reported_at`。
- 标准分类绑定在 EventInstance：每个事项携带 `classification_node_id / classification_source (source_code|model|human) / classification_confidence / classification_decision (resolved|ambiguous|unresolved|human_corrected) / evidence_refs / full_path / printed_code / printed_name`。工单列表上的“诉求事项分类”是当前有效事项的聚合投影。
- Entity reference 新增 `resolution_state`；`unresolved` 时页面显示“未解析”，不能把 UUID 前 8 位当业务名称。
- Cluster summary 包含 `frequency_status`（`high_frequency | not_reached | insufficient_date_evidence`，禁止 `low_frequency`）、`distinct_work_order_count`、`event_instance_count`、winning three-day window、canonical object、classification path、report window、cluster narrative、active versions、`review_status`、`is_multi_frequency`。多频列表仍只返回 `is_multi_frequency=true`；人工 remove 导致失效后，用 cluster_id 直访详情仍可返回审计/处理/纠错历史，前端必须保留 confirm_member 恢复入口。
- `POST /multi-frequency-events/{id}/review` 请求为 `review_status / actor_id / reason`；支持 pending/confirmed/rejected，不得用 handling status 替代。
- `POST /attachments` 是 multipart `file`，返回 `attachment_id/reference/original_filename/size/content_type`；历史处理记录可只读引用附件，新增处置记录请求体不再包含 `attachment_references` 字段，下载调用 `GET /attachments/{attachment_id}`。

事件详情字段：`current_problem`、`current_request`、`classification_node_id` + 完整路径、`focal_object_mentions`、`responsible_party_mentions`、`location_mentions`、`occurrence_interval`、`history_context`、`evidence_spans`（原文 quote/offset/segment）、`unknown_fields`、`trace`。多频列表的 `distinct_work_order_count` 是不同原始工单数，`event_instance_count` 是 AI 事件成员数；详情页优先遍历 `work_orders`：每张原始工单只渲染一张 raw card，其下遍历该工单的 `events`；`members` 仅为 event-level 旧合同兼容。

多频详情还包含 `same_event` edge（`same_focal_object / same_responsible_party / same_classification / report_window_compatible / same_handling_chain / same_location / claimant_variation_compatible / contradictions[] / unknowns[] / final_decision / confidence / evidence_refs[]`）、cluster `handling_status` 和 trace，以及 `handling_history`、`human_corrections`。处理记录写入 `handling_status`、说明、结果（不再写附件编号）；纠错支持 `remove_member` / `confirm_member`，两者均写入 HumanCorrection 与 AuditLog，原始工单不变。CSV 至少包含 cluster、工单编号、标题、事件摘要、主体/地点、AI 依据、处理状态和处理结果。不要把 `confidence` 或 embedding 分数单独渲染成事实结论。

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
- 不得把“多频 cluster”直接改名或自行推断成“高频”。后端 cluster 提供 `frequency_status`（`high_frequency | not_reached | insufficient_date_evidence`，禁止 `low_frequency`）、`distinct_work_order_count`、winning three-day window、`frequency_work_order_count`：含义是 active cluster 任意滚动 3 个自然日窗口内至少 3 张不同真实 WorkOrder（按 `reported_at`），缺少 `reported_at` 的记录不计入；前端只展示字段，不自行设置相似度阈值或重算。
- 不得擅自改变 Provider routing；不得写死商业模型厂商；不得绕过 backend 直接调用模型；不得修改 API key / secret 管理方式。任务前在 UI 选择 Provider Profile，任务创建后锁定快照；前端只传 `profile_id`，不传 API Key / Base URL。
- 不得在页面、API 请求或数据库中保留“研判数量”输入、`max_work_orders`、`selection_mode`、`attachment_references`（新增处置记录）或 `low_frequency` 枚举。
- 不得保留 Dashboard 质量指标板块（质量状态灯、准确率/Gold Set 卡、“暂无 Gold Set”说明、对应占位空格和布局容器）；删除后重新排版，不保留隐藏节点或空卡。
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
