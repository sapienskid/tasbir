import { Hono } from "hono";
import { cors } from "hono/cors";
import { secureHeaders } from "hono/secure-headers";
import {
  generateHtmlLayout,
  normalizeSourceContent,
  stripHtml,
  createAdvancedModelChain,
  resolveProviderConfig,
} from "./ai";
import {
  generateImage,
  imageToDataUrl,
  type GeneratedImage,
} from "./lib/ai-image";
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
  callOrchestrator,
  type OrchestratorInput,
  type OrchestratorOutput,
} from "./agents/marketing-orchestrator";
import {
  tokensToCSSFromRaw,
  fontImportFromTokens,
  buildTailwindConfigFromTokens,
  stripInjectedDesignTokens,
  formatDesignTokensForPromptFromObject,
  formatSemanticBriefForPrompt,
  generateSemanticUtilityCSS,
  getDefaultDesignTokens,
  normalizeDesignTokensForRendering,
} from "../shared/tokens";
import { generateTokensAI } from "./lib/tokens";
import { loadSettings, saveSettings, patchSettings, getDefaultSettings, type WorkspaceSettings } from "./lib/settings";
import {
  listTemplates,
  getTemplate,
  saveTemplate,
  deleteTemplate,
  toggleTemplate,
  fillTemplateSlots,
  extractSlotsFromHtml,
  validateTemplateHtml,
  type TemplateMetadata,
} from "./lib/templates";
import { classifyContent, type ContentClassification } from "./lib/content-classifier";
import { checkHealth } from "./lib/health";
import {
  generateCacheKey,
  hashDesignTokens,
  getCachedHtml,
  setCachedHtml,
  shouldUseCache,
  type CacheEntry,
} from "./lib/ai-cache";
import {
  decideTemplateOrGenerate,
  getSavedTemplate,
  saveHtmlAsTemplate,
  listSavedTemplates,
  deleteSavedTemplate,
  rateTemplate,
  recordTemplateUsage,
  type SavedHtmlTemplate,
  type TemplateDecision,
} from "./lib/smart-template-selector";

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


async function launchRenderingBrowser(env: Env): Promise<any> {
  const keepAliveMs = (PIPELINE_CONFIG.runtime?.browser_keep_alive_ms as number) ?? 60000;

  // Always use Cloudflare Browser in Workers environment
  if (!env.BROWSER) {
    throw new HttpError(500, "BROWSER binding is required for Cloudflare Browser Rendering");
  }
  const cloudflarePuppeteer = (await import("@cloudflare/puppeteer")).default as any;
  return cloudflarePuppeteer.launch(env.BROWSER, { keep_alive: keepAliveMs });
}

interface Env extends SecurityEnv {
  SETTINGS_KV?: KVNamespace;
  TEMPLATES_KV?: KVNamespace;
  AI_CACHE_KV?: KVNamespace;
  ASSETS?: Fetcher;
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

app.get("/health", async (c) => {
  const health = await checkHealth(c.env);
  return c.json(health);
});

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

// ==================== PRE-COMPUTED TOKEN ASSETS ====================

interface PrecomputedTokenAssets {
  cssVars: string;
  fontLinks: string;
  tailwindConfigScript: string;
  baseline: string;
  semanticUtilityCSS: string;
  /** Lightweight semantic brief for AI prompts */
  semanticBrief: string;
}

/**
 * Pre-compute all token-derived assets once per request.
 * This avoids redundant normalization and computation for each format.
 */
function precomputeDesignTokenAssets(tokens: Record<string, unknown>): PrecomputedTokenAssets {
  const normalizedTokens = normalizeDesignTokensForRendering(tokens);
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
    "}",
    "*, *::before, *::after { box-sizing: border-box; }",
  ].join("\n");
  
  // Generate semantic utility CSS for AI-generated HTML
  const semanticUtilityCSS = generateSemanticUtilityCSS();
  
  // Generate lightweight semantic brief for AI prompts (avoids full token dump)
  const semanticBrief = formatSemanticBriefForPrompt(normalizedTokens);

  return { cssVars, fontLinks, tailwindConfigScript, baseline, semanticUtilityCSS, semanticBrief };
}

/**
 * Fast HTML injection using pre-computed token assets.
 * Avoids re-normalizing tokens for each format.
 */
