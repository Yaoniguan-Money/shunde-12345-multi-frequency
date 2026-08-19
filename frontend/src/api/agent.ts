import { apiRequest } from "./client";
import type {
  AgentQueryDSL,
  AgentQueryResponse,
  BatchActionExecuteResponse,
  BatchActionPreviewResponse,
  DynamicDashboardResponse,
  UUID,
  WorksetResponse,
} from "../types/api";

export function queryAgent(body: {
  query: string;
  previous_query?: string;
  previous_query_snapshot?: AgentQueryDSL;
  previous_work_order_ids?: UUID[];
  limit?: number;
}, signal?: AbortSignal): Promise<AgentQueryResponse> {
  return apiRequest<AgentQueryResponse>("/agent/query", { method: "POST", body, signal });
}

export function createWorkset(body: {
  name: string;
  original_query: string;
  query_snapshot: AgentQueryDSL;
  work_order_ids: UUID[];
  cluster_ids: UUID[];
  created_by?: string;
}): Promise<WorksetResponse> {
  return apiRequest<WorksetResponse>("/worksets", { method: "POST", body });
}

export function previewWorksetAction(worksetId: UUID, body: {
  action_type: "add_handling_record" | "set_handling_status" | "export_csv";
  new_status?: "unhandled" | "investigating" | "resolved";
  description?: string;
  result?: string;
  actor_id?: string;
}): Promise<BatchActionPreviewResponse> {
  return apiRequest<BatchActionPreviewResponse>(`/worksets/${worksetId}/actions/preview`, { method: "POST", body });
}

export function executeWorksetAction(worksetId: UUID, body: { preview_id: UUID; actor_id?: string }): Promise<BatchActionExecuteResponse> {
  return apiRequest<BatchActionExecuteResponse>(`/worksets/${worksetId}/actions/execute`, { method: "POST", body });
}

export function generateAgentDashboard(body: {
  title: string;
  work_order_ids: UUID[];
  cluster_ids: UUID[];
}): Promise<DynamicDashboardResponse> {
  return apiRequest<DynamicDashboardResponse>("/agent/dashboard", { method: "POST", body });
}
