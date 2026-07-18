import { describe, it, expect, vi, beforeEach } from 'vitest';

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('API client', () => {
  it('uses base URL from env', async () => {
    const orig = import.meta.env.PUBLIC_API_URL;
    // @ts-expect-error testing
    import.meta.env.PUBLIC_API_URL = 'http://test:8000';

    const { api } = await import('$lib/api/client');
    const mock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    await api.get('/health');
    expect(mock).toHaveBeenCalledWith('http://test:8000/health', expect.any(Object));

    // @ts-expect-error testing
    import.meta.env.PUBLIC_API_URL = orig;
  });

  it('includes API key header when set', async () => {
    localStorage.setItem('apiKey', 'test-key-123');

    const { api } = await import('$lib/api/client');
    const mock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    await api.get('/test');
    const call = mock.mock.calls[0];
    const headers = (call[1] as Record<string, unknown>).headers as Record<string, string>;
    expect(headers['x-api-key']).toBe('test-key-123');
  });

  it('throws on error response', async () => {
    const { api } = await import('$lib/api/client');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    );

    await expect(api.get('/bad')).rejects.toThrow('Not found');
  });
});
