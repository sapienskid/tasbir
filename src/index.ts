import { Hono } from "hono";
import { cors } from "hono/cors";
import { secureHeaders } from "hono/secure-headers";
import type { MarketingOrchestratorAgent } from "./agents/marketing-orchestrator";
import {
  generateHtmlLayout,
  normalizeSourceContent,
  stripHtml,
  createModelChain,
  resolveProviderConfig,
} from "./ai";
import { PIPELINE_CONFIG, getFormatConfig, getAllFormats, getFormatNames, setFormat, deleteFormat, loadFormatsFromStorage, type FormatConfig } from "./config";
import {
  HttpError,
  enforceApiAuth,
  enforceRateLimit,
  resolveSecurityConfig,
  readJsonBody,
  readJsonBodyWithRaw,
  sanitizeHttpUrl,
  type ResolvedSecurityConfig,
  type Env as SecurityEnv
} from "./lib/security";
import {
  tokensToCSSFromRaw,
  fontImportFromTokens,
  buildTailwindConfigFromTokens,
  stripInjectedDesignTokens,
  formatDesignTokensForPromptFromObject,
  getDefaultDesignTokens,
  normalizeDesignTokensForRendering,
} from "../shared/tokens";
import {
  loadSettings,
  saveSettings,
  patchSettings,
  getDefaultSettings,
  type WorkspaceSettings,
} from "./lib/settings";
import {
  listTemplates,
  getTemplate,
  saveTemplate,
  deleteTemplate,
  toggleTemplate,
  fillTemplateSlots,
  extractSlotsFromHtml,
  validateTemplateHtml,
} from "./lib/templates";

interface LlmPromptOverrides {
  systemPrompt?: string | string[];
  userInstructions?: string | string[];
  userInstructionsAppend?: string;
  temperature?: number;
  maxTokens?: number;
}

interface LlmOutput {
  generated_html: string;
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

function isCloudflareWorker(): boolean {
  return typeof navigator !== "undefined" && navigator.userAgent === "Cloudflare-Workers";
}

async function launchRenderingBrowser(env: Env): Promise<any> {
  const keepAliveMs = (PIPELINE_CONFIG.runtime?.browser_keep_alive_ms as number) ?? 60000;
  const shouldUseCloudflareBrowser = isCloudflareWorker() || Boolean(env.BROWSER);

  if (shouldUseCloudflareBrowser) {
    if (!env.BROWSER) {
      throw new HttpError(500, "BROWSER binding is required for Cloudflare Browser Rendering");
    }
    const cloudflarePuppeteer = (await import("@cloudflare/puppeteer")).default as any;
    return cloudflarePuppeteer.launch(env.BROWSER, { keep_alive: keepAliveMs });
  }

  const nodePuppeteer = (await import("puppeteer")).default as any;
  return nodePuppeteer.launch({ headless: true });
}

interface Env extends SecurityEnv {
  MARKETING_ORCHESTRATOR?: DurableObjectNamespace<MarketingOrchestratorAgent>;
  SETTINGS_KV?: KVNamespace;
  TEMPLATES_KV?: KVNamespace;
}

interface ImageGenerationOptions {
  mode?: "auto" | "none" | "feature" | "ai" | "custom";
  customUrl?: string;
  prompt?: string;
  allowAi?: boolean;
  preferFeature?: boolean;
}

interface OutputOptions {
  formats?: string[];
  carouselSlides?: number;
  postCount?: number;
}

interface AgentRenderPolicy {
  allowMarkdown?: boolean;
  allowMath?: boolean;
  allowDiagrams?: boolean;
  allowTextInAiImages?: boolean;
}

interface AgentOptions {
  mode?: "agentic";
  promptProfile?: string;
  renderPolicy?: AgentRenderPolicy;
}

interface GenerateRequestBody {
  slug?: string;
  url?: string;
  brandName?: string;
  prompt?: string;
  storage?: StorageOptions;
  notifyUrl?: string;
  image?: ImageGenerationOptions;
  output?: OutputOptions;
  agent?: AgentOptions;
  designTokens?: Record<string, unknown>;
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
  brandName?: string;
  prompt?: string;
  storage?: StorageOptions;
  notifyUrl?: string;
  image?: ImageGenerationOptions;
  output?: OutputOptions;
  agent?: AgentOptions;
  designTokens?: Record<string, unknown>;
}

interface StorageOptions {
  mode?: "overwrite" | "versioned";
  includeDate?: boolean;
  runId?: string;
}

interface SelectedImage {
  source: "feature" | "ai" | "custom" | "none";
  imageUrl: string;
}

interface StoredAsset {
  format: string;
  key: string;
  url: string | null;
}

interface GhostWebhookPayload {
  post?: {
    current?: { slug?: string; url?: string };
    slug?: string;
    url?: string;
  };
  slug?: string;
  url?: string;
}

interface ResolvedAgentRenderPolicy {
  allowMarkdown: boolean;
  allowMath: boolean;
  allowDiagrams: boolean;
  allowTextInAiImages: boolean;
}

interface ResolvedAgentPromptProfile {
  name: string;
  mastermind: string[];
  strategist: string[];
  copywriter: string[];
  visualDirector: string[];
  renderGuard: string[];
}

interface AgentExecutionContext {
  mode: "agentic";
  promptProfile: ResolvedAgentPromptProfile;
  renderPolicy: ResolvedAgentRenderPolicy;
  copyOverrides?: LlmPromptOverrides;
  strategicBrief: string;
  visualNotes: string;
  warnings: string[];
}

const DEFAULT_IMAGE_MODEL = (PIPELINE_CONFIG.generation?.image?.default_model as string) || "@cf/black-forest-labs/flux-1-schnell";
const DEFAULT_CAROUSEL_SLIDES = (PIPELINE_CONFIG.generation?.carousel_required_slides as number) || 5;

const DEFAULT_AGENT_PROFILE: ResolvedAgentPromptProfile = {
  name: "default",
  mastermind: [],
  strategist: [],
  copywriter: [],
  visualDirector: [],
  renderGuard: []
};

const DEFAULT_AGENT_RENDER_POLICY: ResolvedAgentRenderPolicy = {
  allowMarkdown: true,
  allowMath: true,
  allowDiagrams: true,
  allowTextInAiImages: false
};

const AGENT_APPLIED_ROLES = ["mastermind", "strategist", "copywriter", "visual_director", "render_guard"] as const;

const app = new Hono<{ Bindings: Env }>();

// Initialize formats from R2 storage on first request
let formatsInitialized = false;
async function ensureFormatsLoaded(env: Env) {
  if (formatsInitialized) return;
  try {
    const stored = await env.OUTPUT_BUCKET.get("config/formats.json");
    if (stored) {
      const formats = await stored.json() as Record<string, FormatConfig>;
      loadFormatsFromStorage(formats);
      console.log("[startup] Loaded custom formats from R2");
    }
  } catch (error) {
    console.warn("[startup] Failed to load formats from R2:", error);
  }
  formatsInitialized = true;
}

app.use("*", async (c, next) => {
  await ensureFormatsLoaded(c.env);
  await next();
});

app.use("*", async (c, next) => {
  const security = resolveSecurityConfig(c.env);
  if (security.cors.enabled) {
    const corsHandler = cors({
      origin: security.cors.allowed_origins.includes("*") ? "*" : security.cors.allowed_origins,
      allowHeaders: security.cors.allowed_headers,
      allowMethods: security.cors.allowed_methods,
      maxAge: security.cors.max_age_seconds,
      credentials: security.cors.allow_credentials
    });
    return corsHandler(c, next);
  }
  await next();
});

app.use("*", async (c, next) => {
  if (c.req.method === "OPTIONS") return next();
  return secureHeaders({
    xContentTypeOptions: true,
    referrerPolicy: "no-referrer"
  })(c, next);
});

app.get("/health", (c) => c.json({ ok: true }));

app.get("/config/design-tokens", (c) => {
  const tokens = normalizeDesignTokensForRendering(getDefaultDesignTokens() as unknown as Record<string, unknown>);
  return c.json({ tokens, tailwindConfig: buildTailwindConfigFromTokens(tokens) });
});

app.get("/config/prompts", (c) => {
  const agentsConfig = (PIPELINE_CONFIG.generation?.agents ?? {}) as Record<string, any>;
  const prompts = (agentsConfig.prompts ?? {}) as Record<string, any>;
  return c.json({
    html_layout_system_prompt: prompts.html_layout_system_prompt ?? [],
    html_layout_user_instructions: prompts.html_layout_user_instructions ?? [],
    prompt_profiles: agentsConfig.prompt_profiles ?? {},
    render_policy: agentsConfig.render_policy ?? {}
  });
});

app.get("/config/formats", (c) => c.json({ formats: getAllFormats() }));

app.get("/asset", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");

  const key = (c.req.query("key") || "").trim();
  if (!key) throw new HttpError(400, "Missing required query parameter: key");
  if (key.length > 1024) throw new HttpError(400, "Asset key is too long");
  if (key.startsWith("/") || key.includes("..")) throw new HttpError(400, "Invalid asset key");

  const object = await c.env.OUTPUT_BUCKET.get(key);
  if (!object) throw new HttpError(404, "Asset not found");

  const contentType = object.httpMetadata?.contentType || "application/octet-stream";
  const cacheControl = object.httpMetadata?.cacheControl || "private, max-age=60";
  return new Response(object.body, {
    status: 200,
    headers: {
      "content-type": contentType,
      "cache-control": cacheControl,
    },
  });
});