function injectDesignTokensIntoHtmlFast(html: string, precomputed: PrecomputedTokenAssets): string {
  if (!html.trim()) return html;

  let nextHtml = stripInjectedDesignTokens(html);

  const hasTailwindCdn = /<script[^>]+src=["'][^"']*cdn\.tailwindcss\.com[^"']*["'][^>]*><\/script>/i.test(nextHtml);
  const hasTailwindConfig = /id=["']tasbir-tailwind-config["']/i.test(nextHtml);

  if (!hasTailwindConfig) {
    if (hasTailwindCdn) {
      nextHtml = nextHtml.replace(
        /<script[^>]+src=["'][^"']*cdn\.tailwindcss\.com[^"']*["'][^>]*><\/script>/i,
        (m) => `${precomputed.tailwindConfigScript}\n${m}`,
      );
    } else {
      nextHtml = nextHtml.replace(/<head[^>]*>/i, (m) => `${m}\n${precomputed.tailwindConfigScript}\n<script src="https://cdn.tailwindcss.com"></script>`);
    }
  }

  const injectedBlock = `${precomputed.fontLinks}\n<style id="tasbir-design-tokens">\n${precomputed.cssVars}\n\n${precomputed.semanticUtilityCSS}\n\n${precomputed.baseline}\n</style>`;

  if (/<\/head>/i.test(nextHtml)) {
    return nextHtml.replace(/<\/head>/i, `${injectedBlock}\n</head>`);
  }
  if (/<head[^>]*>/i.test(nextHtml)) {
    return nextHtml.replace(/<head[^>]*>/i, (m) => `${m}\n${injectedBlock}`);
  }
  if (/<html[^>]*>/i.test(nextHtml)) {
    return nextHtml.replace(/<html[^>]*>/i, (m) => `${m}\n<head>\n${injectedBlock}\n</head>`);
  }
  return `<!DOCTYPE html>\n<html>\n<head>\n${precomputed.tailwindConfigScript}\n<script src="https://cdn.tailwindcss.com"></script>\n${injectedBlock}\n</head>\n<body>${nextHtml}</body>\n</html>`;
}

function injectDesignTokensIntoHtml(html: string, tokens: Record<string, unknown>): string {
  if (!html.trim()) return html;

  const normalizedTokens = normalizeDesignTokensForRendering(tokens);
  let nextHtml = stripInjectedDesignTokens(html);
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
    "}",
    "*, *::before, *::after { box-sizing: border-box; }",
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

  const injectedBlock = `${fontLinks}\n<style id="tasbir-design-tokens">\n${cssVars}\n\n${generateSemanticUtilityCSS()}\n\n${baseline}\n</style>`;

  if (/<\/head>/i.test(nextHtml)) {
    return nextHtml.replace(/<\/head>/i, `${injectedBlock}\n</head>`);
  }
  if (/<head[^>]*>/i.test(nextHtml)) {
    return nextHtml.replace(/<head[^>]*>/i, (m) => `${m}\n${injectedBlock}`);
  }
  if (/<html[^>]*>/i.test(nextHtml)) {
    return nextHtml.replace(/<html[^>]*>/i, (m) => `${m}\n<head>\n${injectedBlock}\n</head>`);
  }
  return `<!DOCTYPE html>\n<html>\n<head>\n${tailwindConfigScript}\n<script src="https://cdn.tailwindcss.com"></script>\n${injectedBlock}\n</head>\n<body>${nextHtml}</body>\n</html>`;
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

function extractDesignInstructions(tokens: Record<string, unknown>): string {
  const meta = tokens.meta as Record<string, unknown> | undefined;
  if (meta && typeof meta.instructions === "string") {
    return meta.instructions.trim();
  }
  return "";
}

app.post("/generate-tokens", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");

  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const vibe = (body.vibe as string) || "custom design system";
  const primaryHint = body.primaryHint as string | undefined;
  const secondaryHint = body.secondaryHint as string | undefined;

  // Debug logging for AI Gateway configuration
  console.log("[generate-tokens] AI binding present:", !!c.env.AI);
  console.log("[generate-tokens] GOOGLE_API_KEY present:", !!c.env.GOOGLE_API_KEY);
  
  try {
    const tokens = await generateTokensAI(vibe, c.env.AI, c.env.GOOGLE_API_KEY, primaryHint, secondaryHint);
    return c.json(tokens);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;
    console.error("[generate-tokens] Error:", message);
    if (stack) console.error("[generate-tokens] Stack:", stack);
    
    return c.json({ 
      error: message,
      details: {
        aiBindingPresent: !!c.env.AI,
        googleApiKeyPresent: !!c.env.GOOGLE_API_KEY,
      }
    }, 500);
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
  // No authentication required for reading settings - users need this to configure API key
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
  // No authentication required for browsing templates - users need this to see available templates
  if (!c.env.TEMPLATES_KV) throw new HttpError(500, "TEMPLATES_KV binding is not configured");
  const templates = await listTemplates(c.env.TEMPLATES_KV);
  return c.json({ templates });
});

app.get("/templates/:id", async (c) => {
  // No authentication required for viewing individual templates  
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

// ==================== SAVED HTML TEMPLATES (Smart Selection) ====================

/**
 * List all saved HTML templates for smart selection.
 * These are full HTML designs that can be reused for similar content.
 */
app.get("/saved-templates", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  if (!c.env.AI_CACHE_KV) throw new HttpError(500, "AI_CACHE_KV binding is not configured");
  
  const format = c.req.query("format");
  const templates = await listSavedTemplates(c.env.AI_CACHE_KV, format);
  return c.json({ templates });
});

/**
 * Get a specific saved HTML template by ID.
 */
app.get("/saved-templates/:id", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  if (!c.env.AI_CACHE_KV) throw new HttpError(500, "AI_CACHE_KV binding is not configured");
  
  const id = c.req.param("id");
  const template = await getSavedTemplate(c.env.AI_CACHE_KV, id);
  if (!template) return c.json({ error: "Template not found" }, 404);
  return c.json(template);
});

/**
 * Save generated HTML as a reusable template.
 * Call this after generation when the output looks good.
 */
app.post("/saved-templates", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.AI_CACHE_KV) throw new HttpError(500, "AI_CACHE_KV binding is not configured");
  
  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const html = typeof body.html === "string" ? body.html : "";
  if (!html) return c.json({ error: "html is required" }, 400);
  
  const name = typeof body.name === "string" ? body.name : "Untitled Template";
  const description = typeof body.description === "string" ? body.description : "";
  const format = typeof body.format === "string" ? body.format : "instagram-square";
  const contentTypes = Array.isArray(body.contentTypes) ? body.contentTypes.filter((t): t is string => typeof t === "string") : [];
  const tags = Array.isArray(body.tags) ? body.tags.filter((t): t is string => typeof t === "string") : [];
  
  const template = await saveHtmlAsTemplate(c.env.AI_CACHE_KV, {
    name,
    description,
    html,
    contentTypes,
    format,
    tags,
  });
  
  return c.json({ ok: true, template });
});

/**
 * Delete a saved HTML template.
 */
app.delete("/saved-templates/:id", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.AI_CACHE_KV) throw new HttpError(500, "AI_CACHE_KV binding is not configured");
  
  const id = c.req.param("id");
  const deleted = await deleteSavedTemplate(c.env.AI_CACHE_KV, id);
  if (!deleted) return c.json({ error: "Template not found" }, 404);
  return c.json({ ok: true });
});

/**
 * Rate a saved template (1-5 stars).
 * Higher-rated templates are preferred by the AI selector.
 */
app.post("/saved-templates/:id/rate", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate");
  if (!c.env.AI_CACHE_KV) throw new HttpError(500, "AI_CACHE_KV binding is not configured");
  
  const id = c.req.param("id");
  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const quality = typeof body.quality === "number" ? body.quality : 3;
  
  if (quality < 1 || quality > 5) {
    return c.json({ error: "quality must be between 1 and 5" }, 400);
  }
  
  await rateTemplate(c.env.AI_CACHE_KV, id, quality);
  return c.json({ ok: true });
});

/**
 * Ask AI to decide: use existing template or generate new HTML?
 * This is the core of the smart template selection system.
 */
app.post("/decide-template", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  if (!c.env.AI_CACHE_KV) throw new HttpError(500, "AI_CACHE_KV binding is not configured");
  
  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const title = typeof body.title === "string" ? body.title : "";
  const excerpt = typeof body.excerpt === "string" ? body.excerpt : "";
  const content = typeof body.content === "string" ? body.content : typeof body.body === "string" ? body.body : "";
  const format = typeof body.format === "string" ? body.format : "instagram-square";
  const contentType = typeof body.contentType === "string" ? body.contentType : undefined;
  
  if (!title || !content) {
    return c.json({ error: "title and content (or body) are required" }, 400);
  }
  
  const providerConfig = resolveProviderConfig(c.env.AI, c.env.GOOGLE_API_KEY);
  const availableTemplates = await listSavedTemplates(c.env.AI_CACHE_KV, format);
  
  const preferences = {
    preferTemplates: body.preferTemplates === true,
    alwaysGenerate: body.alwaysGenerate === true,
    qualityThreshold: typeof body.qualityThreshold === "number" ? body.qualityThreshold : 3,
  };
  
  const decision = await decideTemplateOrGenerate(
    providerConfig,
    { title, excerpt, body: content, contentType },
    format,
    availableTemplates,
    preferences,
    c.env.SETTINGS_KV ? await loadSettings(c.env.SETTINGS_KV) : getDefaultSettings()
  );
  
  return c.json(decision);
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

/**
 * STREAMING: Generate content with real-time progress updates via Server-Sent Events.
 * This endpoint streams generation progress for better UX on slow connections.
 */
app.post("/generate-from-content/stream", async (c) => {
  const security = resolveSecurityConfig(c.env);
  enforceApiAuth(c.req.raw, security, "generate-from-content");
  enforceRateLimit(c.req.raw, security, "generate-from-content");

  const body = await readJsonBody<Record<string, unknown>>(c.req.raw, security.request_limits.max_json_body_bytes);
  const validated = validateDirectContentRequestBody(body);
  const post = buildPostFromDirectContent(validated, security);
  
  // Create SSE response
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      try {
        // Send initial event
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "start", message: "Starting generation..." })}\n\n`));
        
        // Run pipeline with progress updates
        const result = await runPipelineFromPostWithProgress(post, c.env, validated, security, (progress) => {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(progress)}\n\n`));
        });
        
        // Send completion event
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "complete", result })}\n\n`));
        controller.close();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "error", message })}\n\n`));
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  });
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
  routes: ["POST /generate", "POST /generate-from-content", "POST /generate-from-content/stream", "POST /webhook/ghost", "GET /health", "GET /settings", "PUT /settings", "PATCH /settings", "GET /templates", "GET /templates/:id", "PUT /templates/:id", "DELETE /templates/:id", "POST /templates/:id/toggle", "POST /templates/:id/validate", "GET /saved-templates", "GET /saved-templates/:id", "POST /saved-templates", "DELETE /saved-templates/:id", "POST /saved-templates/:id/rate", "POST /decide-template", "GET /config/design-tokens", "GET /config/prompts", "GET /config/formats"]
}, 404 as any));

