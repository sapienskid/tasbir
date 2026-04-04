const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8787";

export interface DesignTokens {
  colors: Record<string, string>;
  fonts: Record<string, string>;
  spacing: Record<string, string>;
}

export interface FormatConfig {
  width: number;
  height: number;
  caption_source: string;
  hashtag_count: number;
}

export interface GenerationResult {
  ok: boolean;
  slug: string;
  post_url: string;
  requested_formats: string[];
  image_source: { source: string; imageUrl: string };
  llm_output: {
    instagram_caption: string;
    twitter_caption: string;
    linkedin_caption: string;
    hashtags: string[];
    image_prompt: string;
    generated_html: string;
    carousel_slides: Array<{ heading: string; body: string }>;
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
    copy_system_prompt: string[];
    copy_user_instructions: string[];
    gemini_html_generation_system_prompt: string[];
    gemini_html_generation_user_instructions: string[];
    prompt_profiles: Record<string, any>;
    render_policy: Record<string, any>;
  }>("/config/prompts"),
  getFormats: () => request<{ formats: Record<string, FormatConfig> }>("/config/formats"),
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
