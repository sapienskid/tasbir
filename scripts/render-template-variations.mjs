#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import process from "node:process";

const DEFAULT_BASE_URL = "http://127.0.0.1:8787";
const DEFAULT_IMAGE_URL = "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%201200%20900%22%3E%3Crect%20width=%221200%22%20height=%22900%22%20fill=%22%230b0b0b%22/%3E%3C/svg%3E";
const DEFAULT_VARIATION_COUNT = 3;
const DEFAULT_CONCURRENCY = 2;
const HEALTH_TIMEOUT_MS = 60_000;
const HEALTH_POLL_MS = 500;
const MAX_RETRY_ATTEMPTS = 6;
const GENERATED_ASSETS_PATH = resolve(process.cwd(), "src/generated/template-assets.json");
const PRESET_VARIATIONS = [
  {
    id: "default",
    title: "Build a reusable social content system",
    caption: "One source article. Platform-native outputs with consistent structure.",
    heading: "Structure first. Style through tokens.",
    body: "A deterministic template workflow keeps tone, spacing, and hierarchy coherent across every format.",
    brandName: "Tasbir Blog",
    slide: "1",
    total: "5",
    metricValue: "9.8K",
    slotHeadline: "Signal that compounds",
    slotBody: "Design once, repurpose everywhere with a predictable template system.",
    slotTag: "FEATURE",
    slotCta: "Apply framework",
    slotQuote: "Consistency beats random volume.",
    slotByline: "Editorial Desk",
    slotFallbackPrefix: "Core"
  },
  {
    id: "angle-proof",
    title: "Turn one post into a full campaign",
    caption: "Deterministic slot filling improves speed, quality, and output consistency.",
    heading: "Proof over guesswork.",
    body: "Template selection, slot mapping, and export steps are automated while content still feels platform-native.",
    brandName: "Tasbir Labs",
    slide: "2",
    total: "5",
    metricValue: "27%",
    slotHeadline: "Execution with evidence",
    slotBody: "Campaign output becomes measurable when layout and copy constraints are explicit.",
    slotTag: "METHOD",
    slotCta: "Review outputs",
    slotQuote: "Quality improves when decisions are constrained.",
    slotByline: "Growth Ops",
    slotFallbackPrefix: "Proof"
  },
  {
    id: "angle-action",
    title: "Publish faster without losing visual quality",
    caption: "Reliable templates reduce redesign cycles and keep messaging aligned.",
    heading: "Ship, inspect, iterate.",
    body: "Render all formats, compare variations side by side, and promote only the strongest version.",
    brandName: "Tasbir Studio",
    slide: "3",
    total: "5",
    metricValue: "42",
    slotHeadline: "Actionable pipeline",
    slotBody: "Generate previews for every compatible template and save them in one pass.",
    slotTag: "SYSTEM",
    slotCta: "Export all",
    slotQuote: "Repeatable workflows create creative headroom.",
    slotByline: "Content Team",
    slotFallbackPrefix: "Action"
  }
];

function printHelp() {
  console.log(`Render all template variations for every format.

Usage:
  node scripts/render-template-variations.mjs [options]

Options:
  --base-url <url>       Worker URL (default: ${DEFAULT_BASE_URL})
  --out-dir <path>       Output directory (default: renders/all-variations-<timestamp>)
  --image-url <url>      Image URL for preview renders (default: ${DEFAULT_IMAGE_URL})
  --variations <number>  Number of variation profiles per template (default: ${DEFAULT_VARIATION_COUNT})
  --concurrency <number> Parallel screenshot requests (default: ${DEFAULT_CONCURRENCY})
  --api-key <key>        Optional API key when hitting a protected worker
  --build                Run pnpm build before rendering
  --no-start-server      Do not auto-start wrangler (requires an already running server)
  --keep-server          Keep auto-started wrangler running after script exits
  --verbose              Print wrangler logs while rendering
  --help                 Show this help
`);
}

