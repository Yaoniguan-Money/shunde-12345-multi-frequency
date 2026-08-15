# 演讲稿对齐总升级计划

> 本文件已拆分为专项计划目录，避免单个 Agent 一次读取超长文档。  
> 文档状态：待实施，不代表其中功能已经完成。

正文入口：

- [总索引与 Agent 阅读规则](presentation-alignment-plan/README.md)
- [锁定产品决策](presentation-alignment-plan/00-LOCKED-DECISIONS.md)
- [DB44/T 2479—2024 附录 A 全量分类方案](presentation-alignment-plan/01-DB44-TAXONOMY.md)
- [领域模型、数据与时间](presentation-alignment-plan/02-DOMAIN-DATA-TIME.md)
- [工单理解与标准分类](presentation-alignment-plan/03-UNDERSTANDING-CLASSIFICATION.md)
- [模型切换、本地链路与性能](presentation-alignment-plan/04-PROVIDER-TASK-PERFORMANCE.md)
- [同事件、聚类与三天三单](presentation-alignment-plan/05-SAME-EVENT-FREQUENCY.md)
- [API、统计与筛选](presentation-alignment-plan/06-API-PROJECTIONS.md)
- [前端页面规格](presentation-alignment-plan/07-FRONTEND-UX.md)
- [实施工作包](presentation-alignment-plan/08-IMPLEMENTATION-WORK-PACKAGES.md)
- [测试与验收](presentation-alignment-plan/09-TESTS-ACCEPTANCE.md)
- [禁止降级与完成定义](presentation-alignment-plan/10-NO-DEGRADATION-AND-DOD.md)

附录 A 的 515 条机器可读记录位于：

- [db44t2479-2024-appendix-a.csv](presentation-alignment-plan/reference/db44t2479-2024-appendix-a.csv)
- [提取与校验记录](presentation-alignment-plan/reference/APPENDIX-A-VALIDATION.md)

任何执行 Agent 都必须先读总索引和锁定决策，再读取自己负责的专项文件；不得绕过锁定决策自行改变分类、高频、模型切换或不降级口径。
