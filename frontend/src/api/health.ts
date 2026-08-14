export type Liveness = { status: "alive" };

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8080";

export async function fetchLiveness(signal?: AbortSignal): Promise<Liveness> {
  const response = await fetch(`${apiBaseUrl}/health/live`, { signal });
  if (!response.ok) {
    throw new Error(`Backend health check failed with ${response.status}`);
  }
  return (await response.json()) as Liveness;
}

