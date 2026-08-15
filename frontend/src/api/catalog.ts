import { apiRequest } from "./client";
import type {
  ClusterDetailResponse,
  ClusterSummaryResponse,
  EventDetailResponse,
  EventResponse,
  ListResponse,
  WorkOrderDetailResponse,
  WorkOrderListResponse,
} from "../types/api";

export type {
  ClusterDetailResponse,
  ClusterSummaryResponse,
  EventDetailResponse,
  EventResponse,
  ListResponse,
  WorkOrderDetailResponse,
  WorkOrderListResponse,
};

/** GET /work-orders?offset&limit&query */
export function listWorkOrders(params: {
  offset?: number;
  limit?: number;
  query?: string;
  signal?: AbortSignal;
}): Promise<WorkOrderListResponse> {
  return apiRequest<WorkOrderListResponse>("/work-orders", {
    signal: params.signal,
    searchParams: {
      offset: params.offset ?? 0,
      limit: params.limit ?? 20,
      query: params.query,
    },
  });
}

/** GET /work-orders/{id} */
export function getWorkOrder(
  workOrderId: string,
  signal?: AbortSignal,
): Promise<WorkOrderDetailResponse> {
  return apiRequest<WorkOrderDetailResponse>(`/work-orders/${workOrderId}`, {
    signal,
  });
}

/** GET /events?offset&limit&pipeline_version&work_order_id */
export function listEvents(params: {
  offset?: number;
  limit?: number;
  pipelineVersion?: string;
  workOrderId?: string;
  signal?: AbortSignal;
}): Promise<ListResponse<EventDetailResponse>> {
  return apiRequest<ListResponse<EventDetailResponse>>("/events", {
    signal: params.signal,
    searchParams: {
      offset: params.offset ?? 0,
      limit: params.limit ?? 20,
      pipeline_version: params.pipelineVersion,
      work_order_id: params.workOrderId,
    },
  });
}

/** GET /events/{id} */
export function getEvent(
  eventId: string,
  signal?: AbortSignal,
): Promise<{
  event: EventResponse;
  work_order: WorkOrderDetailResponse["summary"];
  raw_title: string | null;
  raw_content: string;
}> {
  return apiRequest(`/events/${eventId}`, { signal });
}

/** GET /multi-frequency-events?offset&limit */
export function listClusters(params: {
  offset?: number;
  limit?: number;
  signal?: AbortSignal;
}): Promise<ListResponse<ClusterSummaryResponse>> {
  return apiRequest<ListResponse<ClusterSummaryResponse>>(
    "/multi-frequency-events",
    {
      signal: params.signal,
      searchParams: {
        offset: params.offset ?? 0,
        limit: params.limit ?? 20,
      },
    },
  );
}

/** GET /multi-frequency-events/{cluster_id} */
export function getCluster(
  clusterId: string,
  signal?: AbortSignal,
): Promise<ClusterDetailResponse> {
  return apiRequest<ClusterDetailResponse>(
    `/multi-frequency-events/${clusterId}`,
    { signal },
  );
}
