import puppeteer from "@cloudflare/puppeteer";
import {
  chooseTemplateAssignments,
  generateStructuredCopy,
  normalizeSourceContent,
  type LlmOutput,
  type LlmPromptOverrides,
  type TemplateChoiceCandidate
} from "./ai";
import {
  getTemplateDimensions,
  isTemplateKind,
  listRequiredSlotKeys,
  listTemplateFields,
  listTemplateKinds,
  previewParamsFromUrl,
  resolveTemplateId,
  renderTemplate,
  type BrandTokenOverrides,
  type BaseTemplateParams,
  type CarouselTemplateParams,
  type TemplateControlSet,
  type TemplateKind
} from "./templates";
import { PIPELINE_CONFIG, TEMPLATE_FILES } from "./generated/template-assets";

interface Env {
  AI: Ai;
  BROWSER: Fetcher;
  OUTPUT_BUCKET: R2Bucket;
  GHOST_API_URL: string;
  GHOST_CONTENT_API_KEY: string;
  GHOST_WEBHOOK_TOKEN?: string;
  PEXELS_API_KEY?: string;
  R2_PUBLIC_BASE_URL?: string;
  DEFAULT_BRAND_COLOR?: string;
  BRAND_NAME?: string;
  LLM_MODEL?: string;
  IMAGE_MODEL?: string;
  R2_KEY_PREFIX?: string;
  NOTIFY_WEBHOOK_URL?: string;
  API_KEYS?: string;
  CORS_ALLOWED_ORIGINS?: string;
  CORS_ALLOWED_HEADERS?: string;
  CORS_ALLOW_CREDENTIALS?: string;
  CORS_MAX_AGE_SECONDS?: string;
  NOTIFY_HOST_ALLOWLIST?: string;
  IMAGE_HOST_ALLOWLIST?: string;
  ALLOW_PRIVATE_NETWORK_TARGETS?: string;
}

interface ImageGenerationOptions {
  mode?: "auto" | "none" | "feature" | "stock" | "ai" | "custom";
  customUrl?: string;
  prompt?: string;
  allowStock?: boolean;
  allowAi?: boolean;
  preferFeature?: boolean;
}

interface OutputOptions {
  formats?: TemplateKind[];
  carouselSlides?: number;
  postCount?: number;
}

interface GenerateRequestBody {
  slug?: string;
  url?: string;
  brandingColor?: string;
  brandName?: string;
  prompt?: string;
  templateIds?: Partial<Record<TemplateKind, string>>;
  slotOverrides?: Record<string, string>;
  brandTokens?: BrandTokenOverrides;
  design?: TemplateControlSet;
  storage?: StorageOptions;
  notifyUrl?: string;
  llm?: LlmPromptOverrides;
  image?: ImageGenerationOptions;
  output?: OutputOptions;
}

interface DirectContentRequestBody {
  title?: string;
  excerpt?: string;
  content?: string;
  body?: string;
  slug?: string;
  url?: string;
  feature_image?: string;
  tags?: string[] | string;
  primary_tag?: string;
  brandingColor?: string;
  brandName?: string;
  prompt?: string;
  templateIds?: Partial<Record<TemplateKind, string>>;
  slotOverrides?: Record<string, string>;
  brandTokens?: BrandTokenOverrides;
  design?: TemplateControlSet;
  storage?: StorageOptions;
  notifyUrl?: string;
  llm?: LlmPromptOverrides;
  image?: ImageGenerationOptions;
  output?: OutputOptions;
}

interface StorageOptions {
  mode?: "overwrite" | "versioned";
  includeDate?: boolean;
  runId?: string;
}

interface GhostWebhookPost {
  current?: {
    slug?: string;
    url?: string;
  };
  slug?: string;
  url?: string;
}

interface GhostWebhookPayload {
  post?: GhostWebhookPost;
  slug?: string;
  url?: string;
}

interface GhostPost {
  id: string;
  title: string;
  slug: string;
  url: string;
  html?: string;
  plaintext?: string;
  excerpt?: string;
  custom_excerpt?: string;
  feature_image?: string;
  tags?: Array<{ name?: string }>;
  primary_tag?: { name?: string };
}

interface SelectedImage {
  source: "feature" | "stock" | "ai" | "custom" | "none";
  imageUrl: string;
  attribution?: string;
  sourceUrl?: string;
}

interface StoredAsset {
  format: string;
  key: string;
  url: string | null;
}

interface TemplatePlan {
  templateIds: Partial<Record<TemplateKind, string>>;
  requiredSlotKeys: string[];
  slotFields: import("./templates").TemplateFieldDeclaration[];
}

interface GenerationResult {
  ok: true;
  slug: string;
  post_url: string;
  requested_formats: TemplateKind[];
  image_source: SelectedImage;
  template_plan: {
    required_slot_keys: string[];
    template_ids: Partial<Record<TemplateKind, string>>;
  };
  llm_output: LlmOutput;
  assets: {
    instagram_portrait: StoredAsset | null;
    instagram_square: StoredAsset | null;
    instagram_story: StoredAsset | null;
    twitter_card: StoredAsset | null;
    linkedin_post: StoredAsset | null;
    carousel: StoredAsset[];
  };
  variants?: Array<{
    index: number;
    image_source: SelectedImage;
    template_plan: GenerationResult["template_plan"];
    llm_output: LlmOutput;
    assets: GenerationResult["assets"];
  }>;
}

type ProtectedRoute = "preview" | "catalog" | "generate" | "generate-from-content" | "webhook";

interface SecurityConfig {
  api_auth: {
    enabled: boolean;
    header_name: string;
    require_for_preview: boolean;
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
    slot_overrides_max_keys: number;
    template_ids_max_keys: number;
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
}

interface ResolvedSecurityConfig extends SecurityConfig {
  apiKeys: Set<string>;
}

const SECURITY_DEFAULTS: SecurityConfig = {
  api_auth: {
    enabled: true,
    header_name: "x-api-key",
    require_for_preview: true,
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
    max_json_body_bytes: 256_000,
    slot_overrides_max_keys: 40,
    template_ids_max_keys: 5
  },
  rate_limit: {
    enabled: true,
    window_seconds: 60,
    max_requests_per_window: 30
  },
  outbound: {
    allow_private_network_targets: false,
    allowed_notify_hosts: [],
    allowed_image_hosts: []
  }
};

const RATE_LIMIT_BUCKETS = new Map<string, { count: number; resetAt: number }>();
const PROTECTED_ROUTE_SET = new Set<ProtectedRoute>(["preview", "catalog", "generate", "generate-from-content", "webhook"]);

const DEFAULT_IMAGE_MODEL = PIPELINE_CONFIG.generation.image.default_model;
const STOCK_TOPIC_PATTERN = createTopicKeywordPattern(PIPELINE_CONFIG.generation.stock_topic_keywords);
const DEFAULT_CAROUSEL_SLIDES = PIPELINE_CONFIG.generation.carousel_required_slides;
const TEMPLATE_KINDS = listTemplateKinds();
const TEMPLATE_KIND_SET = new Set(TEMPLATE_KINDS);
const TEMPLATE_REGISTRY = PIPELINE_CONFIG.templates as ReadonlyArray<{
  id: string;
  label: string;
  description?: string;
}>;
// All discovered templates support all formats
const ALL_TEMPLATE_IDS = new Set(TEMPLATE_REGISTRY.map((t) => t.id));
const TEMPLATE_IDS_BY_FORMAT: Record<TemplateKind, Set<string>> = TEMPLATE_KINDS.reduce(
  (acc, format) => {
    acc[format] = ALL_TEMPLATE_IDS;
    return acc;
  },
  {} as Record<TemplateKind, Set<string>>
);

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const security = resolveSecurityConfig(env);

    try {
      if (request.method === "OPTIONS") {
        return finalizeResponse(request, security, handleCorsPreflight(request, security));
      }

      if (request.method === "GET" && url.pathname.startsWith("/template/")) {
        enforceRouteSecurity(request, security, "preview");
        if (!PIPELINE_CONFIG.features.enable_template_preview) {
          throw new HttpError(403, "Template preview route is disabled by configuration");
        }
        return finalizeResponse(request, security, handleTemplatePreview(url));
      }

      if (request.method === "GET" && url.pathname === "/template-catalog") {
        enforceRouteSecurity(request, security, "catalog");
        return finalizeResponse(request, security, handleTemplateCatalog());
      }

      if (request.method === "GET" && url.pathname === "/health") {
        return finalizeResponse(request, security, json({ ok: true }));
      }

      if (request.method === "POST" && url.pathname === "/generate") {
        enforceRouteSecurity(request, security, "generate");
        const body = validateGenerateRequestBody(
          await readJsonBody(request, security.request_limits.max_json_body_bytes),
          security
        );
        const result = await runPipeline(body, env, security);
        const notifyUrl = resolveNotifyUrl(body.notifyUrl, env.NOTIFY_WEBHOOK_URL, security);
        if (notifyUrl && PIPELINE_CONFIG.features.enable_notifications) {
          ctx.waitUntil(sendNotification(notifyUrl, result, security));
        }
        return finalizeResponse(request, security, json(result));
      }

      if (request.method === "POST" && url.pathname === "/generate-from-content") {
        enforceRouteSecurity(request, security, "generate-from-content");
        const body = validateDirectContentRequestBody(
          await readJsonBody(request, security.request_limits.max_json_body_bytes),
          security
        );
        const post = buildPostFromDirectContent(body, security);
        const result = await runPipelineFromPost(post, env, body, security);
        const notifyUrl = resolveNotifyUrl(body.notifyUrl, env.NOTIFY_WEBHOOK_URL, security);
        if (notifyUrl && PIPELINE_CONFIG.features.enable_notifications) {
          ctx.waitUntil(sendNotification(notifyUrl, result, security));
        }
        return finalizeResponse(request, security, json(result));
      }

      if (request.method === "POST" && url.pathname === "/webhook/ghost") {
        enforceRouteSecurity(request, security, "webhook");
        const expected = env.GHOST_WEBHOOK_TOKEN?.trim();
        if (!expected) {
          throw new HttpError(500, "Missing env var GHOST_WEBHOOK_TOKEN");
        }
        const provided = request.headers.get("x-webhook-token")?.trim();
        if (!provided || provided !== expected) {
          throw new HttpError(401, "Unauthorized webhook token");
        }

        const payload = validateWebhookPayload(await readJsonBody(request, security.request_limits.max_json_body_bytes));
        const slug = extractSlugFromWebhook(payload);
        if (!slug) {
          throw new HttpError(400, "Could not resolve slug from Ghost webhook payload");
        }

        const result = await runPipeline({ slug }, env, security);
        const notifyUrl = resolveNotifyUrl(undefined, env.NOTIFY_WEBHOOK_URL, security);
        if (notifyUrl && PIPELINE_CONFIG.features.enable_notifications) {
          ctx.waitUntil(sendNotification(notifyUrl, result, security));
        }
        return finalizeResponse(request, security, json(result));
      }

      return finalizeResponse(
        request,
        security,
        json(
          {
            error: "Not found",
            routes: [
              "POST /generate",
              "POST /generate-from-content",
              "POST /webhook/ghost",
              "GET /template-catalog",
              ...TEMPLATE_KINDS.map((kind) => `GET /template/${kind}?...`)
            ]
          },
          404
        )
      );
    } catch (error) {
      return finalizeResponse(request, security, handleError(error));
    }
  }
};

