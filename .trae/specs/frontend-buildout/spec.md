# 前端完整硬装 Spec

## Why

后端基线 `173fbf6` 已冻结，真实 API 已完整提供导入、工单、事件、多频事件、研判纠错、处理记录、CSV 导出与 bounded 分析任务全链路。但当前前端仅是 Phase 1 工程骨架（`App.tsx` 只调一个 `/health/live`），不是可路演的 12345 多频工单研判产品。需要在不修改任何后端契约的前提下，把这个项目做成完整、可操作、可路演的 12345 多频工单智能研判前端，**视觉主角必须是"民生事件"**，不是 KPI 大屏或普通 CRUD 后台。

## What Changes

- 新增前端信息架构：左侧一级导航（仅三项：多频事件 / 工单中心 / 数据导入与AI研判）+ 顶部全局状态条 + 主内容区。事件详情通过列表进入，不作为一级导航项。
- 新增 React Router（真实 URL，工单与事件详情可分享/刷新）。
- 新增四个核心页面：
  1. **数据导入与AI研判**：上传 Excel/CSV → 预览 → 导入 → 触发 AI 研判 → 任务轮询。
  2. **工单中心**：工单列表（搜索/分页）+ 工单详情（原始工单 vs AI 派生结果分区）。
  3. **多频事件**：事件列表（搜索/筛选/排序），产品主工作台。
  4. **事件详情/研判**：事件概要 + 关联工单 + AI 判断依据 + 人工纠错（remove/confirm member）+ 业务处理（handling records）+ 审计历史 + CSV 导出。
- 新增前端 API 客户端层：基于真实后端契约的 typed fetch 客户端，禁止 mock 数据进入生产路径。
- 新增轮询机制：`POST /analysis-jobs` 创建后自动轮询 `GET /analysis-jobs/{job_id}`，真实展示 `queued → running → completed | failed`，失败不伪装成功。
- 新增状态视觉系统：统一 status badge、AI evidence 区分色、原始 vs AI 派生分区、loading/skeleton/empty/error/toast/操作确认。
- 新增长期文本展开/折叠、表格分页、筛选搜索交互。
- 适配 1920×1080 路演屏幕，整体为白色/浅色 AI 研判工作台风格，不做传统蓝色渐变政务大屏。
- **新增 GSAP 动效系统**：按 greensock/gsap-skills 规范按需使用，动效只服务于强化状态变化、帮助理解页面层级、提升任务执行反馈、提升事件列表/详情切换体验；不为炫技堆动画，不用动效掩盖 loading/error，不做满屏炫技效果。

### 不做（边界）

- 不修改后端 API、数据库、domain schema、pipeline。
- 不为页面方便要求后端删字段、改字段。
- 不用 mock 数据伪装功能完成；所有页面必须调用真实后端接口。
- 后端不存在的能力（merge/split、Gold Set、全量 128278 推理、benchmark 质量指标）前端不假装实现。
- AI 判断状态、人工纠错状态、事件业务处理状态必须明确区分。
- `queued/running/completed/failed` 等真实状态完整展示，失败不伪装成功。
- `partial/failed/ambiguous/unresolved` 必须原样呈现，不视觉抹平。
- `confidence` 与 embedding 分数不单独渲染成事实结论；必须配合 SameEvent evidence。
- `max_work_orders` 前端硬限制 1–300，没有"默认全量"按钮。
- 动效不用来掩盖 loading/error，不做满屏炫技效果。
- 不做 KPI 大屏或普通 CRUD 后台，视觉主角必须是"民生事件"。

## Impact

- Affected specs: 新增前端硬装 spec，无既有 spec 被修改。
- Affected code:
  - `frontend/src/App.tsx`（替换骨架为真实工作台 shell + Router）
  - `frontend/src/main.tsx`（保持 QueryClient，新增 RouterProvider 与 ToastProvider）
  - `frontend/src/styles.css`（重写为 AI 研判工作台设计系统）
  - 新增 `frontend/src/api/`（typed client：health、imports、catalog、analysis、review）
  - 新增 `frontend/src/pages/`（ImportsPage、WorkOrdersPage、EventsListPage、ClusterDetailPage、WorkOrderDetailPage）
  - 新增 `frontend/src/components/`（StatusBadge、EvidencePanel、Skeleton、EmptyState、ErrorState、Toast、ConfirmDialog、Pagination、SearchInput、LongText、TraceTag 等）
  - 新增 `frontend/src/hooks/`（useAnalysisJobPolling、useToast、useGSAP 动效 hooks 等）
  - 新增 `frontend/src/types/`（与后端 schema 对齐的 TS 类型）
  - `frontend/package.json`（新增 react-router-dom、gsap、@gsap/react 依赖）
