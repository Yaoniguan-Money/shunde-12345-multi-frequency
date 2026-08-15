# CURRENT_STATE.md

更新日期：2026-08-15（Asia/Shanghai）

状态只允许：`DONE / PARTIAL / BLOCKED / PLANNED`。本文件区分已经实测的 shipped state 与后续目标，不以骨架冒充业务功能。

## Git

- Branch：`main`
- 基线 checkpoint：`c28398513bb476f2f42b199089ee13ae19618b4f`
- Hard-install checkpoint：`75ea7e7`（Phase 0–3 已推送）
- 本轮 AI understanding/retrieval 行为提交：`c35403337769ad0467e0afa1ca9bf63d26d681b7`；本轮 provider/quality 提交：`8954e18`（已推送 `origin/main`）。
- Remote：private repo 已创建：`https://github.com/Yaoniguan-Money/shunde-12345-multi-frequency`
- Push：`DONE` — GitHub OAuth 已增加 `workflow` scope；`main` 已推送并设置跟踪 `origin/main`。本轮提交完成后再次 push。
- 本轮 cloud-first Demo Core commit：`8e9e5fc`；文档 checkpoint：`79f48b7`，均已推送 `origin/main`。
- Final Codex hard-install closure commit：`7595dd2`（bounded analysis job HTTP contract），已推送 `origin/main`。

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

当前验收数据集：`C:\Users\Lenovo\Desktop\顺德12345热线精选工单数据集（含重复工单）.xlsx`（100 条精选工单；原 128,278 条政府全量 Excel 保留为归档参考，不作为当前验收库）。

2026-08-15 验收环境已重置：旧导入、AI 派生结果、cluster、analysis job、人工纠错、处理记录和审计记录清空；数据库结构及地名知识快照保留。精选数据重新导入 100/100，无失败。当前服务：backend `http://127.0.0.1:8080`、frontend `http://127.0.0.1:5173`，ready/live 均通过。

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
- Alembic revision：`9c0d1e2f3a4b (head)`；新增 Qwen `qwen3.7-text-embedding` 1024 维 cosine HNSW partial index（只匹配该 model_id/dimensions）；此前 revision 已包含 AI trace 的 nullable `provider` 字段、AI 处理幂等约束、768 维 cosine HNSW partial index、可恢复导入字段、失败行表与 raw immutability trigger
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
| 4 AI understanding/indexing | PARTIAL | v1 本地 smoke 11 条仍保留；Demo Core 以 `understanding.v2` 真实处理选中工单，当前库有 17 个 v2 event、remote Qwen 1024 维 embedding；128,278 条全量尚未运行 |
| 5 retrieval/rerank | DONE（Demo Core 范围） | PostgreSQL/pgvector candidate retrieval 已接入 remote embedding；`qwen3.7-text-embedding` 真实返回 1024 维并有专用 HNSW partial index；embedding 仍只是 recall evidence，reranker 接口未实现 |
| 6 event matching/clustering | DONE（Demo Core 范围） | Remote `SameEventMatcher` 已真实调用 qwen-plus；Demo 产出 6 positive / 5 hard-negative edges、1 个一致性 cluster；不是 128,278 条全量聚类，也没有 cosine threshold 判定 |
| 7 product loop | DONE（backend contract） | 集群一致性回归、处理状态/历史、人工 remove/confirm 纠错、AuditLog、详情聚合、CSV 导出和 bounded AI analysis job HTTP contract 均已真实可调用；前端仍为工程/health 骨架，不是四页业务产品 |
| 8 benchmark/handoff | PARTIAL | Demo review artifact 已生成且保留 raw→v2 event→entity→embedding→candidate→SameEvent trace；没有 Gold Set，不报告 Recall/Precision/F1；500–1000 条人工 benchmark 仍是后续工作 |

## 本轮 Provider / Quality Validation 状态

