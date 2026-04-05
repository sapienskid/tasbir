export interface ResolvedSecurityConfig {
  api_auth: {
    enabled: boolean;
    header_name: string;
    require_for_generate: boolean;
    require_for_direct_content: boolean;
    require_for_webhook: boolean;
  };
  cors: {
    enabled: boolean;
    allowed_origins: string[];
    allowed_headers: string[];
    allowed_methods: string[];
    allow_credentials: boolean;
    max_age_seconds: number;
  };
  request_limits: {
    max_json_body_bytes: number;
  };
  rate_limit: {
    enabled: boolean;
    window_seconds: number;
    max_requests_per_window: number;
  };
  outbound: {
    allow_private_network_targets: boolean;
    allowed_notify_hosts: string[];
    allowed_image_hosts: string[];
  };
  apiKeys: Set<string>;
}

export interface Env {
  GOOGLE_API_KEY?: string;
  GOOGLE_MODEL?: string;
  GOOGLE_FAST_MODEL?: string;
  CLOUDFLARE_API_TOKEN?: string;
  CLOUDFLARE_ACCOUNT_ID?: string;
  LLM_MODEL?: string;
  LLM_FAST_MODEL?: string;
  IMAGE_MODEL?: string;
  AI: Ai;
  BROWSER: Fetcher;
  OUTPUT_BUCKET: R2Bucket;
  SETTINGS_KV?: KVNamespace;
  TEMPLATES_KV?: KVNamespace;
  GHOST_API_URL?: string;
  GHOST_CONTENT_API_KEY?: string;
  GHOST_WEBHOOK_TOKEN?: string;
  GHOST_WEBHOOK_SECRET?: string;
  R2_PUBLIC_BASE_URL?: string;
  BRAND_NAME?: string;
  R2_KEY_PREFIX?: string;
  NOTIFY_WEBHOOK_URL?: string;
  API_KEYS?: string;
  CORS_ALLOWED_ORIGINS?: string;
  CORS_ALLOWED_HEADERS?: string;
  CORS_ALLOW_CREDENTIALS?: string;
  CORS_MAX_AGE_SECONDS?: string;
  RATE_LIMIT_ENABLED?: string;
  RATE_LIMIT_WINDOW_SECONDS?: string;
  RATE_LIMIT_MAX_REQUESTS_PER_WINDOW?: string;
  NOTIFY_HOST_ALLOWLIST?: string;
  IMAGE_HOST_ALLOWLIST?: string;
  ALLOW_PRIVATE_NETWORK_TARGETS?: string;
  API_AUTH_REQUIRE_FOR_PREVIEW?: string;
}

const RATE_LIMIT_BUCKETS = new Map<string, { count: number; resetAt: number }>();

export class HttpError extends Error {
  status: number;
  headers?: Record<string, string>;

  constructor(status: number, message: string, headers?: Record<string, string>) {
    super(message);
    this.status = status;
    this.headers = headers;
  }
}

export function enforceApiAuth(request: Request, security: ResolvedSecurityConfig, route: string): void {
  if (!security.api_auth.enabled) return;

  const routeNeedsAuth =
    (route === "generate" && security.api_auth.require_for_generate) ||
    (route === "generate-from-content" && security.api_auth.require_for_direct_content) ||
    (route === "webhook" && security.api_auth.require_for_webhook);

  if (!routeNeedsAuth) return;

  if (security.apiKeys.size === 0) {
    throw new HttpError(500, "API auth is enabled but env var API_KEYS is not configured");
  }

  const apiKey = extractApiKey(request, security.api_auth.header_name);
  if (!apiKey || !security.apiKeys.has(apiKey)) {
    throw new HttpError(401, "Unauthorized API key");
  }
}

