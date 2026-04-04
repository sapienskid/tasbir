const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8787";

export interface DesignTokens {
  colors: Record<string, string>;
  fonts: Record<string, string>;
  spacing: Record<string, string>;
}

export interface FormatConfig {
  width: number;
  height: number;
  name?: string;
  aiInstruction?: string;
}

export interface GenerationResult {
  ok: boolean;
  slug: string;
  post_url: string;
  requested_formats: string[];
  image_source: { source: string; imageUrl: string };
  llm_output: {
    generated_html: string;
  };
  assets: Record<string, { format: string; key: string; url: string | null } | null>;
}

let _apiKey = import.meta.env.VITE_API_KEY || "";

export function setApiKey(key: string) {
  _apiKey = key;
}

export function getApiKey() {
  return _apiKey;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(options?.headers as Record<string, string> || {}) };
  if (_apiKey) {
    headers["x-api-key"] = _apiKey;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getHealth: () => request<{ ok: boolean }>("/health"),
  getConfig: () => request<any>("/config"),
  getDesignTokens: () => request<{ tokens: DesignTokens; tailwindConfig: string }>("/config/design-tokens"),
  getPrompts: () => request<{
    html_layout_system_prompt: string[];
    html_layout_user_instructions: string[];
    prompt_profiles: Record<string, any>;
    render_policy: Record<string, any>;
  }>("/config/prompts"),
  getFormats: () => request<{ formats: Record<string, FormatConfig> }>("/config/formats"),
  
  // Token management
  getSavedTokens: () => request<any>("/tokens"),
  saveTokens: (tokens: any) => request<{ ok: boolean }>("/tokens", {
    method: "PUT",
    body: JSON.stringify(tokens),
  }),
  generateTokens: (body: { vibe?: string; primaryHint?: string; secondaryHint?: string }) => request<any>("/generate-tokens", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  
  // Format management
  getAllFormats: () => request<Record<string, FormatConfig>>("/formats"),
  saveFormat: (id: string, format: FormatConfig) => request<{ ok: boolean; format: FormatConfig }>(`/formats/${id}`, {
    method: "PUT",
    body: JSON.stringify(format),
  }),
  deleteFormat: (id: string) => request<{ ok: boolean }>(`/formats/${id}`, {
    method: "DELETE",
  }),
  
  generateFromContent: (body: {
    title: string;
    content: string;
    excerpt?: string;
    tags?: string[];
    formats?: string[];
    prompt?: string;
    image?: { mode?: string };
    agent?: { mode?: string; promptProfile?: string };
  }) => request<GenerationResult>("/generate-from-content", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  generate: (body: {
    slug: string;
    formats?: string[];
    prompt?: string;
    image?: { mode?: string };
  }) => request<GenerationResult>("/generate", {
    method: "POST",
    body: JSON.stringify(body),
  }),
};