| 项目 | 状态 | 实测事实与影响 |
|---|---|---|
| Local provider | DONE | `OpenAICompatibleLLMProvider` 保留公网 URL 拒绝；Ollama `qwen2.5:3b` 实测返回结构化 JSON；`nomic-embed-text` native `/api/embed` 保持可用；local 调用失败不会云回退 |
| Remote provider architecture | DONE | 通用 OpenAI-compatible LLM/embedding adapters、`AI_PROVIDER_MODE=local|remote|hybrid`、显式 route policy、API key `SecretStr`、provider trace 与 migration `9c0d1e2f3a4b` 已落地；contract/routing tests 通过 |
| Remote real integration | DONE | 2026-08-15 09:51（Asia/Shanghai）显式配置 Qwen DashScope 后，`scripts/remote_provider_smoke.py` 真实通过：health=`qwen-plus`、structured_keys=`["ok"]`、provider=`remote-openai-compatible`；只发送合成 JSON，不发送政府工单，API key 未写入日志/仓库 |
| Quality sample selector | DONE | 从真实 batch `95e6e941-fe47-4952-abb2-3ba5ed5615eb` 确定性抽样逻辑已实测 500 条，6 个 strata（recurrence/multi-event/mixed history-reply/alias/identifier/general）分布可审计 |
| Quality review execution | PARTIAL | `scripts/quality_review.py` 可输出 raw→segmentation→events→entity resolution→embedding→pgvector candidates→trace；本轮本地 300 条运行因耗时按操作者指示停止，保留的旧 partial artifact 含模型截断错误，不能当质量结论；已修复通用 JSON wrapper 解包、简洁摘要提示和输出上限，需重新运行才生成有效 artifact |
| Event Schema for SameEventMatcher | DONE（Demo Core）/ PARTIAL（正式验收） | `understanding.v2` 已补齐 `event_type`、event-specific `behavior`、`time_signals`、`mention_indexes`、经过原文精确校验的 evidence quote；SameEvent 输入包含 canonical entity/location/issue/behavior/time/evidence。正式 Gold Set、时间区间与业务边界仍需人工确认 |

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
uv run pytest -q                         PASS — 12 passed（早期 Phase checkpoint；最新门禁见本文件下方）
pnpm install --frozen-lockfile           PASS
pnpm lint                                PASS
pnpm test --run                          PASS — 1 test file / 1 test passed
pnpm build                               PASS — Vite 8.2.1, 64 modules transformed
docker compose config --quiet            PASS
uv run alembic upgrade head              PASS — 7a8b9c0d1e2f（早期 Phase checkpoint）
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

本轮追加实测（2026-08-15）：

```text
uv run alembic upgrade head                  PASS — 7a8b9c0d1e2f -> 8b9c0d1e2f3a（早期 provider checkpoint）
uv run pytest -q                             PASS — 18 passed（早期 provider checkpoint）
uv run ruff check backend/app scripts/...    PASS
uv run ruff format --check ...               PASS
uv run pyright backend                       PASS — 0 errors
provider contract/routing tests              PASS — 6 passed；公网 local URL 被拒绝；remote key 不进 trace
Ollama qwen2.5:3b structured smoke           PASS — RTX 3080 Laptop 16 GiB，真实 JSON 返回
quality sample selector (500)                PASS — 6 strata，500 个真实 work_order_id
quality review run                           PARTIAL — 按操作者指示停止本地 300 条运行；未把 partial artifact 当质量指标
remote_provider_smoke.py                     PASS — Qwen `qwen-plus` health 与结构化 JSON 真实通过；只发送合成 JSON，API key 未记录
```

## Known blockers / decisions needed later

