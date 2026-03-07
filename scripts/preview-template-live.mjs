#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { constants as FS_CONSTANTS } from "node:fs";
import { access, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import process from "node:process";

const DEFAULT_BASE_URL = "http://127.0.0.1:8787";
const DEFAULT_FORMAT = "instagram-square";
const DEFAULT_IMAGE_URL =
  "https://picsum.photos/seed/tasbir-template-preview/1600/1200";
const HEALTH_TIMEOUT_MS = 60_000;
const HEALTH_POLL_MS = 500;
const GENERATED_ASSETS_PATH = resolve(process.cwd(), "src/generated/template-assets.json");

function printHelp() {
  console.log(`Live-preview one template locally with instant reload.

Usage:
  node scripts/preview-template-live.mjs [options]

Options:
  --format <id>          Output format (default: ${DEFAULT_FORMAT})
  --template <id>        Template id or filename (example: layout/statement-cta, statement-cta.html)
  --base-url <url>       Worker URL (default: ${DEFAULT_BASE_URL})
  --api-key <key>        Optional API key when preview auth is enabled
  --title <text>         Override preview title
  --caption <text>       Override preview caption
  --heading <text>       Override carousel heading
  --body <text>          Override carousel body
  --brand-name <text>    Override brand name
  --image-url <url>      Override preview image URL
  --slide <number>       Override carousel slide number
  --total <number>       Override carousel total slides
  --list                 List templates compatible with --format and exit
  --build                Run pnpm build before preview
  --no-start-server      Do not auto-start pnpm run dev
  --open                 Open preview URL in browser (default)
  --no-open              Print URL but do not open browser
  --help                 Show this help

Examples:
  pnpm run preview:template -- --format instagram-square --template statement-dark
  pnpm run preview:template -- --format twitter-card --template layout/split-copy-media --no-open
`);
}

function parseArgs(argv) {
  const options = {
    format: DEFAULT_FORMAT,
    template: "",
    baseUrl: DEFAULT_BASE_URL,
    apiKey: process.env.API_KEY?.trim() || "",
    title: "",
    caption: "",
    heading: "",
    body: "",
    brandName: "",
    imageUrl: "",
    slide: "",
    total: "",
    list: false,
    build: false,
    noStartServer: false,
    open: true,
    help: false
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];

    if (arg === "--") {
      continue;
    }

    if (arg === "--help" || arg === "-h") {
      options.help = true;
      continue;
    }
    if (arg === "--list") {
      options.list = true;
      continue;
    }
    if (arg === "--build") {
      options.build = true;
      continue;
    }
    if (arg === "--no-start-server") {
      options.noStartServer = true;
      continue;
    }
    if (arg === "--open") {
      options.open = true;
      continue;
    }
    if (arg === "--no-open") {
      options.open = false;
      continue;
    }

    if ((arg === "--format" || arg === "--template" || arg === "--template-id" || arg === "--base-url" || arg === "--api-key" || arg === "--title" || arg === "--caption" || arg === "--heading" || arg === "--body" || arg === "--brand-name" || arg === "--image-url" || arg === "--slide" || arg === "--total") && next) {
      if (arg === "--format") options.format = next.trim();
      else if (arg === "--template" || arg === "--template-id") options.template = next.trim();
      else if (arg === "--base-url") options.baseUrl = next.trim();
      else if (arg === "--api-key") options.apiKey = next.trim();
      else if (arg === "--title") options.title = next.trim();
      else if (arg === "--caption") options.caption = next.trim();
      else if (arg === "--heading") options.heading = next.trim();
      else if (arg === "--body") options.body = next.trim();
      else if (arg === "--brand-name") options.brandName = next.trim();
      else if (arg === "--image-url") options.imageUrl = next.trim();
      else if (arg === "--slide") options.slide = next.trim();
      else if (arg === "--total") options.total = next.trim();
      index += 1;
      continue;
    }

    if (arg.startsWith("--format=")) {
      options.format = arg.slice("--format=".length).trim();
      continue;
    }
    if (arg.startsWith("--template=")) {
      options.template = arg.slice("--template=".length).trim();
      continue;
    }
    if (arg.startsWith("--template-id=")) {
      options.template = arg.slice("--template-id=".length).trim();
      continue;
    }
    if (arg.startsWith("--base-url=")) {
      options.baseUrl = arg.slice("--base-url=".length).trim();
      continue;
    }
    if (arg.startsWith("--api-key=")) {
      options.apiKey = arg.slice("--api-key=".length).trim();
      continue;
    }
    if (arg.startsWith("--title=")) {
      options.title = arg.slice("--title=".length).trim();
      continue;
    }
    if (arg.startsWith("--caption=")) {
      options.caption = arg.slice("--caption=".length).trim();
      continue;
    }
    if (arg.startsWith("--heading=")) {
      options.heading = arg.slice("--heading=".length).trim();
      continue;
    }
    if (arg.startsWith("--body=")) {
      options.body = arg.slice("--body=".length).trim();
      continue;
    }
    if (arg.startsWith("--brand-name=")) {
      options.brandName = arg.slice("--brand-name=".length).trim();
      continue;
    }
    if (arg.startsWith("--image-url=")) {
      options.imageUrl = arg.slice("--image-url=".length).trim();
      continue;
    }
    if (arg.startsWith("--slide=")) {
      options.slide = arg.slice("--slide=".length).trim();
      continue;
    }
    if (arg.startsWith("--total=")) {
      options.total = arg.slice("--total=".length).trim();
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  const parsedUrl = new URL(options.baseUrl);
  if (parsedUrl.protocol !== "http:") {
    throw new Error("--base-url must use http:// for local wrangler dev");
  }

  options.format = options.format.trim();
  options.template = options.template.trim();

  return options;
}

function authHeaders(options) {
  if (!options.apiKey) return undefined;
  return { "x-api-key": options.apiKey };
}

async function runCommand(command, args, opts = {}) {
  await new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, {
      cwd: opts.cwd ?? process.cwd(),
      stdio: opts.stdio ?? "inherit"
    });

    child.on("error", rejectPromise);
    child.on("exit", (code) => {
      if (code === 0) {
        resolvePromise(undefined);
      } else {
        rejectPromise(new Error(`Command failed: ${command} ${args.join(" ")} (exit ${String(code)})`));
      }
    });
  });
}