function applyBodyDesignSystemClasses(html: string): string {
  return html.replace(/<body([^>]*)>/i, (match, attrs) => {
    const current = String(attrs || "");
    const classMatch = current.match(/class\s*=\s*"([^"]*)"|class\s*=\s*'([^']*)'/i);
    const required = ["font-sans", "bg-surface-base", "text-content-primary"];
    if (classMatch) {
      const existing = (classMatch[1] || classMatch[2] || "").trim();
      const all = [...new Set([...existing.split(/\s+/).filter(Boolean), ...required])].join(" ");
      return match.replace(classMatch[0], `class="${all}"`);
    }
    return `<body${current} class="${required.join(" ")}">`;
  });
}

function injectDesignTokensIntoHtml(html: string, tokens: Record<string, unknown>): string {
  if (!html.trim()) return html;

  const normalizedTokens = normalizeDesignTokensForRendering(tokens);
  let nextHtml = applyBodyDesignSystemClasses(stripInjectedDesignTokens(html));
  const cssVars = tokensToCSSFromRaw(normalizedTokens);
  const fontLinks = fontImportFromTokens(normalizedTokens);
  const tailwindConfig = JSON.stringify(buildTailwindConfigFromTokens(normalizedTokens));
  const tailwindConfigScript = `<script id="tasbir-tailwind-config">window.tailwind = window.tailwind || {}; window.tailwind.config = ${tailwindConfig};</script>`;
  const baseline = [
    "html, body {",
    "  margin: 0;",
    "  padding: 0;",
    "  width: 100%;",
    "  height: 100%;",
    "  background: var(--surface-base);",
    "  color: var(--text-primary);",
    "  font-family: var(--font-sans);",
    "}",
    "*, *::before, *::after { box-sizing: border-box; }",
    "h1, h2, h3, h4, h5, h6 { color: var(--text-primary, inherit); }",
    "p, span, li, small { color: var(--text-secondary, inherit); }",
    ".ds-accent { color: var(--text-accent, var(--color-primary-500)); }",
    ".ds-surface { background: var(--surface-elevated, transparent); }",
    ".ds-border { border-color: var(--color-neutral-300); }",
  ].join("\n");

  const hasTailwindCdn = /<script[^>]+src=["'][^"']*cdn\.tailwindcss\.com[^"']*["'][^>]*><\/script>/i.test(nextHtml);
  const hasTailwindConfig = /id=["']tasbir-tailwind-config["']/i.test(nextHtml);

  if (!hasTailwindConfig) {
    if (hasTailwindCdn) {
      nextHtml = nextHtml.replace(
        /<script[^>]+src=["'][^"']*cdn\.tailwindcss\.com[^"']*["'][^>]*><\/script>/i,
        (m) => `${tailwindConfigScript}\n${m}`,
      );
    } else {
      nextHtml = nextHtml.replace(/<head[^>]*>/i, (m) => `${m}\n${tailwindConfigScript}\n<script src="https://cdn.tailwindcss.com"></script>`);
    }
  }

  const injectedBlock = `${fontLinks}\n<style id=\"tasbir-design-tokens\">\n${cssVars}\n\n/* Baseline design-system application */\n${baseline}\n</style>`;

  if (/<\/head>/i.test(nextHtml)) {
    return nextHtml.replace(/<\/head>/i, `${injectedBlock}\n</head>`);
  }
  if (/<head[^>]*>/i.test(nextHtml)) {
    return nextHtml.replace(/<head[^>]*>/i, (m) => `${m}\n${injectedBlock}`);
  }
  if (/<html[^>]*>/i.test(nextHtml)) {
    return nextHtml.replace(/<html[^>]*>/i, (m) => `${m}\n<head>\n${injectedBlock}\n</head>`);
  }
  return `<!DOCTYPE html>\n<html>\n<head>\n${tailwindConfigScript}\n<script src="https://cdn.tailwindcss.com"></script>\n${injectedBlock}\n</head>\n<body class="font-sans bg-surface-base text-content-primary">${nextHtml}</body>\n</html>`;
}

async function loadDesignTokensForGeneration(env: Env): Promise<Record<string, unknown>> {
  try {
    const stored = await env.OUTPUT_BUCKET.get("config/design-tokens.json");
    if (stored) {
      const parsed = await stored.json();
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return normalizeDesignTokensForRendering(parsed as Record<string, unknown>);
      }
    }
  } catch (error) {
    console.warn("[tokens] failed to read saved tokens, falling back to defaults", error);
  }

  return normalizeDesignTokensForRendering(getDefaultDesignTokens() as unknown as Record<string, unknown>);
}

function resolveDesignTokensForRequest(bodyTokens: unknown, fallbackTokens: Record<string, unknown>): Record<string, unknown> {
  if (!bodyTokens || typeof bodyTokens !== "object" || Array.isArray(bodyTokens)) return fallbackTokens;
  return normalizeDesignTokensForRendering(bodyTokens as Record<string, unknown>);
}

app.post("/generate-tokens", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");

  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const vibe = (body.vibe as string) || "custom design system";
  const primaryHint = body.primaryHint as string | undefined;
  const secondaryHint = body.secondaryHint as string | undefined;

  try {
    const { generateTokensAI } = await import("./lib/tokens");
    const tokens = await generateTokensAI(vibe, {
      CLOUDFLARE_API_TOKEN: c.env.CLOUDFLARE_API_TOKEN,
      CLOUDFLARE_ACCOUNT_ID: c.env.CLOUDFLARE_ACCOUNT_ID,
      CLOUDFLARE_MODEL: c.env.CLOUDFLARE_MODEL,
      CLOUDFLARE_FAST_MODEL: c.env.CLOUDFLARE_FAST_MODEL,
    }, primaryHint, secondaryHint);
    
    return c.json(tokens);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[generate-tokens] Error:", message);
    return c.json({ error: message }, 500);
  }
});


app.get("/config", (c) => {
  return c.json({
    formats: getAllFormats(),
    generation: {
      limits: PIPELINE_CONFIG.generation?.limits ?? {},
      prompts: (PIPELINE_CONFIG.generation as any)?.agents?.prompts ?? {},
      prompt_profiles: (PIPELINE_CONFIG.generation as any)?.agents?.prompt_profiles ?? {},
      render_policy: (PIPELINE_CONFIG.generation as any)?.agents?.render_policy ?? {},
      image: PIPELINE_CONFIG.generation?.image ?? {},
      carousel_required_slides: PIPELINE_CONFIG.generation?.carousel_required_slides ?? 5,
    },
    runtime: PIPELINE_CONFIG.runtime ?? {},
    features: PIPELINE_CONFIG.features ?? {},
    storage: PIPELINE_CONFIG.storage ?? {},
  });
});

app.get("/tokens", async (c) => {
  try {
    const stored = await c.env.OUTPUT_BUCKET.get("config/design-tokens.json");
    if (!stored) {
      return c.json(null);
    }
    const tokens = normalizeDesignTokensForRendering(await stored.json() as Record<string, unknown>);
    return c.json(tokens);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[get-tokens] Error:", message);
    return c.json({ error: message }, 500);
  }
});

app.put("/tokens", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");

  try {
    const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
    const normalizedTokens = normalizeDesignTokensForRendering(body);
    await c.env.OUTPUT_BUCKET.put("config/design-tokens.json", JSON.stringify(normalizedTokens), {
      httpMetadata: { contentType: "application/json" }
    });
    return c.json({ ok: true, tokens: normalizedTokens });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[put-tokens] Error:", message);
    return c.json({ error: message }, 500);
  }
});