app.onError((err, c) => {
  console.error("Unhandled error:", err);
  if (err instanceof HttpError) return c.json({ error: err.message }, err.status as any);
  const message = err instanceof Error ? err.message : "Unexpected error";
  return c.json({ error: message }, 500 as any);
});

const API_ROUTE_PATTERNS = [
  /^\/health$/,
  /^\/config(?:\/|$)/,
  /^\/asset(?:\/|$)/,
  /^\/generate-tokens$/,
  /^\/tokens(?:\/|$)/,
  /^\/formats(?:\/|$)/,
  /^\/settings(?:\/|$)/,
  /^\/templates(?:\/|$)/,
  /^\/saved-templates(?:\/|$)/,
  /^\/decide-template$/,
  /^\/generate(?:\/|$)/,
  /^\/generate-from-content(?:\/|$)/,
  /^\/webhook\/ghost$/,
];

function isApiRoute(pathname: string): boolean {
  return API_ROUTE_PATTERNS.some((pattern) => pattern.test(pathname));
}

async function serveStaticAssetOrSpa(request: Request, env: Env): Promise<Response | null> {
  if (!env.ASSETS) return null;
  if (request.method !== "GET" && request.method !== "HEAD") return null;

  const direct = await env.ASSETS.fetch(request);
  if (direct.status !== 404) return direct;

  const url = new URL(request.url);
  const indexRequest = new Request(`${url.origin}/index.html`, request);
  const indexResponse = await env.ASSETS.fetch(indexRequest);
  if (indexResponse.status !== 404) return indexResponse;

  return null;
}

export default {
  async fetch(request: Request, env: Env, executionCtx: ExecutionContext): Promise<Response> {
    const pathname = new URL(request.url).pathname;
    if (isApiRoute(pathname)) {
      return app.fetch(request, env, executionCtx);
    }

    const staticResponse = await serveStaticAssetOrSpa(request, env);
    if (staticResponse) return staticResponse;

    return app.fetch(request, env, executionCtx);
  },
};

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

  const providerConfig = resolveProviderConfig(args.env.AI, args.env.GOOGLE_API_KEY);
  const models = createAdvancedModelChain(providerConfig);
  if (models.length === 0) {
    context.warnings.push("no_ai_provider");
    return context;
  }

  const sourceBody = (args.post.plaintext ?? "").trim();
  const sourceExcerpt = (args.post.excerpt ?? "").trim();
  const sourceText = sourceBody || sourceExcerpt;
  const truncatedSource = sourceText.length > 14000 ? `${sourceText.slice(0, 14000)}...` : sourceText;
  const tags = (args.post.tags ?? []).slice(0, 8).join(", ");
  const requestedFormats = args.requestedFormats.join(", ");

  const systemPrompt = [
    ...context.promptProfile.mastermind,
    ...context.promptProfile.strategist,
    ...context.promptProfile.copywriter,
    ...context.promptProfile.visualDirector,
    ...context.promptProfile.renderGuard,
    "Return strict JSON matching the required response schema."
  ].filter(Boolean).join("\n");

  const prompt = [
    "Build one creative campaign orchestration decision for social content generation.",
    "",
    `Requested output formats: ${requestedFormats || "(none)"}`,
    `User prompt: ${args.userPrompt?.trim() || "(none)"}`,
    "",
    "Source content:",
    `<title>${args.post.title.trim()}</title>`,
    `<excerpt>${sourceExcerpt || "(none)"}</excerpt>`,
    `<tags>${tags || "(none)"}</tags>`,
    "<body>",
    truncatedSource || "(none)",
    "</body>",
    "",
    "Produce concise notes for:",
    "- strategic_brief: campaign intent, creative angle, and hook strategy",
    "- copywriter_notes: platform tone, structure, and copy direction",
    "- visual_notes: image direction and composition guidance",
    "- warnings: potential quality/compliance risks"
  ].join("\n");

  try {
    const { generateObject } = await import("ai");
    const { z } = await import("zod");
    const schema = z.object({
      strategic_brief: z.string(),
      copywriter_notes: z.string(),
      visual_notes: z.string(),
      warnings: z.array(z.string())
    });

    const result = await generateObject({
      model: models[0],
      system: systemPrompt,
      prompt,
      schema,
      temperature: 0.7,
      maxOutputTokens: 900,
    });

    context.strategicBrief = result.object.strategic_brief;
    context.visualNotes = [context.visualNotes, result.object.visual_notes].filter(Boolean).join("\n");
    context.copyOverrides = {
      ...context.copyOverrides,
      userInstructionsAppend: [context.copyOverrides?.userInstructionsAppend, result.object.copywriter_notes].filter(Boolean).join("\n")
    };
    context.warnings = [...new Set([...context.warnings, ...result.object.warnings])];
    return context;
  } catch {
    context.warnings.push("orchestrator_request_failed");
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

interface ImageSpecInput {
  type: string;
  position: string;
  count: number;
}

async function runHtmlLayoutAgent(
  env: Env,
  post: GhostPost,
  platform: string,
  formatName: string | undefined,
  formatInstruction: string | undefined,
  width: number,
  height: number,
  designBrief: string,
  userPrompt?: string,
  overrides?: LlmPromptOverrides,
  designInstructions?: string,
  generatedImage?: GeneratedImage,
  imageSpec?: ImageSpecInput,
  settings?: WorkspaceSettings | null,
): Promise<LlmOutput> {
  const providerConfig = resolveProviderConfig(env.AI, env.GOOGLE_API_KEY);
  const models = createAdvancedModelChain(providerConfig);

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
    designBrief,
    userPrompt: [
      userPrompt ? `User specifically asked for: ${userPrompt}` : "",
      overrides?.userInstructionsAppend || ""
    ].filter(Boolean).join("\n"),
    systemPrompt,
    userInstructions: overrides?.userInstructions,
    userInstructionsAppend: designInstructions
      ? [overrides?.userInstructionsAppend || "", designInstructions].filter(Boolean).join("\n")
      : overrides?.userInstructionsAppend,
    generatedImage: generatedImage ? {
      dataUrl: imageToDataUrl(generatedImage.data),
      imageType: generatedImage.imageType,
      prompt: generatedImage.prompt,
    } : undefined,
    imageSpec,
    settings,
  });

  return {
    generated_html: result.generated_html,
  };
}

