// 统一 fetch wrapper。
// baseURL 来自 import.meta.env.VITE_API_BASE_URL，默认指向本地后端。
// 支持 GET/POST JSON、POST FormData/multipart、Blob/CSV 下载。
// 非 2xx 抛 ApiError（含 status + detail）；AbortSignal 透传。

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

export type ResponseType = "json" | "blob" | "text";

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: BodyInit | Record<string, unknown> | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  searchParams?: Record<string, string | number | boolean | null | undefined>;
  responseType?: ResponseType;
}

function buildUrl(
  path: string,
  searchParams?: RequestOptions["searchParams"],
): string {
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

/** 从 FastAPI 错误响应里提取用户可读消息。 */
export function describeApiError(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail;
    if (detail && typeof detail === "object") {
      // FastAPI ValidationError 格式：{ detail: [{ msg, ... }] }
      const maybeDetail = (detail as { detail?: unknown }).detail;
      if (Array.isArray(maybeDetail) && maybeDetail.length > 0) {
        const first = maybeDetail[0] as { msg?: string };
        if (first.msg) return first.msg;
      }
      if (typeof (detail as { message?: string }).message === "string") {
        return (detail as { message: string }).message;
      }
    }
    if (typeof detail === "string" && detail.length > 0) return detail;
    return `请求失败（HTTP ${error.status}）`;
  }
  if (error instanceof Error) return error.message;
  return "未知错误";
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    method = "GET",
    body,
    headers,
    signal,
    searchParams,
    responseType = "json",
  } = options;

  const url = buildUrl(path, searchParams);
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers ?? {}),
  };

  let requestBody: BodyInit | null | undefined = undefined;
  if (body != null) {
    if (body instanceof FormData) {
      // 不要手工设置 Content-Type，让浏览器自动生成 multipart boundary
      requestBody = body;
      Reflect.deleteProperty(
        finalHeaders as { "Content-Type"?: string },
        "Content-Type",
      );
    } else if (typeof body === "object") {
      finalHeaders["Content-Type"] = "application/json";
      requestBody = JSON.stringify(body);
    } else {
      requestBody = body as BodyInit;
    }
  }

  const response = await fetch(url, {
    method,
    signal,
    headers: finalHeaders,
    body: requestBody,
  });

  if (!response.ok) {
    const detail = await parseErrorBody(response);
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (responseType === "blob") {
    return (await response.blob()) as unknown as T;
  }
  if (responseType === "text") {
    return (await response.text()) as unknown as T;
  }
  return (await response.json()) as T;
}

/** 便捷方法：GET JSON。 */
export function apiGet<T>(
  path: string,
  searchParams?: RequestOptions["searchParams"],
  signal?: AbortSignal,
): Promise<T> {
  return apiRequest<T>(path, { method: "GET", searchParams, signal });
}

/** 便捷方法：POST JSON。 */
export function apiPostJson<T>(
  path: string,
  body?: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body, signal });
}

/** 便捷方法：POST FormData。 */
export function apiPostForm<T>(
  path: string,
  formData: FormData,
  signal?: AbortSignal,
): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body: formData, signal });
}

/** 便捷方法：下载 Blob（CSV 等）。返回 { blob, filename }。单次请求。 */
export async function apiDownload(
  path: string,
  searchParams?: RequestOptions["searchParams"],
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string | null }> {
  const url = buildUrl(path, searchParams);
  const response = await fetch(url, {
    method: "GET",
    signal,
    headers: { Accept: "text/csv, */*" },
  });
  if (!response.ok) {
    const detail = await parseErrorBody(response);
    throw new ApiError(response.status, detail);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition");
  let filename: string | null = null;
  if (disposition) {
    const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)/i);
    if (match) filename = decodeURIComponent(match[1]);
  }
  return { blob, filename };
}

/** 触发浏览器下载 Blob。 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