app.get("/formats", (c) => {
  return c.json(getAllFormats());
});

app.put("/formats/:id", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");

  try {
    const id = c.req.param("id");
    const body = await readJsonBody<FormatConfig>(c.req.raw, security.request_limits.max_json_body_bytes);
    
    if (!body.width || !body.height) {
      return c.json({ error: "width and height are required" }, 400);
    }
    
    setFormat(id, body);
    
    const allFormats = getAllFormats();
    await c.env.OUTPUT_BUCKET.put("config/formats.json", JSON.stringify(allFormats), {
      httpMetadata: { contentType: "application/json" }
    });
    
    return c.json({ ok: true, format: body });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[put-format] Error:", message);
    return c.json({ error: message }, 500);
  }
});

app.delete("/formats/:id", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");

  try {
    const id = c.req.param("id");
    const deleted = deleteFormat(id);
    
    if (!deleted) {
      return c.json({ error: "Format not found" }, 404);
    }
    
    const allFormats = getAllFormats();
    await c.env.OUTPUT_BUCKET.put("config/formats.json", JSON.stringify(allFormats), {
      httpMetadata: { contentType: "application/json" }
    });
    
    return c.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[delete-format] Error:", message);
    return c.json({ error: message }, 500);
  }
});

// ==================== SETTINGS ====================

app.get("/settings", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  if (!c.env.SETTINGS_KV) throw new HttpError(500, "SETTINGS_KV binding is not configured");
  const settings = await loadSettings(c.env.SETTINGS_KV);
  return c.json(settings);
});

app.put("/settings", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.SETTINGS_KV) throw new HttpError(500, "SETTINGS_KV binding is not configured");
  const body = await readJsonBody<Partial<WorkspaceSettings>>(c.req.raw, security.request_limits.max_json_body_bytes);
  await saveSettings(c.env.SETTINGS_KV, body as WorkspaceSettings);
  return c.json({ ok: true });
});

app.patch("/settings", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.SETTINGS_KV) throw new HttpError(500, "SETTINGS_KV binding is not configured");
  const body = await readJsonBody<Partial<WorkspaceSettings>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const settings = await patchSettings(c.env.SETTINGS_KV, body);
  return c.json({ ok: true, settings });
});

// ==================== TEMPLATES ====================

app.get("/templates", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  if (!c.env.TEMPLATES_KV) throw new HttpError(500, "TEMPLATES_KV binding is not configured");
  const templates = await listTemplates(c.env.TEMPLATES_KV);
  return c.json({ templates });
});

app.get("/templates/:id", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  if (!c.env.TEMPLATES_KV || !c.env.OUTPUT_BUCKET) throw new HttpError(500, "KV or R2 binding is not configured");
  const id = c.req.param("id");
  const result = await getTemplate(c.env.TEMPLATES_KV, c.env.OUTPUT_BUCKET, id);
  if (!result) return c.json({ error: "Template not found" }, 404);
  return c.json(result);
});

app.put("/templates/:id", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.TEMPLATES_KV || !c.env.OUTPUT_BUCKET) throw new HttpError(500, "KV or R2 binding is not configured");
  const id = c.req.param("id");
  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const html = typeof body.html === "string" ? body.html : "";
  if (!html) return c.json({ error: "html is required" }, 400);
  const metadata = await saveTemplate(c.env.TEMPLATES_KV, c.env.OUTPUT_BUCKET, id, html, {
    name: typeof body.name === "string" ? body.name : undefined,
    description: typeof body.description === "string" ? body.description : undefined,
    category: typeof body.category === "string" ? body.category : undefined,
  });
  return c.json({ ok: true, metadata });
});

app.delete("/templates/:id", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.TEMPLATES_KV || !c.env.OUTPUT_BUCKET) throw new HttpError(500, "KV or R2 binding is not configured");
  const id = c.req.param("id");
  const deleted = await deleteTemplate(c.env.TEMPLATES_KV, c.env.OUTPUT_BUCKET, id);
  if (!deleted) return c.json({ error: "Template not found" }, 404);
  return c.json({ ok: true });
});

app.post("/templates/:id/toggle", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.TEMPLATES_KV) throw new HttpError(500, "TEMPLATES_KV binding is not configured");
  const id = c.req.param("id");
  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const enabled = typeof body.enabled === "boolean" ? body.enabled : true;
  const metadata = await toggleTemplate(c.env.TEMPLATES_KV, id, enabled);
  if (!metadata) return c.json({ error: "Template not found" }, 404);
  return c.json({ ok: true, metadata });
});

app.post("/templates/:id/validate", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const html = typeof body.html === "string" ? body.html : "";
  const result = validateTemplateHtml(html);
  return c.json(result);
});

app.post("/generate", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  enforceRateLimit(c.req.raw, security, "generate");

  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const validated = validateGenerateRequestBody(body);
  const result = await runPipeline(validated, c.env, security);

  const envNotifyUrl = shouldUseDefaultNotifyWebhook(c.req.url) ? c.env.NOTIFY_WEBHOOK_URL : undefined;
  const notifyUrl = resolveNotifyUrl(validated.notifyUrl, envNotifyUrl, security);
  if (notifyUrl && (PIPELINE_CONFIG.features?.enable_notifications ?? true)) {
    c.executionCtx.waitUntil(sendNotification(notifyUrl, result, security));
  }

  return c.json(result);
});

app.post("/generate-from-content", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  enforceRateLimit(c.req.raw, security, "generate-from-content");

  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const validated = validateDirectContentRequestBody(body);
  const post = buildPostFromDirectContent(validated, security);
  const result = await runPipelineFromPost(post, c.env, validated, security);

  const envNotifyUrl = shouldUseDefaultNotifyWebhook(c.req.url) ? c.env.NOTIFY_WEBHOOK_URL : undefined;
  const notifyUrl = resolveNotifyUrl(validated.notifyUrl, envNotifyUrl, security);
  if (notifyUrl && (PIPELINE_CONFIG.features?.enable_notifications ?? true)) {
    c.executionCtx.waitUntil(sendNotification(notifyUrl, result, security));
  }

  return c.json(result);
});

