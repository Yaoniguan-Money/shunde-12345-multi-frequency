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

该 smoke 只发送合成 JSON 提示词，不发送真实工单。代码也支持其他 OpenAI-compatible 服务；本阶段没有把任何商业厂商写进业务 handler。没有 API key 时必须记录 `BLOCKED`，不能用 mock 输出冒充成功。

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

artifact 与 summary 写入 `data/runtime/quality/`（已 gitignore），包括原始工单、分段、结构化事件、地名解析、embedding、pgvector 候选和完整 trace；`gold_set`、precision、recall、F1 保持 `null`。原计划 500–1000 条，本轮因本地推理耗时按操作者指示停止在 300 条；summary 必须标明实际成功/失败数。事件 schema 当前只够候选检索，不足以可靠判定 `same_event`，应先人工 Gold Set 与 schema v2 评审。
