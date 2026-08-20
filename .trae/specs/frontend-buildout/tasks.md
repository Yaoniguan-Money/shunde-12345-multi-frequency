# Tasks

## 阶段 0：基础架构与 Shell（核心展示链的地基）

- [ ] Task 1: 安装依赖与搭建设计系统
  - [ ] SubTask 1.1: 安装 `react-router-dom`、`gsap`、`@gsap/react`
  - [ ] SubTask 1.2: 重写 `frontend/src/styles.css` 为 AI 研判工作台设计系统（白色/浅色背景、信息层级、状态色统一、AI evidence 区分色、原始 vs AI 派生分区；视觉主角是"民生事件"，不是 KPI 大屏/CRUD）
  - [ ] SubTask 1.3: 建立 TS 类型层 `frontend/src/types/` 与后端 schema 对齐（禁止 any，nullable 一致）

- [ ] Task 2: 建立前端 typed API 客户端层
  - [ ] SubTask 2.1: `frontend/src/api/client.ts` 统一 fetch wrapper（baseURL 来自 `VITE_API_BASE_URL`、error handling、AbortSignal 透传）
  - [ ] SubTask 2.2: 扩展 `frontend/src/api/health.ts`（live/ready/dependencies）
  - [ ] SubTask 2.3: `frontend/src/api/imports.ts`（preview + import，multipart）
  - [ ] SubTask 2.4: `frontend/src/api/catalog.ts`（work-orders 列表/详情、events 列表/详情、multi-frequency-events 列表/详情）
  - [ ] SubTask 2.5: `frontend/src/api/analysis.ts`（POST /analysis-jobs、GET /analysis-jobs/{job_id}）
  - [ ] SubTask 2.6: `frontend/src/api/review.ts`（handling-records、corrections、CSV 导出下载）
  - [ ] SubTask 2.7: 生产路径无 mock 数据

- [ ] Task 3: 搭建工作台 Shell + Router
  - [ ] SubTask 3.1: `frontend/src/main.tsx` 包裹 QueryClientProvider + RouterProvider + ToastProvider
  - [ ] SubTask 3.2: `frontend/src/App.tsx` 为 shell 布局：左侧一级导航（仅三项：多频事件 / 工单中心 / 数据导入与AI研判）+ 顶部全局状态条 + 主内容区
  - [ ] SubTask 3.3: React Router 路由：`/` 重定向到 `/events`、`/events`、`/events/:clusterId`、`/work-orders`、`/work-orders/:workOrderId`、`/imports`
  - [ ] SubTask 3.4: 顶部状态条接入 /health/live 与 /health/dependencies，后端离线显示"后端未连接"
  - [ ] SubTask 3.5: 左侧导航高亮当前页

- [ ] Task 4: 通用交互组件库
  - [ ] SubTask 4.1: `frontend/src/components/StatusBadge.tsx`（queued/running/completed/failed + handling_status 独立色系）
  - [ ] SubTask 4.2: `frontend/src/components/Skeleton.tsx`（列表/详情骨架）
  - [ ] SubTask 4.3: `frontend/src/components/EmptyState.tsx`（含引导文案）
  - [ ] SubTask 4.4: `frontend/src/components/ErrorState.tsx`（含 HTTP 状态码 + detail）
  - [ ] SubTask 4.5: `frontend/src/components/Toast.tsx` + `frontend/src/hooks/useToast.ts`
  - [ ] SubTask 4.6: `frontend/src/components/ConfirmDialog.tsx`（高风险操作确认）
  - [ ] SubTask 4.7: `frontend/src/components/Pagination.tsx`（offset/limit 分页）
  - [ ] SubTask 4.8: `frontend/src/components/SearchInput.tsx`（min_length/max_length 校验）
  - [ ] SubTask 4.9: `frontend/src/components/LongText.tsx`（展开/收起）
  - [ ] SubTask 4.10: `frontend/src/components/TraceTag.tsx`（provider/model 标签）

## 阶段 1：多频事件列表（产品视觉主角，第一印象）

- [ ] Task 5: 多频事件列表页面
  - [ ] SubTask 5.1: `frontend/src/pages/EventsListPage.tsx` 调用 `GET /multi-frequency-events?offset=0&limit=20`
  - [ ] SubTask 5.2: 展示 cluster_id、name、status、confidence、handling_status、member_count、evidence 摘要、trace
  - [ ] SubTask 5.3: 卡片化布局（视觉主角是"民生事件"，不是普通 CRUD 表格），每个卡片让用户一眼看懂"发生了什么"
  - [ ] SubTask 5.4: 分页（Pagination 组件）
  - [ ] SubTask 5.5: 本地筛选/排序仅作用于当前已加载结果，UI 明确表现为"筛选当前页"，不伪装成全局搜索（后端列表 API 不支持 search query）
  - [ ] SubTask 5.6: confidence 不单独作为结论，必须配合 evidence
  - [ ] SubTask 5.7: empty state（total=0 引导去发起 AI 研判）
  - [ ] SubTask 5.8: 点击 event 跳转 `/events/:clusterId`
  - [ ] SubTask 5.9: 真实接通后端验证此页（不允许最后统一接接口）

