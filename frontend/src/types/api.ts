// 与后端 schema 严格对齐的 TypeScript 类型定义。
// UUID 在前端统一用 string 表示，类型名保留 UUID 语义。
// 不允许 any；未知结构使用 Record<string, unknown>。

export type UUID = string;
export type ISODateString = string;

/** 后端追踪信息，AI 派生数据均带此字段用于可解释性。 */
export interface TraceResponse {
  provider: string | null;
  model_id: string | null;
  model_config_hash: string | null;
  schema_version: string;
  knowledge_snapshot_id: UUID | null;
  pipeline_version: string;
}

export interface EntityReferenceResponse {
  entity_id: UUID;
  standard_name: string | null;
  entity_type: string | null;
  resolution_state: "resolved" | "unresolved" | string;
}

export interface EventResponse {
  event_id: UUID;
  work_order_id: UUID;
  ordinal: number;
  event_type: string | null;
  behavior: string | null;
  normalized_summary: string;
  entities: EntityReferenceResponse[];
  location_signals: string[];
  time_signals: string[];
  evidence: Record<string, unknown>[];
  trace: TraceResponse;
  occurrence_date: ISODateString | null;
}

export type WorkOrderAnalysisState =
  | "unprocessed"
  | "analyzed_no_event"
  | "analyzed"
  | "failed";

export interface WorkOrderSummaryResponse {
  work_order_id: UUID;
  external_work_order_number: string | null;
  source_row_number: number;
  raw_title: string | null;
  created_at: ISODateString;
  event_count: number;
  cluster_count: number;
  analysis_state: WorkOrderAnalysisState;
  title_tags: string[];
  is_urgent: boolean;
}

export interface ClusterReferenceResponse {
  cluster_id: UUID;
  cluster_name: string;
  review_status: ReviewStatus;
  handling_status: string;
}

export interface WorkOrderDetailResponse {
  summary: WorkOrderSummaryResponse;
  import_batch_id: UUID;
  raw_content: string;
  raw_fields: Record<string, unknown>;
  events: EventResponse[];
  cluster_refs: ClusterReferenceResponse[];
}

export interface EventDetailResponse {
  event: EventResponse;
  work_order: WorkOrderSummaryResponse;
  raw_title: string | null;
  raw_content: string;
}

export interface MatchEdgeResponse {
  left_event_id: UUID;
  right_event_id: UUID;
  same_event: boolean;
  confidence: number;
  evidence: Record<string, unknown>;
  trace: TraceResponse;
}

export type ClusterStatus = string;
export type HandlingStatus = string;
export type AnalysisJobStatus = "queued" | "running" | "completed" | "failed";
export type AnalysisJobStage =
  | "queued"
  | "understanding"
  | "embedding"
  | "retrieval"
  | "matching"
  | "clustering"
  | "completed";
export type AnalysisSelectionMode = "sequential" | "recurrence_candidates";
export type ReviewStatus = "pending_review" | "confirmed" | "rejected";

export interface ClusterSummaryResponse {
  cluster_id: UUID;
  name: string;
  status: ClusterStatus;
  confidence: number;
  handling_status: HandlingStatus;
  member_count: number;
  work_order_count: number;
  event_count: number;
  evidence: Record<string, unknown>;
  trace: TraceResponse | null;
  review_status: ReviewStatus;
  is_multi_frequency: boolean;
  /** Backend-calculated high-frequency projection; clients must not recompute it. */
  is_high_frequency: boolean;
  frequency_window_days: number;
  frequency_work_order_count: number;
}

export interface ClusterDetailResponse {
  summary: ClusterSummaryResponse;
  members: EventDetailResponse[];
  work_orders: WorkOrderDetailResponse[];
  edges: MatchEdgeResponse[];
  handling_history: HandlingRecordResponse[];
  human_corrections: HumanCorrectionResponse[];
  removed_members: RemovedMemberResponse[];
}

export interface HandlingRecordResponse {
  record_id: UUID;
  cluster_id: UUID;
  previous_status: string | null;
  new_status: string;
  actor_id: string;
  description: string | null;
  result: string | null;
  attachment_references: string[];
  created_at: ISODateString;
}

export interface HumanCorrectionResponse {
  correction_id: UUID;
  cluster_id: UUID | null;
  work_order_id: UUID | null;
  correction_type: string;
  actor_id: string;
  reason: string | null;
  payload: Record<string, unknown>;
  supersedes_correction_id: UUID | null;
  created_at: ISODateString;
}

export interface RemovedMemberResponse {
  event: EventResponse | null;
  event_instance_id: UUID;
  work_order: WorkOrderSummaryResponse | null;
  raw_title: string | null;
  raw_content: string | null;
  correction_id: UUID;
  actor_id: string;
  reason: string | null;
  removed_at: ISODateString;
  can_restore: boolean;
}

export interface AnalysisJobResponse {
  job_id: UUID;
  status: AnalysisJobStatus;
  current_stage: AnalysisJobStage;
  total_rows: number;
  selected_rows: number;
  processed_rows: number;
  event_count: number;
  match_edge_count: number;
  cluster_count: number;
  started_at: ISODateString | null;
  finished_at: ISODateString | null;
  error: string | null;
  trace: TraceResponse | null;
  selection_mode: AnalysisSelectionMode;
}

export interface AttachmentResponse {
  attachment_id: UUID;
  reference: string;
  original_filename: string;
  size: number;
  content_type: string;
}

