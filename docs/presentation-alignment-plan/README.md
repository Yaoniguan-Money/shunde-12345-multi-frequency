# 演讲稿对齐总升级计划：阅读入口

> 文档状态：待实施，不代表功能已经完成  
> 编写日期：2026-08-16  
> 目标：让真实产品能力自然对齐演讲稿，不使用案例硬编码、静态结果或静默降级

## 1. 为什么拆成这个文件夹

原总计划超过一千行，不利于多个 Agent 按职责读取和实施。本目录把同一份目标拆成“锁定决策 + 专项合同 + 工作包 + 验收”，每个执行 Agent 只需要读取公共入口和自己负责的文件。

旧入口 `docs/PRESENTATION_ALIGNMENT_OPTIMIZATION_PLAN.md` 仅保留跳转说明。本目录是本轮优化计划的唯一正文。

## 2. Agent 最小阅读规则

任何 Agent 开始工作前必须先读：

1. 本文件；
2. [00-LOCKED-DECISIONS.md](00-LOCKED-DECISIONS.md)；
3. 下表中与自己工作包对应的专项文件；
4. [10-NO-DEGRADATION-AND-DOD.md](10-NO-DEGRADATION-AND-DOD.md) 中的完成条件。

| 责任范围 | 必读文件 |
|---|---|
| 附录 A、分类代码、类型筛选 | [01-DB44-TAXONOMY.md](01-DB44-TAXONOMY.md) |
| 数据库、时间、版本、审计 | [02-DOMAIN-DATA-TIME.md](02-DOMAIN-DATA-TIME.md) |
| 工单理解、事项拆分、标准分类 | [03-UNDERSTANDING-CLASSIFICATION.md](03-UNDERSTANDING-CLASSIFICATION.md) |
| 本地/云端模型、任务切换、速度 | [04-PROVIDER-TASK-PERFORMANCE.md](04-PROVIDER-TASK-PERFORMANCE.md) |
| 同事件、聚类、三天三单 | [05-SAME-EVENT-FREQUENCY.md](05-SAME-EVENT-FREQUENCY.md) |
| API、统计、筛选、投影 | [06-API-PROJECTIONS.md](06-API-PROJECTIONS.md) |
| 页面删改与现场 Demo 流程 | [07-FRONTEND-UX.md](07-FRONTEND-UX.md) |
| 分阶段实施与文件落点 | [08-IMPLEMENTATION-WORK-PACKAGES.md](08-IMPLEMENTATION-WORK-PACKAGES.md) |
| 自动化测试、Gold Set、真实回放 | [09-TESTS-ACCEPTANCE.md](09-TESTS-ACCEPTANCE.md) |

总协调 Agent 才需要把整个目录一次读完。专项 Agent 不得脱离锁定决策自行改口径。

## 3. 计划文件清单

- `00-LOCKED-DECISIONS.md`：不可妥协的产品口径。
- `01-DB44-TAXONOMY.md`：DB44/T 2479—2024 附录 A 全量分类方案。
- `02-DOMAIN-DATA-TIME.md`：Work Order、AI 事项、受理时间、版本和迁移。
- `03-UNDERSTANDING-CLASSIFICATION.md`：当前投诉分段、对象抽取和标准分类。
- `04-PROVIDER-TASK-PERFORMANCE.md`：任务前模型切换、本地真实链路、云端提速。
- `05-SAME-EVENT-FREQUENCY.md`：候选召回、同事件判断、聚类和高频规则。
- `06-API-PROJECTIONS.md`：接口、全量统计、分类 facets 和数字口径。
- `07-FRONTEND-UX.md`：前端页面最终规格。
- `08-IMPLEMENTATION-WORK-PACKAGES.md`：推荐实施顺序、依赖和代码位置。
- `09-TESTS-ACCEPTANCE.md`：测试矩阵、Demo Gold Set 和性能验收。
- `10-NO-DEGRADATION-AND-DOD.md`：禁止做法与最终完成定义。
- `reference/`：从标准 PDF 核出的机器可读目录及校验记录。

## 4. 本轮最重要的统一口径

- 成功导入多少张工单，就研判多少张；产品层没有 50、100、300 的截断上限。
- 本地模型和云端模型在每次任务开始前可选；任务开始后锁定该任务的 Provider Profile。
- 本地模型必须走真实 LLM、Embedding、结构化输出和最小完整研判链路，不能只做 ping。
- 云端当前显示“千问，已适配”，业务层不得绑定厂商。
- 诉求事项分类完整采用 DB44/T 2479—2024 附录 A；有来源代码时确定性映射，无来源代码时 AI 只能从标准目录选择。
- 一张 Work Order 可以拆出多个 AI 研判事项，因此 100 张工单产生 103 个事项是合法结果。
- 高频判定锁定为：同一事件在任意连续 3 个自然日内达到 3 张及以上不同工单。
- 只设置“高频 / 未达到高频门槛 / 时间证据不足”，不存在“低频事件”标签。
- 美涂士五张欠薪工单是通用能力的正向验收；三个“美的”是负向验收。生产代码不得读取案例名称或工单号做特判。

## 5. 标准附件与机器可读资源

标准附件：`DB44_T+2479-2024(1).pdf`  
PDF SHA-256：`7EE0C304308C9B65DD626D7DF2442CEDE4A89615B40C193EDDC5E9AF2A7535FC`

附录 A 已核成：

- 14 个一级分类；
- 99 个二级分类；
- 515 条三级记录；
- 514 个不同的印刷三级代码；
- 原文唯一重码为 `090499`，必须用内部 `node_id + 完整父路径` 区分。

完整目录见 [reference/db44t2479-2024-appendix-a.csv](reference/db44t2479-2024-appendix-a.csv)，校验说明见 [reference/APPENDIX-A-VALIDATION.md](reference/APPENDIX-A-VALIDATION.md)。

## 6. 变更边界

本目录只重写实施计划和验收合同，没有执行任何前后端业务代码修改。实施时必须按工作包逐阶段改造、迁移、测试和记录真实结果，不能把计划中的目标状态提前写成 `DONE`。
