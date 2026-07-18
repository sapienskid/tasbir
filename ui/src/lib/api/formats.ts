import { api } from "./client";

export interface Format {
  id: string;
  name: string;
  width: number;
  height: number;
  ai_instruction: string;
  enabled: boolean;
}

export async function listFormats(
  enabledOnly = true
): Promise<Format[]> {
  return api.get(`/formats?enabled_only=${enabledOnly}`);
}
