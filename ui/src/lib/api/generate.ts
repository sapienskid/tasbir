import { api } from "./client";

export interface GenerateRequest {
  content: string;
  title?: string;
  excerpt?: string;
  tags?: string[];
  source_url?: string;
  feature_image?: string;
  requested_formats?: string[];
  brand?: Record<string, unknown>;
  campaign?: Record<string, unknown>;
  design_tokens?: Record<string, unknown>;
}

export interface GenerateResponse {
  task_id: string;
  status: string;
}

export interface TaskResult {
  id: string;
  celery_task_id: string | null;
  status: string;
  source_data: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  progress: number;
  created_at: string;
  updated_at: string;
}

export async function startGeneration(
  data: GenerateRequest
): Promise<GenerateResponse> {
  return api.post("/generate", data);
}

export async function getTask(id: string): Promise<TaskResult> {
  return api.get(`/tasks/${id}`);
}

export async function listTasks(
  limit = 50,
  offset = 0,
  status?: string
): Promise<{ id: string; status: string; progress: number }[]> {
  let path = `/tasks?limit=${limit}&offset=${offset}`;
  if (status) path += `&status=${status}`;
  return api.get(path);
}

export function streamTask(
  id: string,
  onProgress: (data: { status: string; progress: number; error?: string }) => void,
  onComplete: (data: { result: Record<string, unknown> }) => void,
  onError: (error: string) => void
): () => void {
  const BASE_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";
  const eventSource = new EventSource(`${BASE_URL}/tasks/${id}/stream`);

  eventSource.addEventListener("progress", (event) => {
    onProgress(JSON.parse(event.data));
  });

  eventSource.addEventListener("complete", (event) => {
    onComplete(JSON.parse(event.data));
    eventSource.close();
  });

  eventSource.addEventListener("error", () => {
    onError("Connection lost");
    eventSource.close();
  });

  return () => eventSource.close();
}