// ==================== PIPELINE ====================

export async function runPipeline(body: GenerateRequestBody, env: Env, security: ResolvedSecurityConfig) {
  const slug = resolveSlug(body);
  if (!slug) throw new HttpError(400, "Request must include either slug or url");
  const post = await fetchGhostPost(env, slug);
  return runPipelineFromPost(post, env, body, security);
}

export async function runPipelineFromPost(post: GhostPost, env: Env, body: GenerateRequestBody | DirectContentRequestBody, security: ResolvedSecurityConfig) {
  const settings = env.SETTINGS_KV ? await loadSettings(env.SETTINGS_KV) : getDefaultSettings();
  const outputPlan = resolveOutputPlanWithSettings(body.output, settings);
  const defaultTokens = await loadDesignTokensForGeneration(env);
  const designTokensForRun = resolveDesignTokensForRequest(body.designTokens, defaultTokens);
  
  // PRE-COMPUTE: Generate all token-derived values once upfront
  const precomputedTokens = precomputeDesignTokenAssets(designTokensForRun);
  // OPTIMIZED: Use lightweight semantic brief instead of full token dump
  const designTokensPrompt = precomputedTokens.semanticBrief;
  const designInstructions = extractDesignInstructions(designTokensForRun);
  
  // CACHE: Generate design tokens hash for cache key
  const designTokensHash = await hashDesignTokens(designTokensForRun);
  const useCache = shouldUseCache({ postCount: outputPlan.postCount });
  
  const brandName = body.brandName ?? settings.brand.name ?? env.BRAND_NAME ?? "Tasbir Blog";
  const variants: Array<{ index: number; image_source: SelectedImage; llm_output: LlmOutput; assets: Record<string, StoredAsset | null>; cacheHit?: boolean; templateDecision?: TemplateDecision }> = [];
  const baseAgentContext = resolveAgentExecutionContext(body.agent);
  const agentContexts: AgentExecutionContext[] = [];
  const sharedStorage = resolveBatchStorageOptions(body.storage);

  let classification: ContentClassification | null = null;
  let matchedTemplate: { html: string; metadata: TemplateMetadata } | null = null;

  // === MARKETING ORCHESTRATOR: Plan posts with gemma-4 ===
  let orchestratorPlan: OrchestratorOutput | null = null;
  try {
    console.log("[orchestrator] Calling Marketing Orchestrator with gemma-4...");
    const orchestratorInput: OrchestratorInput = {
      post: {
        title: post.title,
        excerpt: post.custom_excerpt || post.excerpt || "",
        plaintext: post.plaintext || "",
        tags: post.tags?.map((t: any) => typeof t === 'string' ? t : t.name).slice(0, 8) || [],
      },
      requestedFormats: [...outputPlan.formats],
      userPrompt: body.prompt || "",
      promptProfile: baseAgentContext.promptProfile,
      renderPolicy: baseAgentContext.renderPolicy,
      postCount: outputPlan.postCount,
      settings: {
        brand: settings.brand,
        campaign: settings.campaign,
        formats: settings.formats,
        image: settings.image,
        templates: settings.templates,
      },
      imageConfig: {
        mode: body.image?.mode || settings.image?.mode || 'auto',
      },
    };
    
    orchestratorPlan = await callOrchestrator(
      orchestratorInput,
      env.AI,
      env.GOOGLE_API_KEY
    );
    
    console.log(`[orchestrator] Planned ${orchestratorPlan.plannedPosts?.length || 0} posts`);
    console.log(`[orchestrator] strategic_brief: ${orchestratorPlan.strategic_brief?.slice(0, 100)}...`);
  } catch (error) {
    console.error("[orchestrator] Failed to call orchestrator:", error);
  }

  // SMART TEMPLATE SELECTION: Check for saved HTML templates first
  const providerConfig = resolveProviderConfig(env.AI, env.GOOGLE_API_KEY);
  const templateDecisions: Map<string, TemplateDecision> = new Map();
  const usedSavedTemplates: Map<string, SavedHtmlTemplate> = new Map();

  if (settings.templates.autoSelect && env.TEMPLATES_KV) {
    try {
      const allTemplates = await listTemplates(env.TEMPLATES_KV);
      const enabledTemplates = allTemplates.filter((t) => t.enabled && !settings.templates.disabled.includes(t.id));
      classification = await classifyContent(
        env.AI,
        env.GOOGLE_API_KEY,
        post.title,
        post.plaintext || post.excerpt || "",
        enabledTemplates,
      );

      if (classification.templateMatch) {
        const templateResult = await getTemplate(env.TEMPLATES_KV, env.OUTPUT_BUCKET, classification.templateMatch);
        if (templateResult) {
          matchedTemplate = { html: templateResult.html, metadata: templateResult.metadata };
        }
      }
    } catch (error) {
      console.warn("[classification] Failed to classify content or load template:", error);
    }
  }

  // SMART TEMPLATE: For each format, decide whether to use saved HTML template or generate new
  if (env.AI_CACHE_KV && !matchedTemplate) {
    const formatsArray = [...outputPlan.formats];
    await Promise.all(
      formatsArray.map(async (format) => {
        try {
          const savedTemplates = await listSavedTemplates(env.AI_CACHE_KV!, format);
          if (savedTemplates.length > 0) {
            const decision = await decideTemplateOrGenerate(
              providerConfig,
              {
                title: post.title,
                excerpt: post.custom_excerpt || post.excerpt || "",
                body: post.plaintext || "",
                contentType: classification?.type,
              },
              format,
              savedTemplates,
              {
                preferTemplates: settings.templates.autoSelect,
                qualityThreshold: 3,
              },
              settings
            );
            templateDecisions.set(format, decision);
            
            // If decision is to use template, load it
            if (decision.action === "use_template" && decision.templateId) {
              const savedTemplate = await getSavedTemplate(env.AI_CACHE_KV!, decision.templateId);
              if (savedTemplate) {
                usedSavedTemplates.set(format, savedTemplate);
                // Record usage for popularity tracking
                recordTemplateUsage(env.AI_CACHE_KV!, decision.templateId).catch(() => {});
              }
            }
          }
        } catch (error) {
          console.warn(`[smart-template] Failed to decide for ${format}:`, error);
        }
      })
    );
  }

  const effectivePrompt = buildEffectivePrompt(body.prompt, settings, classification);
  const keyPrefix = buildR2KeyPrefix(env, post.slug, sharedStorage);

  // AI IMAGE GENERATION: Use orchestrator's image decisions
  let generatedImages: Map<string, GeneratedImage | null> = new Map();
  
  // Get effective image mode: body overrides settings
  const effectiveImageMode = body.image?.mode || settings.image?.mode || 'auto';
  
  // Generate images based on orchestrator's planned posts
  if (orchestratorPlan?.plannedPosts && env.AI) {
    try {
      // Filter posts that need AI-generated images based on effective image mode
      const postsNeedingImages = orchestratorPlan.plannedPosts.filter(post => {
        // If user set 'none', skip all
        if (effectiveImageMode === 'none') return false;
        // If user set 'ai', always generate
        if (effectiveImageMode === 'ai') return true;
        // If 'auto' or 'feature', use orchestrator's decision
        if (effectiveImageMode === 'auto' || effectiveImageMode === 'feature') {
          return post.imageSpec && 
            post.imageSpec.type !== 'none' && 
            post.imageSpec.type !== 'feature' &&
            post.imageMode !== 'none';
        }
        return false;
      });
      
      if (postsNeedingImages.length > 0) {
        console.log(`[ai-image] Generating images for ${postsNeedingImages.length} posts based on orchestrator decisions (mode: ${effectiveImageMode})`);
        
        // Generate images in parallel for each post that needs them
        const imagePromises = postsNeedingImages.map(async (post) => {
          const imageSpec = post.imageSpec!;
          if (!imageSpec.prompt) return { format: post.format, image: null };
          
          try {
            const image = await generateImage(env.AI, imageSpec.prompt, {
              width: post.width || 1200,
              height: post.height || 630,
              style: imageSpec.style,
            });
            return { format: post.format, image };
          } catch (e) {
            console.warn(`[ai-image] Failed to generate for ${post.format}:`, e);
            return { format: post.format, image: null };
          }
        });
        
        const results = await Promise.all(imagePromises);
        for (const { format, image } of results) {
          generatedImages.set(format, image);
        }
        
        console.log(`[ai-image] Generated ${generatedImages.size} images: ${Array.from(generatedImages.keys()).join(', ')}`);
      } else {
        console.log(`[ai-image] No posts require AI-generated images based on orchestrator (mode: ${effectiveImageMode})`);
      }
    } catch (error) {
      console.warn(`[ai-image] Image generation failed:`, error);
    }
  }

  // OPTIMIZATION: Launch browser ONCE for the entire request
  const browser = await launchRenderingBrowser(env);
  
  try {
    for (let index = 0; index < outputPlan.postCount; index += 1) {
      const variantPrompt = outputPlan.postCount > 1
        ? [effectivePrompt?.trim(), `Variation index ${index + 1} of ${outputPlan.postCount}.`].filter(Boolean).join(" ")
        : effectivePrompt;

      const agentContext = await resolveAgentContextForRun({
        env,
        post,
        baseContext: baseAgentContext,
        userPrompt: variantPrompt,
        requestedFormats: [...outputPlan.formats]
      });
      agentContexts.push(agentContext);

      // OPTIMIZATION: Generate HTML for all formats in parallel when not using templates
      const formatsArray = [...outputPlan.formats];
      const formatConfigs = formatsArray.map(format => ({ format, config: getFormatConfig(format) })).filter(f => f.config);
      
      // Track cache hits for this variant
      let variantCacheHits = 0;
      
      // Generate all HTML outputs in parallel (with caching and smart template selection)
      const htmlOutputs = await Promise.all(
        formatConfigs.map(async ({ format, config }) => {
          if (!config) return { format, output: null, cacheHit: false, usedSavedTemplate: false };
          
          // SMART TEMPLATE: Check if we should use a saved HTML template for this format
          const savedTemplate = usedSavedTemplates.get(format);
          const templateDecision = templateDecisions.get(format);
          
          if (savedTemplate && templateDecision?.action === "use_template") {
            console.log(`[smart-template] Using saved template "${savedTemplate.name}" for ${format}`);
            const finalHtml = injectDesignTokensIntoHtmlFast(savedTemplate.html, precomputedTokens);
            return { 
              format, 
              output: { generated_html: finalHtml }, 
              config, 
              cacheHit: false, 
              usedSavedTemplate: true,
              templateDecision,
            };
          }
          
          // CACHE: Try to get cached HTML first (only for single-variant requests)
          if (useCache && env.AI_CACHE_KV && !matchedTemplate) {
            const cacheKey = await generateCacheKey({
              title: post.title,
              content: post.plaintext || post.excerpt || "",
              format,
              width: config.width,
              height: config.height,
              prompt: variantPrompt,
              designTokensHash,
            });
            
            const cached = await getCachedHtml(env.AI_CACHE_KV, cacheKey);
            if (cached) {
              console.log(`[ai-cache] HIT for ${format}`);
              variantCacheHits++;
              // Still inject tokens in case they changed slightly
              const finalHtml = injectDesignTokensIntoHtmlFast(cached.html, precomputedTokens);
              return { format, output: { generated_html: finalHtml }, config, cacheHit: true, cacheKey, templateDecision };
            }
          }
          
          let llmOutput: LlmOutput;

          if (matchedTemplate && classification) {
            const slotValues = { ...classification.slotValues };
            if (!slotValues.headline) slotValues.headline = post.title;
            if (!slotValues.brand) slotValues.brand = brandName;
            const filledHtml = fillTemplateSlots(matchedTemplate.html, slotValues);
            llmOutput = { generated_html: filledHtml };
          } else {
            // Use orchestrator's per-post brief if available
            const plannedPost = orchestratorPlan?.plannedPosts?.find(p => 
              p.format.toLowerCase() === format.toLowerCase()
            );
            
            // Build design instructions combining system design guidance + orchestrator's brief
            const baseInstructions = designInstructions ? [designInstructions] : [];
            if (plannedPost?.visualDirection) {
              baseInstructions.push(`VISUAL DIRECTION: ${plannedPost.visualDirection}`);
            }
            if (plannedPost?.copyFocus) {
              baseInstructions.push(`COPY FOCUS: ${plannedPost.copyFocus}`);
            }
            if (plannedPost?.cta && plannedPost.cta !== 'none') {
              baseInstructions.push(`CTA: ${plannedPost.cta}`);
            }
            const instructionsWithDesignGuidance = baseInstructions.length > 0 
              ? baseInstructions.join('\n')
              : undefined;

            // Get generated image for this format (consider orchestrator's imageMode)
            const generatedImage = generatedImages.get(format);

            llmOutput = await runHtmlLayoutAgent(
              env,
              post,
              format,
              config.name,
              config.aiInstruction,
              plannedPost?.width || config.width,
              plannedPost?.height || config.height,
              designTokensPrompt,
              variantPrompt,
              agentContext.copyOverrides,
              instructionsWithDesignGuidance,
              generatedImage || undefined,
              plannedPost?.imageSpec ? {
                type: plannedPost.imageSpec.type || 'background',
                position: plannedPost.imageSpec.position || 'background',
                count: plannedPost.imageSpec.count || 1,
              } : undefined,
              settings,
            );
            
            // CACHE: Store the generated HTML for future requests
            if (useCache && env.AI_CACHE_KV && !matchedTemplate) {
              const cacheKey = await generateCacheKey({
                title: post.title,
                content: post.plaintext || post.excerpt || "",
                format,
                width: config.width,
                height: config.height,
                prompt: variantPrompt,
                designTokensHash,
              });
              
              // Don't await cache write - fire and forget
              setCachedHtml(env.AI_CACHE_KV, cacheKey, {
                html: llmOutput.generated_html,
                generatedAt: Date.now(),
                contentHash: designTokensHash,
                format,
              }).catch(() => {/* ignore cache errors */});
            }
          }

          // Use pre-computed token assets for injection
          const finalHtml = injectDesignTokensIntoHtmlFast(llmOutput.generated_html, precomputedTokens);
          return { 
            format, 
            output: { generated_html: finalHtml }, 
            config, 
            cacheHit: false,
            templateDecision,
            // Mark if AI suggested saving this as template
            suggestSaveAsTemplate: templateDecision?.suggestedSaveAsTemplate ?? false,
          };
        })
      );

      // OPTIMIZATION: Render all formats in parallel using separate browser pages
      const renderResults = await Promise.all(
        htmlOutputs.map(async ({ format, output, config, cacheHit, usedSavedTemplate, templateDecision, suggestSaveAsTemplate }) => {
          if (!output || !config) return { format, asset: null, cacheHit, usedSavedTemplate, templateDecision, suggestSaveAsTemplate };
          
          const asset = await renderStoreSingleAssetWithPage(env, browser, {
            key: `${keyPrefix}/${buildAssetFileName(format, assetNameSuffixForVariant(index, outputPlan.postCount))}`,
            format,
            rawHtml: output.generated_html,
            formatLabel: format,
            width: config.width,
            height: config.height,
          });
          
          return { format, asset, output, cacheHit, usedSavedTemplate, templateDecision, suggestSaveAsTemplate };
        })
      );

      const formatAssets: Record<string, StoredAsset | null> = {};
      let variantLlmOutput: LlmOutput | null = null;
      let imageSource: SelectedImage = { source: "none", imageUrl: "" };
      const smartTemplateInfo: Record<string, { used: boolean; templateId?: string; suggestSave?: boolean }> = {};

      for (const { format, asset, output, usedSavedTemplate, templateDecision, suggestSaveAsTemplate } of renderResults) {
        if (asset) formatAssets[format] = asset;
        if (!variantLlmOutput && output) variantLlmOutput = output;
        smartTemplateInfo[format] = {
          used: usedSavedTemplate ?? false,
          templateId: templateDecision?.templateId,
          suggestSave: suggestSaveAsTemplate,
        };
      }

      if (index === 0) {
        imageSource = { source: post.feature_image ? "feature" : "none", imageUrl: post.feature_image || "" };
      }

      variants.push({
        index: index + 1,
        image_source: imageSource,
        llm_output: variantLlmOutput || { generated_html: "" },
        assets: formatAssets,
        templateDecision: Object.keys(smartTemplateInfo).length > 0 ? smartTemplateInfo as any : undefined,
      });
    }
  } finally {
    // Close browser once after all rendering is complete
    await browser.close();
  }

  const primaryVariant = variants[0];
  if (!primaryVariant) throw new HttpError(500, "Generation pipeline did not produce any output variants");

  // Summarize smart template decisions for response
  const smartTemplateSummary = templateDecisions.size > 0 ? {
    decisions: Object.fromEntries(
      Array.from(templateDecisions.entries()).map(([format, decision]) => [
        format,
        {
          action: decision.action,
          templateId: decision.templateId,
          confidence: decision.confidence,
          suggestSave: decision.suggestedSaveAsTemplate,
        },
      ])
    ),
    templatesUsed: Array.from(usedSavedTemplates.entries()).map(([format, template]) => ({
      format,
      templateId: template.id,
      templateName: template.name,
    })),
  } : undefined;

  return {
    ok: true,
    slug: post.slug,
    post_url: post.url,
    requested_formats: [...outputPlan.formats],
    image_source: primaryVariant.image_source,
    llm_output: primaryVariant.llm_output,
    agentic: summarizeAgentExecution(agentContexts),
    assets: primaryVariant.assets,
    variants: outputPlan.postCount > 1 ? variants : undefined,
    classification: classification ? {
      type: classification.type,
      templateUsed: classification.templateMatch,
      reasoning: classification.reasoning,
    } : undefined,
    smartTemplates: smartTemplateSummary,
  };
}