- `PARTIAL`（Phase 4 full-scale acceptance）：真实本地模型已部署并通过小批 inference；128,278 条全量理解/向量化尚未执行，不能宣称全量完成。
- `BLOCKED`（quality acceptance）：尚无业务方确认的 Gold Set、3–5 组官方同事件正例与 hard negatives；benchmark 因此只报告性能，不报告 Recall/Precision。
- `PARTIAL`（retrieval acceptance）：当前 smoke 数据只有 10 条已索引事件；需要完成明确规模的 1k/10k/full benchmark 后才能判断索引/吞吐是否满足目标。
- `BLOCKED`（domain decision）：同一持续事件与复发事件的时间边界未确认。
- `BLOCKED`（delete behavior）：软删除、硬删除或 audit tombstone 规则未由业务方确认。
- `BLOCKED`（Care Signal）：是否存在稳定匿名诉求人 ID 未确认；不得实现个人级 Care Signal。

## 本轮 Demo Core（2026-08-15）

| 项目 | 状态 | 实际结果 |
|---|---|---|
| Understanding v2 | DONE（小样本） | 新增 event-specific `behavior`、`time_signals` 与 verbatim evidence；无效模型 quote 会被丢弃，数据库只保存能在分段原文中精确找到的 quote |
| Remote chat contract | DONE | `uv run python scripts/remote_provider_smoke.py` → health `qwen-plus`、provider `remote-openai-compatible`、结构化 JSON PASS；API key 未进入输出 |
| Remote embedding contract | DONE | `uv run python scripts/remote_embedding_smoke.py` → `qwen3.7-text-embedding`、真实返回 `1024` dimensions、专用 HNSW partial index PASS |
| Demo selector | DONE | 从真实数据库动态选取 source rows `9/43/3451/4781/11862/14715`；没有硬编码 UUID，包含恒艺锚点、跨地点噪音、同主体/不同问题候选 |
| SameEventMatcher | DONE（Demo Core） | `qwen-plus` remote 判断；显式 remote route；实体/地点/问题/行为/时间/evidence 输入；不以 cosine threshold 下结论 |
| Event graph / cluster | DONE（Demo Core） | 实际 artifact `data/runtime/demo/demo-core-20260815T023809Z.json`：6 positive edges、5 hard negatives、1 cluster；cluster builder 拒绝矛盾的传递合并 |
| Read API | DONE | 真实 uvicorn smoke：`GET /work-orders` total `128278`、`GET /events` total `17`、`GET /multi-frequency-events` total `1`；三个列表及三个详情均 HTTP 200，详情含 raw、evidence、trace、edge |
| Full-corpus AI | PARTIAL | 128,278 条原始工单仍未全量发送给 LLM；当前 v2 event 17 条（本轮真实 bounded job 选 1 条），旧 v1 smoke event 11 条，不能据此宣称全量完成 |

### 本轮实际门禁

```text
uv run alembic upgrade head                  PASS — 9c0d1e2f3a4b
uv run ruff check .                          PASS
uv run ruff format --check .                 PASS
uv run pyright backend                       PASS — 0 errors, 0 warnings
uv run pytest -q                             PASS — 29 passed
remote_provider_smoke.py                     PASS — qwen-plus / structured JSON
remote_embedding_smoke.py                    PASS — qwen3.7-text-embedding / 1024 dims
demo_core.py --anchor-limit 4 --candidate-limit 4 PASS — 6 positive / 5 negative / 1 cluster
uvicorn + catalog endpoint smoke             PASS — six list/detail endpoints HTTP 200
```

## Final Codex hard-install closure (2026-08-15)