app.post("/webhook/ghost", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "webhook");

  const { raw, body } = await readJsonBodyWithRaw(c.req.raw, security.request_limits.max_json_body_bytes);
  await verifyGhostWebhookRequest(c.req.raw, c.env, raw);
  const payload = validateWebhookPayload(body);
  const slug = extractSlugFromWebhook(payload);
  if (!slug) throw new HttpError(400, "Could not resolve slug from Ghost webhook payload");

  const result = await runPipeline({ slug }, c.env, security);
  const envNotifyUrl = shouldUseDefaultNotifyWebhook(c.req.url) ? c.env.NOTIFY_WEBHOOK_URL : undefined;
  const notifyUrl = resolveNotifyUrl(undefined, envNotifyUrl, security);
  if (notifyUrl && (PIPELINE_CONFIG.features?.enable_notifications ?? true)) {
    c.executionCtx.waitUntil(sendNotification(notifyUrl, result, security));
  }

  return c.json(result);
});

app.notFound((c) => c.json({
  error: "Not found",
  routes: ["POST /generate", "POST /generate-from-content", "POST /webhook/ghost", "GET /health", "GET /settings", "PUT /settings", "PATCH /settings", "GET /templates", "GET /templates/:id", "PUT /templates/:id", "DELETE /templates/:id", "POST /templates/:id/toggle", "POST /templates/:id/validate", "GET /config/design-tokens", "GET /config/prompts", "GET /config/formats"]
}, 404 as any));

app.onError((err, c) => {
  console.error("Unhandled error:", err);
  if (err instanceof HttpError) return c.json({ error: err.message }, err.status as any);
  const message = err instanceof Error ? err.message : "Unexpected error";
  return c.json({ error: message }, 500 as any);
});

export { MarketingOrchestratorAgent } from "./agents/marketing-orchestrator";

export default app;

// ==================== AGENT CONTEXT ====================

function resolveAgentExecutionContext(options: AgentOptions | undefined): AgentExecutionContext {
  const warnings: string[] = [];
  const agentsConfig = ((PIPELINE_CONFIG.generation as any).agents ?? {}) as Record<string, unknown>;
  const agentPrompts = asRecord(agentsConfig.prompts);
  const featureEnabled = Boolean(PIPELINE_CONFIG.features?.enable_agentic_orchestration);
  if (!featureEnabled) warnings.push("agentic_disabled_by_feature_flag");

  const requestedProfile = toSingleLineString(agentsConfig.default_prompt_profile) || DEFAULT_AGENT_PROFILE.name;
  const promptProfile = resolveAgentPromptProfile(requestedProfile, agentsConfig, warnings);
  const renderPolicyDefaults = resolveAgentRenderPolicyDefaults(agentsConfig);
  const renderPolicy: ResolvedAgentRenderPolicy = {
    allowMarkdown: options?.renderPolicy?.allowMarkdown ?? renderPolicyDefaults.allowMarkdown,
    allowMath: options?.renderPolicy?.allowMath ?? renderPolicyDefaults.allowMath,
    allowDiagrams: options?.renderPolicy?.allowDiagrams ?? renderPolicyDefaults.allowDiagrams,
    allowTextInAiImages: options?.renderPolicy?.allowTextInAiImages ?? renderPolicyDefaults.allowTextInAiImages
  };

  const copySystemPrompt = mergePromptField(
    agentPrompts?.html_layout_system_prompt as string[] | string | undefined,
    [...promptProfile.mastermind, ...promptProfile.copywriter]
  );
  const copyUserInstructions = agentPrompts?.html_layout_user_instructions as string[] | string | undefined;

  const renderGuardNotes = promptProfile.renderGuard.join(" ").trim();
  const strategistNotes = promptProfile.strategist.join(" ").trim();
  const baseInstructionAppend = [strategistNotes, renderGuardNotes].filter(Boolean).join("\n");

  return {
    mode: "agentic",
    promptProfile,
    renderPolicy,
    copyOverrides: {
      systemPrompt: copySystemPrompt,
      userInstructions: copyUserInstructions,
      userInstructionsAppend: baseInstructionAppend || undefined
    },
    strategicBrief: "",
    visualNotes: promptProfile.visualDirector.join(" ").trim(),
    warnings
  };
}

function resolveAgentPromptProfile(requestedName: string, agentsConfig: Record<string, unknown>, warnings: string[]): ResolvedAgentPromptProfile {
  const profilesRaw = asRecord(agentsConfig.prompt_profiles);
  const profileRaw = asRecord(profilesRaw?.[requestedName]) ?? asRecord(profilesRaw?.default);
  if (!profileRaw) {
    warnings.push("agent_prompt_profile_missing_default");
    return { ...DEFAULT_AGENT_PROFILE, name: requestedName || DEFAULT_AGENT_PROFILE.name };
  }
  const roles = asRecord(profileRaw.roles);
  return {
    name: requestedName || DEFAULT_AGENT_PROFILE.name,
    mastermind: toPromptLines(profileRaw.mastermind),
    strategist: toPromptLines(roles?.strategist),
    copywriter: toPromptLines(roles?.copywriter),
    visualDirector: toPromptLines(roles?.visual_director),
    renderGuard: toPromptLines(roles?.render_guard)
  };
}

function resolveAgentRenderPolicyDefaults(agentsConfig: Record<string, unknown>): ResolvedAgentRenderPolicy {
  const renderPolicy = asRecord(agentsConfig.render_policy);
  return {
    allowMarkdown: toBoolean(renderPolicy?.allow_markdown, DEFAULT_AGENT_RENDER_POLICY.allowMarkdown),
    allowMath: toBoolean(renderPolicy?.allow_math, DEFAULT_AGENT_RENDER_POLICY.allowMath),
    allowDiagrams: toBoolean(renderPolicy?.allow_diagrams, DEFAULT_AGENT_RENDER_POLICY.allowDiagrams),
    allowTextInAiImages: toBoolean(renderPolicy?.allow_text_in_ai_images, DEFAULT_AGENT_RENDER_POLICY.allowTextInAiImages)
  };
}

async function resolveAgentContextForRun(args: {
  env: Env;
  post: GhostPost;
  baseContext: AgentExecutionContext;
  userPrompt?: string;
  requestedFormats: string[];
}): Promise<AgentExecutionContext> {
  const context = cloneAgentExecutionContext(args.baseContext);
  if (!args.env.MARKETING_ORCHESTRATOR) {
    context.warnings.push("agent_binding_missing");
    return context;
  }

  const orchestratorId = args.env.MARKETING_ORCHESTRATOR.idFromName(`marketing-${args.post.slug}`);
  const orchestratorStub = args.env.MARKETING_ORCHESTRATOR.get(orchestratorId);

  const payload = {
    post: {
      title: args.post.title,
      excerpt: args.post.custom_excerpt || args.post.excerpt || "",
      plaintext: args.post.plaintext || stripHtml(args.post.html || ""),
      tags: (args.post.tags ?? []).map((item) => item.name ?? "").filter(Boolean)
    },
    requestedFormats: args.requestedFormats,
    userPrompt: args.userPrompt,
    promptProfile: {
      mastermind: context.promptProfile.mastermind,
      strategist: context.promptProfile.strategist,
      copywriter: context.promptProfile.copywriter,
      visualDirector: context.promptProfile.visualDirector,
      renderGuard: context.promptProfile.renderGuard
    },
    renderPolicy: context.renderPolicy
  };

  try {
    const response = await orchestratorStub.fetch("https://marketing-agent.local/orchestrate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      context.warnings.push(`agent_orchestrator_http_${response.status}`);
      return context;
    }
    const raw = (await response.json()) as unknown;
    const parsed = parseAgentOrchestrationResponse(raw);
    if (!parsed) {
      context.warnings.push("agent_orchestrator_invalid_payload");
      return context;
    }

    context.strategicBrief = parsed.strategic_brief;
    context.visualNotes = [context.visualNotes, parsed.visual_notes].filter(Boolean).join("\n");
    context.copyOverrides = {
      ...context.copyOverrides,
      userInstructionsAppend: [context.copyOverrides?.userInstructionsAppend, parsed.copywriter_notes].filter(Boolean).join("\n")
    };
    context.warnings = [...new Set([...context.warnings, ...parsed.warnings])];
    return context;
  } catch {
    context.warnings.push("agent_orchestrator_request_failed");
    return context;
  }
}

