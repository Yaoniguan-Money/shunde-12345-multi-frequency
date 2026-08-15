# TRAE_CHANGELOG.md

TRAE appends entries; do not rewrite history.

## 2026-08-15 — Demo Core read contracts

- 改动目标：为真实 cloud-first Demo Core 提供只读工单、事件和多频事件列表/详情接口。
- 修改文件：`backend/app/api/catalog.py`、`backend/app/schemas/catalog.py`、`backend/app/application/services/catalog.py`、`backend/app/infrastructure/db/catalog.py`、`docs/TRAE_HANDOFF.md`。
- API 变更：新增 `GET /work-orders`、`GET /work-orders/{id}`、`GET /events`、`GET /events/{id}`、`GET /multi-frequency-events`、`GET /multi-frequency-events/{id}`。详情保留原始工单与 v2 evidence/trace；列表使用 `items/offset/limit/total`。
- 本地验证：真实 uvicorn smoke 调用六个端点均 HTTP 200；`uv run pytest -q` 通过。
- 已知问题：当前接口展示的是小样本 Demo Core；全量 128,278 条 AI 理解和正式 Gold Set 仍未完成。
