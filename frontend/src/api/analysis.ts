import { apiRequest } from "./client";
import type { AnalysisJobResponse, UUID } from "../types/api";

export interface AnalysisJobCreate {
  import_batch_id: UUID;
  provider_profile_id?: string;
}

/** POST /analysis-jobs (202) */
export function createAnalysisJob(
  body: AnalysisJobCreate,
  signal?: AbortSignal,
): Promise<AnalysisJobResponse> {
  return apiRequest<AnalysisJobResponse>("/analysis-jobs", {
    method: "POST",
    body: body as unknown as Record<string, unknown>,
    signal,
  });
}

/** GET /analysis-jobs/{job_id} */
export function getAnalysisJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<AnalysisJobResponse> {
  return apiRequest<AnalysisJobResponse>(`/analysis-jobs/${jobId}`, { signal });
}