## 阶段 2：事件详情 / 研判（最重要页面，核心展示链终点）

- [ ] Task 6: 事件详情页基础结构
  - [ ] SubTask 6.1: `frontend/src/pages/ClusterDetailPage.tsx` 调用 `GET /multi-frequency-events/{cluster_id}`
  - [ ] SubTask 6.2: 事件概要区（summary：name、status、confidence、handling_status、member_count、evidence、trace）
  - [ ] SubTask 6.3: 关联工单区（members：每个 member 是 EventDetail，含 event + work_order + raw_title + raw_content）
  - [ ] SubTask 6.4: 原始工单（raw_content/raw_title）与 AI 派生（event）视觉分区
  - [ ] SubTask 6.5: 真实接通后端验证此页

- [ ] Task 7: AI 判断依据区（核心）
  - [ ] SubTask 7.1: 展示 edges（MatchEdge：left_event_id、right_event_id、same_event、confidence、evidence、trace）
  - [ ] SubTask 7.2: evidence 展开显示：主体一致、地点一致、事件内容一致、时间证据、冲突证据
  - [ ] SubTask 7.3: 不只显示"相似度 92%"，confidence 与 evidence 配合
  - [ ] SubTask 7.4: AI evidence 有明显但克制的视觉区分（左侧色条 + 浅色背景）

- [ ] Task 8: 人工纠错区
  - [ ] SubTask 8.1: 展示当前后端真实支持的 `remove_member` / `confirm_member`
  - [ ] SubTask 8.2: 用户选择 member event_instance_id 后发起纠错（POST corrections）
  - [ ] SubTask 8.3: remove_member 高风险操作必须 ConfirmDialog
  - [ ] SubTask 8.4: 纠错后刷新 cluster detail
  - [ ] SubTask 8.5: 不展示后端不支持的 merge/split
  - [ ] SubTask 8.6: 真实接通后端验证纠错流程

- [ ] Task 9: 业务处理区
  - [ ] SubTask 9.1: 展示当前 handling_status
  - [ ] SubTask 9.2: 添加处理记录表单（new_status、actor_id、description、result、attachment_references）
  - [ ] SubTask 9.3: POST handling-records
  - [ ] SubTask 9.4: 展示 handling_history
  - [ ] SubTask 9.5: 业务处理状态与 AI 判断状态、人工纠错状态视觉明确区分
  - [ ] SubTask 9.6: 真实接通后端验证处理流程

- [ ] Task 10: 审计历史区
  - [ ] SubTask 10.1: 展示 human_corrections 列表全字段
  - [ ] SubTask 10.2: 展示 handling_history（聚焦"谁做了什么修改、什么时间"）

- [ ] Task 11: CSV 导出
  - [ ] SubTask 11.1: 事件详情页"导出 CSV"按钮
  - [ ] SubTask 11.2: 调用 `GET /multi-frequency-events/export.csv?cluster_id={cluster_id}` 触发浏览器下载
  - [ ] SubTask 11.3: 失败时 error state，不假装成功
  - [ ] SubTask 11.4: 真实接通后端验证导出

## 阶段 3：工单中心

- [ ] Task 12: 工单列表
  - [ ] SubTask 12.1: `frontend/src/pages/WorkOrdersPage.tsx` 调用 `GET /work-orders?offset=0&limit=20&query=`
  - [ ] SubTask 12.2: 展示 work_order_id、external_work_order_number、source_row_number、raw_title、created_at、event_count、cluster_count
  - [ ] SubTask 12.3: 分页 + 搜索（query min_length=1, max_length=128）
  - [ ] SubTask 12.4: 展示 total 总数
  - [ ] SubTask 12.5: 真实接通后端验证

- [ ] Task 13: 工单详情
  - [ ] SubTask 13.1: `frontend/src/pages/WorkOrderDetailPage.tsx` 调用 `GET /work-orders/{work_order_id}`
  - [ ] SubTask 13.2: 展示 summary（import_batch_id、raw_content、raw_fields）
  - [ ] SubTask 13.3: 展示 events 列表全字段
  - [ ] SubTask 13.4: 原始工单（raw_content/raw_fields）与 AI 派生（events）视觉明显分区
  - [ ] SubTask 13.5: AI 派生字段带 TraceTag
  - [ ] SubTask 13.6: 真实接通后端验证

## 阶段 4：数据导入与AI研判

- [ ] Task 14: 文件上传与预览
  - [ ] SubTask 14.1: `frontend/src/pages/ImportsPage.tsx` 文件选择（Excel/CSV）
  - [ ] SubTask 14.2: 调用 `POST /imports/preview`（multipart）展示 columns、total_rows、suggested_mapping
  - [ ] SubTask 14.3: 用户可调整列映射
  - [ ] SubTask 14.4: 真实接通后端验证预览

