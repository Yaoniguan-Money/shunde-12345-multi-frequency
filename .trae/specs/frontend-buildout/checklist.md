# 前端完整硬装 Checklist

## GSAP Skill 安装与可读

- [ ] greensock/gsap-skills 已通过 `npx skills@latest add greensock/gsap-skills --yes` 安装
- [ ] `.agents/skills/gsap-*/SKILL.md` 8 个 skill 文件存在且 TRAE 环境可读取
- [ ] 已读取 gsap-core、gsap-react、gsap-timeline SKILL.md 了解规范

## 信息架构与全局 Shell

- [ ] App.tsx 为工作台 shell（左侧一级导航仅三项：多频事件 / 工单中心 / 数据导入与AI研判 + 顶部全局状态条 + 主内容区）
- [ ] 事件详情不作为一级导航项，通过多频事件列表进入
- [ ] React Router 已引入，真实 URL（/events、/events/:clusterId、/work-orders、/work-orders/:workOrderId、/imports）
- [ ] / 重定向到 /events
- [ ] 工单与事件详情 URL 可分享/刷新
- [ ] styles.css 为 AI 研判工作台设计系统（白色/浅色背景、信息层级、状态色统一）
- [ ] 顶部状态条接入 /health/live 与 /health/dependencies
- [ ] 后端离线时顶部显示"后端未连接"，不假装在线
- [ ] 左侧导航高亮当前页

## Typed API 客户端层

- [ ] client.ts 统一 fetch wrapper（baseURL、error handling、AbortSignal）
- [ ] health.ts 覆盖 live/ready/dependencies
- [ ] imports.ts 覆盖 preview + import（multipart）
- [ ] catalog.ts 覆盖 work-orders / events / multi-frequency-events 列表与详情
- [ ] analysis.ts 覆盖 POST /analysis-jobs 与 GET /analysis-jobs/{job_id}
- [ ] review.ts 覆盖 handling-records、corrections、CSV 导出
- [ ] types/ 与后端 schema 对齐，禁止 any，nullable 字段一致
- [ ] 生产路径无 mock 数据

## 通用交互组件

- [ ] StatusBadge（queued/running/completed/failed + handling_status 独立色系）
- [ ] Skeleton（列表/详情骨架）
- [ ] EmptyState（含引导文案）
- [ ] ErrorState（含 HTTP 状态码 + detail）
- [ ] Toast + useToast（成功/失败反馈）
- [ ] ConfirmDialog（高风险操作确认）
- [ ] Pagination（offset/limit 分页）
- [ ] SearchInput（min_length/max_length 校验）
- [ ] LongText（展开/收起）
- [ ] TraceTag（provider/model 标签）

## 多频事件列表（产品视觉主角，第一印象）

- [ ] 调用 GET /multi-frequency-events?offset=0&limit=20
- [ ] 展示 cluster_id、name、status、confidence、handling_status、member_count、evidence 摘要、trace
- [ ] 卡片化布局（视觉主角是"民生事件"，不是普通 CRUD 表格）
- [ ] 每个卡片让用户一眼看懂"发生了什么"
- [ ] 分页
- [ ] 本地筛选/排序仅作用于当前已加载结果，UI 明确表现为"筛选当前页"，不伪装成全局搜索（后端列表 API 不支持 search query）
- [ ] confidence 不单独作为结论，配合 evidence
- [ ] empty state（total=0 引导发起 AI 研判）
- [ ] 点击 event 跳转 /events/:clusterId
- [ ] 真实接通后端验证此页（不允许最后统一接接口）

## 事件详情 / 研判（最重要页面）

- [ ] 调用 GET /multi-frequency-events/{cluster_id}
- [ ] 事件概要区（summary 全字段）
- [ ] 关联工单区（members：EventDetail）
- [ ] 原始工单 vs AI 派生视觉分区
- [ ] AI 判断依据区：edges + evidence 展开（主体/地点/事件/时间/冲突）
- [ ] 不只显示"相似度 92%"
- [ ] AI evidence 有明显但克制的视觉区分
- [ ] 人工纠错：remove_member / confirm_member（后端真实支持的）
- [ ] remove_member 高风险操作 ConfirmDialog
- [ ] 纠错后刷新 cluster detail
- [ ] 不展示后端不支持的 merge/split
- [ ] 业务处理：当前 handling_status + 添加处理记录表单 + handling_history
- [ ] 业务处理状态与 AI 判断状态、人工纠错状态视觉明确区分
- [ ] 审计历史：human_corrections 全字段展示
- [ ] CSV 导出：GET /multi-frequency-events/export.csv?cluster_id= 触发下载
- [ ] CSV 导出失败时不假装成功
- [ ] 真实接通后端验证此页及纠错/处理/导出流程

## 工单中心

