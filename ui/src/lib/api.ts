const RAW_API_BASE = (import.meta.env.VITE_API_BASE || "").trim();
const API_BASE = RAW_API_BASE.replace(/\/+$/, "");
const API_KEY_STORAGE_KEY = "tasbir:api-key";

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
  assets: Record<string, { format: string; key: string; url: string | null } | null>;
  agentic?: {
    mode: string;
    prompt_profile: string;
    applied_roles: string[];
    warnings: string[];
  };
  variants?: Array<{
    index: number;
    image_source: { source: string; imageUrl: string };
    llm_output: { generated_html: string };
    assets: Record<string, { format: string; key: string; url: string | null } | null>;
  }>;
}

function readStoredApiKey(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(API_KEY_STORAGE_KEY)?.trim() || "";
  } catch {
    return "";
  }
}

let _apiKey = (import.meta.env.VITE_API_KEY || "").trim() || readStoredApiKey();

export function setApiKey(key: string) {
  _apiKey = key.trim();
  if (typeof window === "undefined") return;
  try {
    if (_apiKey) {
      window.localStorage.setItem(API_KEY_STORAGE_KEY, _apiKey);
    } else {
      window.localStorage.removeItem(API_KEY_STORAGE_KEY);
    }
  } catch {
    // Ignore storage errors (private mode, quota, etc.) and still keep in-memory key.
  }
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
  
  getSavedTokens: () => request<any>("/tokens"),
  saveTokens: (tokens: any) => request<{ ok: boolean }>("/tokens", {
    method: "PUT",
    body: JSON.stringify(tokens),
  }),
  generateTokens: (body: { vibe?: string; primaryHint?: string; secondaryHint?: string }) => request<any>("/generate-tokens", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  
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
    designTokens?: any;
  }) => request<GenerationResult>("/generate", {
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

  saveToR2: (key: string, dataUri: string) => request<{ ok: boolean; url: string }>("/save-to-r2", {
    method: "POST",
    body: JSON.stringify({ key, dataUri }),
  }),

  getSettings: () => request<any>("/settings"),
  saveSettings: (settings: any) => request<{ ok: boolean }>("/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  }),
  patchSettings: (patch: any) => request<{ ok: boolean; settings: any }>("/settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
  }),

  getTemplates: () => request<{ templates: any[] }>("/templates"),
  getTemplate: (id: string) => request<{ metadata: any; html: string }>(`/templates/${id}`),
  saveTemplate: (id: string, html: string, metadata?: { name?: string; description?: string; category?: string }) =>
    request<{ ok: boolean; metadata: any }>(`/templates/${id}`, {
      method: "PUT",
      body: JSON.stringify({ html, ...metadata }),
    }),
  deleteTemplate: (id: string) => request<{ ok: boolean }>(`/templates/${id}`, {
    method: "DELETE",
  }),
  toggleTemplate: (id: string, enabled: boolean) => request<{ ok: boolean; metadata: any }>(`/templates/${id}/toggle`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  }),
  validateTemplate: (html: string) => request<{ valid: boolean; errors: string[]; slots: string[] }>(`/templates/validate`, {
    method: "POST",
    body: JSON.stringify({ html }),
  }),
};
