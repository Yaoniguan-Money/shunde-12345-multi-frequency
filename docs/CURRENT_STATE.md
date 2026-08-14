# CURRENT_STATE.md

更新日期：2026-08-15（Asia/Shanghai）

状态只允许：`DONE / PARTIAL / BLOCKED / PLANNED`。本文件区分已经实测的 shipped state 与后续目标，不以骨架冒充业务功能。

## Git

- Branch：`main`
- 基线 checkpoint：`c28398513bb476f2f42b199089ee13ae19618b4f`
- Phase 1 commit：`382588f70617fa368c48df4a17815e7ba27c84d3`
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

- Container：`shunde-12345-postgres-1`（当前 Docker Desktop 未启动，运行态验证暂时 BLOCKED）
- PostgreSQL：`17.8`
- pgvector extension：`0.8.1`
- Port：`127.0.0.1:5432`
- Alembic revision：`fff93032eb16` → `6b7c8d9e0f10`（待 Docker 恢复后 upgrade 验证）
- 表：18 张要求的业务骨架表 + `alembic_version`，共 19 张 public tables。
- 已在空开发库实测 `alembic downgrade base` → `alembic upgrade head` 成功。
- Docker Hub 曾出现 TLS handshake timeout；随后通过 DaoCloud 的 Docker Hub 镜像代理拉取同名 tag，digest 为 `sha256:3e8b3adfd27b5707128f60956f62a793c3c9326ea8cfaf0eab7adccb5d700b21`。

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| 0 factual inspection | DONE | Excel、地名包/OpenAPI、硬件、WSL2、Docker、工具链均已只读实测 |
| 1 repo hardening | DONE | Git checkpoint、uv/pnpm lock、FastAPI、React 19 + Vite 8、PostgreSQL + pgvector、Alembic、CI、health、typed ports、18 表骨架 |
| 2 import | PARTIAL | Polars + fastexcel 真实 reader、字段映射、坏行继续、SHA 幂等、checkpoint、失败行表与 `/imports` API 已完成；8 个应用/知识库单测通过；真实 PostgreSQL 迁移/12.8 万行入库被 Docker Desktop 未启动阻塞 |
| 3 gazetteer | PARTIAL | 已从真实 SQLite 构建 229 实体运行时快照，真实 `/openapi.json` 发现 `/batch` 并实测凤城/人民医院/未知地点；`/entities/resolve` 已接入；服务/快照 smoke 通过 |
| 4 AI structured understanding | PARTIAL | LLM/Embedding/Reranker 等 typed ports 已存在，新增 WorkOrderUnderstanding Pydantic schema；本地模型未配置，未运行 LLM |
| 5 retrieval/rerank | PLANNED | 无 Gold Set benchmark，不报告质量数字 |
| 6 event matching/clustering | PLANNED | 只有 interface/schema skeleton，无生产 matcher |
| 7 product loop | PLANNED | 前端仅工程/health 骨架，不是四页业务产品 |
| 8 benchmark/handoff | PLANNED | 未运行 1k/10k/full benchmark |

## Shipped Phase 1 interfaces

- Core ports：`GazetteerProvider`、`LLMProvider`、`EmbeddingProvider`、`RerankerProvider`、`CandidateRetriever`、`SameEventMatcher`、`ClusterConsistencyChecker`、`WorkOrderRepository`、`EventRepository`、`JobRepository`、`Exporter`。
- Production fake implementations：无。测试 fake 仅位于 `backend/tests`。
- Health：
  - `GET /health/live` → process alive
  - `GET /health/ready` → 真实数据库 readiness，失败返回 HTTP 503
  - `GET /health/dependencies` → database / gazetteer / local model 的真实或明确未配置状态
- 实测运行态：database `up`、gazetteer `up` version `1.0`、local model `not_configured`。

## Validation evidence

2026-08-15 实际执行：

```text
uv sync --locked                         PASS
uv run ruff check .                      PASS — All checks passed
uv run ruff format --check .             PASS — 43 files already formatted
uv run pyright backend                   PASS — 0 errors, 0 warnings
uv run pytest -q                         PASS — 8 passed, 1 skipped（PostgreSQL raw immutability integration test；Docker 未启动）
pnpm install --frozen-lockfile           PASS
pnpm lint                                PASS
pnpm test --run                          PASS — 1 test file / 1 test passed
pnpm build                               PASS — Vite 8.2.1, 64 modules transformed
docker compose config --quiet            PASS
alembic downgrade base / upgrade head    PASS
GET /health/live                         PASS — alive
GET /health/ready                        PASS — PostgreSQL up
GET /health/dependencies                 PASS — DB/gazetteer up; model not_configured
GET gazetteer /normalize?text=凤城        PASS — 大良街道 / 0.98
uv run python scripts/gazetteer_smoke.py PASS — OpenAPI 1.0；快照 229 entities；凤城 resolved；未知地点 unresolved
uv run ruff check .                      PASS — 本轮导入/知识库/AI schema 后
uv run pyright backend                   PASS — 0 errors, 0 warnings
uv run pytest -q                         PASS — 8 passed
docker compose up -d postgres            BLOCKED — Docker API npipe 不存在，Docker Desktop 未运行
uv run alembic upgrade head              BLOCKED — PostgreSQL 连接被拒绝（同一 Docker blocker）
uv run python scripts/import_real_smoke.py BLOCKED — 必须先完成数据库迁移；命令已写入 docs/DEVELOPMENT.md
```

## Known blockers / decisions needed later

- `BLOCKED`（Phase 4 acceptance）：尚未选择、部署并验证真实本地模型；Phase 1 不要求模型 inference。
- `BLOCKED`（Phase 2 runtime acceptance）：Docker Desktop 当前未启动；PostgreSQL 迁移、raw immutability trigger 与政府 Excel 真实入库待用户启动 Docker 后执行。
- `BLOCKED`（quality acceptance）：尚无业务方确认的 Gold Set、3–5 组官方同事件正例与 hard negatives。
- `BLOCKED`（domain decision）：同一持续事件与复发事件的时间边界未确认。
- `BLOCKED`（delete behavior）：软删除、硬删除或 audit tombstone 规则未由业务方确认。
- `BLOCKED`（Care Signal）：是否存在稳定匿名诉求人 ID 未确认；不得实现个人级 Care Signal。