- [ ] Task 15: 执行导入
  - [ ] SubTask 15.1: 调用 `POST /imports`（multipart + mapping JSON）
  - [ ] SubTask 15.2: 展示 batch_id、status、total_rows、successful_rows、failed_rows、duplicate_rows、checkpoint_row、idempotent
  - [ ] SubTask 15.3: idempotent=true 明确提示
  - [ ] SubTask 15.4: 真实接通后端验证导入

- [ ] Task 16: 发起 AI 研判
  - [ ] SubTask 16.1: 导入完成（completed/partial）后展示"发起 AI 研判"
  - [ ] SubTask 16.2: 用户填写 max_work_orders，前端硬限制 1–300（无"默认全量"按钮）
  - [ ] SubTask 16.3: 调用 `POST /analysis-jobs`，body 含 import_batch_id 与 max_work_orders
  - [ ] SubTask 16.4: HTTP 202 成功后进入轮询

- [ ] Task 17: 任务状态轮询
  - [ ] SubTask 17.1: `frontend/src/hooks/useAnalysisJobPolling.ts` 每 2–3 秒轮询 `GET /analysis-jobs/{job_id}`
  - [ ] SubTask 17.2: 真实展示 queued → running → completed | failed
  - [ ] SubTask 17.3: 展示 total_rows、selected_rows、processed_rows、event_count、match_edge_count、cluster_count
  - [ ] SubTask 17.4: completed 展示 trace
  - [ ] SubTask 17.5: failed 展示 error 原文，不伪装成功
  - [ ] SubTask 17.6: 提供"重试"操作（新建 job，不复活旧 job）
  - [ ] SubTask 17.7: 用户不需要手动刷新
  - [ ] SubTask 17.8: 真实接通后端验证轮询

## 阶段 5：GSAP 动效与全局打磨

- [ ] Task 18: GSAP 动效（克制使用，按 gsap-skills 规范，视觉收益明确时才用）
  - [ ] SubTask 18.1: 安装并注册 `@gsap/react` useGSAP hook
  - [ ] SubTask 18.2: 适合 GSAP 的场景（SHOULD 用）：页面层级进入/退出、分析任务状态阶段变化、Evidence 展开、数字更新、列表 stagger、Dialog/drawer
  - [ ] SubTask 18.3: 简单状态变化（MAY 用 CSS transition）：status badge 颜色变化等，不必强制 GSAP；failed 红色高亮淡入
  - [ ] SubTask 18.4: 列表→详情切换动效（详情区从右淡入/滑入，返回反向）
  - [ ] SubTask 18.5: 任务进度数字变化动效（count up / 高亮闪现）
  - [ ] SubTask 18.6: 路由切换页面过渡动效
  - [ ] SubTask 18.7: 遵守 prefers-reduced-motion（reduced-motion 时 duration=0 或跳过）
  - [ ] SubTask 18.8: useGSAP + scope + cleanup，避免泄漏；不用动效掩盖 loading/error；不做满屏炫技；不为证明装了 GSAP 对每个元素都套 gsap.timeline

## 阶段 6：验证与收尾

- [ ] Task 19: 前端验证
  - [ ] SubTask 19.1: `pnpm install --frozen-lockfile` PASS
  - [ ] SubTask 19.2: `pnpm lint` PASS
  - [ ] SubTask 19.3: `pnpm test --run` PASS
  - [ ] SubTask 19.4: `pnpm build` PASS
  - [ ] SubTask 19.5: 手动连通真实后端跑通主闭环：导入 → 研判 → 多频事件 → 事件详情 → 纠错 → 处理 → 导出

- [ ] Task 20: 文档与交接
  - [ ] SubTask 20.1: 更新 `docs/TRAE_CHANGELOG.md`（日期、改动目标、修改文件、是否需要 API 变更、本地验证命令、已知问题）
  - [ ] SubTask 20.2: 不修改 `docs/CURRENT_STATE.md` 的后端状态（后端冻结），追加前端阶段状态
  - [ ] SubTask 20.3: 记录任何"现有 API 不够支持某 UI"的问题，不自行修改后端

# Task Dependencies

- Task 1, 2, 3, 4 可并行（基础架构）
- Task 5 依赖 Task 1–4（多频事件列表是第一印象）
- Task 6–11 依赖 Task 5（事件详情从列表进入，核心展示链终点）
- Task 12–13 依赖 Task 1–4（工单中心独立分支）
- Task 14–17 依赖 Task 1–4（数据导入独立分支）
- Task 18 依赖 Task 5–17 全部完成（动效打磨在真实功能之上）
- Task 19 依赖所有前置 Task
- Task 20 依赖 Task 19

# 核心展示链（优先级最高）

Shell（Task 1–4）→ 多频事件列表（Task 5）→ 事件详情（Task 6–11）

这条链先做漂亮，方向错了能早点纠正。工单中心与数据导入随后补。