async function fileReadable(path) {
  try {
    await access(path, FS_CONSTANTS.R_OK);
    return true;
  } catch {
    return false;
  }
}

function templateSupportsFormat(template, formatId) {
  const single = typeof template?.format === "string" ? template.format.trim() : "";
  if (single) return single === formatId;
  const formats = Array.isArray(template?.formats)
    ? template.formats.map((item) => (typeof item === "string" ? item.trim() : "")).filter(Boolean)
    : [];
  if (formats.length > 0) return formats.includes(formatId);
  return true;
}

async function loadTemplateCatalog() {
  const raw = await readFile(GENERATED_ASSETS_PATH, "utf8");
  const generated = JSON.parse(raw);
  const pipelineConfig = generated?.pipeline_config ?? {};
  const formatConfig = pipelineConfig.formats ?? {};
  const templates = Array.isArray(pipelineConfig.templates) ? pipelineConfig.templates : [];
  const previewDefaults = pipelineConfig.preview_defaults ?? {};
  const brandName = String(pipelineConfig?.brand?.default_name ?? "Tasbir");

  const templatesById = new Map(
    templates
      .map((template) => ({
        ...template,
        id: String(template?.id ?? "").trim()
      }))
      .filter((template) => template.id.length > 0)
      .map((template) => [template.id, template])
  );

  return {
    formatConfig,
    templates,
    templatesById,
    previewDefaults,
    brandName
  };
}

