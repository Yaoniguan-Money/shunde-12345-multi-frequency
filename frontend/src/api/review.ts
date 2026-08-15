import { apiDownload, apiRequest } from "./client";
import type {
  HandlingRecordResponse,
  HumanCorrectionResponse,
  UUID,
} from "../types/api";

export interface HandlingRecordCreate {
  new_status: string;
  actor_id: string;
  description?: string | null;
  result?: string | null;
  attachment_references?: string[];
}

export interface HumanCorrectionCreate {
  correction_type: "remove_member" | "confirm_member";
  event_instance_id: UUID;
  actor_id: string;
  reason?: string | null;
}

/** POST /multi-frequency-events/{cluster_id}/handling-records (201) */
export function addHandlingRecord(
  clusterId: string,
  body: HandlingRecordCreate,
  signal?: AbortSignal,
): Promise<HandlingRecordResponse> {
  return apiRequest<HandlingRecordResponse>(
    `/multi-frequency-events/${clusterId}/handling-records`,
    { method: "POST", body: body as unknown as Record<string, unknown>, signal },
  );
}

/** GET /multi-frequency-events/{cluster_id}/handling-records */
export function listHandlingRecords(
  clusterId: string,
  signal?: AbortSignal,
): Promise<{ items: HandlingRecordResponse[] }> {
  return apiRequest<{ items: HandlingRecordResponse[] }>(
    `/multi-frequency-events/${clusterId}/handling-records`,
    { signal },
  );
}

/** POST /multi-frequency-events/{cluster_id}/corrections (201) */
export function addCorrection(
  clusterId: string,
  body: HumanCorrectionCreate,
  signal?: AbortSignal,
): Promise<HumanCorrectionResponse> {
  return apiRequest<HumanCorrectionResponse>(
    `/multi-frequency-events/${clusterId}/corrections`,
    { method: "POST", body: body as unknown as Record<string, unknown>, signal },
  );
}

/** GET /multi-frequency-events/{cluster_id}/corrections */
export function listCorrections(
  clusterId: string,
  signal?: AbortSignal,
): Promise<{ items: HumanCorrectionResponse[] }> {
  return apiRequest<{ items: HumanCorrectionResponse[] }>(
    `/multi-frequency-events/${clusterId}/corrections`,
    { signal },
  );
}

/** GET /multi-frequency-events/export.csv?cluster_id= → 下载 Blob。 */
export function exportClusterCsv(
  clusterId: string,
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string | null }> {
  return apiDownload(
    "/multi-frequency-events/export.csv",
    { cluster_id: clusterId },
    signal,
  );
}