| 项目 | 状态 | 实际结果 |
|---|---|---|
| Cluster consistency | DONE | `EventClusterBuilder` 不再把不完全相同的 `event_type` 当硬冲突；实体/地点明确冲突和 SameEvent `false`/contradiction 仍拒绝合并；回归测试覆盖 `commercial_noise` vs `noise_disturbance` 同事件 |
| Handling API | DONE | `POST/GET /multi-frequency-events/{id}/handling-records` 更新当前 `handling_status` 并追加说明/结果/附件引用与历史；真实 smoke 写入 1 条记录 |
| Human correction API | DONE | `POST/GET /multi-frequency-events/{id}/corrections` 支持 `remove_member` / `confirm_member`；复用 HumanCorrection + AuditLog，raw work order 不变；真实 smoke 产生 2 条纠错、3 条审计，成员移除后确认恢复为 2 |
| Cluster detail | DONE | `GET /multi-frequency-events/{id}` 已包含 handling history、human corrections、成员工单、SameEvent evidence 和 AI trace |
| CSV export | DONE | `GET /multi-frequency-events/export.csv?cluster_id=...` 返回 UTF-8 BOM CSV；真实 HTTP 200，Content-Disposition 正确，字段包含 cluster/工单/标题/摘要/主体/地点/AI依据/handling status/result |
| TRAE handoff | DONE | 已移除过期“不得把本地模型改成云 API”规则，改为禁止擅改 Provider routing、写死厂商、绕过 backend、修改 secret 管理；同步更新 PRODUCT_SCOPE/DEVELOPMENT/CHANGELOG/ADR |

### Final closure validation

```text
uv run ruff check backend                  PASS
uv run ruff format --check backend         PASS
uv run pyright backend                     PASS — 0 errors, 0 warnings
uv run pytest -q                           PASS — 29 passed（含 review API、analysis job 合同与 event_type 回归）
uv run alembic upgrade head                PASS — 9c0d1e2f3a4b（本轮不新增表）
real uvicorn review smoke                  PASS — handling=1, corrections=2, audits=3, members restored=2
real CSV export smoke                      PASS — HTTP 200 / text/csv / required header
```

本轮明确没有运行 128,278 条全量 AI、Gold Set/benchmark 或前端页面。当前仍有 `PARTIAL/BLOCKED` 的全量理解、正式质量验收和领域时间边界事项，不能在 TRAE 页面中显示为已完成。远程 API key 曾在聊天中暴露，交接前应在 DashScope 控制台撤销并重新生成；仓库、日志和数据库 trace 不保存 key。

## Bounded AI analysis job HTTP contract (2026-08-15)

| 项目 | 状态 | 实际结果 |
|---|---|---|
| `POST /analysis-jobs` | DONE | 必须传 `import_batch_id` 与 `max_work_orders`；Pydantic/API 硬限制 1–300，queued 后立即返回，不同步等待模型 |
| `GET /analysis-jobs/{job_id}` | DONE | 返回 status、total/selected/processed rows、event/edge/cluster 计数、started/finished、error、provider/model/config/schema/pipeline trace；不含 API key |
| Shared application seam | DONE | `DemoAnalysisOrchestrator` 同时被 HTTP 后台任务与 `scripts/demo_core.py` 调用；底层复用 indexing checkpoint、remote embedding、pgvector、SameEvent 和 EventGraph |
| Real bounded HTTP smoke | DONE | job `362398b6-fecc-4423-aa58-9b5fbc596640`：queued → running → completed；total `128278`、selected/processed `1`、event `1`、edges/clusters `0`（单条样本无配对，结果符合事实）；trace 为 remote `qwen-plus` |
| Job tests | DONE | `pytest` 覆盖创建/查询、必填和上限、失败不伪装 completed、chunk 不越界、完成后 event/edge/cluster 计数合同 |

该 bounded smoke 没有运行全量；现有真实 Demo Core cluster 仍通过多频事件读 API 可查。最大 300 只是 Demo 成本保护，不代表全量 AI 已完成。

### 当前阻塞与手工动作

- `BLOCKED（正式质量验收）`：没有业务确认 Gold Set；Demo edge 仅是可人工审核候选，不得转写成 Recall/Precision/F1。
- `PARTIAL（全量理解/embedding）`：全量远程推理尚未执行；除非另行批准成本、吞吐和隐私边界，不运行全量。
- 远程调用必须保持显式 `SHUNDE_AI_PROVIDER_MODE=remote` 与环境变量 API key。API key 曾在聊天中暴露，使用者应在 DashScope 控制台撤销并重新生成；仓库、日志、数据库 trace 均不保存 key。

## Distinct-WorkOrder 多频语义修复（2026-08-15）

### 修复前真实事实