interface StreamProgress {
  type: "start" | "classifying" | "generating" | "rendering" | "complete" | "error";
  message: string;
  format?: string;
  progress?: number;
  total?: number;
}

/**
 * STREAMING: Pipeline with progress callback for real-time updates.
 * Provides progress events that can be streamed to clients via SSE.
 */
export async function runPipelineFromPostWithProgress(
  post: GhostPost,
  env: Env,
  body: GenerateRequestBody | DirectContentRequestBody,
  security: ResolvedSecurityConfig,
  onProgress: (progress: StreamProgress) => void
) {
  const settings = env.SETTINGS_KV ? await loadSettings(env.SETTINGS_KV) : getDefaultSettings();
  const outputPlan = resolveOutputPlanWithSettings(body.output, settings);
  const defaultTokens = await loadDesignTokensForGeneration(env);
  const designTokensForRun = resolveDesignTokensForRequest(body.designTokens, defaultTokens);
  
  const precomputedTokens = precomputeDesignTokenAssets(designTokensForRun);
  const designTokensPrompt = formatDesignTokensForPromptFromObject(designTokensForRun);
  const designInstructions = extractDesignInstructions(designTokensForRun);
  const designTokensHash = await hashDesignTokens(designTokensForRun);
  const useCache = shouldUseCache({ postCount: outputPlan.postCount });
  
  const brandName = body.brandName ?? settings.brand.name ?? env.BRAND_NAME ?? "Tasbir Blog";
  const variants: Array<{ index: number; image_source: SelectedImage; llm_output: LlmOutput; assets: Record<string, StoredAsset | null> }> = [];
  const baseAgentContext = resolveAgentExecutionContext(body.agent);
  const agentContexts: AgentExecutionContext[] = [];
  const sharedStorage = resolveBatchStorageOptions(body.storage);

  let classification: ContentClassification | null = null;
  let matchedTemplate: { html: string; metadata: TemplateMetadata } | null = null;

  // === MARKETING ORCHESTRATOR: Plan posts with gemma-4 ===
  let orchestratorPlan: OrchestratorOutput | null = null;
  try {
    onProgress({ type: "generating", message: "Planning content strategy with AI..." });
    console.log("[orchestrator] Calling Marketing Orchestrator with gemma-4...");
    const orchestratorInput: OrchestratorInput = {
      post: {
        title: post.title,
        excerpt: post.custom_excerpt || post.excerpt || "",
        plaintext: post.plaintext || "",
        tags: post.tags?.map((t: any) => typeof t === 'string' ? t : t.name).slice(0, 8) || [],
      },
      requestedFormats: [...outputPlan.formats],
      userPrompt: body.prompt || "",
      promptProfile: baseAgentContext.promptProfile,
      renderPolicy: baseAgentContext.renderPolicy,
      postCount: outputPlan.postCount,
      settings: {
        brand: settings.brand,
        campaign: settings.campaign,
        formats: settings.formats,
        image: settings.image,
        templates: settings.templates,
      },
      imageConfig: {
        mode: body.image?.mode || settings.image?.mode || 'auto',
      },
    };
    
    orchestratorPlan = await callOrchestrator(
      orchestratorInput,
      env.AI,
      env.GOOGLE_API_KEY
    );
    
    console.log(`[orchestrator] Planned ${orchestratorPlan.plannedPosts?.length || 0} posts`);
    console.log(`[orchestrator] strategic_brief: ${orchestratorPlan.strategic_brief?.slice(0, 100)}...`);
  } catch (error) {
    console.error("[orchestrator] Failed to call orchestrator:", error);
  }

  // Classification phase
  if (settings.templates.autoSelect && env.TEMPLATES_KV) {
    onProgress({ type: "classifying", message: "Analyzing content..." });
    try {
      const allTemplates = await listTemplates(env.TEMPLATES_KV);
      const enabledTemplates = allTemplates.filter((t) => t.enabled && !settings.templates.disabled.includes(t.id));
      classification = await classifyContent(
        env.AI,
        env.GOOGLE_API_KEY,
        post.title,
        post.plaintext || post.excerpt || "",
        enabledTemplates,
      );

      if (classification.templateMatch) {
        const templateResult = await getTemplate(env.TEMPLATES_KV, env.OUTPUT_BUCKET, classification.templateMatch);
        if (templateResult) {
          matchedTemplate = { html: templateResult.html, metadata: templateResult.metadata };
        }
      }
    } catch (error) {
      console.warn("[classification] Failed to classify content or load template:", error);
    }
  }

  // AI IMAGE GENERATION: Use orchestrator's image decisions
  let generatedImages: Map<string, GeneratedImage | null> = new Map();
  
  // Get effective image mode: body overrides settings
  const effectiveImageMode = body.image?.mode || settings.image?.mode || 'auto';
  
  // Generate images based on orchestrator's planned posts
  if (orchestratorPlan?.plannedPosts && env.AI) {
    try {
      // Filter posts that need AI-generated images based on effective image mode
      const postsNeedingImages = orchestratorPlan.plannedPosts.filter(post => {
        // If user set 'none', skip all
        if (effectiveImageMode === 'none') return false;
        // If user set 'ai', always generate
        if (effectiveImageMode === 'ai') return true;
        // If 'auto' or 'feature', use orchestrator's decision
        if (effectiveImageMode === 'auto' || effectiveImageMode === 'feature') {
          return post.imageSpec && 
            post.imageSpec.type !== 'none' && 
            post.imageSpec.type !== 'feature' &&
            post.imageMode !== 'none';
        }
        return false;
      });
      
      if (postsNeedingImages.length > 0) {
        onProgress({ type: "generating", message: `Generating ${postsNeedingImages.length} illustrations...` });
        console.log(`[ai-image] Generating images for ${postsNeedingImages.length} posts based on orchestrator decisions`);
        
        // Generate images in parallel for each post that needs them
        const imagePromises = postsNeedingImages.map(async (post) => {
          const imageSpec = post.imageSpec!;
          if (!imageSpec.prompt) return { format: post.format, image: null };
          
          try {
            const image = await generateImage(env.AI, imageSpec.prompt, {
              width: post.width || 1200,
              height: post.height || 630,
              style: imageSpec.style,
            });
            return { format: post.format, image };
          } catch (e) {
            console.warn(`[ai-image] Failed to generate for ${post.format}:`, e);
            return { format: post.format, image: null };
          }
        });
        
        const results = await Promise.all(imagePromises);
        for (const { format, image } of results) {
          generatedImages.set(format, image);
        }
        
        console.log(`[ai-image] Generated ${generatedImages.size} images: ${Array.from(generatedImages.keys()).join(', ')}`);
      } else {
        console.log(`[ai-image] No posts require AI-generated images based on orchestrator (mode: ${effectiveImageMode})`);
      }
    } catch (error) {
      console.warn(`[ai-image] Image generation failed:`, error);
    }
  }

  const effectivePrompt = buildEffectivePrompt(body.prompt, settings, classification);
  const keyPrefix = buildR2KeyPrefix(env, post.slug, sharedStorage);
  const formatsArray = [...outputPlan.formats];
  const totalFormats = formatsArray.length;

  const browser = await launchRenderingBrowser(env);
  
  try {
    for (let index = 0; index < outputPlan.postCount; index += 1) {
      const variantPrompt = outputPlan.postCount > 1
        ? [effectivePrompt?.trim(), `Variation index ${index + 1} of ${outputPlan.postCount}.`].filter(Boolean).join(" ")
        : effectivePrompt;

      const agentContext = await resolveAgentContextForRun({
        env,
        post,
        baseContext: baseAgentContext,
        userPrompt: variantPrompt,
        requestedFormats: formatsArray
      });
      agentContexts.push(agentContext);

      const formatConfigs = formatsArray.map(format => ({ format, config: getFormatConfig(format) })).filter(f => f.config);
      const formatAssets: Record<string, StoredAsset | null> = {};
      let variantLlmOutput: LlmOutput | null = null;
      let imageSource: SelectedImage = { source: "none", imageUrl: "" };

      // Generate and render each format with progress updates
      for (let i = 0; i < formatConfigs.length; i++) {
        const { format, config } = formatConfigs[i];
        if (!config) continue;

        onProgress({ 
          type: "generating", 
          message: `Generating ${format}...`,
          format,
          progress: i + 1,
          total: totalFormats
        });

        let llmOutput: LlmOutput | null = null;

        // Check cache first
        if (useCache && env.AI_CACHE_KV && !matchedTemplate) {
          const cacheKey = await generateCacheKey({
            title: post.title,
            content: post.plaintext || post.excerpt || "",
            format,
            width: config.width,
            height: config.height,
            prompt: variantPrompt,
            designTokensHash,
          });
          
          const cached = await getCachedHtml(env.AI_CACHE_KV, cacheKey);
          if (cached) {
            llmOutput = { generated_html: cached.html };
            onProgress({ type: "generating", message: `Using cached ${format}`, format, progress: i + 1, total: totalFormats });
          }
        }
        
        // If not cached, generate
        if (!llmOutput) {
          if (matchedTemplate && classification) {
            const slotValues = { ...classification.slotValues };
            if (!slotValues.headline) slotValues.headline = post.title;
            if (!slotValues.brand) slotValues.brand = brandName;
            llmOutput = { generated_html: fillTemplateSlots(matchedTemplate.html, slotValues) };
          } else {
            const instructionsWithDesignGuidance = designInstructions
              ? [`DESIGN SYSTEM INSTRUCTIONS (follow these closely):`, designInstructions].join('\n')
              : undefined;

            // Get generated image for this format  
            const generatedImage = generatedImages.get(format);

            // Get planned post from orchestrator for this format (if available)
            const plannedPost = orchestratorPlan?.plannedPosts?.find((p: any) => 
              p.format.toLowerCase() === format.toLowerCase()
            ) || null;

            llmOutput = await runHtmlLayoutAgent(
              env,
              post,
              format,
              config.name,
              config.aiInstruction,
              config.width,
              config.height,
              designTokensPrompt,
              variantPrompt,
              agentContext.copyOverrides,
              instructionsWithDesignGuidance,
              generatedImage || undefined,
              plannedPost?.imageSpec ? {
                type: plannedPost.imageSpec.type || 'background',
                position: plannedPost.imageSpec.position || 'background',
                count: plannedPost.imageSpec.count || 1,
              } : undefined,
              settings,
            );

            // Cache the result if caching is enabled
            if (useCache && env.AI_CACHE_KV) {
              const cacheKey = await generateCacheKey({
                title: post.title,
                content: post.plaintext || post.excerpt || "",
                format,
                width: config.width,
                height: config.height,
                prompt: variantPrompt,
                designTokensHash,
              });
              
              setCachedHtml(env.AI_CACHE_KV, cacheKey, {
                html: llmOutput.generated_html,
                generatedAt: Date.now(),
                contentHash: designTokensHash,
                format,
              }).catch(() => {});
            }
          }
        }

        const finalHtml = injectDesignTokensIntoHtmlFast(llmOutput.generated_html, precomputedTokens);

        onProgress({ 
          type: "rendering", 
          message: `Rendering ${format}...`,
          format,
          progress: i + 1,
          total: totalFormats
        });

        const asset = await renderStoreSingleAssetWithPage(env, browser, {
          key: `${keyPrefix}/${buildAssetFileName(format, assetNameSuffixForVariant(index, outputPlan.postCount))}`,
          format,
          rawHtml: finalHtml,
          formatLabel: format,
          width: config.width,
          height: config.height,
        });

        formatAssets[format] = asset;
        if (!variantLlmOutput) variantLlmOutput = { generated_html: finalHtml };
      }

      if (index === 0) {
        imageSource = { source: post.feature_image ? "feature" : "none", imageUrl: post.feature_image || "" };
      }

      variants.push({
        index: index + 1,
        image_source: imageSource,
        llm_output: variantLlmOutput || { generated_html: "" },
        assets: formatAssets
      });
    }
  } finally {
    await browser.close();
  }

  const primaryVariant = variants[0];
  if (!primaryVariant) throw new HttpError(500, "Generation pipeline did not produce any output variants");

  return {
    ok: true,
    slug: post.slug,
    post_url: post.url,
    requested_formats: formatsArray,
    image_source: primaryVariant.image_source,
    llm_output: primaryVariant.llm_output,
    agentic: summarizeAgentExecution(agentContexts),
    assets: primaryVariant.assets,
    variants: outputPlan.postCount > 1 ? variants : undefined,
    classification: classification ? {
      type: classification.type,
      templateUsed: classification.templateMatch,
      reasoning: classification.reasoning,
    } : undefined,
  };
}

