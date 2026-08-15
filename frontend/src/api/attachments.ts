import { apiPostForm } from "./client";
import type { AttachmentResponse } from "../types/api";

export function uploadAttachment(
  file: File,
  signal?: AbortSignal,
): Promise<AttachmentResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiPostForm<AttachmentResponse>("/attachments", form, signal);
}