export function enforceRateLimit(request: Request, security: ResolvedSecurityConfig, route: string): void {
  if (!security.rate_limit.enabled) return;

  const now = Date.now();
  const windowMs = security.rate_limit.window_seconds * 1000;
  const clientId = getClientId(request);
  const key = `${route}:${clientId}`;
  const existing = RATE_LIMIT_BUCKETS.get(key);

  if (!existing || now >= existing.resetAt) {
    RATE_LIMIT_BUCKETS.set(key, { count: 1, resetAt: now + windowMs });
    return;
  }

  if (existing.count >= security.rate_limit.max_requests_per_window) {
    const retryAfter = Math.max(1, Math.ceil((existing.resetAt - now) / 1000));
    throw new HttpError(429, "Rate limit exceeded", { "retry-after": String(retryAfter) });
  }

  existing.count += 1;
}

function getClientId(request: Request): string {
  const cfConnectingIp = request.headers.get("cf-connecting-ip")?.trim();
  if (cfConnectingIp) return cfConnectingIp;
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (forwarded) return forwarded;
  const realIp = request.headers.get("x-real-ip")?.trim();
  return realIp || "anonymous";
}

function extractApiKey(request: Request, headerName: string): string | null {
  const direct = request.headers.get(headerName)?.trim();
  if (direct) return direct;
  const auth = request.headers.get("authorization")?.trim();
  if (!auth) return null;
  const bearerMatch = auth.match(/^Bearer\s+(.+)$/i);
  return bearerMatch?.[1]?.trim() || null;
}

export function resolveSecurityConfig(env: Env): ResolvedSecurityConfig {
  const merged: ResolvedSecurityConfig = {
    api_auth: {
      enabled: true,
      header_name: "x-api-key",
      require_for_generate: true,
      require_for_direct_content: true,
      require_for_webhook: false
    },
    cors: {
      enabled: true,
      allowed_origins: ["*"],
      allowed_headers: ["content-type", "authorization", "x-api-key", "x-webhook-token"],
      allowed_methods: ["GET", "POST", "OPTIONS"],
      allow_credentials: false,
      max_age_seconds: 86400
    },
    request_limits: {
      max_json_body_bytes: 256_000
    },
    rate_limit: {
      enabled: false,
      window_seconds: 60,
      max_requests_per_window: 30
    },
    outbound: {
      allow_private_network_targets: false,
      allowed_notify_hosts: [],
      allowed_image_hosts: []
    },
    apiKeys: new Set()
  };

  const envApiKeys = splitCsv(env.API_KEYS);
  merged.apiKeys = new Set(envApiKeys);

  if (env.API_AUTH_REQUIRE_FOR_PREVIEW !== undefined) {
    merged.api_auth.require_for_generate = parseBooleanString(env.API_AUTH_REQUIRE_FOR_PREVIEW, merged.api_auth.require_for_generate);
  }

  const notifyHostAllowlist = new Set(merged.outbound.allowed_notify_hosts);
  for (const host of splitCsv(env.NOTIFY_HOST_ALLOWLIST).map((e) => e.toLowerCase())) {
    notifyHostAllowlist.add(host);
  }
  if (env.NOTIFY_WEBHOOK_URL?.trim()) {
    try {
      const parsed = new URL(env.NOTIFY_WEBHOOK_URL.trim());
      notifyHostAllowlist.add(parsed.hostname.toLowerCase());
    } catch {}
  }
  merged.outbound.allowed_notify_hosts = [...notifyHostAllowlist];

  const imageHostAllowlist = new Set(merged.outbound.allowed_image_hosts);
  for (const host of splitCsv(env.IMAGE_HOST_ALLOWLIST).map((e) => e.toLowerCase())) {
    imageHostAllowlist.add(host);
  }
  merged.outbound.allowed_image_hosts = [...imageHostAllowlist];

  return merged;
}

function splitCsv(value: string | undefined): string[] {
  if (!value) return [];
  return value.split(",").map((e) => e.trim()).filter(Boolean);
}