- [ ] 列表调用 GET /work-orders?offset=0&limit=20&query=
- [ ] 展示 work_order_id、external_work_order_number、source_row_number、raw_title、created_at、event_count、cluster_count
- [ ] 分页 + 搜索（query min_length=1, max_length=128）
- [ ] 展示 total 总数
- [ ] 详情调用 GET /work-orders/{work_order_id}（URL /work-orders/:workOrderId）
- [ ] 展示 summary（import_batch_id、raw_content、raw_fields）
- [ ] 展示 events 列表全字段
- [ ] 原始工单 vs AI 派生视觉明显分区
- [ ] AI 派生字段带 TraceTag
- [ ] 真实接通后端验证

## 数据导入与AI研判

- [ ] 文件选择（Excel/CSV）
- [ ] 调用 POST /imports/preview（multipart）展示 columns、total_rows、suggested_mapping
- [ ] 用户可调整列映射
- [ ] 调用 POST /imports（multipart + mapping JSON）
- [ ] 展示 batch_id、status、total_rows、successful_rows、failed_rows、duplicate_rows、checkpoint_row、idempotent
- [ ] idempotent=true 明确提示
- [ ] 导入完成后展示"发起 AI 研判"
- [ ] max_work_orders 前端硬限制 1–300（无"默认全量"按钮）
- [ ] 调用 POST /analysis-jobs，body 含 import_batch_id 与 max_work_orders
- [ ] HTTP 202 成功后进入轮询
- [ ] 每 2–3 秒轮询 GET /analysis-jobs/{job_id}
- [ ] 真实展示 queued → running → completed | failed
- [ ] 展示 total_rows、selected_rows、processed_rows、event_count、match_edge_count、cluster_count
- [ ] completed 展示 trace
- [ ] failed 展示 error 原文，不伪装成功
- [ ] 提供"重试"操作（新建 job）
- [ ] 用户不需要手动刷新
- [ ] 真实接通后端验证轮询

## GSAP 动效（克制使用，视觉收益明确时才用）

- [ ] @gsap/react useGSAP hook 已安装并注册
- [ ] 适合 GSAP 的场景（SHOULD 用）：页面层级进入/退出、分析任务状态阶段变化、Evidence 展开、数字更新、列表 stagger、Dialog/drawer
- [ ] 简单状态变化（MAY 用 CSS transition）：status badge 颜色变化等，不必强制 GSAP；failed 红色高亮淡入
- [ ] 列表→详情切换动效（详情区从右淡入/滑入，返回反向）
- [ ] 任务进度数字变化动效（count up / 高亮闪现）
- [ ] 路由切换页面过渡动效
- [ ] 遵守 prefers-reduced-motion（reduced-motion 时 duration=0 或跳过）
- [ ] useGSAP + scope + cleanup，避免泄漏
- [ ] 不用动效掩盖 loading/error
- [ ] 不做满屏炫技效果
- [ ] 不为证明装了 GSAP 对每个元素都套 gsap.timeline

## 边界与诚信

- [ ] 不修改后端 API、数据库、domain schema、pipeline
- [ ] 不用 mock 数据伪装功能完成
- [ ] 所有页面调用真实后端接口
- [ ] 后端不存在的能力（merge/split、Gold Set、全量推理、benchmark 质量指标）前端不假装实现
- [ ] AI 判断状态、人工纠错状态、事件业务处理状态明确区分
- [ ] queued/running/completed/failed 真实状态完整展示
- [ ] partial/failed/ambiguous/unresolved 原样呈现，不视觉抹平
- [ ] confidence 与 embedding 分数不单独渲染成事实结论
- [ ] 发现 API 不够支持某 UI 时记录问题，不自行修改后端
- [ ] 每完成一个阶段都接真实 API 验证，不允许最后统一接接口

## 视觉规范

- [ ] 白色/浅色背景，非传统蓝色渐变政务大屏
- [ ] 视觉主角是"民生事件"，不是 KPI 数字大屏，不是普通 CRUD 表格
- [ ] 信息层级明确
- [ ] 较强的表格与详情阅读体验
- [ ] AI evidence 有明显但克制的视觉区分
- [ ] 原始工单 vs AI 派生分区
- [ ] 状态色统一
- [ ] 高风险操作有确认（remove_member、删除等；不出现"全量研判"按钮，max_work_orders 硬限制 1–300）
- [ ] 适配 1920×1080 路演屏幕
- [ ] 整体感觉是"工作人员真的可以每天用的系统"

## 施工顺序

- [ ] 核心展示链优先：Shell → 多频事件列表 → 事件详情
- [ ] 工单中心随后补
- [ ] 数据导入与AI研判随后补
- [ ] GSAP 动效在真实功能之上做全局打磨
- [ ] 验证与收尾最后

## 验证

- [ ] pnpm install --frozen-lockfile PASS
- [ ] pnpm lint PASS
- [ ] pnpm test --run PASS
- [ ] pnpm build PASS
- [ ] 手动连通真实后端跑通主闭环：导入 → 研判 → 多频事件 → 事件详情 → 纠错 → 处理 → 导出
- [ ] docs/TRAE_CHANGELOG.md 已更新
- [ ] 任何 API 缺口已记录，未自行修改后端