export interface ClusterReviewResponse {
  cluster_id: UUID;
  previous_status: ReviewStatus;
  review_status: ReviewStatus;
  actor_id: string;
  reason: string | null;
  reviewed_at: ISODateString;
}

/** 统一列表响应。 */
export interface ListResponse<T> {
  items: T[];
  offset: number;
  limit: number;
  total: number;
}

/** /work-orders 列表行（精简于 WorkOrderSummaryResponse 的子集，按后端契约）。 */
export interface WorkOrderListItem {
  work_order_id: UUID;
  external_work_order_number: string | null;
  source_row_number: number;
  raw_title: string | null;
  created_at: ISODateString;
  event_count: number;
  cluster_count: number;
  analysis_state: WorkOrderAnalysisState;
  title_tags: string[];
  is_urgent: boolean;
}

export type WorkOrderListResponse = ListResponse<WorkOrderListItem>;

/** 健康检查响应。 */
export interface LivenessResponse {
  status: "alive";
}

export interface ReadinessResponse {
  status: string;
  database: {
    state: string;
    version: string | null;
    detail: string | null;
  };
}

export interface DependencyState {
  state: "up" | "down" | "not_configured";
  version?: string | null;
  detail?: string | null;
}

export interface DependenciesResponse {
  status: string;
  database: DependencyState;
  gazetteer: DependencyState;
  local_model: DependencyState;
}

export type AgentHandlingStatus = "unhandled" | "investigating" | "resolved";

export interface AgentTimeRange {
  kind: "relative" | "absolute";
  value?: string | null;
  start?: ISODateString | null;
  end?: ISODateString | null;
}

export interface AgentQueryDSL {
  intent: string;
  time_range: AgentTimeRange | null;
  keywords: string[];
  topic: string | null;
  title_tag: string | null;
  aggregation: "none" | "count" | "group_by_topic" | "group_by_status" | "group_by_location";
  context_mode: "new_scope" | "refine_scope" | "reference_results";
  issue_required: boolean;
  entity: string | null;
  location: string | null;
  event_type: string | null;
  handling_status: AgentHandlingStatus | null;
  cluster_status: string | null;
  sort: "relevance" | "newest" | "oldest";
  limit: number;
  work_order_ids: UUID[];
}

export interface AgentTopicGroup { label: string; count: number; }

export interface AgentTreeChild {
  label: string;
  count: number;
  work_orders: AgentWorkOrderResult[];
}

export interface AgentTreeGroup {
  label: string;
  count: number;
  urgent_count: number;
  multi_frequency_count: number;
  children: AgentTreeChild[];
}

export interface AgentWorkOrderResult {
  work_order_id: UUID;
  external_work_order_number: string | null;
  title: string | null;
  title_tags: string[];
  is_urgent: boolean;
  reported_at: ISODateString | null;
  time_label: string;
  normalized_summary: string | null;
  location: string | null;
  event_type: string | null;
  handling_status: string;
  cluster_ids: UUID[];
  is_multi_frequency: boolean;
  is_high_frequency: boolean;
  retrieval_evidence: string[];
}

export interface AgentQueryResponse {
  original_query: string;
  compiled_query: AgentQueryDSL;
  planner_mode: "llm" | "rules";
  answer: string;
  disclaimer: string;
  total: number;
  matched_total: number;
  page: number;
  page_size: number;
  topic_groups: AgentTopicGroup[];
  handling_groups: AgentTopicGroup[];
  work_orders: AgentWorkOrderResult[];
  cluster_ids: UUID[];
  retrieval_trace: Record<string, unknown>[];
}

export interface AgentDrilldown {
  topic?: string | null;
  location?: string | null;
  handling_status?: AgentHandlingStatus | null;
  frequency?: "all" | "multi_frequency" | "high_frequency";
}

export interface AgentQueryResultsResponse {
  matched_total: number;
  page: number;
  page_size: number;
  items: AgentWorkOrderResult[];
}

export interface WorksetResponse {
  id: UUID;
  name: string;
  original_query: string;
  query_snapshot: AgentQueryDSL;
  work_order_ids: UUID[];
  cluster_ids: UUID[];
  created_at: ISODateString;
  created_by: string;
  result_count: number;
  metadata: Record<string, unknown>;
}

export interface WorksetListResponse {
  items: WorksetResponse[];
  total: number;
}

export interface BatchActionPreviewResponse {
  preview_id: UUID;
  action_type: "add_handling_record" | "set_handling_status" | "export_csv";
  affected_work_order_count: number;
  affected_cluster_count: number;
  skipped_work_order_count: number;
  before_status_counts: Record<string, number>;
  after_status: string | null;
  message: string;
}

export interface BatchActionExecuteResponse {
  preview_id: UUID;
  action_type: "add_handling_record" | "set_handling_status" | "export_csv";
  executed_work_order_count: number;
  audit_action: string;
  csv_content: string | null;
}

export interface DynamicDashboardResponse {
  title: string;
  work_order_count: number;
  multi_frequency_event_count: number;
  multi_frequency_work_order_count: number;
  high_frequency_event_count: number;
  urgent_count: number;
  handling_groups: AgentTopicGroup[];
  topic_groups: AgentTopicGroup[];
  location_groups: AgentTopicGroup[];
  topic_tree: AgentTreeGroup[];
  location_tree: AgentTreeGroup[];
  status_tree: AgentTreeGroup[];
  focus_cluster_ids: UUID[];
  disclaimer: string;
}

export interface WorksetWorkspaceResponse {
  workset: WorksetResponse;
  work_orders: AgentWorkOrderResult[];
  dashboard: DynamicDashboardResponse;
}
