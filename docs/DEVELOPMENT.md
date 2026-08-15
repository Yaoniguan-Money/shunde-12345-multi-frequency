# 开发与环境约定

## 真实输入位置

- 政府工单 Excel（只读，不复制进仓库）：
  `C:\Users\Lenovo\Desktop\政数局资料-顺德区12345热线工单（2025年1月至3月）.xlsx`
- 地名库交接包（只读知识源）：
  `C:\Users\Lenovo\Desktop\顺德地名库交接包`
- 地名服务 SQLite：
  `C:\Users\Lenovo\Desktop\顺德地名库交接包\地名服务\shunde_places.db`

## 下载策略

凡需要安装依赖、下载镜像或拉取模型，优先使用供应商正规镜像源/镜像代理，并把来源、版本和校验结果写入 `docs/CURRENT_STATE.md`。当前 Python 包默认使用清华 PyPI 镜像（`pyproject.toml` 的 `tool.uv.index`）；PostgreSQL pgvector 默认使用 DaoCloud 的 Docker Hub 正规镜像代理，可用 `SHUNDE_POSTGRES_IMAGE` 显式覆盖。

不得使用来历不明的破解包、未知模型权重或云端替代实现。镜像不可用时记录失败原因，再询问是否切换官方源；不把下载缓存、模型权重、真实政府数据提交到 Git。

## Phase 2 实际导入

先启动 PostgreSQL 并执行 `uv run alembic upgrade head`，再运行：

```powershell
$env:SHUNDE_GOVERNMENT_XLSX = 'C:\Users\Lenovo\Desktop\政数局资料-顺德区12345热线工单（2025年1月至3月）.xlsx'
uv run python scripts/import_real_smoke.py
```

导入按源文件 SHA-256 幂等，按物理行 checkpoint 可恢复；原始工单正文只写入 `work_orders`，不写日志。失败行写入 `import_row_errors`，批次会明确返回 `partial` 或 `failed`。

## Phase 3 地名服务

在交接包的 `地名服务` 目录启动真实服务后，运行：

```powershell
$env:SHUNDE_GAZETTEER_DB = 'C:\Users\Lenovo\Desktop\顺德地名库交接包\地名服务\shunde_places.db'
uv run python scripts/gazetteer_smoke.py
```

HTTP adapter 启动时读取 `/openapi.json`，从真实 schema 发现批量操作，不猜 endpoint；快照从 SQLite 只读构建并原子写入 `data/runtime/gazetteer.snapshot.json`。运行时先查快照别名，再对剩余 mention 做一次批量远端查询。

## 常用检查

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright backend
uv run pytest -q
```

前端和 Docker 检查仍由 `scripts/check.ps1` 统一执行。Docker Desktop 未启动时，数据库迁移、真实导入和原始字段不可变触发器的运行态验证均应标记 `BLOCKED`，不得用内存 fake 冒充通过。

## 本地 AI 理解与检索

Ollama 只在 WSL2/本机运行，当前采用官方模型仓库：

```bash
ollama serve
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Windows PowerShell 中运行真实批次 smoke（先完成 `alembic upgrade head`）：

```powershell
$env:SHUNDE_MODEL_API_BASE_URL = 'http://127.0.0.1:11434'
$env:SHUNDE_LLM_MODEL_ID = 'qwen2.5:3b'
$env:SHUNDE_EMBEDDING_MODEL_ID = 'nomic-embed-text'
uv run python scripts/run_understanding.py --limit 4 --chunk-size 2
```

去掉 `--limit` 会从 durable checkpoint 继续直到该真实导入批次完成；失败不会伪造成功。检索 benchmark 使用：

```powershell
uv run python scripts/retrieval_benchmark.py --profile 1000 --embedding-model nomic-embed-text
```

没有业务确认的 Gold Set 时只报告硬件、吞吐、P50/P95 与候选数，不报告 Recall/Precision；Gold Set JSON 必须显式传入 `--gold-set`。

