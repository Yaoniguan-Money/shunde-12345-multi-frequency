import { apiRequest } from "./client";

export interface ProviderProfile {
  profile_id: string;
  deployment_kind: "local" | "cloud";
  display_name: string;
  configured: boolean;
  validation_status: "configured" | "validated" | "unavailable" | "validation_failed";
  last_validated_at: string | null;
  model_display_name: string | null;
  service_description: string;
  configuration_version: string;
}

export interface ProviderValidationResponse {
  profile: ProviderProfile;
  stages: Array<{
    name: string;
    status: "passed" | "failed";
    latency_ms: number;
    model_id?: string | null;
    error?: string | null;
  }>;
}

export function listProviderProfiles(signal?: AbortSignal): Promise<{ items: ProviderProfile[] }> {
  return apiRequest<{ items: ProviderProfile[] }>("/ai/provider-profiles", { signal });
}

export function validateProviderProfile(
  profileId: string,
  signal?: AbortSignal,
): Promise<ProviderValidationResponse> {
  return apiRequest<ProviderValidationResponse>(
    `/ai/provider-profiles/${encodeURIComponent(profileId)}/validate`,
    { method: "POST", signal },
  );
}
