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
