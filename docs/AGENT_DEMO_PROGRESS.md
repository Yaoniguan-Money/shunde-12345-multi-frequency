# 12345 自然语言研判 Agent — Demo 进度

更新日期：2026-08-19（Asia/Shanghai）

## 已完成

- `agent-demo-v2` 已从稳定 V2 commit `6e2150e24457c6d59b6c380f589e4f64660b8884` 创建；V3/frontend-redesign 未跟踪文件未被删除、覆盖或纳入提交。
- V2 只读 baseline smoke 通过：数据库返回 100 张真实工单、205 个 V2 `EventInstance`、6 个多频簇；金域滨江一期艾灸馆簇仍在。
- 新增受控 `AgentQueryDSL`，LLM 只可返回意图和筛选槽位，后端只编译固定 SQLAlchemy 查询，绝不执行 LLM SQL。
- Hybrid Retrieval 已组合工单结构化字段、原始标题/正文、V2 `normalized_summary` / 事件类型 / 地点、簇关联，且在已有 embedding 模型可用时复用 pgvector 语义候选。`location` / `entity` / 工单 ID / 办理状态 / 时间是硬 scope；存在任一条件时，向量检索只在该 scope 内排序，绝不以全库语义候选补足。
- 地点按开放文本处理，不依赖顺德地点枚举；每张地点查询结果都必须有原文或 V2 `location_signals` 证据。`retrieval_evidence` 明确标注地点命中、原文命中、V2地点信号命中和语义相关。
- `/agent/query` 返回真实工单、检索依据、V2 多频簇链接、可核查统计与“群众投诉不等于行政认定”提示。最终 Top-N 还会交给 DeepSeek 生成带“AI研判 / AI推测 / AI建议”边界的摘要，真实工单卡和链接始终保留。
- Workset 已落库，含原始问题、DSL 快照、工单/簇 ID、创建人和审计；不是浏览器内存状态。
- 批量操作为 Preview → Confirm → Execute → `AuditLog`，对 WorkOrder 追加独立不可变 `WorkOrderHandlingRecord`，不改原文和 V2 研判结果；CSV 导出同样需要确认。
- 执行预览必须属于 URL 指定的 Workset，不能使用另一个 Workset 的 preview ID 跨范围执行。
- 动态看板只按当前查询/Workset 范围的真实工单统计问题、地点、处理状态和关联多频簇。
- `/assistant` 已成为一级业务页面，支持上下文追问、工单/多频事件详情跳转、工作集、批量确认与临时看板。
- 当前查询区域已升级为“当前查询洞察”：真实问题/地点横向条形图、状态环图、核心数字、确定事实优先级和工单关系树均由同一查询范围 API 驱动，图表与关系节点可下钻到工单卡片。
- 工作集不再是窄抽屉：`GET /worksets` 恢复最近工作集，`GET /worksets/{id}/workspace` 恢复持久化成员和实时状态统计；页面提供全宽“当前分析 / 工作集”研判工作区。
- 看板新增 `urgent_count`，它仅统计后端 `is_urgent` 的确定性标题标签，不创建风险分数或预测。

## 本地数据边界

- 为避免当前 V3 数据库迁移污染稳定 Demo，运行时使用本地可丢弃副本 `shunde_agent_demo_v2`；其创建时只复制了现有 V2 真实演示数据（100 张工单），源库 `shunde` 未回迁、未降级、未改写。
- Agent migration：`e4f5a6b7c8d9_add_agent_worksets.py`，只创建 Agent 自有表；不修改 V2 事件、候选、SameEvent edge、cluster 或原始工单表字段。

## 已验证

```text
V2 GET /health/ready                         PASS
V2 GET /work-orders?limit=3                 PASS — 真实工单
V2 GET /multi-frequency-events?limit=3      PASS — 含金域滨江 V2 簇
POST /agent/query                            PASS — 真实工程款相关工单和 V2 证据
DeepSeek Agent Planner                       PASS — `planner_mode=llm`、3 条真实工单；复用用户级 `SHUNDE_AI_DEEPSEEK_*` 配置
POST /worksets                               PASS — 真实创建 5 条工作集
POST /worksets/{id}/actions/preview          PASS
POST /worksets/{id}/actions/execute          PASS — 5 条、AuditLog action
POST /agent/dashboard                        PASS — 按工作集真实统计
浏览器 /assistant 主场景                     PASS
GET /worksets                                PASS — 最近工作集恢复列表
GET /worksets/{id}/workspace                 PASS — 持久化成员和实时统计
POST /agent/dashboard（容桂范围）             PASS — 20 条工单、4 个多频事件、4 个急单
浏览器 /assistant V3 视觉检查                PASS — 1440 图表/关系树/工作集；1280 无横向溢出
uv run pytest -q test_agent_query_planner + test_event_graph
                                               PASS — 13 passed
pnpm --dir frontend lint && build            PASS
pnpm --dir frontend test --run               PASS — 8 files / 34 tests
uv run ruff check .                          PASS
uv run ruff format --check .                 PASS
uv run pyright backend                       PASS — 0 errors
Agent Alembic current                         PASS — e4f5a6b7c8d9 (head)
Agent follow-up “只看还没处理的”              PASS — 在上一轮真实范围内筛选
Agent AuditLog                                PASS — 1 条 batch action 审计记录
地点 hard-scope：美的大道最近有什么？          PASS — 1 条；每条具地点、原文或 V2地点信号证据
地点 hard-scope：金域滨江最近有什么？          PASS — 10 条；没有无地点证据的混入结果
无地点 topic：最近有什么工程款拖欠？           PASS — location=null、10 条、全库语义相关证据可用
DeepSeek Analysis Composer                    PASS — 真实地点结果含 AI研判、AI推测、AI建议标签
```

## 尚未完成 / 运行说明

- Agent 同时兼容 `SHUNDE_AGENT_DEEPSEEK_*`、现有用户级 `SHUNDE_AI_DEEPSEEK_*` 和通用 `DEEPSEEK_*` 配置。2026-08-19 已以现有用户级配置完成真实 DeepSeek 结构化规划 smoke；短暂不可用时会记录不含工单原文和密钥的结构化告警，并明确回退 `planner_mode=rules`。V2 embedding 仍使用原有配置，不会被替换。
- Demo 启动时需要将后端数据库定向到隔离副本：`$env:SHUNDE_DATABASE_URL='postgresql+asyncpg://shunde:shunde@127.0.0.1:5432/shunde_agent_demo_v2'`，然后运行 `uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8080`；前端使用 `VITE_API_BASE_URL=http://127.0.0.1:8080 pnpm --dir frontend dev`。