function resolveOutputPlanWithSettings(bodyOutput: OutputOptions | undefined, settings: WorkspaceSettings): { formats: Set<string>; carouselSlides: number; postCount: number } {
  const formatNames = getFormatNames();
  const formatSet = new Set(formatNames);
  const enabledFormats = settings.formats.enabled.length > 0 ? settings.formats.enabled : formatNames;
  const requestedFormats = bodyOutput?.formats && bodyOutput.formats.length > 0 ? bodyOutput.formats : enabledFormats;
  const normalizedFormats = new Set<string>();
  for (const format of requestedFormats) {
    if (formatSet.has(format)) normalizedFormats.add(format);
  }
  if (normalizedFormats.size === 0) throw new HttpError(400, "output.formats must include at least one supported format");

  const postCount = Math.round(clampNumber(bodyOutput?.postCount, 1, 10, settings.formats.postCount || 1));
  return { formats: normalizedFormats, carouselSlides: DEFAULT_CAROUSEL_SLIDES, postCount };
}

function buildEffectivePrompt(bodyPrompt: string | undefined, settings: WorkspaceSettings, classification: ContentClassification | null): string | undefined {
  if (bodyPrompt?.trim()) return bodyPrompt.trim();

  const parts: string[] = [];

  if (settings.brand.tone) {
    parts.push(`Tone: ${settings.brand.tone}.`);
  }
  if (settings.brand.audience) {
    parts.push(`Audience: ${settings.brand.audience}.`);
  }
  if (settings.campaign.goal && settings.campaign.goal !== "awareness") {
    parts.push(`Campaign goal: ${settings.campaign.goal}.`);
  }
  if (settings.campaign.framework && settings.campaign.framework !== "none") {
    parts.push(`Use ${settings.campaign.framework} copywriting framework.`);
  }
  if (settings.campaign.cta) {
    parts.push(`Include CTA: ${settings.campaign.cta}`);
  }
  if (classification) {
    parts.push(`Content type: ${classification.type}.`);
  }

  return parts.length > 0 ? parts.join(" ") : undefined;
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

/**
 * OPTIMIZED: Render a single asset using an existing browser instance.
 * Creates a new page, renders, and closes the page - but keeps browser alive.
 */
async function renderStoreSingleAssetWithPage(
  env: Env,
  browser: any,
  args: { key: string; format: string; rawHtml?: string; formatLabel: string; width: number; height: number }
): Promise<StoredAsset> {
  const html = args.rawHtml;
  if (!html) throw new HttpError(500, "No HTML provided for rendering");

  const png = await renderPng(browser, html, args.width, args.height);

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

/**
 * OPTIMIZED: Render HTML to PNG with reduced wait times.
 * - Uses domcontentloaded instead of networkidle0 for faster initial load
 * - Reduces Tailwind detection timeout from 3000ms to 1500ms
 * - Removes fixed 150ms wait, uses immediate RAF instead
 * - Parallelizes font and image loading checks
 */
async function renderPng(browser: any, html: string, width: number, height: number): Promise<Uint8Array> {
  const page = await browser.newPage();
  try {
    await page.setViewport({ width, height, deviceScaleFactor: 1 });
    
    // Use domcontentloaded for faster initial render, then wait for specific conditions
    await page.setContent(html, { waitUntil: "domcontentloaded", timeout: 10_000 });

    // OPTIMIZED: Combined wait for Tailwind + fonts + images in a single evaluate
    await page.evaluate(`
      (async () => {
        // Wait for Tailwind styles (reduced from 3000ms to 1500ms)
        const maxWait = 1500;
        const start = Date.now();
        while (Date.now() - start < maxWait) {
          const tailwindStyles = document.querySelector('style[data-tailwind]') || 
                                 document.querySelector('style:not([id])');
          if (tailwindStyles && tailwindStyles.textContent && tailwindStyles.textContent.length > 500) {
            break;
          }
          await new Promise(r => setTimeout(r, 25));
        }
        
        // Single RAF for layout stabilization (removed extra 150ms wait)
        await new Promise((resolve) => requestAnimationFrame(resolve));
        
        // Wait for fonts and images in parallel
        await Promise.all([
          document.fonts.ready,
          Promise.all(Array.from(document.images).map(async (img) => {
            try { await img.decode(); } catch {}
          }))
        ]);
      })();
    `);

    // Check for custom render completion flag (reduced timeout)
    await page.waitForFunction(
      "() => typeof window.__RICH_RENDER_DONE__ === 'undefined' || window.__RICH_RENDER_DONE__ === true",
      { timeout: 3_000 }
    );

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
  const ghostUrl = env.GHOST_API_URL;
  const ghostKey = env.GHOST_CONTENT_API_KEY;
  if (!ghostUrl) throw new HttpError(500, "GHOST_API_URL is not configured");
  if (!ghostKey) throw new HttpError(500, "GHOST_CONTENT_API_KEY is not configured");

  const base = ghostUrl.replace(/\/+$/, "");
  const endpoint = `${base}/posts/slug/${encodeURIComponent(slug)}/?key=${encodeURIComponent(ghostKey)}&include=tags,authors&formats=html,plaintext`;
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
