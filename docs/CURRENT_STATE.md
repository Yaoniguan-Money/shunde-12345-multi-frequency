# CURRENT_STATE.md

更新日期：2026-08-15（Asia/Shanghai）

状态只允许：`DONE / PARTIAL / BLOCKED / PLANNED`。本文件区分已经实测的 shipped state 与后续目标，不以骨架冒充业务功能。

## Git

- Branch：`main`
- 基线 checkpoint：`c28398513bb476f2f42b199089ee13ae19618b4f`
- Hard-install checkpoint：`75ea7e7`（Phase 0–3 已推送）
- 本轮 AI understanding/retrieval 行为提交：`c35403337769ad0467e0afa1ca9bf63d26d681b7`；本文件记录该提交的实测证据，不把未完成的全量分析标成 DONE。
- Remote：private repo 已创建：`https://github.com/Yaoniguan-Money/shunde-12345-multi-frequency`
- Push：`DONE` — GitHub OAuth 已增加 `workflow` scope；`main` 已推送并设置跟踪 `origin/main`。本轮提交完成后再次 push。

## Environment

| 项目 | 状态 | 实测结果 |
|---|---|---|
| OS | DONE | Windows 11 专业版 `10.0.26200`，64 位，约 32 GiB RAM |
| Python | DONE | CPython `3.12.10` 已安装；项目 `.venv` 由 uv 管理 |
| GPU / VRAM | DONE | NVIDIA GeForce RTX 3080 Laptop GPU，`16384 MiB`；驱动 `610.88`，Windows CUDA UMD `13.3` |
| Windows CUDA Toolkit | PARTIAL | `nvidia-smi` 可用；Windows `nvcc` 未安装。Phase 1 不依赖 `nvcc` |
| WSL2 | DONE | Ubuntu，WSL version 2；WSL 内可识别 RTX 3080 Laptop GPU / 16 GiB |
| Docker | DONE | Docker Engine `29.7.2`，Compose `v5.3.1` |
| uv | DONE | `uv 0.12.3` |
| Node / pnpm | DONE | Node `v24.14.0`；pnpm `11.19.0` |
| Git / gh | DONE | Git `2.53.0.windows.3`；GitHub CLI `2.93.0`；账号 `Yaoniguan-Money` 已认证，具备 `repo` scope |
| Ollama / local model | DONE | WSL2 Ubuntu 内 Ollama `0.32.13`；`qwen2.5:3b`（约 1.9 GB）与 `nomic-embed-text:latest`（约 274 MB）已从官方 Ollama registry 拉取；OpenAI-compatible `/v1` 与 `/api/embed` 健康检查通过 |

## Government workbook — read-only inspection

源文件必须保持原位且不得修改：

`C:\Users\Lenovo\Desktop\政数局资料-顺德区12345热线工单（2025年1月至3月）.xlsx`

| 项目 | 实测结果 |
|---|---|
| 大小 | `37,207,701` bytes（约 `35.48 MiB`） |
| SHA-256 | `764c73a2b512ab07d378739945a9ea2e73b0a7b972896a583d6bd02d106a88fb` |
| Sheet 数 | 3 |
| `Sheet1` | 128,279 行含表头；128,278 条数据；4 列 |
| `Sheet1` 字段 | `序号`、`工单编号`、`标题`、`内容` |
| `Sheet1` 空值 | 四列均为 0；完全空白数据行 0 |
| `Sheet2` / `Sheet3` | 空 sheet |

检查使用 bundled Python `openpyxl` 的 read-only 流式模式；未保存、写回、移动或复制源文件，也未把原始工单正文输出到日志。

## Gazetteer package and live service

