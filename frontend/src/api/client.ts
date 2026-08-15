// 统一 fetch wrapper。
// baseURL 来自 import.meta.env.VITE_API_BASE_URL，默认指向本地后端。
// 非 2xx 抛 ApiError（含 status + detail）；AbortSignal 透传；JSON 解析。

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8080";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  signal?: AbortSignal;
  searchParams?: Record<string, string | number | boolean | null | undefined>;
}

function buildUrl(path: string, searchParams?: RequestOptions["searchParams"]): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (searchParams) {
    for (const [key, value] of Object.entries(searchParams)) {
      if (value === null || value === undefined) continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function parseErrorBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = await response.text().catch(() => null);
    return text ?? null;
  }
  return await response.json().catch(() => null);
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = buildUrl(path, options.searchParams);
  const response = await fetch(url, {
    method: "GET",
    signal: options.signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const detail = await parseErrorBody(response);
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