function handleTemplatePreview(url: URL): Response {
  const kind = matchTemplateKind(url.pathname);
  if (!kind) {
    return json({ error: "Unknown template type" }, 404);
  }

  const params = previewParamsFromUrl(kind, url);
  const html = renderTemplate(kind, params);
  return new Response(html, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}

function handleTemplateCatalog(): Response {
  const templateFileMap = TEMPLATE_FILES as Record<string, string>;
  const allKinds = listTemplateKinds();

  const templates = (PIPELINE_CONFIG.templates as ReadonlyArray<{
    id: string;
    label: string;
    description?: string;
    file: string;
  }>).map((template) => {
    const templateMarkup = templateFileMap[template.id] ?? "";
    const fields = listTemplateFields(template.id);
    return {
      id: template.id,
      label: template.label,
      description: template.description ?? "",
      file: template.file,
      fields,
      required_slot_keys: fields.map((f) => f.key),
      version: stableShortHash(`${template.id}:${templateMarkup}`)
    };
  });

  // All templates support all formats in the auto-discovery model
  const templatesByFormat = allKinds.reduce(
    (acc, kind) => {
      acc[kind] = templates.map((t) => t.id);
      return acc;
    },
    {} as Record<TemplateKind, string[]>
  );

  const formats = allKinds.map((kind) => ({
    id: kind,
    width: PIPELINE_CONFIG.formats[kind].width,
    height: PIPELINE_CONFIG.formats[kind].height,
    caption_source: PIPELINE_CONFIG.formats[kind].caption_source,
    hashtag_count: PIPELINE_CONFIG.formats[kind].hashtag_count,
    default_template_id: PIPELINE_CONFIG.formats[kind].default_template_id
  }));

  const catalogVersion = stableShortHash(
    JSON.stringify({
      schema_version: PIPELINE_CONFIG.schema_version,
      templates: templates.map((template) => `${template.id}:${template.version}`)
    })
  );

  return json({
    ok: true,
    schema_version: PIPELINE_CONFIG.schema_version,
    catalog_version: catalogVersion,
    defaults: {
      carousel_required_slides: PIPELINE_CONFIG.generation.carousel_required_slides
    },
    formats,
    templates,
    templates_by_format: templatesByFormat
  });
}

function matchTemplateKind(pathname: string): TemplateKind | null {
  const candidate = pathname.replace(/^\/template\//, "").replace(/\/+$/, "").trim();
  return isTemplateKind(candidate) ? candidate : null;
}


function resolveSecurityConfig(env: Env): ResolvedSecurityConfig {
  const raw = ((PIPELINE_CONFIG as unknown as { security?: Partial<SecurityConfig> }).security ?? {}) as Partial<SecurityConfig>;

  const merged: SecurityConfig = {
    api_auth: {
      enabled: raw.api_auth?.enabled ?? SECURITY_DEFAULTS.api_auth.enabled,
      header_name: raw.api_auth?.header_name ?? SECURITY_DEFAULTS.api_auth.header_name,
      require_for_preview: raw.api_auth?.require_for_preview ?? SECURITY_DEFAULTS.api_auth.require_for_preview,
      require_for_generate: raw.api_auth?.require_for_generate ?? SECURITY_DEFAULTS.api_auth.require_for_generate,
      require_for_direct_content:
        raw.api_auth?.require_for_direct_content ?? SECURITY_DEFAULTS.api_auth.require_for_direct_content,
      require_for_webhook: raw.api_auth?.require_for_webhook ?? SECURITY_DEFAULTS.api_auth.require_for_webhook
    },
    cors: {
      enabled: raw.cors?.enabled ?? SECURITY_DEFAULTS.cors.enabled,
      allowed_origins: normalizeLowercaseList(raw.cors?.allowed_origins, SECURITY_DEFAULTS.cors.allowed_origins),
      allowed_headers: normalizeLowercaseList(
        raw.cors?.allowed_headers,
        SECURITY_DEFAULTS.cors.allowed_headers
      ),
      allowed_methods: normalizeUppercaseList(raw.cors?.allowed_methods, SECURITY_DEFAULTS.cors.allowed_methods),
      allow_credentials: raw.cors?.allow_credentials ?? SECURITY_DEFAULTS.cors.allow_credentials,
      max_age_seconds: clampNumber(raw.cors?.max_age_seconds, 0, 86400, SECURITY_DEFAULTS.cors.max_age_seconds)
    },
    request_limits: {
      max_json_body_bytes: Math.round(
        clampNumber(
          raw.request_limits?.max_json_body_bytes,
          4_096,
          10_485_760,
          SECURITY_DEFAULTS.request_limits.max_json_body_bytes
        )
      ),
      slot_overrides_max_keys: Math.round(
        clampNumber(
          raw.request_limits?.slot_overrides_max_keys,
          1,
          200,
          SECURITY_DEFAULTS.request_limits.slot_overrides_max_keys
        )
      ),
      template_ids_max_keys: Math.round(
        clampNumber(
          raw.request_limits?.template_ids_max_keys,
          1,
          20,
          SECURITY_DEFAULTS.request_limits.template_ids_max_keys
        )
      )
    },
    rate_limit: {
      enabled: raw.rate_limit?.enabled ?? SECURITY_DEFAULTS.rate_limit.enabled,
      window_seconds: Math.round(
        clampNumber(raw.rate_limit?.window_seconds, 1, 3600, SECURITY_DEFAULTS.rate_limit.window_seconds)
      ),
      max_requests_per_window: Math.round(
        clampNumber(
          raw.rate_limit?.max_requests_per_window,
          1,
          10_000,
          SECURITY_DEFAULTS.rate_limit.max_requests_per_window
        )
      )
    },
    outbound: {
      allow_private_network_targets:
        env.ALLOW_PRIVATE_NETWORK_TARGETS !== undefined
          ? parseBooleanString(env.ALLOW_PRIVATE_NETWORK_TARGETS, SECURITY_DEFAULTS.outbound.allow_private_network_targets)
          : raw.outbound?.allow_private_network_targets ?? SECURITY_DEFAULTS.outbound.allow_private_network_targets,
      allowed_notify_hosts: normalizeLowercaseList(raw.outbound?.allowed_notify_hosts, SECURITY_DEFAULTS.outbound.allowed_notify_hosts),
      allowed_image_hosts: normalizeLowercaseList(raw.outbound?.allowed_image_hosts, SECURITY_DEFAULTS.outbound.allowed_image_hosts)
    }
  };

  const envApiKeys = splitCsv(env.API_KEYS);
  const envAllowedOrigins = splitCsv(env.CORS_ALLOWED_ORIGINS);
  if (envAllowedOrigins.length > 0) {
    merged.cors.allowed_origins = envAllowedOrigins.map((origin) => origin.toLowerCase());
  }

  const envAllowedHeaders = splitCsv(env.CORS_ALLOWED_HEADERS);
  if (envAllowedHeaders.length > 0) {
    merged.cors.allowed_headers = envAllowedHeaders.map((header) => header.toLowerCase());
  }

  if (env.CORS_ALLOW_CREDENTIALS !== undefined) {
    merged.cors.allow_credentials = parseBooleanString(env.CORS_ALLOW_CREDENTIALS, merged.cors.allow_credentials);
  }
  if (env.CORS_MAX_AGE_SECONDS !== undefined) {
    merged.cors.max_age_seconds = Math.round(
      clampNumber(Number(env.CORS_MAX_AGE_SECONDS), 0, 86400, merged.cors.max_age_seconds)
    );
  }

  const notifyHostAllowlist = new Set(merged.outbound.allowed_notify_hosts);
  for (const host of splitCsv(env.NOTIFY_HOST_ALLOWLIST).map((entry) => entry.toLowerCase())) {
    notifyHostAllowlist.add(host);
  }

  if (env.NOTIFY_WEBHOOK_URL?.trim()) {
    try {
      const parsed = new URL(env.NOTIFY_WEBHOOK_URL.trim());
      notifyHostAllowlist.add(parsed.hostname.toLowerCase());
    } catch {
      // Ignore invalid env URL here; it will fail at request-time when used.
    }
  }
  merged.outbound.allowed_notify_hosts = [...notifyHostAllowlist];

  const imageHostAllowlist = new Set(merged.outbound.allowed_image_hosts);
  for (const host of splitCsv(env.IMAGE_HOST_ALLOWLIST).map((entry) => entry.toLowerCase())) {
    imageHostAllowlist.add(host);
  }
  merged.outbound.allowed_image_hosts = [...imageHostAllowlist];

  return {
    ...merged,
    apiKeys: new Set(envApiKeys)
  };
}

function enforceRouteSecurity(request: Request, security: ResolvedSecurityConfig, route: ProtectedRoute): void {
  if (!PROTECTED_ROUTE_SET.has(route)) {
    return;
  }
  enforceRateLimit(request, security, route);
  enforceApiAuth(request, security, route);
}

function enforceApiAuth(request: Request, security: ResolvedSecurityConfig, route: ProtectedRoute): void {
  if (!security.api_auth.enabled) {
    return;
  }
  const routeNeedsAuth =
    (route === "preview" && security.api_auth.require_for_preview) ||
    (route === "catalog" && security.api_auth.require_for_preview) ||
    (route === "generate" && security.api_auth.require_for_generate) ||
    (route === "generate-from-content" && security.api_auth.require_for_direct_content) ||
    (route === "webhook" && security.api_auth.require_for_webhook);

  if (!routeNeedsAuth) {
    return;
  }

  if (security.apiKeys.size === 0) {
    throw new HttpError(500, "API auth is enabled but env var API_KEYS is not configured");
  }

  const apiKey = extractApiKey(request, security.api_auth.header_name);
  if (!apiKey || !security.apiKeys.has(apiKey)) {
    throw new HttpError(401, "Unauthorized API key");
  }
}

function enforceRateLimit(request: Request, security: ResolvedSecurityConfig, route: ProtectedRoute): void {
  if (!security.rate_limit.enabled) {
    return;
  }
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
  if (cfConnectingIp) {
    return cfConnectingIp;
  }
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (forwarded) {
    return forwarded;
  }
  const realIp = request.headers.get("x-real-ip")?.trim();
  return realIp || "anonymous";
}

function extractApiKey(request: Request, headerName: string): string | null {
  const direct = request.headers.get(headerName)?.trim();
  if (direct) {
    return direct;
  }
  const auth = request.headers.get("authorization")?.trim();
  if (!auth) {
    return null;
  }
  const bearerMatch = auth.match(/^Bearer\s+(.+)$/i);
  return bearerMatch?.[1]?.trim() || null;
}

function handleCorsPreflight(request: Request, security: ResolvedSecurityConfig): Response {
  if (!security.cors.enabled) {
    return new Response(null, { status: 204 });
  }
  const headers = corsHeadersForRequest(request, security);
  headers.set("access-control-max-age", String(security.cors.max_age_seconds));
  return new Response(null, {
    status: 204,
    headers
  });
}

function finalizeResponse(request: Request, security: ResolvedSecurityConfig, response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("x-content-type-options", "nosniff");
  headers.set("referrer-policy", "no-referrer");
  headers.set("x-frame-options", "DENY");

  if (security.cors.enabled) {
    const corsHeaders = corsHeadersForRequest(request, security);
    for (const [key, value] of corsHeaders.entries()) {
      headers.set(key, value);
    }
  }

  return new Response(response.body, {
    status: response.status,
    headers
  });
}

function corsHeadersForRequest(request: Request, security: ResolvedSecurityConfig): Headers {
  const headers = new Headers();
  const origin = request.headers.get("origin")?.trim();
  const allowedOrigin = resolveCorsOrigin(origin, security.cors);
  if (allowedOrigin) {
    headers.set("access-control-allow-origin", allowedOrigin);
    if (allowedOrigin !== "*") {
      headers.append("vary", "Origin");
    }
    if (security.cors.allow_credentials) {
      headers.set("access-control-allow-credentials", "true");
    }
    headers.set("access-control-allow-methods", security.cors.allowed_methods.join(", "));
    headers.set("access-control-allow-headers", security.cors.allowed_headers.join(", "));
  }
  return headers;
}

function resolveCorsOrigin(origin: string | undefined, cors: SecurityConfig["cors"]): string | null {
  if (!origin) {
    if (cors.allowed_origins.includes("*")) {
      return cors.allow_credentials ? null : "*";
    }
    return null;
  }
  const normalized = origin.toLowerCase();
  if (cors.allowed_origins.includes("*")) {
    return cors.allow_credentials ? origin : "*";
  }
  if (cors.allowed_origins.includes(normalized)) {
    return origin;
  }
  return null;
}

function normalizeLowercaseList(input: string[] | undefined, fallback: string[]): string[] {
  if (!Array.isArray(input) || input.length === 0) {
    return [...fallback];
  }
  const values = input
    .map((value) => (typeof value === "string" ? value.trim().toLowerCase() : ""))
    .filter(Boolean);
  return values.length > 0 ? values : [...fallback];
}

function normalizeUppercaseList(input: string[] | undefined, fallback: string[]): string[] {
  if (!Array.isArray(input) || input.length === 0) {
    return [...fallback];
  }
  const values = input
    .map((value) => (typeof value === "string" ? value.trim().toUpperCase() : ""))
    .filter(Boolean);
  return values.length > 0 ? values : [...fallback];
}

function splitCsv(value: string | undefined): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

async function runPipeline(input: GenerateRequestBody, env: Env, security: ResolvedSecurityConfig): Promise<GenerationResult> {
  assertRequiredEnv(env);

  const slug = resolveSlug(input);
  if (!slug) {
    throw new HttpError(400, "Request must include either slug or url");
  }

  const post = await fetchGhostPost(env, slug);
  return runPipelineFromPost(post, env, input, security);
}

async function runPipelineFromPost(
  post: GhostPost,
  env: Env,
  brandInput: {
    brandingColor?: string;
    brandName?: string;
    prompt?: string;
    templateIds?: Partial<Record<TemplateKind, string>>;
    slotOverrides?: Record<string, string>;
    brandTokens?: BrandTokenOverrides;
    design?: TemplateControlSet;
    storage?: StorageOptions;
    llm?: LlmPromptOverrides;
    image?: ImageGenerationOptions;
    output?: OutputOptions;
  },
  security: ResolvedSecurityConfig
): Promise<GenerationResult> {
  const outputPlan = resolveOutputPlan(brandInput.output);
  const brandColor = brandInput.brandingColor ?? env.DEFAULT_BRAND_COLOR ?? PIPELINE_CONFIG.brand.default_color;
  const brandName = brandInput.brandName ?? env.BRAND_NAME ?? PIPELINE_CONFIG.brand.default_name;
  const variants: NonNullable<GenerationResult["variants"]> = [];

  for (let index = 0; index < outputPlan.postCount; index += 1) {
    const variantPrompt =
      outputPlan.postCount > 1
        ? [brandInput.prompt?.trim(), `Variation index ${index + 1} of ${outputPlan.postCount}.`].filter(Boolean).join(" ")
        : brandInput.prompt;

    const templatePlan = await buildTemplatePlan({
      ai: env.AI,
      llmModel: env.LLM_MODEL,
      post,
      userPrompt: variantPrompt,
      outputFormats: outputPlan.formats,
      templateIds: brandInput.templateIds
    });

    const llmOutput = await generateStructuredCopy({
      ai: env.AI,
      llmModel: env.LLM_MODEL,
      post,
      requiredCarouselSlides: outputPlan.carouselSlides,
      requiredSlotKeys: templatePlan.requiredSlotKeys,
      slotFields: templatePlan.slotFields,
      userPrompt: variantPrompt,
      llmOverrides: brandInput.llm,
      normalizeSlotContent
    });
    const mergedSlotContent = mergeSlotContent(
      llmOutput.slot_content,
      normalizeSlotContent(brandInput.slotOverrides, {
        title: post.title,
        fallbackText: post.custom_excerpt || post.excerpt || post.plaintext || "",
        requiredSlotKeys: templatePlan.requiredSlotKeys
      })
    );
    const selectedImage = await chooseImageSource(env, post, llmOutput, brandInput.image, security);
    const renderAssets = await renderAndStoreAssets(env, {
      slug: post.slug,
      postTitle: post.title,
      imageUrl: selectedImage.imageUrl,
      llmOutput: {
        ...llmOutput,
        slot_content: mergedSlotContent
      },
      brandColor,
      brandName,
      templateIds: templatePlan.templateIds,
      requiredSlotKeys: templatePlan.requiredSlotKeys,
      slotContent: mergedSlotContent,
      brandTokens: brandInput.brandTokens,
      design: brandInput.design,
      storage: storageForVariant(brandInput.storage, index, outputPlan.postCount),
      requestedFormats: outputPlan.formats
    });

    variants.push({
      index: index + 1,
      image_source: selectedImage,
      template_plan: {
        required_slot_keys: templatePlan.requiredSlotKeys,
        template_ids: templatePlan.templateIds
      },
      llm_output: {
        ...llmOutput,
        slot_content: mergedSlotContent
      },
      assets: renderAssets
    });
  }

  const primaryVariant = variants[0];
  if (!primaryVariant) {
    throw new HttpError(500, "Generation pipeline did not produce any output variants");
  }

  return {
    ok: true,
    slug: post.slug,
    post_url: post.url,
    requested_formats: [...outputPlan.formats],
    image_source: primaryVariant.image_source,
    template_plan: primaryVariant.template_plan,
    llm_output: primaryVariant.llm_output,
    assets: primaryVariant.assets,
    variants: outputPlan.postCount > 1 ? variants : undefined
  };
}

function storageForVariant(storage: StorageOptions | undefined, index: number, totalCount: number): StorageOptions | undefined {
  if (totalCount <= 1 || index === 0) {
    return storage;
  }

  const existing = storage?.runId ? sanitizeRunId(storage.runId) : null;
  const variantRunId = [existing ?? "variant", `v${index + 1}`].join("-");
  return {
    mode: "versioned",
    includeDate: storage?.includeDate,
    runId: variantRunId
  };
}

function resolveOutputPlan(output: OutputOptions | undefined): {
  formats: Set<TemplateKind>;
  carouselSlides: number;
  postCount: number;
} {
  const requestedFormats = output?.formats && output.formats.length > 0 ? output.formats : TEMPLATE_KINDS;
  const normalizedFormats = new Set<TemplateKind>();
  for (const format of requestedFormats) {
    if (TEMPLATE_KIND_SET.has(format)) {
      normalizedFormats.add(format);
    }
  }

  if (normalizedFormats.size === 0) {
    throw new HttpError(400, "output.formats must include at least one supported format");
  }

  const requestedSlides = Math.round(
    clampNumber(output?.carouselSlides, 1, 10, DEFAULT_CAROUSEL_SLIDES)
  );
  const postCount = Math.round(clampNumber(output?.postCount, 1, 10, 1));
  return {
    formats: normalizedFormats,
    carouselSlides: requestedSlides,
    postCount
  };
}

async function buildTemplatePlan(args: {
  ai: Ai;
  llmModel?: string;
  post: GhostPost;
  userPrompt?: string;
  outputFormats: Set<TemplateKind>;
  templateIds?: Partial<Record<TemplateKind, string>>;
}): Promise<TemplatePlan> {
  const requestedFormats = [...args.outputFormats];
  const templateCandidates = buildTemplateCandidates(requestedFormats);

  const preselected: Record<string, string> = {};
  const formatsForLlm: string[] = [];
  for (const format of requestedFormats) {
    const forcedTemplateId = args.templateIds?.[format];
    if (forcedTemplateId) {
      preselected[format] = forcedTemplateId;
      continue;
    }
    formatsForLlm.push(format);
  }

  const llmSelected = formatsForLlm.length
    ? await chooseTemplateAssignments({
      ai: args.ai,
      llmModel: args.llmModel,
      post: args.post,
      requestedFormats: formatsForLlm,
      templateCandidates,
      userPrompt: args.userPrompt
    })
    : {};

  const templateIds: Partial<Record<TemplateKind, string>> = {};
  const requiredSlotKeySet = new Set<string>();
  const slotFieldMap = new Map<string, import("./templates").TemplateFieldDeclaration>();

  for (const format of requestedFormats) {
    const selectedTemplateId = preselected[format] ?? llmSelected[format];
    const resolvedTemplateId = resolveTemplateId(format, {
      templateId: selectedTemplateId
    });
    templateIds[format] = resolvedTemplateId;

    const requiredForTemplate = listRequiredSlotKeys(format, {
      templateId: resolvedTemplateId
    });
    for (const key of requiredForTemplate) {
      const normalized = normalizeSlotKey(key);
      if (normalized) requiredSlotKeySet.add(normalized);
    }

    // Collect field declarations (with hints) from the selected template
    for (const field of listTemplateFields(resolvedTemplateId)) {
      if (!slotFieldMap.has(field.key)) {
        slotFieldMap.set(field.key, field);
      }
    }
  }

  return {
    templateIds,
    requiredSlotKeys: [...requiredSlotKeySet],
    slotFields: [...slotFieldMap.values()]
  };
}

function buildTemplateCandidates(formats: TemplateKind[]): Record<string, TemplateChoiceCandidate[]> {
  const candidates: Record<string, TemplateChoiceCandidate[]> = {};
  for (const format of formats) {
    // All templates are available for all formats — pass the full list as candidates
    candidates[format] = TEMPLATE_REGISTRY.map((template) => ({
      id: template.id,
      label: template.label,
      description: template.description,
      requiredSlotKeys: listRequiredSlotKeys(format, { templateId: template.id }),
      fields: listTemplateFields(template.id)
    }));
  }
  return candidates;
}

function buildPostFromDirectContent(input: DirectContentRequestBody, security: ResolvedSecurityConfig): GhostPost {
  const title = (input.title ?? "").trim();
  if (!title) {
    throw new HttpError(400, "title is required for /generate-from-content");
  }

  const plainContent = normalizeSourceContent((input.content ?? input.body ?? "").trim());
  if (!plainContent) {
    throw new HttpError(400, "content (or body) is required for /generate-from-content");
  }

  const derivedSlug = sanitizeSlug(input.slug ?? slugify(title));
  if (!derivedSlug) {
    throw new HttpError(400, "Could not derive a valid slug from title");
  }

  const tags = normalizeTags(input.tags);
  const excerpt = normalizeSourceContent(
    (input.excerpt ?? plainContent.slice(0, PIPELINE_CONFIG.generation.limits.direct_excerpt_default_max_chars)).trim()
  );
  const url = input.url?.trim() || `https://local.test/${derivedSlug}/`;
  const featureImage = input.feature_image
    ? sanitizeImageUrl(
      input.feature_image,
      security,
      "feature_image",
      {
        allowDataUrl: false,
        requireAllowedHost: false
      }
    )
    : undefined;

  return {
    id: crypto.randomUUID(),
    title,
    slug: derivedSlug,
    url,
    plaintext: plainContent,
    excerpt,
    custom_excerpt: excerpt,
    feature_image: featureImage,
    tags: tags.map((name) => ({ name })),
    primary_tag: input.primary_tag ? { name: input.primary_tag } : tags[0] ? { name: tags[0] } : undefined
  };
}

function normalizeTags(input: string[] | string | undefined): string[] {
  if (!input) {
    return [];
  }
  const rawItems = Array.isArray(input) ? input : input.split(",");
  return rawItems
    .map((item) => item.trim())
    .map((item) => item.replace(/[^\p{L}\p{N}\s-]/gu, ""))
    .filter((item) => item.length > 1)
    .slice(0, PIPELINE_CONFIG.generation.limits.input_tags_max_count);
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

function resolveSlug(input: GenerateRequestBody): string | null {
  if (typeof input.slug === "string" && input.slug.trim().length > 0) {
    return sanitizeSlug(input.slug);
  }
  if (typeof input.url === "string" && input.url.trim().length > 0) {
    return parseSlugFromUrl(input.url);
  }
  return null;
}

function extractSlugFromWebhook(payload: GhostWebhookPayload): string | null {
  const direct =
    payload.post?.current?.slug ?? payload.post?.slug ?? payload.slug ?? parseSlugFromUrl(payload.post?.current?.url ?? "") ?? parseSlugFromUrl(payload.url ?? "");
  if (!direct) {
    return null;
  }
  return sanitizeSlug(direct);
}

function sanitizeSlug(value: string): string {
  return value
    .trim()
    .replace(/^\/+|\/+$/g, "")
    .replace(/[^\p{L}\p{N}\-_/]/gu, "")
    .split("/")
    .filter(Boolean)
    .at(-1)
    ?.toLowerCase() ?? "";
}

function parseSlugFromUrl(rawUrl: string): string | null {
  try {
    const url = new URL(rawUrl);
    const segments = url.pathname.split("/").filter(Boolean);
    if (segments.length === 0) {
      return null;
    }
    return sanitizeSlug(segments[segments.length - 1]);
  } catch {
    return null;
  }
}

async function fetchGhostPost(env: Env, slug: string): Promise<GhostPost> {
  const base = env.GHOST_API_URL.replace(/\/+$/, "");
  const endpoint = `${base}/posts/slug/${encodeURIComponent(slug)}/?key=${encodeURIComponent(
    env.GHOST_CONTENT_API_KEY
  )}&include=tags,authors&formats=html,plaintext`;

  const response = await fetch(endpoint, {
    headers: { accept: "application/json" }
  });

  if (!response.ok) {
    const details = await response.text();
    throw new HttpError(
      response.status,
      `Ghost Content API failed: ${details.slice(0, PIPELINE_CONFIG.runtime.ghost_error_preview_chars)}`
    );
  }

  const data = (await response.json()) as { posts?: GhostPost[] };
  const post = data.posts?.[0];
  if (!post) {
    throw new HttpError(404, `No post found for slug: ${slug}`);
  }

  return post;
}

async function chooseImageSource(
  env: Env,
  post: GhostPost,
  llmOutput: LlmOutput,
  options: ImageGenerationOptions | undefined,
  security: ResolvedSecurityConfig
): Promise<SelectedImage> {
  const mode = (options?.mode ?? "auto").trim().toLowerCase() as NonNullable<ImageGenerationOptions["mode"]>;
  const prompt = ensureLength(options?.prompt ?? llmOutput.image_prompt, PIPELINE_CONFIG.generation.limits.image_prompt_max_chars, llmOutput.image_prompt);
  const featureImage = post.feature_image
    ? sanitizeImageUrl(post.feature_image, security, "feature_image", {
      allowDataUrl: false,
      requireAllowedHost: false
    })
    : "";
  const preferFeature = options?.preferFeature ?? PIPELINE_CONFIG.features.prefer_feature_image;
  const allowStock = options?.allowStock ?? PIPELINE_CONFIG.features.enable_stock_image_search;
  const allowAi = options?.allowAi ?? PIPELINE_CONFIG.features.enable_ai_image_generation;

  if (mode === "none") {
    return {
      source: "none",
      imageUrl: ""
    };
  }

  if (mode === "custom") {
    if (!options?.customUrl) {
      throw new HttpError(400, "image.customUrl is required when image.mode is custom");
    }
    return {
      source: "custom",
      imageUrl: sanitizeImageUrl(options.customUrl, security, "image.customUrl", {
        allowDataUrl: false,
        requireAllowedHost: false
      })
    };
  }

  if (mode === "feature") {
    if (!featureImage) {
      throw new HttpError(422, "Requested feature image mode, but source post has no valid feature image");
    }
    return { source: "feature", imageUrl: featureImage };
  }

  if (mode === "stock") {
    if (!allowStock || !env.PEXELS_API_KEY?.trim()) {
      throw new HttpError(422, "Stock image mode requires enable_stock_image_search and PEXELS_API_KEY");
    }
    const stockImage = await searchPexelsImage(post.title, env.PEXELS_API_KEY.trim(), security);
    if (!stockImage) {
      throw new HttpError(422, "Stock image mode did not return a usable image");
    }
    return stockImage;
  }

  if (mode === "ai") {
    if (!allowAi) {
      throw new HttpError(422, "AI image mode is disabled by configuration or request controls");
    }
    const aiImage = await generateAiImage(env, {
      prompt,
      postTitle: post.title,
      topTags: (post.tags ?? [])
        .map((tag) => tag.name ?? "")
        .filter(Boolean)
        .slice(0, 5)
        .join(", ")
    });
    if (!aiImage) {
      throw new HttpError(422, "AI image mode did not return a usable image");
    }
    return aiImage;
  }

  if (preferFeature && llmOutput.use_feature_image && featureImage.length > 0) {
    return {
      source: "feature",
      imageUrl: featureImage
    };
  }

  const topicText = `${post.title} ${(post.primary_tag?.name ?? "")} ${(post.tags ?? [])
    .map((tag) => tag.name ?? "")
    .join(" ")} ${prompt}`.toLowerCase();

  const concreteTopic = STOCK_TOPIC_PATTERN ? STOCK_TOPIC_PATTERN.test(topicText) : false;

  if (allowStock && concreteTopic && env.PEXELS_API_KEY?.trim()) {
    const stockImage = await searchPexelsImage(post.title, env.PEXELS_API_KEY.trim(), security);
    if (stockImage) {
      return stockImage;
    }
  }

  if (allowAi) {
    const aiImage = await generateAiImage(env, {
      prompt,
      postTitle: post.title,
      topTags: (post.tags ?? [])
        .map((tag) => tag.name ?? "")
        .filter(Boolean)
        .slice(0, 5)
        .join(", ")
    });
    if (aiImage) {
      return aiImage;
    }
  }

  if (featureImage.length > 0) {
    return {
      source: "feature",
      imageUrl: featureImage
    };
  }

  return {
    source: "none",
    imageUrl: ""
  };
}

async function searchPexelsImage(title: string, apiKey: string, security: ResolvedSecurityConfig): Promise<SelectedImage | null> {
  const query = title
    .replace(/[^a-zA-Z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, PIPELINE_CONFIG.generation.limits.stock_query_term_max_count)
    .join(" ");

  const endpoint = `https://api.pexels.com/v1/search?query=${encodeURIComponent(
    query || PIPELINE_CONFIG.generation.fallbacks.stock_search_query
  )}&per_page=1&orientation=landscape&size=large`;

  const response = await fetch(endpoint, {
    headers: {
      Authorization: apiKey,
      accept: "application/json"
    }
  });

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as {
    photos?: Array<{
      url?: string;
      photographer?: string;
      src?: {
        large2x?: string;
        original?: string;
      };
    }>;
  };

  const photo = data.photos?.[0];
  const imageUrl = photo?.src?.large2x ?? photo?.src?.original;
  if (!imageUrl) {
    return null;
  }

  const safeImageUrl = sanitizeImageUrl(imageUrl, security, "Pexels image URL", {
    allowDataUrl: false,
    requireAllowedHost: false
  });

  return {
    source: "stock",
    imageUrl: safeImageUrl,
    sourceUrl: photo?.url ? sanitizeHttpUrl(photo.url, security, "Pexels source URL", { requireAllowedHost: false }) : undefined,
    attribution: photo?.photographer ? `Photo by ${photo.photographer} via Pexels` : "Photo via Pexels"
  };
}

async function generateAiImage(
  env: Env,
  args: {
    prompt: string;
    postTitle?: string;
    topTags?: string;
  }
): Promise<SelectedImage | null> {
  const model = (env.IMAGE_MODEL || DEFAULT_IMAGE_MODEL) as keyof AiModels;
  const negativeClauses = (
    (PIPELINE_CONFIG.generation.image as unknown as { negative_clauses?: string[] }).negative_clauses ?? []
  ) as string[];

  const imagePrompt = [
    ...PIPELINE_CONFIG.generation.image.prompt_prefix,
    args.postTitle ? `Campaign context title: ${args.postTitle}` : "",
    args.topTags ? `Context tags: ${args.topTags}` : "",
    `Scene: ${args.prompt}`,
    ...negativeClauses
  ]
    .filter(Boolean)
    .join(" ");

  try {
    const raw = await env.AI.run(model, {
      prompt: imagePrompt
    });

    const dataUrl = toDataUrl(raw);
    if (!dataUrl) {
      return null;
    }

    return {
      source: "ai",
      imageUrl: dataUrl
    };
  } catch {
    return null;
  }
}

function toDataUrl(value: unknown): string | null {
  if (!value) {
    return null;
  }

  if (typeof value === "string") {
    if (value.startsWith("data:image/")) {
      return value;
    }
    return null;
  }

  if (value instanceof ArrayBuffer) {
    return `data:image/png;base64,${arrayBufferToBase64(new Uint8Array(value))}`;
  }

  if (ArrayBuffer.isView(value)) {
    const view = value as ArrayBufferView;
    const bytes = new Uint8Array(view.buffer, view.byteOffset, view.byteLength);
    return `data:image/png;base64,${arrayBufferToBase64(bytes)}`;
  }

  if (typeof value === "object") {
    const object = value as Record<string, unknown>;
    if (typeof object.image === "string" && object.image.length > 0) {
      return `data:image/jpeg;base64,${object.image}`;
    }
    if (typeof object.result === "string" && object.result.startsWith("data:image/")) {
      return object.result;
    }
  }

  return null;
}

async function renderAndStoreAssets(
  env: Env,
  args: {
    slug: string;
    postTitle: string;
    imageUrl: string;
    llmOutput: LlmOutput;
    brandColor: string;
    brandName: string;
    templateIds?: Partial<Record<TemplateKind, string>>;
    requiredSlotKeys: string[];
    slotContent: Record<string, string>;
    brandTokens?: BrandTokenOverrides;
    design?: TemplateControlSet;
    storage?: StorageOptions;
    requestedFormats: Set<TemplateKind>;
  }
): Promise<GenerationResult["assets"]> {
  const keyPrefix = buildR2KeyPrefix(env, args.slug, args.storage);
  const sharedSlots = buildSharedSlotContent({
    ...args,
    requiredSlotKeys: args.requiredSlotKeys
  });

  const commonTemplateValues: BaseTemplateParams = {
    title: args.postTitle,
    caption: args.llmOutput.instagram_caption,
    imageUrl: args.imageUrl,
    brandColor: args.brandColor,
    brandName: args.brandName,
    slots: sharedSlots,
    brandTokens: args.brandTokens,
    design: args.design
  };

  const browser = await puppeteer.launch(env.BROWSER, { keep_alive: PIPELINE_CONFIG.runtime.browser_keep_alive_ms });

  try {
    const instagramPortraitAsset = args.requestedFormats.has("instagram-portrait")
      ? await renderStoreSingleAsset(env, browser, {
        key: `${keyPrefix}/instagram-portrait.png`,
        kind: "instagram-portrait",
        params: {
          ...commonTemplateValues,
          templateId: args.templateIds?.["instagram-portrait"],
          slots: {
            ...sharedSlots,
            headline: sharedSlots.headline || args.postTitle,
            subheadline: sharedSlots.subheadline || args.llmOutput.instagram_caption
          },
          caption: withHashtags(
            args.llmOutput.instagram_caption,
            args.llmOutput.hashtags,
            PIPELINE_CONFIG.formats["instagram-portrait"].hashtag_count
          )
        },
        formatLabel: "instagram-portrait"
      })
      : null;

    const instagramSquareAsset = args.requestedFormats.has("instagram-square")
      ? await renderStoreSingleAsset(env, browser, {
        key: `${keyPrefix}/instagram-square.png`,
        kind: "instagram-square",
        params: {
          ...commonTemplateValues,
          templateId: args.templateIds?.["instagram-square"],
          slots: {
            ...sharedSlots,
            headline: sharedSlots.headline || args.postTitle,
            subheadline: sharedSlots.subheadline || args.llmOutput.instagram_caption
          },
          caption: withHashtags(
            args.llmOutput.instagram_caption,
            args.llmOutput.hashtags,
            PIPELINE_CONFIG.formats["instagram-square"].hashtag_count
          )
        },
        formatLabel: "instagram-square"
      })
      : null;

    const instagramStoryAsset = args.requestedFormats.has("instagram-story")
      ? await renderStoreSingleAsset(env, browser, {
        key: `${keyPrefix}/instagram-story.png`,
        kind: "instagram-story",
        params: {
          ...commonTemplateValues,
          templateId: args.templateIds?.["instagram-story"],
          slots: {
            ...sharedSlots,
            headline: sharedSlots.headline || args.postTitle,
            supporting_line: sharedSlots.supporting_line || args.llmOutput.instagram_caption
          },
          caption: withHashtags(
            args.llmOutput.instagram_caption,
            args.llmOutput.hashtags,
            PIPELINE_CONFIG.formats["instagram-story"].hashtag_count
          )
        },
        formatLabel: "instagram-story"
      })
      : null;

    const twitterCardAsset = args.requestedFormats.has("twitter-card")
      ? await renderStoreSingleAsset(env, browser, {
        key: `${keyPrefix}/twitter-card.png`,
        kind: "twitter-card",
        params: {
          ...commonTemplateValues,
          templateId: args.templateIds?.["twitter-card"],
          slots: {
            ...sharedSlots,
            headline: sharedSlots.headline || args.postTitle,
            supporting_line: sharedSlots.supporting_line || args.llmOutput.twitter_caption
          },
          caption: withHashtags(
            args.llmOutput.twitter_caption,
            args.llmOutput.hashtags,
            PIPELINE_CONFIG.formats["twitter-card"].hashtag_count
          )
        },
        formatLabel: "twitter-card"
      })
      : null;

    const linkedInAsset = args.requestedFormats.has("linkedin-post")
      ? await renderStoreSingleAsset(env, browser, {
        key: `${keyPrefix}/linkedin-post.png`,
        kind: "linkedin-post",
        params: {
          ...commonTemplateValues,
          templateId: args.templateIds?.["linkedin-post"],
          slots: {
            ...sharedSlots,
            headline: sharedSlots.headline || args.postTitle,
            supporting_line: sharedSlots.supporting_line || args.llmOutput.linkedin_caption
          },
          caption: withHashtags(
            args.llmOutput.linkedin_caption,
            args.llmOutput.hashtags,
            PIPELINE_CONFIG.formats["linkedin-post"].hashtag_count
          )
        },
        formatLabel: "linkedin-post"
      })
      : null;

    const carousel: StoredAsset[] = [];
    if (args.requestedFormats.has("carousel-post")) {
      for (const [index, slide] of args.llmOutput.carousel_slides.entries()) {
        const slideAsset = await renderStoreSingleAsset(env, browser, {
          key: `${keyPrefix}/carousel-post-${index + 1}.png`,
          kind: "carousel-post",
          params: {
            ...commonTemplateValues,
            templateId: args.templateIds?.["carousel-post"],
            slots: {
              ...sharedSlots,
              headline: slide.heading,
              body: slide.body,
              short_hook: slide.heading,
              supporting_line: slide.body,
              step_number: String(index + 1),
              step_total: String(args.llmOutput.carousel_slides.length)
            },
            heading: slide.heading,
            body: slide.body,
            slideNumber: index + 1,
            totalSlides: args.llmOutput.carousel_slides.length
          } as CarouselTemplateParams,
          formatLabel: `carousel-post-${index + 1}`
        });
        carousel.push(slideAsset);
      }
    }

    return {
      instagram_portrait: instagramPortraitAsset,
      instagram_square: instagramSquareAsset,
      instagram_story: instagramStoryAsset,
      twitter_card: twitterCardAsset,
      linkedin_post: linkedInAsset,
      carousel
    };
  } finally {
    await browser.close();
  }
}

async function renderStoreSingleAsset(
  env: Env,
  browser: Awaited<ReturnType<typeof puppeteer.launch>>,
  args: {
    key: string;
    kind: TemplateKind;
    params: BaseTemplateParams | CarouselTemplateParams;
    formatLabel: string;
  }
): Promise<StoredAsset> {
  const size = getTemplateDimensions(args.kind);
  const html = renderTemplate(args.kind, args.params);
  const png = await renderPng(browser, html, size.width, size.height);

  await env.OUTPUT_BUCKET.put(args.key, png, {
    httpMetadata: {
      contentType: "image/png",
      cacheControl: PIPELINE_CONFIG.runtime.asset_cache_control
    }
  });

  return {
    format: args.formatLabel,
    key: args.key,
    url: buildPublicUrl(env, args.key)
  };
}

async function renderPng(
  browser: Awaited<ReturnType<typeof puppeteer.launch>>,
  html: string,
  width: number,
  height: number
): Promise<Uint8Array> {
  const page = await browser.newPage();

  try {
    await page.setViewport({ width, height, deviceScaleFactor: 1 });
    await page.setContent(html, {
      waitUntil: PIPELINE_CONFIG.runtime.page_set_content_wait_until as "load" | "domcontentloaded" | "networkidle0"
    });

    await page.evaluate(`
      (async () => {
        await document.fonts.ready;
        const images = Array.from(document.images);
        await Promise.all(
          images.map(async (image) => {
            try {
              await image.decode();
            } catch {}
          })
        );
      })();
    `);

    const screenshot = await page.screenshot({
      type: "png",
      clip: { x: 0, y: 0, width, height }
    });

    if (screenshot instanceof Uint8Array) {
      return screenshot;
    }

    return new Uint8Array(screenshot as ArrayBuffer);
  } finally {
    await page.close();
  }
}

function buildR2KeyPrefix(env: Env, slug: string, storage?: StorageOptions): string {
  const basePrefix = (env.R2_KEY_PREFIX || PIPELINE_CONFIG.storage.default_key_prefix).replace(/\/+$/, "");
  const mode = storage?.mode ?? PIPELINE_CONFIG.storage.default_mode;

  if (mode === "overwrite") {
    return `${basePrefix}/${slug}`;
  }

  const includeDate = storage?.includeDate ?? PIPELINE_CONFIG.storage.versioned_include_date;
  const runId = sanitizeRunId(storage?.runId) ?? crypto.randomUUID().split("-")[0];
  const datePart = includeDate ? `/${new Date().toISOString().slice(0, 10)}` : "";
  return `${basePrefix}/${slug}${datePart}/${runId}`;
}

function sanitizeRunId(input: string | undefined): string | null {
  if (!input) {
    return null;
  }
  const cleaned = input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-_]/g, "");
  if (!cleaned) {
    return null;
  }
  return cleaned.slice(0, PIPELINE_CONFIG.generation.limits.storage_run_id_max_chars);
}

function buildPublicUrl(env: Env, key: string): string | null {
  const base = env.R2_PUBLIC_BASE_URL?.trim();
  if (!base) {
    return null;
  }
  const normalizedBase = base.replace(/\/+$/, "");
  const encodedPath = key
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${normalizedBase}/${encodedPath}`;
}

async function sendNotification(url: string, payload: GenerationResult, security: ResolvedSecurityConfig): Promise<void> {
  try {
    const safeUrl = sanitizeHttpUrl(url, security, "Notification URL", {
      requireAllowedHost: true
    });
    await fetch(safeUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  } catch {
    // Notification failures should not break generation.
  }
}

function resolveNotifyUrl(
  bodyValue: string | undefined,
  envValue: string | undefined,
  security: ResolvedSecurityConfig
): string | null {
  const candidate = (bodyValue ?? envValue)?.trim();
  if (!candidate) {
    return null;
  }
  return sanitizeHttpUrl(candidate, security, "Notification URL", {
    requireAllowedHost: true
  });
}

function createTopicKeywordPattern(keywords: readonly string[]): RegExp | null {
  const safeKeywords = keywords
    .map((keyword) => keyword.trim().toLowerCase())
    .filter(Boolean)
    .map((keyword) => keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));

  if (safeKeywords.length === 0) {
    return null;
  }

  return new RegExp(`\\b(${safeKeywords.join("|")})\\b`, "i");
}

function normalizeSlotContent(
  value: unknown,
  args: {
    title: string;
    fallbackText: string;
    requiredSlotKeys?: string[];
  }
): Record<string, string> {
  const limits = PIPELINE_CONFIG.generation.limits;
  const untitled = PIPELINE_CONFIG.generation.fallbacks.untitled_text;
  const normalized: Record<string, string> = {};

  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [rawKey, rawValue] of Object.entries(value as Record<string, unknown>)) {
      const key = normalizeSlotKey(rawKey);
      const text = toText(rawValue);
      if (!key || !text) {
        continue;
      }
      normalized[key] = ensureLength(text, limits.slot_text_max_chars, text);
    }
  }

  const fallbackLine = toSingleSentence(ensureLength(args.fallbackText, limits.slot_fallback_line_max_chars, args.title));
  const normalizedTitle = ensureLength(args.title, limits.slot_headline_max_chars, untitled);
  const slotFallbackContext: SlotFallbackContext = {
    title: normalizedTitle,
    fallbackLine,
    brandName: PIPELINE_CONFIG.brand.default_name,
    defaultQuoteAuthor: PIPELINE_CONFIG.generation.fallbacks.default_quote_author,
    slideHeadings: [],
    slideCount: 1
  };

  for (const slotKey of ["headline", "subheadline", "short_hook", "supporting_line", "insight_line"]) {
    if (normalized[slotKey]) {
      continue;
    }
    normalized[slotKey] = ensureLength(
      inferSlotFallbackValue(slotKey, slotFallbackContext),
      limits.slot_text_max_chars,
      fallbackLine
    );
  }

  for (const requiredKey of args.requiredSlotKeys ?? []) {
    const normalizedKey = normalizeSlotKey(requiredKey);
    if (!normalizedKey || normalized[normalizedKey]) {
      continue;
    }
    normalized[normalizedKey] = ensureLength(
      inferSlotFallbackValue(normalizedKey, slotFallbackContext),
      limits.slot_text_max_chars,
      fallbackLine
    );
  }

  return normalized;
}

function mergeSlotContent(base: Record<string, string>, overrides: Record<string, string>): Record<string, string> {
  const merged: Record<string, string> = { ...base };
  for (const [key, value] of Object.entries(overrides)) {
    const normalizedKey = normalizeSlotKey(key);
    const normalizedValue = value.trim();
    if (!normalizedKey || !normalizedValue) {
      continue;
    }
    merged[normalizedKey] = normalizedValue;
  }
  return merged;
}

function buildSharedSlotContent(args: {
  postTitle: string;
  llmOutput: LlmOutput;
  brandName: string;
  slotContent: Record<string, string>;
  requiredSlotKeys: string[];
}): Record<string, string> {
  const limits = PIPELINE_CONFIG.generation.limits;
  const defaultQuoteAuthor = PIPELINE_CONFIG.generation.fallbacks.default_quote_author;
  const slots = {
    ...args.slotContent
  };

  const fallbackLine = toSingleSentence(
    ensureLength(args.llmOutput.linkedin_caption || args.llmOutput.instagram_caption, limits.slot_fallback_line_max_chars, args.postTitle)
  );
  const fallbackHeadline = ensureLength(args.postTitle, limits.slot_headline_max_chars, args.postTitle);
  const slideCount = Math.max(args.llmOutput.carousel_slides.length, 1);

  const firstSlide = args.llmOutput.carousel_slides[0];
  const fallbackByKey: Record<string, string> = {
    headline: fallbackHeadline,
    heading: fallbackHeadline,
    body: firstSlide?.body || fallbackLine,
    subheadline: args.llmOutput.linkedin_caption || fallbackLine,
    short_hook: fallbackHeadline,
    supporting_line: args.llmOutput.instagram_caption || fallbackLine,
    insight_line: args.llmOutput.twitter_caption || fallbackLine,
    quote_text: args.llmOutput.linkedin_caption || fallbackLine,
    quote_author: args.brandName || defaultQuoteAuthor,
    step_number: "1",
    step_total: String(slideCount)
  };
  const slotFallbackContext: SlotFallbackContext = {
    title: fallbackHeadline,
    fallbackLine,
    brandName: args.brandName || PIPELINE_CONFIG.brand.default_name,
    defaultQuoteAuthor,
    slideHeadings: args.llmOutput.carousel_slides.map((slide) => slide.heading).filter(Boolean),
    slideCount
  };

  for (const [key, value] of Object.entries(fallbackByKey)) {
    const normalized = normalizeSlotKey(key);
    if (!normalized || slots[normalized]) {
      continue;
    }
    if (value.trim()) {
      slots[normalized] = ensureLength(value, limits.slot_text_max_chars, fallbackLine);
      continue;
    }
    const inferred = inferSlotFallbackValue(normalized, slotFallbackContext);
    if (inferred.trim()) {
      slots[normalized] = ensureLength(inferred, limits.slot_text_max_chars, fallbackLine);
    }
  }

  for (const key of args.requiredSlotKeys) {
    const normalized = normalizeSlotKey(key);
    if (!normalized || slots[normalized]) {
      continue;
    }

    const fallback = fallbackByKey[normalized] || inferSlotFallbackValue(normalized, slotFallbackContext) || fallbackLine;
    slots[normalized] = ensureLength(fallback, limits.slot_text_max_chars, fallbackLine);
  }

  return slots;
}

interface SlotFallbackContext {
  title: string;
  fallbackLine: string;
  brandName: string;
  defaultQuoteAuthor: string;
  slideHeadings: string[];
  slideCount: number;
}

function inferSlotFallbackValue(slotKey: string, context: SlotFallbackContext): string {
  const normalized = normalizeSlotKey(slotKey);
  if (!normalized) {
    return context.fallbackLine;
  }

  const stepMatch = normalized.match(/^step_(\d+)$/);
  if (stepMatch?.[1]) {
    const stepIndex = Math.max(Number.parseInt(stepMatch[1], 10) - 1, 0);
    return context.slideHeadings[stepIndex] || `Step ${stepIndex + 1}`;
  }

  if (normalized === "step_number" || normalized.endsWith("_number")) {
    return "1";
  }
  if (normalized === "step_total" || normalized.endsWith("_total")) {
    return String(Math.max(context.slideCount, 1));
  }

  if (normalized.includes("metric") && normalized.includes("value")) {
    return "2.4K";
  }
  if (normalized.includes("metric") && (normalized.includes("label") || normalized.includes("name"))) {
    return "Weekly readers";
  }
  if (normalized.includes("cta")) {
    return "Read more";
  }
  if (normalized === "kicker" || normalized.endsWith("_kicker")) {
    return "INSIGHT";
  }
  if (normalized === "quote_author" || normalized.endsWith("_author")) {
    return context.brandName || context.defaultQuoteAuthor;
  }

  if (
    normalized.includes("headline") ||
    normalized.includes("heading") ||
    normalized.includes("title") ||
    normalized.includes("hook")
  ) {
    return context.title;
  }

  if (
    normalized.includes("subheadline") ||
    normalized.includes("support") ||
    normalized.includes("insight") ||
    normalized.includes("line") ||
    normalized.includes("body") ||
    normalized.includes("caption") ||
    normalized.includes("summary") ||
    normalized.includes("description") ||
    normalized.includes("text") ||
    normalized.includes("quote")
  ) {
    return context.fallbackLine;
  }

  return context.fallbackLine;
}

function normalizeSlotKey(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function withHashtags(caption: string, hashtags: string[], count: number): string {
  const compactTags = hashtags.slice(0, count).join(" ");
  return ensureLength(
    `${caption} ${compactTags}`.trim(),
    PIPELINE_CONFIG.generation.limits.caption_with_hashtags_max_chars,
    caption
  );
}

function toSingleSentence(text: string): string {
  const maxChars = PIPELINE_CONFIG.generation.limits.single_sentence_max_chars;
  const normalized = text.replace(/\s+/g, " ").trim();
  const match = normalized.match(/^(.+?[.!?])(?:\s|$)/);
  if (match?.[1]) {
    return ensureLength(match[1].trim(), maxChars, normalized);
  }
  return ensureLength(normalized, maxChars, normalized);
}

function ensureLength(value: string, max: number, fallback: string): string {
  const source = value.trim() || fallback.trim() || PIPELINE_CONFIG.generation.fallbacks.untitled_text;
  if (source.length <= max) {
    return source;
  }

  const sentenceWindow = source.slice(0, max);
  const sentenceBoundary = Math.max(
    sentenceWindow.lastIndexOf("."),
    sentenceWindow.lastIndexOf("!"),
    sentenceWindow.lastIndexOf("?")
  );
  if (sentenceBoundary >= Math.floor(max * 0.55)) {
    return source.slice(0, sentenceBoundary + 1).trimEnd();
  }

  const maxBody = Math.max(1, max - 1);
  const sliced = source.slice(0, maxBody);
  const wordBoundary = sliced.lastIndexOf(" ");
  const cutoff = wordBoundary >= Math.floor(max * 0.55) ? sliced.slice(0, wordBoundary) : sliced;
  return `${cutoff.trimEnd()}…`;
}

function stripHtml(html: string): string {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function toText(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function stableShortHash(input: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function arrayBufferToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function validateGenerateRequestBody(input: unknown, security: ResolvedSecurityConfig): GenerateRequestBody {
  const body = requireObject(input, "Request body");
  const templateIds = parseTemplateIds(body.templateIds, security);
  const slotOverrides = parseSlotOverrides(body.slotOverrides, security);
  const brandTokens = parseBrandTokens(body.brandTokens);
  const design = parseDesignOverrides(body.design);
  const storage = parseStorageOptions(body.storage);
  const llm = parseLlmOverrides(body.llm);
  const image = parseImageOptions(body.image);
  const output = parseOutputOptions(body.output);

  return {
    slug: optionalString(body.slug, "slug", 200),
    url: optionalString(body.url, "url", 400),
    brandingColor: optionalColor(body.brandingColor, "brandingColor"),
    brandName: optionalString(body.brandName, "brandName", 120),
    prompt: optionalString(body.prompt, "prompt", 1200),
    templateIds,
    slotOverrides,
    brandTokens,
    design,
    storage,
    notifyUrl: optionalString(body.notifyUrl, "notifyUrl", 500),
    llm,
    image,
    output
  };
}

function validateDirectContentRequestBody(input: unknown, security: ResolvedSecurityConfig): DirectContentRequestBody {
  const body = requireObject(input, "Request body");
  const directContentMaxChars = Math.max(
    1_000,
    Number(PIPELINE_CONFIG.generation?.limits?.direct_content_max_chars ?? 30_000)
  );
  const tags = body.tags;
  const tagValue =
    tags === undefined
      ? undefined
      : Array.isArray(tags)
        ? tags.map((item) => optionalString(item, "tags[]", 80)).filter((item): item is string => Boolean(item))
        : optionalString(tags, "tags", 500);

  const request = {
    title: optionalString(body.title, "title", 280),
    excerpt: optionalString(body.excerpt, "excerpt", 1_000),
    content: optionalString(body.content, "content", directContentMaxChars),
    body: optionalString(body.body, "body", directContentMaxChars),
    slug: optionalString(body.slug, "slug", 200),
    url: optionalString(body.url, "url", 500),
    feature_image: optionalString(body.feature_image, "feature_image", 2_000),
    tags: tagValue,
    primary_tag: optionalString(body.primary_tag, "primary_tag", 80),
    brandingColor: optionalColor(body.brandingColor, "brandingColor"),
    brandName: optionalString(body.brandName, "brandName", 120),
    prompt: optionalString(body.prompt, "prompt", 1200),
    templateIds: parseTemplateIds(body.templateIds, security),
    slotOverrides: parseSlotOverrides(body.slotOverrides, security),
    brandTokens: parseBrandTokens(body.brandTokens),
    design: parseDesignOverrides(body.design),
    storage: parseStorageOptions(body.storage),
    notifyUrl: optionalString(body.notifyUrl, "notifyUrl", 500),
    llm: parseLlmOverrides(body.llm),
    image: parseImageOptions(body.image),
    output: parseOutputOptions(body.output)
  } satisfies DirectContentRequestBody;

  return request;
}

function validateWebhookPayload(input: unknown): GhostWebhookPayload {
  const body = requireObject(input, "Webhook payload");
  const postRaw = body.post;
  const post =
    postRaw && typeof postRaw === "object" && !Array.isArray(postRaw)
      ? (postRaw as Record<string, unknown>)
      : undefined;
  const currentRaw = post?.current;
  const current =
    currentRaw && typeof currentRaw === "object" && !Array.isArray(currentRaw)
      ? (currentRaw as Record<string, unknown>)
      : undefined;

  return {
    slug: optionalString(body.slug, "payload.slug", 200),
    url: optionalString(body.url, "payload.url", 500),
    post: post
      ? {
        slug: optionalString(post.slug, "payload.post.slug", 200),
        url: optionalString(post.url, "payload.post.url", 500),
        current: current
          ? {
            slug: optionalString(current.slug, "payload.post.current.slug", 200),
            url: optionalString(current.url, "payload.post.current.url", 500)
          }
          : undefined
      }
      : undefined
  };
}

function parseTemplateIds(input: unknown, security: ResolvedSecurityConfig): Partial<Record<TemplateKind, string>> | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "templateIds");
  const entries = Object.entries(object);
  if (entries.length > security.request_limits.template_ids_max_keys) {
    throw new HttpError(
      400,
      `templateIds supports at most ${security.request_limits.template_ids_max_keys} keys`
    );
  }
  const parsed: Partial<Record<TemplateKind, string>> = {};
  for (const [key, value] of entries) {
    if (!isTemplateKind(key)) {
      throw new HttpError(400, `templateIds contains unsupported format key: ${key}`);
    }
    const templateId = optionalString(value, `templateIds.${key}`, 140);
    if (!templateId) {
      continue;
    }
    if (!TEMPLATE_IDS_BY_FORMAT[key].has(templateId)) {
      throw new HttpError(400, `templateIds.${key} references unknown template: ${templateId}`);
    }
    parsed[key] = templateId;
  }
  return Object.keys(parsed).length > 0 ? parsed : undefined;
}

function parseSlotOverrides(input: unknown, security: ResolvedSecurityConfig): Record<string, string> | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "slotOverrides");
  const entries = Object.entries(object);
  if (entries.length > security.request_limits.slot_overrides_max_keys) {
    throw new HttpError(
      400,
      `slotOverrides supports at most ${security.request_limits.slot_overrides_max_keys} keys`
    );
  }
  const parsed: Record<string, string> = {};
  for (const [key, value] of entries) {
    const normalizedKey = normalizeSlotKey(key);
    if (!normalizedKey) {
      continue;
    }
    const text = optionalString(value, `slotOverrides.${key}`, PIPELINE_CONFIG.generation.limits.slot_text_max_chars);
    if (!text) {
      continue;
    }
    parsed[normalizedKey] = text;
  }
  return Object.keys(parsed).length > 0 ? parsed : undefined;
}

function parseBrandTokens(input: unknown): BrandTokenOverrides | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "brandTokens");
  const parsed: BrandTokenOverrides = {};
  const tokenKeys: Array<keyof BrandTokenOverrides> = [
    "primaryText",
    "secondaryText",
    "mutedText",
    "surfaceBase",
    "surfaceElevated",
    "borderSubtle",
    "accent",
    "accentForeground"
  ];
  for (const tokenKey of tokenKeys) {
    const value = optionalColor(object[tokenKey], `brandTokens.${tokenKey}`);
    if (value) {
      parsed[tokenKey] = value;
    }
  }
  return Object.keys(parsed).length > 0 ? parsed : undefined;
}

function parseDesignOverrides(input: unknown): TemplateControlSet | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "design");
  const parsed: TemplateControlSet = {};

  if (object.showBrandBadge !== undefined) {
    parsed.showBrandBadge = requiredBoolean(object.showBrandBadge, "design.showBrandBadge");
  }
  if (object.showSlideBadge !== undefined) {
    parsed.showSlideBadge = requiredBoolean(object.showSlideBadge, "design.showSlideBadge");
  }
  if (object.showMetaFooter !== undefined) {
    parsed.showMetaFooter = requiredBoolean(object.showMetaFooter, "design.showMetaFooter");
  }
  if (object.showTitleKicker !== undefined) {
    parsed.showTitleKicker = requiredBoolean(object.showTitleKicker, "design.showTitleKicker");
  }
  if (object.showDecorLayers !== undefined) {
    parsed.showDecorLayers = requiredBoolean(object.showDecorLayers, "design.showDecorLayers");
  }
  if (object.textAlign !== undefined) {
    const textAlign = optionalString(object.textAlign, "design.textAlign", 20);
    if (textAlign && textAlign !== "left" && textAlign !== "center") {
      throw new HttpError(400, "design.textAlign must be either left or center");
    }
    parsed.textAlign = textAlign as TemplateControlSet["textAlign"];
  }
  if (object.imageOpacity !== undefined) {
    parsed.imageOpacity = clampNumber(
      requiredNumber(object.imageOpacity, "design.imageOpacity"),
      0,
      1,
      1
    );
  }
  if (object.contentMaxWidth !== undefined) {
    parsed.contentMaxWidth = Math.round(
      clampNumber(requiredNumber(object.contentMaxWidth, "design.contentMaxWidth"), 320, 2000, 1020)
    );
  }
  if (object.contentInset !== undefined) {
    parsed.contentInset = Math.round(
      clampNumber(requiredNumber(object.contentInset, "design.contentInset"), 0, 220, 48)
    );
  }
  parsed.metaLeftText = optionalString(object.metaLeftText, "design.metaLeftText", 120);
  parsed.metaRightText = optionalString(object.metaRightText, "design.metaRightText", 120);

  const formatOverridesRaw = object.formatOverrides;
  if (formatOverridesRaw !== undefined) {
    const formatOverridesObj = requireObject(formatOverridesRaw, "design.formatOverrides");
    const formatOverrides: Partial<Record<TemplateKind, TemplateControlSet>> = {};
    for (const [rawFormat, rawControl] of Object.entries(formatOverridesObj)) {
      if (!isTemplateKind(rawFormat)) {
        throw new HttpError(400, `design.formatOverrides contains unsupported format: ${rawFormat}`);
      }
      formatOverrides[rawFormat] = parseDesignOverrides(rawControl) ?? {};
    }
    parsed.formatOverrides = formatOverrides;
  }

  return Object.keys(parsed).length > 0 ? parsed : undefined;
}

function parseStorageOptions(input: unknown): StorageOptions | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "storage");
  const mode = optionalString(object.mode, "storage.mode", 20);
  if (mode && mode !== "overwrite" && mode !== "versioned") {
    throw new HttpError(400, "storage.mode must be overwrite or versioned");
  }
  return {
    mode: mode as StorageOptions["mode"],
    includeDate: object.includeDate !== undefined ? requiredBoolean(object.includeDate, "storage.includeDate") : undefined,
    runId: optionalString(object.runId, "storage.runId", PIPELINE_CONFIG.generation.limits.storage_run_id_max_chars)
  };
}

function parseLlmOverrides(input: unknown): LlmPromptOverrides | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "llm");
  const systemPrompt = parsePromptField(object.systemPrompt, "llm.systemPrompt");
  const userInstructions = parsePromptField(object.userInstructions, "llm.userInstructions");
  const userInstructionsAppend = optionalString(object.userInstructionsAppend, "llm.userInstructionsAppend", 2_000);
  const temperature =
    object.temperature !== undefined
      ? clampNumber(requiredNumber(object.temperature, "llm.temperature"), 0, 2, PIPELINE_CONFIG.generation.llm.temperature)
      : undefined;
  const maxTokens =
    object.maxTokens !== undefined
      ? Math.round(clampNumber(requiredNumber(object.maxTokens, "llm.maxTokens"), 256, 4096, PIPELINE_CONFIG.generation.llm.max_tokens))
      : undefined;

  const parsed: LlmPromptOverrides = {
    systemPrompt,
    userInstructions,
    userInstructionsAppend,
    temperature,
    maxTokens
  };
  return Object.values(parsed).some((value) => value !== undefined) ? parsed : undefined;
}

function parsePromptField(input: unknown, field: string): string | string[] | undefined {
  if (input === undefined) {
    return undefined;
  }
  if (typeof input === "string") {
    return ensureLength(input.trim(), 2_000, input.trim());
  }
  if (Array.isArray(input)) {
    const lines = input.map((line, index) => optionalString(line, `${field}[${index}]`, 300)).filter((line): line is string => Boolean(line));
    if (lines.length > 80) {
      throw new HttpError(400, `${field} accepts up to 80 lines`);
    }
    return lines;
  }
  throw new HttpError(400, `${field} must be a string or an array of strings`);
}

function parseImageOptions(input: unknown): ImageGenerationOptions | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "image");
  const mode = optionalString(object.mode, "image.mode", 16);
  if (mode && !["auto", "none", "feature", "stock", "ai", "custom"].includes(mode)) {
    throw new HttpError(400, "image.mode must be one of auto, none, feature, stock, ai, custom");
  }
  const parsed: ImageGenerationOptions = {
    mode: mode as ImageGenerationOptions["mode"],
    customUrl: optionalString(object.customUrl, "image.customUrl", 2_000),
    prompt: optionalString(object.prompt, "image.prompt", PIPELINE_CONFIG.generation.limits.image_prompt_max_chars),
    allowStock: object.allowStock !== undefined ? requiredBoolean(object.allowStock, "image.allowStock") : undefined,
    allowAi: object.allowAi !== undefined ? requiredBoolean(object.allowAi, "image.allowAi") : undefined,
    preferFeature: object.preferFeature !== undefined ? requiredBoolean(object.preferFeature, "image.preferFeature") : undefined
  };
  return Object.values(parsed).some((value) => value !== undefined) ? parsed : undefined;
}

function parseOutputOptions(input: unknown): OutputOptions | undefined {
  if (input === undefined) {
    return undefined;
  }
  const object = requireObject(input, "output");
  const formatsRaw = object.formats;
  let formats: TemplateKind[] | undefined;
  if (formatsRaw !== undefined) {
    if (!Array.isArray(formatsRaw)) {
      throw new HttpError(400, "output.formats must be an array");
    }
    const unique = new Set<TemplateKind>();
    for (const [index, value] of formatsRaw.entries()) {
      const item = optionalString(value, `output.formats[${index}]`, 40);
      if (!item) {
        continue;
      }
      if (!isTemplateKind(item)) {
        throw new HttpError(400, `Unsupported output format: ${item}`);
      }
      unique.add(item);
    }
    formats = [...unique];
    if (formats.length === 0) {
      throw new HttpError(400, "output.formats cannot be empty");
    }
  }

  const carouselSlides =
    object.carouselSlides !== undefined
      ? Math.round(clampNumber(requiredNumber(object.carouselSlides, "output.carouselSlides"), 1, 10, DEFAULT_CAROUSEL_SLIDES))
      : undefined;
  const postCount =
    object.postCount !== undefined
      ? Math.round(clampNumber(requiredNumber(object.postCount, "output.postCount"), 1, 10, 1))
      : undefined;

  const parsed: OutputOptions = {
    formats,
    carouselSlides,
    postCount
  };
  return Object.values(parsed).some((value) => value !== undefined) ? parsed : undefined;
}

function requireObject(input: unknown, field: string): Record<string, unknown> {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new HttpError(400, `${field} must be an object`);
  }
  return input as Record<string, unknown>;
}

function optionalString(input: unknown, field: string, maxLength: number): string | undefined {
  if (input === undefined || input === null) {
    return undefined;
  }
  if (typeof input !== "string") {
    throw new HttpError(400, `${field} must be a string`);
  }
  const trimmed = input.trim();
  if (!trimmed) {
    return undefined;
  }
  if (trimmed.length > maxLength) {
    throw new HttpError(400, `${field} exceeds maximum length ${maxLength}`);
  }
  return trimmed;
}

function optionalEnumString(input: unknown, field: string, allowed: Set<string>): string | undefined {
  const value = optionalString(input, field, 120);
  if (!value) {
    return undefined;
  }
  if (!allowed.has(value)) {
    throw new HttpError(400, `${field} must be one of: ${[...allowed].join(", ")}`);
  }
  return value;
}

function optionalColor(input: unknown, field: string): string | undefined {
  const value = optionalString(input, field, 20);
  if (!value) {
    return undefined;
  }
  if (!/^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/.test(value)) {
    throw new HttpError(400, `${field} must be a valid hex color`);
  }
  return value;
}

function requiredBoolean(input: unknown, field: string): boolean {
  if (typeof input !== "boolean") {
    throw new HttpError(400, `${field} must be a boolean`);
  }
  return input;
}

function requiredNumber(input: unknown, field: string): number {
  if (typeof input !== "number" || !Number.isFinite(input)) {
    throw new HttpError(400, `${field} must be a finite number`);
  }
  return input;
}

function sanitizeImageUrl(
  rawValue: string,
  security: ResolvedSecurityConfig,
  field: string,
  options: { allowDataUrl: boolean; requireAllowedHost: boolean }
): string {
  const value = rawValue.trim();
  if (!value) {
    return "";
  }
  if (options.allowDataUrl && value.startsWith("data:image/")) {
    return value;
  }
  return sanitizeHttpUrl(value, security, field, {
    requireAllowedHost: options.requireAllowedHost,
    hostAllowlist: security.outbound.allowed_image_hosts
  });
}

function sanitizeHttpUrl(
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
  const shouldEnforceAllowlist = requireAllowedHost || allowlist.length > 0;
  if (shouldEnforceAllowlist && !hostMatchesAllowlist(hostname, allowlist)) {
    throw new HttpError(403, `${field} host is not in the allowed host list`);
  }

  return parsed.toString();
}

function isPrivateHostname(hostname: string): boolean {
  const host = hostname.toLowerCase();
  if (host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) {
    return true;
  }
  if (isPrivateIpv4(host)) {
    return true;
  }
  return isPrivateIpv6(host);
}

function isPrivateIpv4(hostname: string): boolean {
  const match = hostname.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!match) {
    return false;
  }
  const octets = match.slice(1).map((part) => Number(part));
  if (octets.some((part) => part < 0 || part > 255)) {
    return false;
  }
  const [a, b] = octets;
  if (a === 10 || a === 127 || a === 0) {
    return true;
  }
  if (a === 169 && b === 254) {
    return true;
  }
  if (a === 172 && b >= 16 && b <= 31) {
    return true;
  }
  if (a === 192 && b === 168) {
    return true;
  }
  if (a === 100 && b >= 64 && b <= 127) {
    return true;
  }
  return false;
}

function isPrivateIpv6(hostname: string): boolean {
  const host = hostname.toLowerCase();
  if (host === "::1" || host === "0:0:0:0:0:0:0:1") {
    return true;
  }
  if (host.startsWith("fc") || host.startsWith("fd") || host.startsWith("fe80:")) {
    return true;
  }
  if (host.startsWith("::ffff:127.")) {
    return true;
  }
  return false;
}

function hostMatchesAllowlist(hostname: string, allowlist: string[]): boolean {
  if (allowlist.length === 0) {
    return false;
  }
  for (const allowed of allowlist) {
    const normalized = allowed.trim().toLowerCase();
    if (!normalized) {
      continue;
    }
    if (hostname === normalized || hostname.endsWith(`.${normalized}`)) {
      return true;
    }
  }
  return false;
}

function parseBooleanString(value: string, fallback: boolean): boolean {
  const normalized = value.trim().toLowerCase();
  if (["true", "1", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["false", "0", "no", "off"].includes(normalized)) {
    return false;
  }
  return fallback;
}

function clampNumber(value: number | undefined, min: number, max: number, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, value));
}

function assertRequiredEnv(env: Env): void {
  if (!env.GHOST_API_URL?.trim()) {
    throw new HttpError(500, "Missing env var GHOST_API_URL");
  }
  if (!env.GHOST_CONTENT_API_KEY?.trim()) {
    throw new HttpError(500, "Missing env var GHOST_CONTENT_API_KEY");
  }
}

async function readJsonBody<T>(request: Request, maxBytes: number): Promise<T> {
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
    if (error instanceof HttpError) {
      throw error;
    }
    if (!raw) {
      throw new HttpError(400, "Invalid or empty JSON body");
    }
    throw new HttpError(400, "Invalid JSON body");
  }
  return body as T;
}

function json(payload: unknown, status = 200, headers?: Record<string, string>): Response {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...(headers ?? {})
    }
  });
}

function handleError(error: unknown): Response {
  if (error instanceof HttpError) {
    return json({ error: error.message }, error.status, error.headers);
  }

  const message = error instanceof Error ? error.message : "Unexpected error";
  return json({ error: message }, 500);
}

class HttpError extends Error {
  status: number;
  headers?: Record<string, string>;

  constructor(status: number, message: string, headers?: Record<string, string>) {
    super(message);
    this.status = status;
    this.headers = headers;
  }
}
