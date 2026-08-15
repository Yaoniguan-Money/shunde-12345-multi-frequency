import { apiRequest } from "./client";
import type {
  DependenciesResponse,
  LivenessResponse,
  ReadinessResponse,
} from "../types/api";

export type { DependenciesResponse, LivenessResponse, ReadinessResponse };

export function fetchLiveness(signal?: AbortSignal): Promise<LivenessResponse> {
  return apiRequest<LivenessResponse>("/health/live", { signal });
}

export function fetchReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return apiRequest<ReadinessResponse>("/health/ready", { signal });
}

export function fetchDependencies(
  signal?: AbortSignal,
): Promise<DependenciesResponse> {
  return apiRequest<DependenciesResponse>("/health/dependencies", { signal });
}
