const DEFAULT_API_BASE = 'http://localhost:8787';

let apiBaseUrl = DEFAULT_API_BASE;
let apiKey = '';

export function setApiConfig(baseUrl: string, key: string) {
  apiBaseUrl = baseUrl || DEFAULT_API_BASE;
  apiKey = key;
}

function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${apiBaseUrl}${normalizedPath}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  };
  if (apiKey) headers['x-api-key'] = apiKey;

  const res = await fetch(buildApiUrl(path), { headers, ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `Request failed: ${res.status}`);
  }
  return res.json();
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
  html_by_format: Record<string, string>;
  template_html_by_format: Record<string, string>;
  slot_values_by_format: Record<string, Record<string, string>>;
  assets: Record<string, { format: string; key: string; url: string | null } | null>;
}

export const api = {
  getHealth: () => request<{ ok: boolean }>('/health'),
  getConfig: () => request<any>('/config'),
  getFormats: () => request<{ formats: Record<string, FormatConfig> }>('/config/formats'),

  getSettings: () => request<any>('/settings'),
  saveSettings: (settings: any) =>
    request<{ ok: boolean }>('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  getTokens: () => request<any>('/tokens'),
  saveTokens: (tokens: any) =>
    request<{ ok: boolean }>('/tokens', {
      method: 'PUT',
      body: JSON.stringify(tokens),
    }),
  generateTokens: (body: { vibe?: string; primaryHint?: string; secondaryHint?: string }) =>
    request<any>('/generate-tokens', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getTemplates: () => request<{ templates: any[] }>('/templates'),
  getTemplate: (id: string) => request<{ metadata: any; html: string }>(`/templates/${id}`),

  generateFromContent: (body: {
    title: string;
    content: string;
    excerpt?: string;
    tags?: string[];
    output?: { formats?: string[]; postCount?: number };
    prompt?: string;
    image?: { mode?: string };
    designTokens?: any;
  }) =>
    request<GenerationResult>('/generate-from-content', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  generateFromContentStream: (body: {
    title: string;
    content: string;
    excerpt?: string;
    tags?: string[];
    output?: { formats?: string[]; postCount?: number };
    prompt?: string;
    image?: { mode?: string };
    designTokens?: any;
  }) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (apiKey) headers['x-api-key'] = apiKey;
    return fetch(buildApiUrl('/generate-from-content/stream'), {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
  },

  renderHtml: (body: {
    html: string;
    width: number;
    height: number;
    format: string;
    slug: string;
    designTokens?: any;
    slot_values?: Record<string, string>;
  }) =>
    request<{ ok: boolean; asset: { format: string; key: string; url: string | null } }>('/render-html', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getEditedContent: (slug: string, format: string) =>
    request<{ ok: boolean; html: string; slot_values: Record<string, string>; updatedAt: string }>(
      `/edited-content?slug=${encodeURIComponent(slug)}&format=${encodeURIComponent(format)}`
    ),
};