- 不影响：`backend/`、数据库、Alembic、pipeline、模型、gazetteer。
- GSAP Skills 已安装到 `.agents/skills/gsap-*`，TRAE 环境可读取 SKILL.md。

## ADDED Requirements

### Requirement: 信息架构与全局 Shell

系统 SHALL 提供一个左侧一级导航（仅三项：多频事件 / 工单中心 / 数据导入与AI研判）+ 顶部全局状态条 + 主内容区的工作台 shell。事件详情通过多频事件列表进入，不作为一级导航项。使用 React Router 建立真实 URL。

#### Scenario: 用户首次进入

- **WHEN** 用户打开 `http://127.0.0.1:5173`
- **THEN** 默认重定向到 `/events`（多频事件主工作台，产品核心闭环起点）
- **AND** 顶部状态条显示后端连接状态
- **AND** 左侧导航高亮当前页

#### Scenario: 真实 URL 可分享

- **WHEN** 用户在事件详情页 `/events/:clusterId`
- **THEN** URL 可直接分享/刷新，重新加载后回到同一事件详情
- **AND** 工单详情 `/work-orders/:workOrderId` 同样可分享/刷新

#### Scenario: 后端离线

- **WHEN** `/health/live` 失败
- **THEN** 顶部状态条显示"后端未连接"
- **AND** 所有页面数据请求显示 error state，不假装有数据

### Requirement: 数据导入与AI研判页面

系统 SHALL 提供一个页面，让用户上传 Excel/CSV，看到文件信息、导入状态、成功/异常数量、原始工单数量，并能发起 AI 研判。

#### Scenario: 上传预览

- **WHEN** 用户选择 Excel/CSV 文件
- **AND** 点击"预览"
- **THEN** 前端调用 `POST /imports/preview`（multipart）
- **AND** 展示 columns、total_rows、suggested_mapping
- **AND** 用户可在 suggested_mapping 基础上调整列映射

#### Scenario: 执行导入

- **WHEN** 用户确认映射后点击"导入"
- **THEN** 前端调用 `POST /imports`（multipart + mapping JSON）
- **AND** 展示 batch_id、status、total_rows、successful_rows、failed_rows、duplicate_rows、checkpoint_row、idempotent
- **AND** 若 `idempotent=true` 明确提示"该文件已导入过，幂等命中"

#### Scenario: 发起 AI 研判

- **WHEN** 导入完成（status 为 completed 或 partial）
- **THEN** 页面展示"发起 AI 研判"操作
- **AND** 用户必须填写 `max_work_orders`，前端硬限制 1–300
- **AND** 前端调用 `POST /analysis-jobs`，body 含 `import_batch_id` 与 `max_work_orders`
- **AND** 创建成功（HTTP 202）后进入轮询

#### Scenario: 任务状态轮询

- **WHEN** 分析任务创建成功
- **THEN** 前端自动每 2–3 秒轮询 `GET /analysis-jobs/{job_id}`
- **AND** 真实展示 `queued → running → completed | failed`
- **AND** 展示 total_rows、selected_rows、processed_rows、event_count、match_edge_count、cluster_count
- **AND** completed 后展示 trace（provider/model_id/schema_version/pipeline_version）
- **AND** failed 时展示 error 原文，不伪装成功
- **AND** 用户不需要手动刷新页面

#### Scenario: 任务失败

- **WHEN** 任务状态为 `failed`
- **THEN** 展示 error 字段原文
- **AND** 提供"重试"操作（重新创建一个新 job，不复活旧 job）

### Requirement: 工单中心页面

系统 SHALL 提供工单列表（搜索/分页）+ 工单详情，让工作人员快速检查原始工单与 AI 对工单的理解。

#### Scenario: 工单列表

- **WHEN** 用户进入 `/work-orders`
- **THEN** 前端调用 `GET /work-orders?offset=0&limit=20&query=`
- **AND** 展示 work_order_id、external_work_order_number、source_row_number、raw_title、created_at、event_count、cluster_count
- **AND** 支持分页（offset/limit，limit≤100）
- **AND** 支持搜索（query 参数，min_length=1, max_length=128）
- **AND** 展示 total 总数

#### Scenario: 工单详情

- **WHEN** 用户点击某工单进入 `/work-orders/:workOrderId`
- **THEN** 前端调用 `GET /work-orders/{work_order_id}`
- **AND** 展示 summary（含 import_batch_id、raw_content、raw_fields）
- **AND** 展示 events 列表（event_id、ordinal、event_type、behavior、normalized_summary、entities、location_signals、time_signals、evidence、trace）
- **AND** 原始工单内容（raw_content / raw_fields）与 AI 派生结果（events）在视觉上明显分区（不同背景/边框/标签）
- **AND** AI 派生字段带 trace 标签（provider/model）

