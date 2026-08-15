import { apiRequest } from "./client";
import type { UUID } from "../types/api";

/** 后端 ImportMappingRequest：四个可映射字段，blank 会被规范化为 None。 */
export interface ImportMapping {
  source_row_number?: string | null;
  external_work_order_number?: string | null;
  title?: string | null;
  content?: string | null;
}

export interface ImportPreviewResponse {
  columns: string[];
  total_rows: number;
  suggested_mapping: Record<string, string>;
}

export interface ImportResponse {
  batch_id: UUID;
  status: string;
  total_rows: number;
  successful_rows: number;
  failed_rows: number;
  duplicate_rows: number;
  checkpoint_row: number;
  idempotent: boolean;
}

/** POST /imports/preview (multipart: file + sheet_name?) */
export function previewImport(params: {
  file: File;
  sheetName?: string;
  signal?: AbortSignal;
}): Promise<ImportPreviewResponse> {
  const form = new FormData();
  form.append("file", params.file);
  if (params.sheetName) form.append("sheet_name", params.sheetName);
  return apiRequest<ImportPreviewResponse>("/imports/preview", {
    method: "POST",
    body: form,
    signal: params.signal,
  });
}

/** POST /imports (multipart: file + mapping JSON + sheet_name?) */
export function executeImport(params: {
  file: File;
  mapping: ImportMapping;
  sheetName?: string;
  signal?: AbortSignal;
}): Promise<ImportResponse> {
  const form = new FormData();
  form.append("file", params.file);
  form.append("mapping", JSON.stringify(params.mapping));
  if (params.sheetName) form.append("sheet_name", params.sheetName);
  return apiRequest<ImportResponse>("/imports", {
    method: "POST",
    body: form,
    signal: params.signal,
  });
}