本轮真实运行记录（2026-08-15）：WSL2 Ubuntu 使用 Ollama `0.32.13`，通过官方 Ollama registry 拉取 `qwen2.5:3b` 与 `nomic-embed-text:latest`；GPU 为 RTX 3080 Laptop 16 GiB。实际 smoke 处理 11/128,278 条，写入 11 个事件与 11 个 768 维向量。没有配置可信模型镜像时不擅自替换模型来源；后续下载仍遵循“正规镜像优先、官方源可回退、记录版本/校验、缓存不入 Git”的规则。

## Local / remote / hybrid Provider

默认 `SHUNDE_AI_PROVIDER_MODE=local`。显式配置项见 `.env.example`：

```text
SHUNDE_AI_PROVIDER_MODE=local|remote|hybrid
SHUNDE_AI_LOCAL_LLM_BASE_URL
SHUNDE_AI_LOCAL_LLM_MODEL_ID
SHUNDE_AI_LOCAL_EMBEDDING_BASE_URL
SHUNDE_AI_LOCAL_EMBEDDING_MODEL_ID
SHUNDE_AI_LOCAL_EMBEDDING_PROTOCOL=ollama|openai
SHUNDE_AI_REMOTE_BASE_URL
SHUNDE_AI_REMOTE_LLM_MODEL_ID
SHUNDE_AI_REMOTE_EMBEDDING_MODEL_ID
SHUNDE_AI_REMOTE_API_KEY
SHUNDE_AI_HYBRID_POLICY=explicit-route-local-default
```

Remote API key 只能作为进程环境变量读取，不写入 `.env`、Git、日志或数据库正文。当前选择 Qwen 做远端 smoke 时，官方 OpenAI-compatible 示例为：

```powershell
$env:SHUNDE_AI_PROVIDER_MODE = 'remote'
$env:SHUNDE_AI_REMOTE_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
$env:SHUNDE_AI_REMOTE_LLM_MODEL_ID = 'qwen-plus'
$env:SHUNDE_AI_REMOTE_API_KEY = Read-Host 'DASHSCOPE API key'
uv run python scripts/remote_provider_smoke.py
```

该 smoke 只发送合成 JSON 提示词，不发送真实工单。2026-08-15 已用 Qwen `qwen-plus` 真实通过 health 与结构化 JSON；代码也支持其他 OpenAI-compatible 服务，本阶段没有把任何商业厂商写进业务 handler。没有 API key 时必须记录 `BLOCKED`，不能用 mock 输出冒充成功。

## Demo Core：cloud-first 小样本路径

比赛演示路径可以显式使用 remote provider；这不改变代码在未配置环境时的 local 安全默认，也不允许 local 失败后自动上云。Windows 新 PowerShell 进程可从用户环境加载配置（不要把 key 写入项目文件）：

```powershell
$names = 'SHUNDE_AI_PROVIDER_MODE','SHUNDE_AI_REMOTE_BASE_URL','SHUNDE_AI_REMOTE_LLM_MODEL_ID','SHUNDE_AI_REMOTE_EMBEDDING_MODEL_ID','SHUNDE_AI_REMOTE_API_KEY','SHUNDE_GAZETTEER_HOME'
foreach ($name in $names) {
  $value = [Environment]::GetEnvironmentVariable($name, 'User')
  if ($null -ne $value) { Set-Item -Path ("Env:" + $name) -Value $value }
}
uv run python scripts/remote_provider_smoke.py
uv run python scripts/remote_embedding_smoke.py
uv run python scripts/demo_core.py --anchor-limit 4 --candidate-limit 4
```

`demo_core.py` 从真实 PostgreSQL 按文本条件动态选择工单，执行 `understanding.v2 → batch entity resolve → remote embedding → pgvector candidates → remote SameEventMatcher → consistency-guarded cluster`。默认样本包含“新桂北路29号116号铺 / 恒艺工作室 / 恒艺音乐”锚点、跨地点噪音 hard negative 与不同问题候选；脚本不嵌入 UUID，不复制正文到 artifact，也不会处理全量 128,278 条。