function templateIdCandidates(input) {
  const raw = String(input ?? "").trim().replaceAll("\\", "/").replace(/^\/+/, "");
  if (!raw) return [];
  const fromTemplatePath = raw.replace(/^templates\//, "").replace(/\.html$/i, "");
  const withoutLayoutPrefix = fromTemplatePath.replace(/^layout\//, "");
  const candidates = [
    raw,
    fromTemplatePath,
    fromTemplatePath.replace(/\.html$/i, ""),
    `layout/${withoutLayoutPrefix.replace(/\.html$/i, "")}`
  ]
    .map((item) => item.trim().replace(/\/{2,}/g, "/"))
    .filter(Boolean);
  return [...new Set(candidates)];
}

function resolveTemplateId(options, catalog) {
  const availableByFormat = catalog.templates.filter((template) => templateSupportsFormat(template, options.format));

  if (options.template) {
    const inputCandidates = templateIdCandidates(options.template);
    for (const candidate of inputCandidates) {
      const template = catalog.templatesById.get(candidate);
      if (!template) continue;
      if (!templateSupportsFormat(template, options.format)) {
        throw new Error(`Template "${candidate}" is not compatible with format "${options.format}"`);
      }
      return candidate;
    }

    const wanted = new Set(inputCandidates);
    for (const template of availableByFormat) {
      const templateFile = String(template?.file ?? "").trim();
      if (!templateFile) continue;
      const fileCandidates = templateIdCandidates(templateFile);
      if (fileCandidates.some((candidate) => wanted.has(candidate))) {
        return String(template.id);
      }
    }

    throw new Error(`Template "${options.template}" not found in generated template catalog`);
  }

  const formatDefault = String(catalog.formatConfig?.[options.format]?.default_template_id ?? "").trim();
  if (formatDefault) {
    const template = catalog.templatesById.get(formatDefault);
    if (template && templateSupportsFormat(template, options.format)) {
      return formatDefault;
    }
  }

  if (availableByFormat.length === 0) {
    throw new Error(`No templates compatible with format "${options.format}"`);
  }
  return String(availableByFormat[0]?.id ?? "");
}

function humanizeKey(value) {
  return String(value || "")
    .replaceAll(/[_:-]+/g, " ")
    .replaceAll(/\s+/g, " ")
    .trim();
}

function truncate(text, maxChars) {
  const normalized = String(text ?? "").replaceAll(/\s+/g, " ").trim();
  if (normalized.length <= maxChars) return normalized;
  return `${normalized.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`;
}

function buildPreviewPayload(catalog, options) {
  const defaults = catalog.previewDefaults ?? {};
  const slideDefault = String(defaults.slide_number ?? 1);
  const totalDefault = String(defaults.total_slides ?? 5);
  const configuredImageDefault = typeof defaults.image_url === "string" ? defaults.image_url.trim() : "";
  const imageDefault = configuredImageDefault && !configuredImageDefault.startsWith("data:")
    ? configuredImageDefault
    : DEFAULT_IMAGE_URL;

  const payload = {
    title: options.title || String(defaults.title ?? "Template preview"),
    caption: options.caption || String(defaults.caption ?? "Local preview payload"),
    heading: options.heading || String(defaults.heading ?? "Template preview heading"),
    body: options.body || String(defaults.body ?? "Local preview body content."),
    brandName: options.brandName || catalog.brandName,
    imageUrl: options.imageUrl || imageDefault,
    slide: options.slide || slideDefault,
    total: options.total || totalDefault
  };

  return {
    ...payload,
    slotHeadline: truncate(payload.heading || payload.title, 120),
    slotBody: truncate(payload.body || payload.caption, 240),
    slotTag: "PREVIEW",
    slotCta: "Read more",
    slotQuote: truncate(payload.caption || "Preview quote.", 160),
    slotByline: payload.brandName,
    slotFallbackPrefix: "Preview",
    metricValue: "42"
  };
}

function deriveSlotValue(field, previewPayload) {
  const rawKey = String(field?.key ?? "").trim();
  const key = rawKey.toLowerCase();
  const defaultValue = typeof field?.default === "string" ? field.default.trim() : "";
  const type = typeof field?.type === "string" ? field.type : "text";

  if (defaultValue.length > 0) {
    return defaultValue;
  }
  if (/(media_position|image_position|stack_position|layout_variant)/.test(key)) {
    return "top";
  }
  if (type === "image_url" || type === "icon_url" || /(image|icon|photo|avatar|logo)/.test(key)) {
    return previewPayload.imageUrl;
  }
  if (/^color_swap$/.test(key)) {
    return "0";
  }
  if (/(slide|index|step)/.test(key)) {
    return previewPayload.slide;
  }
  if (/total/.test(key)) {
    return previewPayload.total;
  }
  if (type === "number" || /(count|number|value|metric|score|percent|pct)/.test(key)) {
    return previewPayload.metricValue;
  }
  if (/(visible|enabled|show|hide)/.test(key)) {
    return "1";
  }
  if (/(headline|title|heading|hook|claim|thesis)/.test(key)) {
    return previewPayload.slotHeadline;
  }
  if (/(body|description|insight|detail|narrative|summary|copy|text|line)/.test(key)) {
    return previewPayload.slotBody;
  }
  if (/(caption|subtitle|subhead|dek)/.test(key)) {
    return previewPayload.caption;
  }
  if (/(tag|label|kicker|badge|meta|category|section)/.test(key)) {
    return previewPayload.slotTag;
  }
  if (/(cta|action|button|prompt|next)/.test(key)) {
    return previewPayload.slotCta;
  }
  if (/quote/.test(key)) {
    return previewPayload.slotQuote;
  }
  if (/(author|name|speaker|source|brand)/.test(key)) {
    return previewPayload.slotByline;
  }

  return truncate(`${previewPayload.slotFallbackPrefix} ${humanizeKey(rawKey || "content")}`, 120);
}

function buildSlotValues(template, previewPayload) {
  const slots = {};
  const fields = Array.isArray(template?.fields) ? template.fields : [];

  for (const field of fields) {
    const slotKey = String(field?.key ?? "").trim();
    if (!slotKey) continue;
    const slotValue = deriveSlotValue(field, previewPayload);
    if (!slotValue) continue;
    slots[slotKey] = slotValue;
  }

  return slots;
}

function buildPreviewUrl(options, templateId, previewPayload, slots) {
  const url = new URL(`/template/${options.format}`, options.baseUrl);
  url.searchParams.set("format", options.format);
  url.searchParams.set("templateId", templateId);
  url.searchParams.set("title", previewPayload.title);
  url.searchParams.set("caption", previewPayload.caption);
  url.searchParams.set("imageUrl", previewPayload.imageUrl);
  url.searchParams.set("brandName", previewPayload.brandName);

  if (options.format === "carousel-post") {
    url.searchParams.set("heading", previewPayload.heading);
    url.searchParams.set("body", previewPayload.body);
    url.searchParams.set("slide", previewPayload.slide);
    url.searchParams.set("total", previewPayload.total);
  }

  for (const [slotKey, slotValue] of Object.entries(slots)) {
    if (!slotValue) continue;
    url.searchParams.set(`slot.${slotKey}`, String(slotValue));
  }

  return url;
}

async function isHealthy(baseUrl, headers) {
  try {
    const response = await fetch(new URL("/health", baseUrl), { headers });
    return response.ok;
  } catch {
    return false;
  }
}

function wait(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

async function waitForHealth(baseUrl, headers, timeoutMs, child) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child && child.exitCode !== null) {
      throw new Error("pnpm run dev exited before health check succeeded");
    }
    if (await isHealthy(baseUrl, headers)) {
      return;
    }
    await wait(HEALTH_POLL_MS);
  }
  throw new Error(`Timed out waiting for worker at ${baseUrl}`);
}