- PostgreSQL 中存在 cluster `1b018cea-52b7-489d-97ad-7685fb406bb4`：2 个 EventInstance 却只来自 1 个 WorkOrder，被错误展示为多频。
- 存量 match edge 中有 12 条连接同一 WorkOrder 内的事件，其中 4 条为 positive。这些记录保留用于审计，未删除。

### 当前状态

| 项目 | 状态 | 实际结果 |
|---|---|---|
| Domain invariant | DONE | 多频次数锁定为 distinct WorkOrder；一张工单可有多个真实 EventInstance，但不能自己构成多频 |
| Retrieval / matcher / graph | DONE | pgvector query 排除同 WorkOrder；RemoteSameEventMatcher 在 LLM 前拒绝同 WorkOrder 事件对；EventGraphService 不调用 matcher、不保存该类 edge |
| Cluster guard | DONE | builder 忽略同 WorkOrder positive edge，只输出至少 2 个 distinct WorkOrder 的簇；repository 在持久化边界再次拒绝单工单簇 |
| Understanding correction | DONE | prompt 与保守 post-processing 将可唯一归属的部门回复/历史处置/当前请求并入投诉事件上下文；噪音+消防等真实多问题仍保留分开 |
| Catalog API | DONE | `work_order_count` 与 `event_count` 分开；`member_count` 兼容语义为 distinct WorkOrder；详情提供 `work_orders[].events`，旧 event-level `members` 保留 |
| Legacy invalid cluster | DONE | 保留 DB 审计记录，Catalog 列表与详情都不再暴露（列表 total `0`，旧 ID 详情 HTTP 404） |
| Frontend semantics | DONE | 列表分开显示关联工单/AI 事件；详情按 WorkOrder 分组，同一 raw work order 只渲染一次，其下可展示多个 AI 事件 |

### 真实 Demo 回归

```text
uv run python scripts/demo_core.py --anchor-limit 4 --candidate-limit 4
PASS — selected 6 real WorkOrders; positive edges 3; negative edges 3
PASS — new cluster aecafa40-cf77-4dd7-ac86-d66342c77a87
PASS — work_order_count=3; event_count=3; member_count=3
PASS — latest analysis run same-WorkOrder edges=0
PASS — detail grouped_work_orders=3; legacy event members=3
```

该 smoke 是小样本真实云端链路，没有运行 128,278 条全量 AI，没有 Gold Set/benchmark，也没有修改 Provider routing 或模型。

### 本轮代码门禁

```text
uv run pytest -q                             PASS — 36 passed
uv run pyright backend                       PASS — 0 errors, 0 warnings
pnpm --dir frontend lint                     PASS
pnpm --dir frontend build                    PASS
pnpm --dir frontend test --run               PASS — 2 files, 3 tests
scripts/check.ps1                            PASS — backend 36 tests; frontend lint/test/build; ruff/format/pyright all green
```

## Product semantics + Dashboard backend prerequisites（2026-08-15）