远程 demo 的实测模型是 `qwen-plus`（结构化理解/SameEvent）和 `qwen3.7-text-embedding`（1024 维）。若供应商余额、权限或接口失败，命令必须失败并保留 `BLOCKED` 事实，不得回退本地或 fake success。

## Demo read API

启动 backend 后，TRAE 只通过 HTTP 读取真实数据：

```text
GET /work-orders?offset=0&limit=20&query=
GET /work-orders/{work_order_id}
GET /events?offset=0&limit=20&pipeline_version=understanding.v2&work_order_id=
GET /events/{event_id}
GET /multi-frequency-events?offset=0&limit=20
GET /multi-frequency-events/{cluster_id}
```

列表响应包含 `items/offset/limit/total`；详情分别包含 immutable raw work-order、v2 event（`event_type/behavior/normalized_summary/location_signals/time_signals/evidence`）、canonical entity references、SameEvent edges、cluster handling status 与 provider/model/config/schema/pipeline trace。Embedding 分数不能直接当 `same_event`。

多频簇的频次单位是 distinct WorkOrder，不是 EventInstance。Catalog 只返回至少包含 2 张不同工单的簇；列表/详情中 `work_order_count` 是频次，`event_count` 是事件证据数，兼容字段 `member_count == work_order_count`。详情中 `work_orders[].events` 是前端的主渲染合同，原始工单每张只展示一次；`members` 仅保留为 event-level 兼容投影。

retrieval 、`RemoteSameEventMatcher` 和 `EventGraphService` 均禁止同一 WorkOrder 内的事件对，cluster builder/repository 再次校验至少 2 个 distinct WorkOrder。这些是产品不变量，不能为了展示层方便在前端重算或放宽。

## Bounded AI analysis job API

导入完成后，Demo 前端通过 HTTP 启动后台研判，不调用脚本：

```powershell
$base = 'http://127.0.0.1:8080'
$body = @{
  import_batch_id = '<completed-or-partial-import-batch-id>'
  max_work_orders = 100      # 必填；当前允许 1–300
  selection_mode = 'recurrence_candidates'
} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri "$base/analysis-jobs" `
  -ContentType 'application/json' -Body $body