function startDevServer() {
  return spawn("pnpm", ["run", "dev"], {
    cwd: process.cwd(),
    stdio: "inherit"
  });
}

async function stopProcess(child) {
  if (!child || child.exitCode !== null) {
    return;
  }

  child.kill("SIGTERM");
  await Promise.race([
    new Promise((resolvePromise) => child.once("exit", resolvePromise)),
    wait(4_000)
  ]);

  if (child.exitCode === null) {
    child.kill("SIGKILL");
  }
}

function openInBrowser(url) {
  const attempts = [];
  if (process.platform === "darwin") {
    attempts.push({ command: "open", args: [url] });
  } else if (process.platform === "win32") {
    attempts.push({ command: "cmd", args: ["/c", "start", "", url] });
  } else {
    attempts.push({ command: "xdg-open", args: [url] });
  }

  for (const attempt of attempts) {
    const result = spawnSync(attempt.command, attempt.args, { stdio: "ignore" });
    if (!result.error && result.status === 0) {
      return true;
    }
    if (result.error && result.error.code === "ENOENT") {
      continue;
    }
  }
  return false;
}

function listTemplatesForFormat(catalog, format) {
  const templates = catalog.templates
    .map((template) => ({
      id: String(template?.id ?? "").trim(),
      label: String(template?.label ?? "").trim()
    }))
    .filter((template) => template.id.length > 0)
    .filter((template) => templateSupportsFormat(catalog.templatesById.get(template.id), format))
    .sort((a, b) => a.id.localeCompare(b.id));

  if (templates.length === 0) {
    console.log(`No templates found for format "${format}".`);
    return;
  }

  console.log(`Templates for format "${format}":`);
  for (const template of templates) {
    if (template.label) {
      console.log(`- ${template.id} (${template.label})`);
    } else {
      console.log(`- ${template.id}`);
    }
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  const needsBuild = options.build || !(await fileReadable(GENERATED_ASSETS_PATH));
  if (needsBuild) {
    console.log("Running build...");
    await runCommand("pnpm", ["run", "build"], { stdio: "inherit" });
  }

  const catalog = await loadTemplateCatalog();
  const allFormats = Object.keys(catalog.formatConfig ?? {});
  if (!allFormats.includes(options.format)) {
    throw new Error(`Unknown format "${options.format}". Available: ${allFormats.join(", ")}`);
  }

  if (options.list) {
    listTemplatesForFormat(catalog, options.format);
    return;
  }

  const templateId = resolveTemplateId(options, catalog);
  const template = catalog.templatesById.get(templateId);
  if (!template) {
    throw new Error(`Template "${templateId}" not found in generated catalog`);
  }

  const previewPayload = buildPreviewPayload(catalog, options);
  const slots = buildSlotValues(template, previewPayload);
  const previewUrl = buildPreviewUrl(options, templateId, previewPayload, slots);
  const headers = authHeaders(options);

  let startedServer = false;
  let devServer = null;

  try {
    const alreadyRunning = await isHealthy(options.baseUrl, headers);
    if (!alreadyRunning) {
      if (options.noStartServer) {
        throw new Error(`No server available at ${options.baseUrl} and --no-start-server was set`);
      }
      console.log(`Starting local dev server at ${options.baseUrl}...`);
      devServer = startDevServer();
      startedServer = true;
      await waitForHealth(options.baseUrl, headers, HEALTH_TIMEOUT_MS, devServer);
    } else {
      console.log(`Using existing server at ${options.baseUrl}`);
    }

    console.log(`Format:    ${options.format}`);
    console.log(`Template:  ${templateId}`);
    console.log(`Preview:   ${previewUrl.toString()}`);

    if (options.open) {
      const opened = openInBrowser(previewUrl.toString());
      if (!opened) {
        console.warn("Could not auto-open browser (install xdg-open/open or open URL manually).");
      }
    }

    if (!startedServer || !devServer) {
      return;
    }

    console.log("Live preview running. Press Ctrl+C to stop.");
    let stopping = false;
    const onSigint = () => {
      if (stopping) return;
      stopping = true;
      void stopProcess(devServer);
    };
    const onSigterm = () => {
      if (stopping) return;
      stopping = true;
      void stopProcess(devServer);
    };
    process.once("SIGINT", onSigint);
    process.once("SIGTERM", onSigterm);

    await new Promise((resolvePromise, rejectPromise) => {
      devServer.once("error", rejectPromise);
      devServer.once("exit", (code, signal) => {
        process.removeListener("SIGINT", onSigint);
        process.removeListener("SIGTERM", onSigterm);
        if (stopping || signal === "SIGINT" || signal === "SIGTERM" || signal === "SIGHUP" || code === 0 || code === 130) {
          resolvePromise(undefined);
          return;
        }
        rejectPromise(new Error(`pnpm run dev exited unexpectedly (code=${String(code)}, signal=${String(signal)})`));
      });
    });
  } finally {
    if (startedServer && devServer && devServer.exitCode === null) {
      await stopProcess(devServer);
    }
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
