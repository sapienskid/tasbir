import { api } from "./client";

export interface Settings {
  database_url?: string;
  redis_url?: string;
  minio_endpoint?: string;
  minio_bucket?: string;
  penpot_url?: string;
  penpot_access_token?: string;
  ghost_url?: string;
  ghost_admin_api_key?: string;
  unsplash_access_key?: string;
  cors_origins?: string[];
  rate_limit_enabled?: boolean;
  rate_limit_per_minute?: number;
  log_level?: string;
}

export async function getSettings(): Promise<{ ok: boolean; data: Settings }> {
  return api.get("/settings");
}