- 包路径：`C:\Users\Lenovo\Desktop\顺德地名库交接包`
- 已完整读取包根 `README.md` 与 `顺德地名库\顺德地名知识库.md`。
- 服务源码：`地名服务\server.py`；数据库：`地名服务\shunde_places.db`。
- 真实 OpenAPI：title `顺德本地地名归一化服务`，version `1.0`。
- 实测 paths：`/`、`/batch`、`/match`、`/normalize`、`/search`、`/stats`。
- `/stats` 实测：217 标准地名、232 别名/曾用名、12 机构同义、8 后缀规则、488 语义候选，pypinyin on。
- 真实 lookup：`GET /normalize?text=凤城` → `大良街道`，rule / alias_exact，confidence `0.98`。
- 文档差异：交接包 README 写“语义候选库 545”，运行态 `/stats` 返回 488。当前只记录冲突，未擅自改地名包。
- Phase 1 已有真实 health probe；本轮新增 schema-driven Gazetteer HTTP adapter 与 SQLite runtime snapshot。

## PostgreSQL / pgvector

- Container：`shunde-12345-postgres-1`，Docker Desktop 已启动并 healthy
- PostgreSQL：`17.8`
- pgvector extension：`0.8.1`
- Port：`127.0.0.1:5432`
- Alembic revision：`7a8b9c0d1e2f (head)`；新增 AI 处理幂等约束与 768 维 cosine HNSW partial index；此前 revision 已包含可恢复导入字段、失败行表与 raw immutability trigger
- 表：18 张要求的业务骨架表 + `import_row_errors` + `alembic_version`，共 20 张 public tables。
- 已在空开发库实测 `alembic downgrade base` → `alembic upgrade head` 成功。
- Docker Hub 曾出现 TLS handshake timeout；随后通过 DaoCloud 的 Docker Hub 镜像代理拉取同名 tag，digest 为 `sha256:3e8b3adfd27b5707128f60956f62a793c3c9326ea8cfaf0eab7adccb5d700b21`。

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| 0 factual inspection | DONE | Excel、地名包/OpenAPI、硬件、WSL2、Docker、工具链均已只读实测 |
| 1 repo hardening | DONE | Git checkpoint、uv/pnpm lock、FastAPI、React 19 + Vite 8、PostgreSQL + pgvector、Alembic、CI、health、typed ports、18 表骨架 |
| 2 import | DONE | 真实 Excel 已导入 PostgreSQL：batch `95e6e941-fe47-4952-abb2-3ba5ed5615eb`，128,278/128,278 成功，0 失败，checkpoint 128,278；第二次真实运行返回 `idempotent=true`，数据库仍 128,278 行 |
| 3 gazetteer | DONE | 已从真实 SQLite 构建 229 实体运行时快照，真实 `/openapi.json` 发现 `/batch` 并实测凤城/人民医院/未知地点；`/entities/resolve` 已接入，未知明确 unresolved |
| 4 AI understanding/indexing | PARTIAL | 已接入本地 Ollama 结构化抽取、规则分段、批量地名解析、版本 trace、可恢复 checkpoint 与持久化；真实导入批次已处理 11/128,278 条（11 events、11 embeddings），全量尚未运行 |
| 5 retrieval/rerank | PARTIAL | pgvector cosine candidate retriever、HNSW 索引和 benchmark 已实装；11 条真实事件的 1000-profile smoke 已完成，另有 PostgreSQL hard-negative/self-exclusion contract test；reranker 仍为接口 |
| 6 event matching/clustering | PLANNED | 只有 interface/schema skeleton，无生产 matcher |
| 7 product loop | PLANNED | 前端仅工程/health 骨架，不是四页业务产品 |
| 8 benchmark/handoff | PARTIAL | 已记录 1000-profile smoke（当前库实际 11 条），无业务 Gold Set 所以 quality 保持 `null`；1k/10k/full 数据规模 benchmark 待全量索引后运行 |

## Shipped Phase 1 interfaces

- Core ports：`GazetteerProvider`、`MentionResolver`、`LLMProvider`、`EmbeddingProvider`、`WorkOrderSegmenter`、`RerankerProvider`、`CandidateRetriever`、`SameEventMatcher`、`ClusterConsistencyChecker`、`WorkOrderRepository`、`EventRepository`、`JobRepository`、`Exporter`。
- AI application seams：`WorkOrderUnderstandingService`（分段→批量结构化抽取→批量地名解析）、`UnderstandingAndIndexingPipeline`（checkpoint/resume）、`SQLAlchemyUnderstandingRepository`、`PostgresCandidateRetriever`。
- Production fake implementations：无。测试 fake 仅位于 `backend/tests`。
- Health：
  - `GET /health/live` → process alive
  - `GET /health/ready` → 真实数据库 readiness，失败返回 HTTP 503
  - `GET /health/dependencies` → database / gazetteer / local model 的真实或明确未配置状态