function cloneAgentExecutionContext(context: AgentExecutionContext): AgentExecutionContext {
  return {
    mode: context.mode,
    promptProfile: {
      ...context.promptProfile,
      mastermind: [...context.promptProfile.mastermind],
      strategist: [...context.promptProfile.strategist],
      copywriter: [...context.promptProfile.copywriter],
      visualDirector: [...context.promptProfile.visualDirector],
      renderGuard: [...context.promptProfile.renderGuard]
    },
    renderPolicy: { ...context.renderPolicy },
    copyOverrides: context.copyOverrides ? { ...context.copyOverrides } : undefined,
    strategicBrief: context.strategicBrief,
    visualNotes: context.visualNotes,
    warnings: [...context.warnings]
  };
}

function parseAgentOrchestrationResponse(input: unknown): { strategic_brief: string; copywriter_notes: string; visual_notes: string; warnings: string[] } | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const object = input as Record<string, unknown>;
  const warnings = Array.isArray(object.warnings) ? object.warnings.map((item) => (typeof item === "string" ? item.trim() : "")).filter(Boolean) : [];
  const strategicBrief = toSingleLineString(object.strategic_brief);
  const copywriterNotes = toSingleLineString(object.copywriter_notes);
  const visualNotes = toSingleLineString(object.visual_notes);
  if (!strategicBrief || !copywriterNotes || !visualNotes) return null;
  return { strategic_brief: strategicBrief, copywriter_notes: copywriterNotes, visual_notes: visualNotes, warnings };
}

function mergePromptField(primary: string | string[] | undefined, secondary: string | string[] | undefined): string | string[] | undefined {
  const combined = [...toPromptLines(primary), ...toPromptLines(secondary)];
  return combined.length === 0 ? undefined : combined;
}

function toPromptLines(input: unknown): string[] {
  if (typeof input === "string") {
    const trimmed = input.trim();
    return trimmed ? [trimmed] : [];
  }
  if (!Array.isArray(input)) return [];
  return input.map((e) => (typeof e === "string" ? e.trim() : "")).filter(Boolean);
}

function toSingleLineString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized || null;
}

function toBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return parseBooleanString(value, fallback);
  return fallback;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  return value as Record<string, unknown>;
}

function parseBooleanString(value: string, fallback: boolean): boolean {
  const normalized = value.trim().toLowerCase();
  if (["true", "1", "yes", "on"].includes(normalized)) return true;
  if (["false", "0", "no", "off"].includes(normalized)) return false;
  return fallback;
}

// ==================== HTML LAYOUT AGENT ====================

async function runHtmlLayoutAgent(
  env: Env,
  post: GhostPost,
  platform: string,
  formatName: string | undefined,
  formatInstruction: string | undefined,
  width: number,
  height: number,
  designTokensPrompt: string,
  userPrompt?: string,
  overrides?: LlmPromptOverrides,
): Promise<LlmOutput> {
  const providerConfig = resolveProviderConfig(env as unknown as Record<string, string | undefined>);
  const models = createModelChain(providerConfig);

  const content = post.plaintext || post.html || "";
  const systemPrompt = [...(Array.isArray(overrides?.systemPrompt) ? overrides.systemPrompt : overrides?.systemPrompt ? [overrides.systemPrompt] : [])].join("\n");

  const result = await generateHtmlLayout(models, {
    platform,
    formatName,
    formatInstruction,
    width,
    height,
    title: post.title,
    excerpt: post.custom_excerpt || post.excerpt || "",
    content,
    designTokens: designTokensPrompt,
    userPrompt: [
      userPrompt ? `User specifically asked for: ${userPrompt}` : "",
      overrides?.userInstructionsAppend || ""
    ].filter(Boolean).join("\n"),
    systemPrompt,
    userInstructions: overrides?.userInstructions,
    userInstructionsAppend: overrides?.userInstructionsAppend,
  });

  return {
    generated_html: result.generated_html,
  };
}

// ==================== PIPELINE ====================

export async function runPipeline(body: GenerateRequestBody, env: Env, security: ResolvedSecurityConfig) {
  assertRequiredEnv(env);
  const slug = resolveSlug(body);
  if (!slug) throw new HttpError(400, "Request must include either slug or url");
  const post = await fetchGhostPost(env, slug);
  return runPipelineFromPost(post, env, body, security);
}

export async function runPipelineFromPost(post: GhostPost, env: Env, body: GenerateRequestBody | DirectContentRequestBody, security: ResolvedSecurityConfig) {
  const outputPlan = resolveOutputPlan(body.output);
  const defaultTokens = await loadDesignTokensForGeneration(env);
  const designTokensForRun = resolveDesignTokensForRequest(body.designTokens, defaultTokens);
  const designTokensPrompt = formatDesignTokensForPromptFromObject(designTokensForRun);
  const brandName = body.brandName ?? env.BRAND_NAME ?? "Tasbir Blog";
  const variants: Array<{ index: number; image_source: SelectedImage; llm_output: LlmOutput; assets: Record<string, StoredAsset | null> }> = [];
  const baseAgentContext = resolveAgentExecutionContext(body.agent);
  const agentContexts: AgentExecutionContext[] = [];
  const sharedStorage = resolveBatchStorageOptions(body.storage);

  for (let index = 0; index < outputPlan.postCount; index += 1) {
    const variantPrompt = outputPlan.postCount > 1
      ? [body.prompt?.trim(), `Variation index ${index + 1} of ${outputPlan.postCount}.`].filter(Boolean).join(" ")
      : body.prompt;

    const agentContext = await resolveAgentContextForRun({
      env,
      post,
      baseContext: baseAgentContext,
      userPrompt: variantPrompt,
      requestedFormats: [...outputPlan.formats]
    });
    agentContexts.push(agentContext);

    const formatAssets: Record<string, StoredAsset | null> = {};
    let imageSource: SelectedImage = { source: "none", imageUrl: "" };
    let variantLlmOutput: LlmOutput | null = null;

    for (const format of outputPlan.formats) {
      const dimensions = getFormatConfig(format);
      if (!dimensions) continue;

      const llmOutput = await runHtmlLayoutAgent(
        env,
        post,
        format,
        dimensions.name,
        dimensions.aiInstruction,
        dimensions.width,
        dimensions.height,
        designTokensPrompt,
        variantPrompt,
        agentContext.copyOverrides,
      );

      const finalLlmOutput = {
        generated_html: injectDesignTokensIntoHtml(llmOutput.generated_html, designTokensForRun)
      };

      const browser = await launchRenderingBrowser(env);

      try {
        if (!variantLlmOutput) {
          variantLlmOutput = finalLlmOutput;
        }

        if (index === 0 && format === [...outputPlan.formats][0]) {
          imageSource = { source: post.feature_image ? "feature" : "none", imageUrl: post.feature_image || "" };
        }

        const keyPrefix = buildR2KeyPrefix(env, post.slug, sharedStorage);
        const asset = await renderStoreSingleAsset(env, browser, {
          key: `${keyPrefix}/${buildAssetFileName(format, assetNameSuffixForVariant(index, outputPlan.postCount))}`,
          format,
          rawHtml: finalLlmOutput.generated_html,
          formatLabel: format
        });

        formatAssets[format] = asset;
      } finally {
        await browser.close();
      }
    }

    variants.push({
      index: index + 1,
      image_source: imageSource,
      llm_output: variantLlmOutput || { generated_html: "" },
      assets: formatAssets
    });
  }

  const primaryVariant = variants[0];
  if (!primaryVariant) throw new HttpError(500, "Generation pipeline did not produce any output variants");

  return {
    ok: true,
    slug: post.slug,
    post_url: post.url,
    requested_formats: [...outputPlan.formats],
    image_source: primaryVariant.image_source,
    llm_output: primaryVariant.llm_output,
    agentic: summarizeAgentExecution(agentContexts),
    assets: primaryVariant.assets,
    variants: outputPlan.postCount > 1 ? variants : undefined
  };
}

