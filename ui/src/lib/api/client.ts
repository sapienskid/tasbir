const BASE_URL = import.meta.env.PUBLIC_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const apiKey = localStorage.getItem('apiKey') || '';

  const headers: Record<string, string> = {
    ...(apiKey ? { 'x-api-key': apiKey } : {}),
  };

  // Only set Content-Type if not already provided (e.g., for FormData uploads
  // the browser must set the multipart boundary itself)
  const isFormData = options.body instanceof FormData;
  if (!isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  // Merge caller's headers last so they can override
  if (options.headers) {
    Object.assign(headers, options.headers as Record<string, string>);
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.detail || err.error || 'Request failed');
  }
  return res.json();
}

function serialize(body: unknown): string | FormData {
  if (body instanceof FormData) return body;
  return JSON.stringify(body);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, extraHeaders?: Record<string, string>) =>
    request<T>(path, {
      method: 'POST',
      body: serialize(body),
      headers: extraHeaders,
    }),
  put: <T>(path: string, body: unknown, extraHeaders?: Record<string, string>) =>
    request<T>(path, {
      method: 'PUT',
      body: serialize(body),
      headers: extraHeaders,
    }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: serialize(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
