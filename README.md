# 顺德 12345 多频工单智能研判

本仓库当前完成 Phase 0（真实现场核验）与 Phase 1（repository hardening）。它不是通用 RAG，也没有把后续导入、实体归一、同事件判断或本地模型能力伪装成已完成。

## 当前已完成

- Python 3.12 + uv lockfile
- FastAPI thin routes / application handler / typed port seams
- React 19 + TypeScript + Vite 8 工程骨架
- PostgreSQL 17 + pgvector 0.8.1 Docker Compose
- 18 张核心数据库模型骨架与可回滚 Alembic migration
- `/health/live`、`/health/ready`、`/health/dependencies`
- pytest、Vitest、ESLint、Ruff、Pyright、GitHub Actions CI
- 真实 Excel、地名服务 OpenAPI 与本机环境检查记录

完整 shipped state 与阻塞项见 `docs/CURRENT_STATE.md`。

## 启动

前置条件：Docker Desktop 已运行、Python 3.12、uv、Node 24、pnpm。

```powershell
./scripts/bootstrap.ps1
./scripts/start.ps1
```

启动后：

- Backend OpenAPI：`http://127.0.0.1:8080/docs`
- Frontend：`http://127.0.0.1:5173`
- Readiness：`http://127.0.0.1:8080/health/ready`

地名服务是独立交接包，Phase 0 启动方式与真实 paths 见 `docs/LOCAL_KNOWLEDGE_BASE.md`。

## 验证

```powershell
./scripts/check.ps1
```

## 数据隐私

- 原始政务 Excel 不进入 Git。
- `.env`、模型权重、运行缓存和数据库文件均被忽略。
- routine logs 不得记录工单正文。
- 默认无云模型调用、无外部 telemetry。

开始改动前必须阅读根 `AGENTS.md`、`docs/PRODUCT_SCOPE.md`、`docs/ARCHITECTURE.md` 与施工总纲。
