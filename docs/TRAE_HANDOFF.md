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

`C:\Users\Lenovo\Desktop\政数局资料-顺德区12345热线工单（2025年1月至3月）.xlsx`

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

- 默认模型运行时：Ollama `http://127.0.0.1:11434`；结构化抽取使用 `qwen2.5:3b`，向量使用 `nomic-embed-text`（768 维）。生产 local adapter 拒绝云端 URL，不做隐式云回退。
- Provider 模式由 `SHUNDE_AI_PROVIDER_MODE=local|remote|hybrid` 显式选择，默认 `local`。remote 使用通用 OpenAI-compatible adapter，API key 只来自环境变量；hybrid 的 `AUTO`/`LOCAL` 走本地，只有显式 `REMOTE` route 才走远端。AI trace 包含 `provider / model_id / model_config_hash / schema_version / pipeline_version`。
- 远端验证命令：`uv run python scripts/remote_provider_smoke.py`。该命令只发送合成 JSON，不发送政府工单；未配置 key 时状态为 `BLOCKED`。2026-08-15 已用 Qwen `qwen-plus` 实际通过 health 与结构化 JSON，provider trace 为 `remote-openai-compatible`。
- `uv run python scripts/run_understanding.py --limit N --chunk-size K`：从真实导入批次 checkpoint 继续执行“规则分段 → 批量结构化抽取 → 批量地名解析 → event/mention/segment 持久化 → embedding 写入”。省略 `--limit` 才会继续到全量，当前只实测了前 11 条，不要在演示环境无意触发全量。
- `uv run python scripts/retrieval_benchmark.py --profile 1000 --embedding-model nomic-embed-text`：运行 pgvector candidate retrieval 性能测试；没有业务 Gold Set 时 `quality` 必须保持 `null`。
- 原始 `work_orders.raw_*` 永不被 AI 改写。AI 结果存放在 `complaint_segments`、`entity_mentions`、`event_instances`、`work_order_embeddings`，并带 `model_id / schema_version / pipeline_version / knowledge_snapshot_id` 等 trace 字段。
- 当前阶段尚未提供事件聚类、同事件判定或业务详情 API；TRAE 不应为这些目标态能力制作静态“已完成”页面。未知/未解析状态必须原样显示。
- 质量 review：`uv run python scripts/quality_review.py --sample-size 300 --chunk-size 8 --candidate-limit 5`。输出在 `data/runtime/quality/`，逐条展示原始工单→分段→事件→实体解析→embedding/pgvector 候选→版本 trace；弱标签只是待人工确认候选，不能显示为 Gold Label。事件 schema 当前足够做候选检索，但不足以可靠判定 `same_event`。

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
- 不得把 AI 结果改回强制人工复核流程。
- 不得删除人工纠错与审计信息。
- 不得隐藏失败/未知状态以制造“全部成功”的观感。
- 不得把本地模型改成云 API。
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