| 项目 | 状态 | 真实结果 |
|---|---|---|
| Imported vs analyzed | DONE | Analysis job 回传 `total_rows / selected_rows / processed_rows / selection_mode`；128,278 导入不再被表述为 128,278 AI 已研判 |
| Recurrence selection | DONE | `sequential` 保持兼容；`recurrence_candidates` 仅用确定性复发词/编号引用路由 bounded 工单，不产生 SameEvent |
| Real selection smoke | DONE | `--limit 100`：顺序样本 recurrence=6/reference=9；candidate 样本 recurrence=51/reference=90，实际 source rows 2–777；未调用任何模型 |
| Current pipeline projection | DONE | 真实 DB 修复前 v1=11 events/v2=32 events；WorkOrder 产品详情和 event/cluster counts 只使用当前 `understanding.v2`，历史未删 |
| WorkOrder analysis outcome | DONE | 新增 `work_order_analysis_results`，按 run/work order/pipeline 记录 `analyzed / analyzed_no_event / failed`；无记录明确为 `unprocessed` |
| Entity integrity | DONE | 审计发现 30/30 entity refs 无法 join，影响 26 events；迁移+修复脚本后 orphan refs=0，新写入只接受真实 CanonicalEntity ID |
| Correction undo | DONE | 2-work-order cluster remove 1 后不出现在多频列表，direct detail 返回 `is_multi_frequency=false` 及纠错历史；confirm 后恢复列表 |
| Attachments | DONE | `POST /attachments` 真实 multipart 写入 gitignored runtime，`GET /attachments/{id}` 安全下载；UUID 存储名、文件名安全化、10 MiB 默认上限、响应不暴露绝对路径 |
| WorkOrder cluster refs | DONE | WorkOrder detail 返回当前有效 `cluster_id/name/review_status/handling_status`，可实现真实跳转 |
| Structured filters | DONE | `/work-orders` 增加 `analysis_state / event_type / title_tag`；返回 whitelist `title_tags[]` 与基于原标题的 `is_urgent`，不把括号文字猜成部门 |
| Review status | DONE | EventCluster 新增 `pending_review / confirmed / rejected`；`POST /multi-frequency-events/{id}/review` 写 AuditLog，与 handling status 独立 |
| Occurrence date | DONE | 只解析 time_signals 中明确完整日期；当前 v2 events 32 条中 dated=16/unknown=16，不使用 WorkOrder.created_at |
| Cluster rerun dedup | DONE | 新 cluster 按排序成员集签名；不同 run 保存相同成员集返回原 cluster_id；修复前真实 DB 无重复成员集 |

本轮没有运行 100 条云端 AI；只运行了 100 条确定性候选选择 smoke。没有 Dashboard UI、全量推理、Gold Set、模型比较或新基础设施。

## Demo 研判吞吐修复（2026-08-15）

| 项目 | 状态 | 真实结果 |
|---|---|---|
| Understanding 并发 | DONE | pipeline chunk 不再固定为 4，按 `SHUNDE_MODEL_CONCURRENCY` 执行；当前安全默认 8 |
| Retrieval embedding | DONE | pgvector 查询优先复用事件已持久化的同模型向量，缺失时才调用远程 embedding，避免每个事件重复上云 |
| Candidate / SameEvent | DONE | `EventGraphService` 对候选检索和 SameEvent 使用有界并发；候选上限、去重、hard contradiction 和模型判断语义均未改变 |
| 回归门禁 | DONE | 并发测试先复现串行失败后通过；pgvector contract 确认已存向量时远程 embedding 调用数为 0；Ruff/format/Pyright/Pytest 通过（42 tests） |
| 验收库 | DONE | 操作者要求重跑后已清空当前 100 条批次及其 job/event/embedding/cluster；数据库结构、地名快照和原始 Excel 保留 |

本次修复不声称固定倍数：实际吞吐仍受 Qwen API 延迟和限流影响；遇到 429 时通过 `SHUNDE_MODEL_CONCURRENCY=4` 降低并发，不得静默回退本地或改用 mock。

安全派生数据 repair 已为存量 event 回填可审计 outcome：`understanding.v1` 11 work orders/11 events，`understanding.v2` 25 work orders/32 events。无 event 的历史工单无法从 event 反推，仍保持 `unprocessed`，不伪造 `analyzed_no_event`。

### 本轮门禁

```text
uv run alembic upgrade head                  PASS — ad1e2f3a4b5c
scripts/check.ps1                            PASS
uv run pytest -q                             PASS — 41 passed
uv run pyright backend                       PASS — 0 errors, 0 warnings
pnpm --dir frontend test --run               PASS — 5 files, 28 tests
pnpm --dir frontend lint                     PASS
pnpm --dir frontend build                    PASS — Vite 8.2.1
selection_smoke.py --limit 100               PASS — deterministic only, no AI
repair_event_semantics.py                    PASS — orphan refs=0, v2 dated/unknown=16/16
```
