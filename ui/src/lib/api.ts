const RAW_API_BASE = (import.meta.env.VITE_API_BASE || "").trim();
const API_BASE = RAW_API_BASE.replace(/\/+$/, "");

function buildApiUrl(path: string): string {
  if (!API_BASE) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalizedPath}`;
}

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
  html_cache?: {
    enabled: boolean;
    mode: "off" | "read-only" | "write-only" | "read-write";
    key: string | null;
    summary: { hits: number; misses: number; writes: number };
    primary_variant_by_format: Record<string, "hit" | "miss">;
  };
  assets: Record<string, { format: string; key: string; url: string | null } | null>;
}

export interface HtmlCacheOptions {
  mode?: "off" | "read-only" | "write-only" | "read-write";
  key?: string;
}

export interface RenderFromCacheResult {
  ok: boolean;
  slug: string;
  requested_formats: string[];
  cache_key_prefix: string;
  variant_index: number;
  missing_formats: string[];
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

  const res = await fetch(buildApiUrl(path), {
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
    output?: { formats?: string[]; postCount?: number };
    prompt?: string;
    image?: { mode?: string };
    htmlCache?: HtmlCacheOptions;
    agent?: { mode?: string; promptProfile?: string };
    designTokens?: any;
  }) => request<GenerationResult>("/generate-from-content", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  generate: (body: {
    slug: string;
    output?: { formats?: string[]; postCount?: number };
    prompt?: string;
    image?: { mode?: string };
    htmlCache?: HtmlCacheOptions;
    designTokens?: any;
  }) => request<GenerationResult>("/generate", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  renderFromCache: (body: {
    slug: string;
    output?: { formats?: string[]; postCount?: number };
    htmlCache?: HtmlCacheOptions;
    variantIndex?: number;
    designTokens?: any;
  }) => request<RenderFromCacheResult>("/render-from-cache", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  fetchAssetBlobUrl: async (key: string): Promise<string> => {
    const headers: Record<string, string> = {};
    if (_apiKey) {
      headers["x-api-key"] = _apiKey;
    }
    const response = await fetch(buildApiUrl(`/asset?key=${encodeURIComponent(key)}`), { headers });
    if (!response.ok) {
      const text = await response.text().catch(() => response.statusText);
      throw new Error(text || `Asset fetch failed: ${response.status}`);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },
};