do {
  Start-Sleep -Seconds 2
  $progress = Invoke-RestMethod "$base/analysis-jobs/$($job.job_id)"
  $progress | Select-Object status,total_rows,selected_rows,processed_rows,event_count,match_edge_count,cluster_count,error
} while ($progress.status -in @('queued','running'))
```

创建接口返回 HTTP 202；状态只能是 `queued`、`running`、`completed` 或 `failed`。完成后
`event_count`、`match_edge_count`、`cluster_count` 是真实持久化结果，`trace` 只含
provider/model/config hash/schema/pipeline，不含 API key。后台链路复用
`UnderstandingAndIndexingPipeline` 的 checkpoint、`understanding.v2`、地名快照、remote
embedding、pgvector candidate retrieval、`RemoteSameEventMatcher` 和
`EventGraphService`。上限是硬门禁，省略 `max_work_orders` 或填写大于 300 会被拒绝，不能误触
128,278 条全量公网推理；remote 失败必须显示 `failed`，不得伪装 `completed`。

只验证确定性选择、不调用 AI：

```powershell
uv run python scripts/selection_smoke.py --limit 100
```

2026-08-15 真实 128,278 条批次结果：顺序前 100 条含复发词 6/编号引用 9；`recurrence_candidates` 100 条含复发词 51/编号引用 90，source row 范围 2–777。该脚本不会调用 LLM/embedding。

## Product semantics and attachment contracts

```text
GET  /work-orders?analysis_state=analyzed&event_type=noise&title_tag=急
POST /attachments                       # multipart field: file
GET  /attachments/{attachment_id}
POST /multi-frequency-events/{id}/review
```

WorkOrder 产品投影固定使用 `SHUNDE_ANALYSIS_PIPELINE_VERSION`（当前 `understanding.v2`）。历史 event 不删除，`GET /events?pipeline_version=understanding.v1` 是显式技术访问，不应混入 WorkOrder 产品详情。`work_order_analysis_results` 是 AI 处理状态真相源，不能由 event_count 反推。

派生数据安全修复（不写 raw WorkOrder）：

```powershell
uv run python scripts/repair_event_semantics.py
```

脚本只删除无法 join CanonicalEntity 的 event `entity_ids`，并将 time_signals 中唯一、有效、完整日期写入 `occurrence_date`。当前 v2 实测 dated/unknown = 16/16。附件保存在 `data/runtime/attachments/`（gitignored），默认上限 10 MiB，API 不返回本机路径。
对能从 event evidence 确认 analysis_run 的存量派生数据，该脚本还会幂等回填 `work_order_analysis_results`；实测回填 v1=11 work orders、v2=25 work orders。无 event 工单不会被猜测为已分析。

## Demo product loop API

TRAE 仍只访问 backend，不直接访问 PostgreSQL 或模型。使用当前详情中的 `cluster_id` 和成员 `event_instance_id`：

```powershell
$base = 'http://127.0.0.1:8080'
$body = @{
  new_status = 'investigating'
  actor_id = 'operator-id'
  description = '已转属地核查'
  result = '待回访'
  attachment_references = @()
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/multi-frequency-events/$clusterId/handling-records" `
  -ContentType 'application/json' -Body $body
Invoke-RestMethod "$base/multi-frequency-events/$clusterId/handling-records"
```

人工纠错请求体为 `correction_type=remove_member|confirm_member`、`event_instance_id`、`actor_id` 和可选 `reason`：

```text
POST /multi-frequency-events/{cluster_id}/corrections
GET  /multi-frequency-events/{cluster_id}/corrections
GET  /multi-frequency-events/export.csv?cluster_id={cluster_id}
```

写 API 使用既有 `EventHandlingRecord`、`HumanCorrection`、`AuditLog`，不修改 `work_orders.raw_*`。处理记录是追加历史并同步当前 `handling_status`；纠错改变的是派生 cluster membership，事实与审计记录不会被下一次 AI run 删除。当前只开放安全的成员移除/确认，不假装提供 merge/split。CSV 为 UTF-8 BOM，便于 Excel 直接打开；未解析主体/地点保持为空或明确未知，不得补造。

## AI quality review artifact

先用真实导入批次做确定性弱标签分层抽样，不把模型输出当 Gold Label：

```powershell
$env:SHUNDE_AI_PROVIDER_MODE = 'local'
$env:SHUNDE_MODEL_API_BASE_URL = 'http://127.0.0.1:11434'
$env:SHUNDE_LLM_MODEL_ID = 'qwen2.5:3b'
$env:SHUNDE_EMBEDDING_MODEL_ID = 'nomic-embed-text'
$env:SHUNDE_GAZETTEER_HOME = 'C:\Users\Lenovo\Desktop\顺德地名库交接包'
uv run python scripts/quality_review.py --sample-size 300 --chunk-size 8 --candidate-limit 5
```

artifact 与 summary 写入 `data/runtime/quality/`（已 gitignore），包括原始工单、分段、结构化事件、地名解析、embedding、pgvector 候选和完整 trace；`gold_set`、precision、recall、F1 保持 `null`。原计划 500–1000 条，本轮因本地推理耗时按操作者指示停止在 300 条；summary 必须标明实际成功/失败数。正式质量验收仍需人工 Gold Set；Demo Core 的 SameEvent 结果是可审核候选，不是 Gold Label。