// ==================== RENDERING ====================

async function renderStoreSingleAsset(env: Env, browser: any, args: { key: string; format: string; rawHtml?: string; formatLabel: string }): Promise<StoredAsset> {
  const formatCfg = getFormatConfig(args.format);
  if (!formatCfg) throw new HttpError(400, `Unknown format: ${args.format}`);

  const html = args.rawHtml;
  if (!html) throw new HttpError(500, "No HTML provided for rendering");

  const png = await renderPng(browser, html, formatCfg.width, formatCfg.height);

  await env.OUTPUT_BUCKET.put(args.key, png, {
    httpMetadata: {
      contentType: "image/png",
      cacheControl: (PIPELINE_CONFIG.runtime?.asset_cache_control as string) || "public, max-age=31536000, immutable"
    }
  });

  return {
    format: args.formatLabel,
    key: args.key,
    url: buildPublicUrl(env, args.key)
  };
}

async function renderPng(browser: any, html: string, width: number, height: number): Promise<Uint8Array> {
  const page = await browser.newPage();
  try {
    await page.setViewport({ width, height, deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: "networkidle0", timeout: 15_000 });

    await page.evaluate(`
      (async () => {
        const maxWait = 3000;
        const start = Date.now();
        while (Date.now() - start < maxWait) {
          const tailwindStyles = document.querySelector('style[data-tailwind]') || 
                                 document.querySelector('style:not([id])');
          if (tailwindStyles && tailwindStyles.textContent && tailwindStyles.textContent.length > 1000) {
            break;
          }
          await new Promise(r => setTimeout(r, 50));
        }
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        await new Promise((resolve) => setTimeout(resolve, 150));
      })();
    `);

    await page.waitForFunction(
      "() => typeof window.__RICH_RENDER_DONE__ === 'undefined' || window.__RICH_RENDER_DONE__ === true",
      { timeout: 7_000 }
    );

    await page.evaluate(`
      (async () => {
        await document.fonts.ready;
        const images = Array.from(document.images);
        await Promise.all(images.map(async (img) => { try { await img.decode(); } catch {} }));
      })();
    `);

    const screenshot = await page.screenshot({ type: "png", clip: { x: 0, y: 0, width, height } });
    return screenshot instanceof Uint8Array ? screenshot : new Uint8Array(screenshot as ArrayBuffer);
  } finally {
    await page.close();
  }
}

function buildR2KeyPrefix(env: Env, slug: string, storage?: StorageOptions): string {
  const basePrefix = ((env.R2_KEY_PREFIX || (PIPELINE_CONFIG.storage?.default_key_prefix as string) || "social-assets") as string).replace(/\/+$/, "");
  const mode = storage?.mode ?? (PIPELINE_CONFIG.storage?.default_mode as string) ?? "overwrite";

  if (mode === "overwrite") return `${basePrefix}/${slug}`;

  const includeDate = storage?.includeDate ?? (PIPELINE_CONFIG.storage?.versioned_include_date as boolean) ?? true;
  const runId = sanitizeRunId(storage?.runId) ?? crypto.randomUUID().split("-")[0];
  const datePart = includeDate ? `/${new Date().toISOString().slice(0, 10)}` : "";
  return `${basePrefix}/${slug}${datePart}/${runId}`;
}

function buildAssetFileName(baseName: string, suffix: string | undefined): string {
  const normalizedSuffix = normalizeAssetSuffix(suffix);
  return normalizedSuffix ? `${baseName}-${normalizedSuffix}.png` : `${baseName}.png`;
}

function normalizeAssetSuffix(value: string | undefined): string | null {
  if (!value) return null;
  const cleaned = value.trim().toLowerCase().replace(/[^a-z0-9-_]/g, "");
  if (!cleaned) return null;
  return cleaned.slice(0, 40);
}

function sanitizeRunId(input: string | undefined): string | null {
  if (!input) return null;
  const cleaned = input.trim().toLowerCase().replace(/[^a-z0-9-_]/g, "");
  if (!cleaned) return null;
  return cleaned.slice(0, (PIPELINE_CONFIG.generation?.limits?.storage_run_id_max_chars as number) || 64);
}

function buildPublicUrl(env: Env, key: string): string | null {
  const base = env.R2_PUBLIC_BASE_URL?.trim();
  if (!base) return null;
  const normalizedBase = base.replace(/\/+$/, "");
  const encodedPath = key.split("/").map((s) => encodeURIComponent(s)).join("/");
  return `${normalizedBase}/${encodedPath}`;
}

function assetNameSuffixForVariant(index: number, totalCount: number): string | undefined {
  if (totalCount <= 1 || index === 0) return undefined;
  return `v${index + 1}`;
}

function resolveBatchStorageOptions(storage: StorageOptions | undefined): StorageOptions | undefined {
  if (!storage || storage.mode !== "versioned") return storage;
  return {
    ...storage,
    runId: sanitizeRunId(storage.runId) ?? crypto.randomUUID().split("-")[0]
  };
}

function resolveOutputPlan(output: OutputOptions | undefined): { formats: Set<string>; carouselSlides: number; postCount: number } {
  const formatNames = getFormatNames();
  const formatSet = new Set(formatNames);
  const requestedFormats = output?.formats && output.formats.length > 0 ? output.formats : formatNames;
  const normalizedFormats = new Set<string>();
  for (const format of requestedFormats) {
    if (formatSet.has(format)) normalizedFormats.add(format);
  }
  if (normalizedFormats.size === 0) throw new HttpError(400, "output.formats must include at least one supported format");

  const postCount = Math.round(clampNumber(output?.postCount, 1, 10, 1));
  return { formats: normalizedFormats, carouselSlides: DEFAULT_CAROUSEL_SLIDES, postCount };
}

function summarizeAgentExecution(contexts: AgentExecutionContext[]) {
  if (contexts.length === 0) return undefined;
  const warnings = [...new Set(contexts.flatMap((c) => c.warnings).filter(Boolean))];
  return { mode: "agentic" as const, prompt_profile: contexts[0].promptProfile.name, applied_roles: [...AGENT_APPLIED_ROLES], warnings };
}

// ==================== CONTENT SOURCES ====================