### Requirement: 多频事件列表页面

系统 SHALL 提供多频事件列表，让工作人员一眼看到系统发现了哪些事件、每个事件关联多少工单、涉及什么主体/地点、AI 置信程度、当前业务处理状态。这是产品视觉主角。

#### Scenario: 事件列表

- **WHEN** 用户进入 `/events`（默认首页）
- **THEN** 前端调用 `GET /multi-frequency-events?offset=0&limit=20`
- **AND** 展示 cluster_id、name、status、confidence、handling_status、member_count、evidence、trace
- **AND** 支持分页（offset/limit，limit≤100）
- **AND** 筛选/排序仅作用于当前已加载结果，UI 必须明确表现为"筛选当前页"，不得伪装成全局搜索（后端事件列表 API 不支持 search query；若数据库有 300 个事件但页面只加载 20 条，筛选只搜这 20 条，不能让用户以为搜的是全部）
- **AND** 支持按 member_count、confidence、handling_status 排序（同样只对当前加载结果生效）
- **AND** 每个事件卡片/行让用户一眼看懂"发生了什么"（name + evidence 摘要）
- **AND** confidence 不单独作为结论，必须配合 evidence

#### Scenario: 空状态

- **WHEN** total=0（没有多频事件，可能尚未运行 AI 研判）
- **THEN** 展示 empty state，提示用户先去"数据导入与AI研判"页面发起研判

### Requirement: 事件详情 / 研判页面

这是整个产品最重要的页面。系统 SHALL 提供事件详情，让用户同时看到事件概要、关联工单、AI 判断依据、人工纠错、业务处理、历史记录与审计。

#### Scenario: 事件概要

- **WHEN** 用户从多频事件列表点击某事件进入 `/events/:clusterId`
- **THEN** 前端调用 `GET /multi-frequency-events/{cluster_id}`
- **AND** 展示 summary（cluster_id、name、status、confidence、handling_status、member_count、evidence、trace）
- **AND** 展示成员工单（members：每个 member 是一个 EventDetail，含 event、work_order、raw_title、raw_content）

#### Scenario: AI 判断依据

- **WHEN** 用户查看事件详情
- **THEN** 展示 edges（MatchEdge：left_event_id、right_event_id、same_event、confidence、evidence、trace）
- **AND** evidence 必须展开显示：主体为什么一致、地点为什么一致、事件内容为什么一致、是否存在时间证据、是否存在冲突证据
- **AND** 不只显示"相似度 92%"
- **AND** confidence 与 evidence 配合展示，不单独作为结论

#### Scenario: 人工纠错

- **WHEN** 用户查看事件详情
- **THEN** 展示当前后端真实支持的纠错操作：`remove_member` / `confirm_member`
- **AND** 用户选择某 member event_instance_id 后可发起纠错
- **AND** 前端调用 `POST /multi-frequency-events/{cluster_id}/corrections`，body 含 correction_type、event_instance_id、actor_id、reason（可选）
- **AND** 高风险操作（remove_member）必须操作确认弹窗
- **AND** 纠错后刷新 cluster detail，展示 human_corrections 历史
- **AND** 不展示后端不支持的 merge/split 操作

#### Scenario: 业务处理

- **WHEN** 用户查看事件详情
- **THEN** 展示当前 handling_status
- **AND** 用户可添加处理记录：new_status、actor_id、description、result、attachment_references
- **AND** 前端调用 `POST /multi-frequency-events/{cluster_id}/handling-records`
- **AND** 展示 handling_history（record_id、previous_status、new_status、actor_id、description、result、attachment_references、created_at）
- **AND** 业务处理状态与 AI 判断状态、人工纠错状态视觉上明确区分

#### Scenario: 审计历史

- **WHEN** 用户查看事件详情
- **THEN** 展示 human_corrections 列表（correction_id、cluster_id、work_order_id、correction_type、actor_id、reason、payload、supersedes_correction_id、created_at）
- **AND** 展示 handling_history
- **AND** 谁做了什么修改、什么时间修改一目了然

#### Scenario: CSV 导出

- **WHEN** 用户在事件详情页点击"导出 CSV"
- **THEN** 前端调用 `GET /multi-frequency-events/export.csv?cluster_id={cluster_id}`
- **AND** 浏览器下载 UTF-8 BOM CSV
- **AND** 导出失败时展示 error state，不假装成功

### Requirement: 交互与状态系统

系统 SHALL 提供统一的交互状态体验。