function parseBooleanString(value: string, fallback: boolean): boolean {
  const normalized = value.trim().toLowerCase();
  if (["true", "1", "yes", "on"].includes(normalized)) return true;
  if (["false", "0", "no", "off"].includes(normalized)) return false;
  return fallback;
}

function clampNumber(value: number, min: number, max: number, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

export async function readJsonBodyWithRaw(request: Request, maxBytes: number): Promise<{ raw: string; body: unknown }> {
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) {
    throw new HttpError(415, "Request content-type must be application/json");
  }

  const contentLength = Number(request.headers.get("content-length"));
  if (Number.isFinite(contentLength) && contentLength > maxBytes) {
    throw new HttpError(413, `Request body exceeds limit (${maxBytes} bytes)`);
  }

  let raw = "";
  let body: unknown;
  try {
    raw = await request.text();
    const bytes = new TextEncoder().encode(raw).byteLength;
    if (bytes > maxBytes) {
      throw new HttpError(413, `Request body exceeds limit (${maxBytes} bytes)`);
    }
    body = JSON.parse(raw);
  } catch (error) {
    if (error instanceof HttpError) throw error;
    if (!raw) throw new HttpError(400, "Invalid or empty JSON body");
    throw new HttpError(400, "Invalid JSON body");
  }
  return { raw, body };
}

export async function readJsonBody<T>(request: Request, maxBytes: number): Promise<T> {
  const { body } = await readJsonBodyWithRaw(request, maxBytes);
  return body as T;
}

export function sanitizeHttpUrl(
  rawValue: string,
  security: ResolvedSecurityConfig,
  field: string,
  options?: { requireAllowedHost?: boolean; hostAllowlist?: string[] }
): string {
  let parsed: URL;
  try {
    parsed = new URL(rawValue);
  } catch {
    throw new HttpError(400, `${field} must be a valid absolute URL`);
  }

  if (parsed.protocol !== "https:") {
    throw new HttpError(400, `${field} must use https`);
  }
  if (parsed.username || parsed.password) {
    throw new HttpError(400, `${field} cannot include credentials`);
  }

  const hostname = parsed.hostname.toLowerCase();
  if (!security.outbound.allow_private_network_targets && isPrivateHostname(hostname)) {
    throw new HttpError(400, `${field} cannot target localhost or private network hosts`);
  }

  const allowlist = options?.hostAllowlist ?? security.outbound.allowed_notify_hosts;
  const requireAllowedHost = options?.requireAllowedHost ?? false;
  const shouldEnforce = requireAllowedHost || allowlist.length > 0;
  if (shouldEnforce && !hostMatchesAllowlist(hostname, allowlist)) {
    throw new HttpError(403, `${field} host is not in the allowed host list`);
  }

  return parsed.toString();
}

function isPrivateHostname(hostname: string): boolean {
  const host = hostname.toLowerCase();
  if (host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) return true;
  if (isPrivateIpv4(host)) return true;
  return isPrivateIpv6(host);
}

function isPrivateIpv4(hostname: string): boolean {
  const match = hostname.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!match) return false;
  const octets = match.slice(1).map(Number);
  if (octets.some((o) => o < 0 || o > 255)) return false;
  const [a, b] = octets;
  if (a === 10 || a === 127 || a === 0) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 100 && b >= 64 && b <= 127) return true;
  return false;
}

function isPrivateIpv6(hostname: string): boolean {
  const host = hostname.toLowerCase();
  if (host === "::1" || host === "0:0:0:0:0:0:0:1") return true;
  if (host.startsWith("fc") || host.startsWith("fd") || host.startsWith("fe80:")) return true;
  if (host.startsWith("::ffff:127.")) return true;
  return false;
}

function hostMatchesAllowlist(hostname: string, allowlist: string[]): boolean {
  if (allowlist.length === 0) return false;
  for (const allowed of allowlist) {
    const normalized = allowed.trim().toLowerCase();
    if (!normalized) continue;
    if (hostname === normalized || hostname.endsWith(`.${normalized}`)) return true;
  }
  return false;
}