function buildPostFromDirectContent(input: DirectContentRequestBody, security: ResolvedSecurityConfig): GhostPost {
  const title = (input.title ?? "").trim();
  if (!title) throw new HttpError(400, "title is required for /generate-from-content");

  const plainContent = normalizeSourceContent((input.content ?? input.body ?? "").trim());
  if (!plainContent) throw new HttpError(400, "content (or body) is required for /generate-from-content");

  const derivedSlug = sanitizeSlug(input.slug ?? slugify(title));
  if (!derivedSlug) throw new HttpError(400, "Could not derive a valid slug from title");

  const tags = normalizeTags(input.tags);
  const excerptMax = (PIPELINE_CONFIG.generation?.limits?.direct_excerpt_default_max_chars as number) || 360;
  const excerpt = normalizeSourceContent((input.excerpt ?? plainContent.slice(0, excerptMax)).trim());
  const url = input.url?.trim() || `https://local.test/${derivedSlug}/`;

  let featureImage: string | undefined;
  if (input.feature_image) {
    try {
      featureImage = sanitizeHttpUrl(input.feature_image, security, "feature_image", { requireAllowedHost: false });
    } catch {
      featureImage = undefined;
    }
  }

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

async function fetchGhostPost(env: Env, slug: string): Promise<GhostPost> {
  const base = env.GHOST_API_URL.replace(/\/+$/, "");
  const endpoint = `${base}/posts/slug/${encodeURIComponent(slug)}/?key=${encodeURIComponent(env.GHOST_CONTENT_API_KEY)}&include=tags,authors&formats=html,plaintext`;
  const response = await fetch(endpoint, { headers: { accept: "application/json" } });

  if (!response.ok) {
    const details = await response.text();
    const previewChars = (PIPELINE_CONFIG.runtime?.ghost_error_preview_chars as number) || 300;
    throw new HttpError(response.status, `Ghost Content API failed: ${details.slice(0, previewChars)}`);
  }

  const data = (await response.json()) as { posts?: GhostPost[] };
  const post = data.posts?.[0];
  if (!post) throw new HttpError(404, `No post found for slug: ${slug}`);
  return post;
}

function normalizeTags(input: string[] | string | undefined): string[] {
  if (!input) return [];
  const rawItems = Array.isArray(input) ? input : input.split(",");
  const maxTags = (PIPELINE_CONFIG.generation?.limits?.input_tags_max_count as number) || 8;
  return rawItems.map((item) => item.trim()).map((item) => item.replace(/[^\p{L}\p{N}\s-]/gu, "")).filter((item) => item.length > 1).slice(0, maxTags);
}

function slugify(text: string): string {
  return text.toLowerCase().trim().replace(/[^\p{L}\p{N}\s-]/gu, "").replace(/\s+/g, "-").replace(/-+/g, "-");
}

function resolveSlug(input: { slug?: string; url?: string }): string | null {
  if (typeof input.slug === "string" && input.slug.trim().length > 0) return sanitizeSlug(input.slug);
  if (typeof input.url === "string" && input.url.trim().length > 0) return parseSlugFromUrl(input.url);
  return null;
}

function sanitizeSlug(value: string): string {
  return value.trim().replace(/^\/+|\/+$/g, "").replace(/[^\p{L}\p{N}\-_/]/gu, "").split("/").filter(Boolean).at(-1)?.toLowerCase() ?? "";
}

function parseSlugFromUrl(rawUrl: string): string | null {
  try {
    const url = new URL(rawUrl);
    const segments = url.pathname.split("/").filter(Boolean);
    if (segments.length === 0) return null;
    return sanitizeSlug(segments[segments.length - 1]);
  } catch {
    return null;
  }
}

// ==================== WEBHOOK ====================

async function verifyGhostWebhookRequest(request: Request, env: Env, rawBody: string): Promise<void> {
  const ghostSignature = request.headers.get("x-ghost-signature")?.trim();
  if (ghostSignature) {
    const signingSecret = env.GHOST_WEBHOOK_SECRET?.trim() || env.GHOST_WEBHOOK_TOKEN?.trim();
    if (!signingSecret) throw new HttpError(500, "Missing env var GHOST_WEBHOOK_SECRET (or GHOST_WEBHOOK_TOKEN fallback)");

    const parsed = parseGhostSignatureHeader(ghostSignature);
    if (!parsed) throw new HttpError(401, "Invalid X-Ghost-Signature header");

    const expectedDigest = await computeHmacSha256Hex(signingSecret, `${rawBody}${parsed.timestamp}`);
    if (!constantTimeEqual(parsed.sha256, expectedDigest)) throw new HttpError(401, "Unauthorized webhook signature");
    return;
  }

  const expectedToken = env.GHOST_WEBHOOK_TOKEN?.trim();
  if (!expectedToken) throw new HttpError(500, "Missing env var GHOST_WEBHOOK_TOKEN");
  const providedToken = request.headers.get("x-webhook-token")?.trim();
  if (!providedToken || !constantTimeEqual(providedToken, expectedToken)) throw new HttpError(401, "Unauthorized webhook token");
}

function parseGhostSignatureHeader(value: string): { sha256: string; timestamp: string } | null {
  const parts = value.split(",").map((p) => p.trim()).filter(Boolean);
  let sha256 = "";
  let timestamp = "";
  for (const part of parts) {
    const [rawKey, ...rawValue] = part.split("=");
    if (!rawKey || rawValue.length === 0) continue;
    const key = rawKey.trim().toLowerCase();
    const resolvedValue = rawValue.join("=").trim();
    if (key === "sha256") sha256 = resolvedValue.toLowerCase();
    else if (key === "t") timestamp = resolvedValue;
  }
  if (!/^[a-f0-9]{64}$/.test(sha256) || !/^\d{10,16}$/.test(timestamp)) return null;
  return { sha256, timestamp };
}

async function computeHmacSha256Hex(secret: string, payload: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return bytesToHex(new Uint8Array(signature));
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes).map((v) => v.toString(16).padStart(2, "0")).join("");
}

function constantTimeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let mismatch = 0;
  for (let i = 0; i < left.length; i += 1) mismatch |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return mismatch === 0;
}

function extractSlugFromWebhook(payload: GhostWebhookPayload): string | null {
  const direct = payload.post?.current?.slug ?? payload.post?.slug ?? payload.slug ?? parseSlugFromUrl(payload.post?.current?.url ?? "") ?? parseSlugFromUrl(payload.url ?? "");
  if (!direct) return null;
  return sanitizeSlug(direct);
}

// ==================== NOTIFICATIONS ====================