#### Scenario: Loading / Skeleton

- **WHEN** 任何数据请求进行中
- **THEN** 展示 skeleton 或 loading 指示，不展示陈旧数据冒充新数据
- **AND** 不用动效掩盖 loading 状态

#### Scenario: Empty state

- **WHEN** 列表 total=0
- **THEN** 展示 empty state，引导用户下一步操作

#### Scenario: Error state

- **WHEN** API 返回非 2xx 或网络失败
- **THEN** 展示 error state，含 HTTP 状态码与后端 detail（若有）
- **AND** 不假装成功，不吞错误
- **AND** 不用动效掩盖 error 状态

#### Scenario: Long text 展开

- **WHEN** 工单 raw_content 或 evidence 文本过长
- **THEN** 默认折叠，提供"展开/收起"操作

#### Scenario: 操作确认

- **WHEN** 执行高风险操作（remove_member、删除等）
- **THEN** 弹出确认对话框，明确告知后果
- **AND** 不出现"全量研判"按钮（max_work_orders 硬限制 1–300，128278 全量推理明确属于"不做"）

#### Scenario: Toast 反馈

- **WHEN** 任何写操作完成或失败
- **THEN** 显示 toast 反馈（成功/失败 + 简短说明）

### Requirement: GSAP 动效系统（克制使用）

系统 SHALL 按 greensock/gsap-skills 规范，在视觉收益明确时使用 GSAP 动效，只服务于强化状态变化、帮助理解页面层级、提升任务执行反馈、提升事件列表/详情切换体验。不为证明安装了 GSAP 而对每个元素都套 gsap.timeline。

#### Scenario: 动效使用规范

- **THEN** 动效只用于：状态变化、页面层级（列表→详情进入/退出）、任务执行反馈（数字变化、进度推进）、页面过渡（路由切换）
- **AND** 使用 useGSAP() hook 与 gsap.context() cleanup，避免泄漏
- **AND** 使用 refs + scope，不用无 scope 的 selector
- **AND** 遵守 prefers-reduced-motion，reduced-motion 时 duration=0 或跳过动画
- **AND** 不为炫技堆动画
- **AND** 不用动效掩盖 loading/error
- **AND** 不做满屏炫技效果

#### Scenario: 适合 GSAP 的动效（视觉收益明确，SHOULD 用 GSAP）

- **WHEN** 涉及页面层级进入/退出、分析任务状态阶段变化、Evidence 展开、数字更新、列表 stagger、Dialog/drawer
- **THEN** SHOULD 按 GSAP Skill 使用（这些场景 GSAP 比 CSS transition 收益更高）

#### Scenario: 简单状态变化（MAY 用 CSS transition）

- **WHEN** status badge 颜色变化等简单视觉切换
- **THEN** MAY 使用纯 CSS transition（比 GSAP 更合理时不必强制 GSAP）
- **AND** failed 状态有明显但克制的视觉反馈（如红色高亮淡入）

#### Scenario: 列表→详情切换

- **WHEN** 用户从多频事件列表点击进入事件详情
- **THEN** 页面过渡有动效（如详情区从右淡入/滑入），帮助理解页面层级
- **AND** 返回列表时反向动效

#### Scenario: 任务进度数字变化

- **WHEN** analysis job 的 processed_rows / event_count 等数字在轮询中变化
- **THEN** 数字变化有动效（如 count up / 高亮闪现），提升任务执行反馈

### Requirement: 视觉设计系统

系统 SHALL 采用现代 AI 研判工作台视觉风格，视觉主角必须是"民生事件"，不做传统蓝色渐变政务大屏，不做 KPI 大屏，不做普通 CRUD 后台。

#### Scenario: 视觉规范

- **THEN** 白色/浅色背景
- **AND** 信息层级明确（标题/正文/次要文字/标签）
- **AND** 较强的表格与详情阅读体验
- **AND** AI evidence 有明显但克制的视觉区分（如左侧色条 + 浅色背景）
- **AND** 原始工单 vs AI 派生结果分区（不同背景/边框/标签）
- **AND** 状态色统一（queued=灰、running=蓝、completed=绿、failed=红、handling_status 用独立色系）
- **AND** 高风险操作有确认
- **AND** 适配 1920×1080 路演屏幕
- **AND** 视觉主角是"民生事件"（事件列表卡片化、事件详情信息密度高），不是 KPI 数字大屏，不是普通 CRUD 表格
- **AND** 整体感觉是"工作人员真的可以每天用的系统"，不是"PPT 做成网页"

## MODIFIED Requirements

（本 spec 为新增，无既有 spec 被修改）

## REMOVED Requirements

（本 spec 不移除任何既有需求）