- 默认未设置模型环境变量时 local model 仍显示 `not_configured`；本轮显式配置 `http://127.0.0.1:11434` 后，两个模型的真实 health 与推理均通过。

## Validation evidence

2026-08-15 实际执行：

```text
uv sync --locked                         PASS
uv run ruff check .                      PASS — All checks passed
uv run ruff format --check .             PASS — repository formatted
uv run pyright backend                   PASS — 0 errors, 0 warnings
uv run pytest -q                         PASS — 12 passed（含 raw immutability、understanding batch、pgvector hard-negative contract）
pnpm install --frozen-lockfile           PASS
pnpm lint                                PASS
pnpm test --run                          PASS — 1 test file / 1 test passed
pnpm build                               PASS — Vite 8.2.1, 64 modules transformed
docker compose config --quiet            PASS
uv run alembic upgrade head              PASS — 7a8b9c0d1e2f
GET /health/live                         PASS — alive
GET /health/ready                        PASS — PostgreSQL up
GET /health/dependencies                 PASS — DB/gazetteer up; model not_configured
GET gazetteer /normalize?text=凤城        PASS — 大良街道 / 0.98
uv run python scripts/gazetteer_smoke.py PASS — OpenAPI 1.0；快照 229 entities；凤城 resolved；未知地点 unresolved
uv run python scripts/import_real_smoke.py PASS — 128,278 success / 0 failure / checkpoint 128,278
uv run python scripts/import_real_smoke.py PASS — second run idempotent=true
psql count check                          PASS — import_batches=1, work_orders=128,278
local model health                        PASS — qwen2.5:3b / nomic-embed-text
uv run python scripts/run_understanding.py --limit 2 --chunk-size 2
                                          PASS — paused；2 rows / 2 events / 2 embeddings；checkpoint 2
uv run python scripts/run_understanding.py --limit 8 --chunk-size 4
                                          PASS — paused；8 rows / 8 events / 8 embeddings；checkpoint 10
uv run python scripts/run_understanding.py --limit 1 --chunk-size 1
                                          PASS — paused；1 row / 1 event / 1 embedding；checkpoint 11；同步 1 个地名 knowledge snapshot
PostgreSQL AI count check                 PASS — complaint_segments=24；event_instances=11；entity_mentions=22；work_order_embeddings=11；dimensions=768；canonical_entities=229
uv run python scripts/retrieval_benchmark.py --profile 1000 --embedding-model nomic-embed-text --k 5
                                          PASS — 实际 rows=11；throughput 3.52 q/s；P50 272.01 ms；P95 353.07 ms；quality=null（无 Gold Set）
benchmark artifact                         PASS — `data/runtime/benchmarks/retrieval-smoke-20260815-final.json`（runtime ignored，不入 Git）
```

## Known blockers / decisions needed later

- `PARTIAL`（Phase 4 full-scale acceptance）：真实本地模型已部署并通过小批 inference；128,278 条全量理解/向量化尚未执行，不能宣称全量完成。
- `BLOCKED`（quality acceptance）：尚无业务方确认的 Gold Set、3–5 组官方同事件正例与 hard negatives；benchmark 因此只报告性能，不报告 Recall/Precision。
- `PARTIAL`（retrieval acceptance）：当前 smoke 数据只有 10 条已索引事件；需要完成明确规模的 1k/10k/full benchmark 后才能判断索引/吞吐是否满足目标。
- `BLOCKED`（domain decision）：同一持续事件与复发事件的时间边界未确认。
- `BLOCKED`（delete behavior）：软删除、硬删除或 audit tombstone 规则未由业务方确认。
- `BLOCKED`（Care Signal）：是否存在稳定匿名诉求人 ID 未确认；不得实现个人级 Care Signal。