function parseArgs(argv) {
  const timestamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "").replace("T", "-").slice(0, 15);
  const options = {
    baseUrl: DEFAULT_BASE_URL,
    outDir: `renders/all-variations-${timestamp}`,
    imageUrl: DEFAULT_IMAGE_URL,
    variations: DEFAULT_VARIATION_COUNT,
    concurrency: DEFAULT_CONCURRENCY,
    apiKey: process.env.API_KEY?.trim() || "",
    build: false,
    noStartServer: false,
    keepServer: false,
    verbose: false
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
    if (arg === "--build") {
      options.build = true;
      continue;
    }
    if (arg === "--no-start-server") {
      options.noStartServer = true;
      continue;
    }
    if (arg === "--keep-server") {
      options.keepServer = true;
      continue;
    }
    if (arg === "--verbose") {
      options.verbose = true;
      continue;
    }

    if (arg === "--base-url" && next) {
      options.baseUrl = next.trim();
      index += 1;
      continue;
    }
    if (arg.startsWith("--base-url=")) {
      options.baseUrl = arg.slice("--base-url=".length).trim();
      continue;
    }

    if (arg === "--out-dir" && next) {
      options.outDir = next.trim();
      index += 1;
      continue;
    }
    if (arg.startsWith("--out-dir=")) {
      options.outDir = arg.slice("--out-dir=".length).trim();
      continue;
    }

    if (arg === "--image-url" && next) {
      options.imageUrl = next.trim();
      index += 1;
      continue;
    }
    if (arg.startsWith("--image-url=")) {
      options.imageUrl = arg.slice("--image-url=".length).trim();
      continue;
    }

    if (arg === "--variations" && next) {
      options.variations = Number.parseInt(next, 10);
      index += 1;
      continue;
    }
    if (arg.startsWith("--variations=")) {
      options.variations = Number.parseInt(arg.slice("--variations=".length), 10);
      continue;
    }

    if (arg === "--concurrency" && next) {
      options.concurrency = Number.parseInt(next, 10);
      index += 1;
      continue;
    }
    if (arg.startsWith("--concurrency=")) {
      options.concurrency = Number.parseInt(arg.slice("--concurrency=".length), 10);
      continue;
    }

    if (arg === "--api-key" && next) {
      options.apiKey = next.trim();
      index += 1;
      continue;
    }
    if (arg.startsWith("--api-key=")) {
      options.apiKey = arg.slice("--api-key=".length).trim();
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  if (!Number.isInteger(options.variations) || options.variations < 1) {
    throw new Error("--variations must be a positive integer");
  }
  if (!Number.isInteger(options.concurrency) || options.concurrency < 1) {
    throw new Error("--concurrency must be a positive integer");
  }

  const parsedUrl = new URL(options.baseUrl);
  if (parsedUrl.protocol !== "http:") {
    throw new Error("--base-url must use http:// for local wrangler dev");
  }

  return options;
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

function startWranglerServer(options) {
  const parsed = new URL(options.baseUrl);
  const host = parsed.hostname;
  const port = parsed.port || "8787";
  const logTail = [];

  const child = spawn(
    "pnpm",
    [
      "exec",
      "wrangler",
      "dev",
      "--local",
      "--ip",
      host,
      "--port",
      port,
      "--var",
      "API_AUTH_REQUIRE_FOR_PREVIEW:false"
    ],
    {
      cwd: process.cwd(),
      stdio: ["ignore", "pipe", "pipe"]
    }
  );

  const onLog = (chunk) => {
    const text = chunk.toString();
    for (const line of text.split(/\r?\n/)) {
      if (!line.trim()) continue;
      logTail.push(line);
      if (logTail.length > 100) logTail.shift();
      if (options.verbose) {
        process.stderr.write(`[wrangler] ${line}\n`);
      }
    }
  };

  child.stdout?.on("data", onLog);
  child.stderr?.on("data", onLog);

  return { child, logTail };
}

async function stopProcess(child) {
  if (!child || child.exitCode !== null) return;

  child.kill("SIGTERM");
  await Promise.race([
    new Promise((resolvePromise) => child.once("exit", () => resolvePromise(undefined))),
    wait(5_000)
  ]);

  if (child.exitCode === null) {
    child.kill("SIGKILL");
  }
}

async function wait(ms) {
  await new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

function authHeaders(options) {
  if (!options.apiKey) {
    return undefined;
  }
  return { "x-api-key": options.apiKey };
}

async function isHealthy(baseUrl, headers) {
  try {
    const response = await fetch(new URL("/health", baseUrl), {
      headers
    });
    return response.ok;
  } catch (_error) {
    return false;
  }
}

async function waitForHealth(baseUrl, headers, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await isHealthy(baseUrl, headers)) {
      return;
    }
    await wait(HEALTH_POLL_MS);
  }
  throw new Error(`Timed out waiting for ${baseUrl}/health`);
}

function buildVariationProfiles(count) {
  const profiles = [];
  for (let i = 0; i < count; i += 1) {
    if (i < PRESET_VARIATIONS.length) {
      profiles.push(PRESET_VARIATIONS[i]);
      continue;
    }
    const seed = i + 1;
    profiles.push({
      id: `variant-${seed}`,
      title: `Template variation ${seed}`,
      caption: `Programmatic variation ${seed} for side-by-side visual review.`,
      heading: `Variation ${seed}`,
      body: `This generated profile helps compare template flexibility under alternate content inputs.`,
      brandName: "Tasbir Variants",
      slide: String(((seed - 1) % 5) + 1),
      total: "5",
      metricValue: String(seed * 7),
      slotHeadline: `Generated profile ${seed}`,
      slotBody: `Evaluate spacing, hierarchy, and readability with generated content profile ${seed}.`,
      slotTag: "AUTO",
      slotCta: "Inspect output",
      slotQuote: `Variation ${seed} demonstrates deterministic rendering.`,
      slotByline: "Automation",
      slotFallbackPrefix: `Var${seed}`
    });
  }
  return profiles;
}

function humanizeKey(value) {
  return value
    .replaceAll(/[_:-]+/g, " ")
    .replaceAll(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function deriveSlotValue(field, profile, imageUrl, context = {}) {
  const rawKey = String(field?.key ?? "").trim();
  const key = rawKey.toLowerCase();
  const defaultValue = typeof field?.default === "string" ? field.default.trim() : "";
  const type = typeof field?.type === "string" ? field.type : "text";
  const contextFormat = String(context.formatId ?? "").trim();
  const contextTemplate = String(context.templateId ?? "").trim();

  if (key === "illustration_seed") {
    return `${profile.id}:${contextFormat}:${contextTemplate}`.slice(0, 180);
  }

  if (profile.id === "default" && defaultValue.length > 0) {
    return defaultValue;
  }

  if (type === "image_url" || type === "icon_url" || /(image|icon|photo|avatar|logo)/.test(key)) {
    return imageUrl;
  }
  if (type === "number" || /(count|number|value|metric|score|percent|pct|slide|total|index)/.test(key)) {
    return profile.metricValue;
  }
  if (/(visible|enabled|show|hide)/.test(key)) {
    return defaultValue || "1";
  }
  if (/(headline|title|heading|hook|claim|thesis)/.test(key)) {
    return profile.slotHeadline;
  }
  if (/(body|description|insight|detail|narrative|summary|copy|text)/.test(key)) {
    return profile.slotBody;
  }
  if (/(caption|subtitle|subhead|dek)/.test(key)) {
    return profile.caption;
  }
  if (/(tag|label|kicker|badge|meta|category|section)/.test(key)) {
    return profile.slotTag;
  }
  if (/(cta|action|button|prompt)/.test(key)) {
    return profile.slotCta;
  }
  if (/quote/.test(key)) {
    return profile.slotQuote;
  }
  if (/(author|name|speaker|source|brand)/.test(key)) {
    return profile.slotByline;
  }
  if (defaultValue.length > 0) {
    return defaultValue;
  }
  return `${profile.slotFallbackPrefix} ${humanizeKey(rawKey || "content")}`.slice(0, 110);
}

function sanitizeFilePart(value) {
  return value.replaceAll(/[^A-Za-z0-9._-]+/g, "_").replaceAll(/^_+|_+$/g, "");
}

function buildRenderTasks(catalog, options, profiles) {
  const tasks = [];
  const templateById = new Map((catalog.templates ?? []).map((template) => [template.id, template]));

  for (const format of catalog.formats ?? []) {
    const formatId = format.id;
    const templateIds = Array.isArray(catalog.templates_by_format?.[formatId])
      ? catalog.templates_by_format[formatId]
      : [];

    for (const templateId of templateIds) {
      const template = templateById.get(templateId) ?? { id: templateId, version: "unknown", fields: [] };
      const fields = Array.isArray(template.fields) ? template.fields : [];
      for (const profile of profiles) {
        const slots = {};
        for (const field of fields) {
          const slotKey = String(field?.key ?? "").trim();
          if (!slotKey) continue;
          slots[slotKey] = deriveSlotValue(field, profile, options.imageUrl, {
            formatId,
            templateId
          });
        }

        tasks.push({
          formatId,
          templateId,
          templateVersion: String(template.version ?? "unknown"),
          profile,
          slots
        });
      }
    }
  }

  return tasks;
}

function templateSupportsFormat(template, formatId) {
  const single = typeof template?.format === "string" ? template.format.trim() : "";
  if (single) {
    return single === formatId;
  }
  const formats = Array.isArray(template?.formats)
    ? template.formats.map((item) => (typeof item === "string" ? item.trim() : "")).filter(Boolean)
    : [];
  if (formats.length > 0) {
    return formats.includes(formatId);
  }
  return true;
}

async function loadTemplateCatalogFromGeneratedAssets() {
  const raw = await readFile(GENERATED_ASSETS_PATH, "utf8");
  const generated = JSON.parse(raw);
  const pipelineConfig = generated?.pipeline_config ?? {};
  const templates = Array.isArray(pipelineConfig.templates) ? pipelineConfig.templates : [];
  const formats = Object.keys(pipelineConfig.formats ?? {}).map((id) => ({ id }));
  const templatesByFormat = {};

  for (const format of formats) {
    templatesByFormat[format.id] = templates
      .filter((template) => templateSupportsFormat(template, format.id))
      .map((template) => String(template.id ?? "").trim())
      .filter(Boolean);
  }

  return {
    formats,
    templates: templates.map((template) => ({
      ...template,
      version: String(template?.version ?? template?.file ?? template?.id ?? "unknown")
    })),
    templates_by_format: templatesByFormat
  };
}

async function runWithConcurrency(tasks, concurrency, worker) {
  let cursor = 0;
  let completed = 0;
  let success = 0;
  const failures = [];

  const workers = Array.from({ length: Math.min(concurrency, tasks.length) }, async () => {
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= tasks.length) return;

      try {
        await worker(tasks[index], index, tasks.length);
        success += 1;
      } catch (error) {
        failures.push({
          task: tasks[index],
          error: error instanceof Error ? error.message : String(error)
        });
      } finally {
        completed += 1;
      }
    }
  });

  await Promise.all(workers);
  return { completed, success, failures };
}

async function renderTask(task, options, outputRoot, headers, index, total) {
  const url = new URL("/preview/screenshot", options.baseUrl);
  url.searchParams.set("format", task.formatId);
  url.searchParams.set("templateId", task.templateId);
  url.searchParams.set("title", task.profile.title);
  url.searchParams.set("caption", task.profile.caption);
  url.searchParams.set("heading", task.profile.heading);
  url.searchParams.set("body", task.profile.body);
  url.searchParams.set("brandName", task.profile.brandName);
  url.searchParams.set("imageUrl", options.imageUrl);
  url.searchParams.set("slide", task.profile.slide);
  url.searchParams.set("total", task.profile.total);

  for (const [slotKey, slotValue] of Object.entries(task.slots)) {
    if (!slotValue) continue;
    url.searchParams.set(`slot.${slotKey}`, slotValue);
  }

  let response = null;
  for (let attempt = 1; attempt <= MAX_RETRY_ATTEMPTS; attempt += 1) {
    response = await fetch(url, { headers });
    if (response.ok) {
      break;
    }

    const bodyPreview = (await response.text()).slice(0, 200).replaceAll(/\s+/g, " ").trim();
    const retryable = response.status === 429 || response.status === 408 || response.status >= 500;
    if (!retryable || attempt === MAX_RETRY_ATTEMPTS) {
      throw new Error(`HTTP ${response.status} ${response.statusText} :: ${bodyPreview}`);
    }

    const retryAfterHeader = response.headers.get("retry-after");
    const retryAfterSeconds = retryAfterHeader ? Number.parseFloat(retryAfterHeader) : Number.NaN;
    const baseDelay = Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0
      ? retryAfterSeconds * 1000
      : 450 * (2 ** (attempt - 1));
    const jitter = Math.floor(Math.random() * 150);
    const waitMs = Math.min(6_000, baseDelay + jitter);

    console.warn(
      `Retry ${attempt}/${MAX_RETRY_ATTEMPTS - 1} for ${task.formatId} :: ${task.templateId} :: ${task.profile.id} after ${Math.round(waitMs)}ms`
    );
    await wait(waitMs);
  }

  if (!response || !response.ok) {
    throw new Error("Failed to render screenshot after retry attempts");
  }

  const png = Buffer.from(await response.arrayBuffer());
  const fileName = `${sanitizeFilePart(task.templateId)}--${sanitizeFilePart(task.profile.id)}--${sanitizeFilePart(task.templateVersion.slice(0, 8))}.png`;
  const filePath = join(outputRoot, task.formatId, fileName);
  await mkdir(join(outputRoot, task.formatId), { recursive: true });
  await writeFile(filePath, png);

  console.log(
    `[${String(index + 1).padStart(4, "0")}/${String(total).padStart(4, "0")}] ${task.formatId} :: ${task.templateId} :: ${task.profile.id} -> ${filePath}`
  );
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  const outputRoot = resolve(process.cwd(), options.outDir);
  const headers = authHeaders(options);
  const startedAt = Date.now();

  let startedServer = false;
  let serverProcess = null;
  let serverLogTail = [];

  try {
    if (options.build) {
      console.log("Running build before render...");
      await runCommand("pnpm", ["run", "build"], { stdio: "inherit" });
    }

    const alreadyRunning = await isHealthy(options.baseUrl, headers);
    if (!alreadyRunning) {
      if (options.noStartServer) {
        throw new Error(`No server available at ${options.baseUrl} and --no-start-server was set`);
      }

      console.log(`Starting local worker at ${options.baseUrl}...`);
      const server = startWranglerServer(options);
      startedServer = true;
      serverProcess = server.child;
      serverLogTail = server.logTail;
      await waitForHealth(options.baseUrl, headers, HEALTH_TIMEOUT_MS);
    } else {
      console.log(`Using existing worker at ${options.baseUrl}`);
    }

    console.log("Loading template catalog from generated assets...");
    const catalog = await loadTemplateCatalogFromGeneratedAssets();

    const profiles = buildVariationProfiles(options.variations);
    const tasks = buildRenderTasks(catalog, options, profiles);
    if (tasks.length === 0) {
      throw new Error("No compatible format/template pairs found in template catalog");
    }

    console.log(`Rendering ${tasks.length} screenshots (${profiles.length} variation profile(s) per template)...`);
    await mkdir(outputRoot, { recursive: true });

    const summary = await runWithConcurrency(tasks, options.concurrency, (task, index, total) =>
      renderTask(task, options, outputRoot, headers, index, total)
    );

    console.log("");
    console.log("Render summary");
    console.log(`- Total tasks: ${summary.completed}`);
    console.log(`- Success: ${summary.success}`);
    console.log(`- Failed: ${summary.failures.length}`);
    console.log(`- Output: ${outputRoot}`);
    console.log(`- Duration: ${((Date.now() - startedAt) / 1000).toFixed(1)}s`);

    if (summary.failures.length > 0) {
      console.log("");
      console.log("Failures:");
      for (const failure of summary.failures.slice(0, 20)) {
        console.log(
          `- ${failure.task.formatId} :: ${failure.task.templateId} :: ${failure.task.profile.id} :: ${failure.error}`
        );
      }
      if (summary.failures.length > 20) {
        console.log(`- ...and ${summary.failures.length - 20} more`);
      }
      process.exitCode = 1;
    }
  } finally {
    if (startedServer && serverProcess && !options.keepServer) {
      await stopProcess(serverProcess);
    }

    if (startedServer && process.exitCode && serverLogTail.length > 0) {
      console.error("");
      console.error("Wrangler log tail:");
      for (const line of serverLogTail.slice(-30)) {
        console.error(line);
      }
    }
  }
}

try {
  await main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