async function sendNotification(url: string, payload: unknown, security: ResolvedSecurityConfig): Promise<void> {
  try {
    const safeUrl = sanitizeHttpUrl(url, security, "Notification URL", { requireAllowedHost: true });
    await fetch(safeUrl, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
  } catch {}
}

function resolveNotifyUrl(bodyValue: string | undefined, envValue: string | undefined, security: ResolvedSecurityConfig): string | null {
  const candidate = (bodyValue ?? envValue)?.trim();
  if (!candidate) return null;
  try {
    return sanitizeHttpUrl(candidate, security, "Notification URL", { requireAllowedHost: true });
  } catch {
    return null;
  }
}

function shouldUseDefaultNotifyWebhook(requestUrl: string): boolean {
  try {
    const hostname = new URL(requestUrl).hostname.trim().toLowerCase();
    if (!hostname) return true;
    if (hostname === "localhost" || hostname === "::1") return false;
    if (hostname.endsWith(".localhost") || hostname.endsWith(".local")) return false;
    if (/^127(?:\.\d{1,3}){3}$/.test(hostname)) return false;
    return true;
  } catch {
    return true;
  }
}

// ==================== VALIDATION ====================

function validateGenerateRequestBody(input: unknown): GenerateRequestBody {
  const body = requireObject(input, "Request body");
  return {
    slug: optionalString(body.slug, "slug", 200),
    url: optionalString(body.url, "url", 400),
    brandName: optionalString(body.brandName, "brandName", 120),
    prompt: optionalString(body.prompt, "prompt", 1200),
    storage: parseStorageOptions(body.storage),
    notifyUrl: optionalString(body.notifyUrl, "notifyUrl", 500),
    image: parseImageOptions(body.image),
    output: parseOutputOptions(body.output),
    agent: parseAgentOptions(body.agent),
    designTokens: parseDesignTokens(body.designTokens)
  };
}

function validateDirectContentRequestBody(input: unknown): DirectContentRequestBody {
  const body = requireObject(input, "Request body");
  const directContentMaxChars = Math.max(1_000, Number(PIPELINE_CONFIG.generation?.limits?.direct_content_max_chars ?? 30_000));
  const tags = body.tags;
  const tagValue = tags === undefined ? undefined : Array.isArray(tags) ? tags.map((item: unknown) => optionalString(item, "tags[]", 80)).filter((t): t is string => Boolean(t)) : optionalString(tags, "tags", 500);

  return {
    title: optionalString(body.title, "title", 280),
    excerpt: optionalString(body.excerpt, "excerpt", 1_000),
    content: optionalString(body.content, "content", directContentMaxChars),
    body: optionalString(body.body, "body", directContentMaxChars),
    slug: optionalString(body.slug, "slug", 200),
    url: optionalString(body.url, "url", 500),
    feature_image: optionalString(body.feature_image, "feature_image", 2_000),
    tags: tagValue,
    primary_tag: optionalString(body.primary_tag, "primary_tag", 80),
    brandName: optionalString(body.brandName, "brandName", 120),
    prompt: optionalString(body.prompt, "prompt", 1200),
    storage: parseStorageOptions(body.storage),
    notifyUrl: optionalString(body.notifyUrl, "notifyUrl", 500),
    image: parseImageOptions(body.image),
    output: parseOutputOptions(body.output),
    agent: parseAgentOptions(body.agent),
    designTokens: parseDesignTokens(body.designTokens)
  };
}

function parseDesignTokens(input: unknown): Record<string, unknown> | undefined {
  if (input === undefined) return undefined;
  return requireObject(input, "designTokens");
}

function validateWebhookPayload(input: unknown): GhostWebhookPayload {
  const body = requireObject(input, "Webhook payload");
  const postRaw = body.post;
  const post = postRaw && typeof postRaw === "object" && !Array.isArray(postRaw) ? (postRaw as Record<string, unknown>) : undefined;
  const currentRaw = post?.current;
  const current = currentRaw && typeof currentRaw === "object" && !Array.isArray(currentRaw) ? (currentRaw as Record<string, unknown>) : undefined;

  return {
    slug: optionalString(body.slug, "payload.slug", 200),
    url: optionalString(body.url, "payload.url", 500),
    post: post ? {
      slug: optionalString(post.slug, "payload.post.slug", 200),
      url: optionalString(post.url, "payload.post.url", 500),
      current: current ? {
        slug: optionalString(current.slug, "payload.post.current.slug", 200),
        url: optionalString(current.url, "payload.post.current.url", 500)
      } : undefined
    } : undefined
  };
}

function parseStorageOptions(input: unknown): StorageOptions | undefined {
  if (input === undefined) return undefined;
  const object = requireObject(input, "storage");
  const mode = optionalString(object.mode, "storage.mode", 20);
  if (mode && mode !== "overwrite" && mode !== "versioned") throw new HttpError(400, "storage.mode must be overwrite or versioned");
  return {
    mode: mode as StorageOptions["mode"],
    includeDate: object.includeDate !== undefined ? requiredBoolean(object.includeDate, "storage.includeDate") : undefined,
    runId: optionalString(object.runId, "storage.runId", (PIPELINE_CONFIG.generation?.limits?.storage_run_id_max_chars as number) || 64)
  };
}

function parseImageOptions(input: unknown): ImageGenerationOptions | undefined {
  if (input === undefined) return undefined;
  const object = requireObject(input, "image");
  const mode = optionalString(object.mode, "image.mode", 16);
  if (mode && !["auto", "none", "feature", "ai", "custom"].includes(mode)) throw new HttpError(400, "image.mode must be one of auto, none, feature, ai, custom");
  const imagePromptMax = (PIPELINE_CONFIG.generation?.limits?.image_prompt_max_chars as number) || 700;
  const parsed: ImageGenerationOptions = {
    mode: mode as ImageGenerationOptions["mode"],
    customUrl: optionalString(object.customUrl, "image.customUrl", 2_000),
    prompt: optionalString(object.prompt, "image.prompt", imagePromptMax),
    allowAi: object.allowAi !== undefined ? requiredBoolean(object.allowAi, "image.allowAi") : undefined,
    preferFeature: object.preferFeature !== undefined ? requiredBoolean(object.preferFeature, "image.preferFeature") : undefined
  };
  return Object.values(parsed).some((v) => v !== undefined) ? parsed : undefined;
}

function parseAgentOptions(input: unknown): AgentOptions | undefined {
  if (input === undefined) return undefined;
  const object = requireObject(input, "agent");
  const mode = optionalString(object.mode, "agent.mode", 20);
  if (mode && mode !== "agentic") throw new HttpError(400, "agent.mode must be agentic");

  const renderPolicyRaw = object.renderPolicy;
  let renderPolicy: AgentRenderPolicy | undefined;
  if (renderPolicyRaw !== undefined) {
    const renderObject = requireObject(renderPolicyRaw, "agent.renderPolicy");
    renderPolicy = {
      allowMarkdown: renderObject.allowMarkdown !== undefined ? requiredBoolean(renderObject.allowMarkdown, "agent.renderPolicy.allowMarkdown") : undefined,
      allowMath: renderObject.allowMath !== undefined ? requiredBoolean(renderObject.allowMath, "agent.renderPolicy.allowMath") : undefined,
      allowDiagrams: renderObject.allowDiagrams !== undefined ? requiredBoolean(renderObject.allowDiagrams, "agent.renderPolicy.allowDiagrams") : undefined,
      allowTextInAiImages: renderObject.allowTextInAiImages !== undefined ? requiredBoolean(renderObject.allowTextInAiImages, "agent.renderPolicy.allowTextInAiImages") : undefined
    };
  }

  const parsed: AgentOptions = {
    mode: mode as AgentOptions["mode"],
    promptProfile: optionalString(object.promptProfile, "agent.promptProfile", 120),
    renderPolicy
  };
  return Object.values(parsed).some((v) => v !== undefined) ? parsed : undefined;
}

function parseOutputOptions(input: unknown): OutputOptions | undefined {
  if (input === undefined) return undefined;
  const object = requireObject(input, "output");
  const formatsRaw = object.formats;
  let formats: string[] | undefined;
  if (formatsRaw !== undefined) {
    if (!Array.isArray(formatsRaw)) throw new HttpError(400, "output.formats must be an array");
    const formatSet = new Set(getFormatNames());
    const unique = new Set<string>();
    for (const [index, value] of (formatsRaw as unknown[]).entries()) {
      const item = optionalString(value, `output.formats[${index}]`, 40);
      if (!item) continue;
      if (!formatSet.has(item)) throw new HttpError(400, `Unsupported output format: ${item}`);
      unique.add(item);
    }
    formats = [...unique];
    if (formats.length === 0) throw new HttpError(400, "output.formats cannot be empty");
  }

  const postCount = object.postCount !== undefined ? Math.round(clampNumber(requiredNumber(object.postCount, "output.postCount"), 1, 10, 1)) : undefined;
  const parsed: OutputOptions = { formats, carouselSlides: DEFAULT_CAROUSEL_SLIDES, postCount };
  return Object.values(parsed).some((v) => v !== undefined) ? parsed : undefined;
}

function requireObject(input: unknown, field: string): Record<string, unknown> {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new HttpError(400, `${field} must be an object`);
  return input as Record<string, unknown>;
}

function optionalString(input: unknown, field: string, maxLength: number): string | undefined {
  if (input === undefined || input === null) return undefined;
  if (typeof input !== "string") throw new HttpError(400, `${field} must be a string`);
  const trimmed = input.trim();
  if (!trimmed) return undefined;
  if (trimmed.length > maxLength) throw new HttpError(400, `${field} exceeds maximum length ${maxLength}`);
  return trimmed;
}

function requiredBoolean(input: unknown, field: string): boolean {
  if (typeof input !== "boolean") throw new HttpError(400, `${field} must be a boolean`);
  return input;
}

function requiredNumber(input: unknown, field: string): number {
  if (typeof input !== "number" || !Number.isFinite(input)) throw new HttpError(400, `${field} must be a finite number`);
  return input;
}

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const numeric = typeof value === "number" && Number.isFinite(value) ? value : fallback;
  return Math.min(max, Math.max(min, numeric));
}

function assertRequiredEnv(env: Env): void {
  if (!env.GHOST_API_URL?.trim()) throw new HttpError(500, "Missing env var GHOST_API_URL");
  if (!env.GHOST_CONTENT_API_KEY?.trim()) throw new HttpError(500, "Missing env var GHOST_CONTENT_API_KEY");
}
