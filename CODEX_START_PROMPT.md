# CODEX_START_PROMPT.md

你现在负责这个项目的“硬装”。先完整阅读根 `AGENTS.md`、`docs/PRODUCT_SCOPE.md`、`docs/ARCHITECTURE.md`、本施工总纲，再开始。

不要一上来写 UI，也不要直接跑全量 LLM。

第一轮只做 Phase 0 + Phase 1：
1. 检查真实政府 Excel 字段/行数/sheet/大小/空值，不修改原文件。
2. 检查 `C:\Users\Lenovo\Desktop\顺德地名库交接包`，读 README，启动 `地名服务`，读取真实 OpenAPI，禁止猜 endpoint。
3. 检查 GPU/VRAM、CUDA、WSL2、Docker、uv、Node、Git、gh auth。
4. 初始化/确认 Git repo，先建立可回滚 checkpoint。
5. 建立 monorepo、FastAPI、React+Vite 8、PostgreSQL+pgvector、Alembic、tests、CI、health endpoints。
6. 建立所有核心 port/interface 和空数据库模型骨架，但不要用 fake implementation 冒充后续功能完成。
7. 更新 `docs/CURRENT_STATE.md`，逐项写 DONE/PARTIAL/BLOCKED、实际命令和结果。
8. 所有检查通过后 commit；GitHub 可用则 push，不可用则明确 REMOTE_PENDING。

完成 Phase 1 后先汇报：真实环境事实、仓库 commit、测试结果、阻塞项、下一阶段计划。不要擅自继续把后面所有功能一次写烂。
