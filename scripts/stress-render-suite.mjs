#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import process from "node:process";

const DEFAULT_BASE_URL = "http://127.0.0.1:8787";
const DEFAULT_IMAGE_URL =
  "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%201200%20900%22%3E%3Crect%20width=%221200%22%20height=%22900%22%20fill=%22%230a0a0a%22/%3E%3C/svg%3E";
const DEFAULT_CONCURRENCY = 2;
const HEALTH_TIMEOUT_MS = 60_000;
const HEALTH_POLL_MS = 500;
const MAX_RETRY_ATTEMPTS = 6;
const GENERATED_ASSETS_PATH = resolve(process.cwd(), "src/generated/template-assets.json");

const LOREM_WORDS = [
  "lorem",
  "ipsum",
  "dolor",
  "sit",
  "amet",
  "consectetur",
  "adipiscing",
  "elit",
  "sed",
  "do",
  "eiusmod",
  "tempor",
  "incididunt",
  "ut",
  "labore",
  "et",
  "dolore",
  "magna",
  "aliqua",
  "ut",
  "enim",
  "ad",
  "minim",
  "veniam",
  "quis",
  "nostrud",
  "exercitation",
  "ullamco",
  "laboris",
  "nisi",
  "ut",
  "aliquip",
  "ex",
  "ea",
  "commodo",
  "consequat"
];

function printHelp() {
  console.log(`Render stress-suite screenshots for every template and platform.

Usage:
  node scripts/stress-render-suite.mjs [options]

Options:
  --base-url <url>        Worker URL (default: ${DEFAULT_BASE_URL})
  --out-dir <path>        Output directory (default: renders/stress-suite-<timestamp>)
  --image-url <url>       Image URL for preview renders
  --api-key <key>         Optional API key when preview auth is enabled
  --concurrency <number>  Parallel screenshot requests (default: ${DEFAULT_CONCURRENCY})
  --formats <csv>         Optional format filter (example: instagram-square,twitter-card)
  --cases <csv>           Optional case filter (example: plain-short,markdown-rich)
  --max-tasks <number>    Optional cap for quick smoke runs
  --build                 Run pnpm build before rendering
  --no-start-server       Do not auto-start wrangler
  --keep-server           Keep auto-started wrangler running after script exits
  --verbose               Print wrangler logs while rendering
  --help                  Show this help
`);
}

function parseArgs(argv) {
  const timestamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "").replace("T", "-").slice(0, 15);
  const options = {
    baseUrl: DEFAULT_BASE_URL,
    outDir: `renders/stress-suite-${timestamp}`,
    imageUrl: DEFAULT_IMAGE_URL,
    apiKey: process.env.API_KEY?.trim() || "",
    concurrency: DEFAULT_CONCURRENCY,
    formats: [],
    cases: [],
    maxTasks: 0,
    build: false,
    noStartServer: false,
    keepServer: false,
    verbose: false,
    help: false
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];

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

    if (arg === "--api-key" && next) {
      options.apiKey = next.trim();
      index += 1;
      continue;
    }
    if (arg.startsWith("--api-key=")) {
      options.apiKey = arg.slice("--api-key=".length).trim();
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

    if (arg === "--formats" && next) {
      options.formats = splitCsv(next);
      index += 1;
      continue;
    }
    if (arg.startsWith("--formats=")) {
      options.formats = splitCsv(arg.slice("--formats=".length));
      continue;
    }

    if (arg === "--cases" && next) {
      options.cases = splitCsv(next);
      index += 1;
      continue;
    }
    if (arg.startsWith("--cases=")) {
      options.cases = splitCsv(arg.slice("--cases=".length));
      continue;
    }

    if (arg === "--max-tasks" && next) {
      options.maxTasks = Number.parseInt(next, 10);
      index += 1;
      continue;
    }
    if (arg.startsWith("--max-tasks=")) {
      options.maxTasks = Number.parseInt(arg.slice("--max-tasks=".length), 10);
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  if (!Number.isInteger(options.concurrency) || options.concurrency < 1) {
    throw new Error("--concurrency must be a positive integer");
  }
  if (options.maxTasks && (!Number.isInteger(options.maxTasks) || options.maxTasks < 1)) {
    throw new Error("--max-tasks must be a positive integer");
  }

  const parsed = new URL(options.baseUrl);
  if (parsed.protocol !== "http:") {
    throw new Error("--base-url must use http:// for local wrangler dev");
  }

  return options;
}

function splitCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
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
    const lines = text.split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      logTail.push(line);
      if (logTail.length > 500) logTail.shift();
      if (options.verbose) {
        console.log(`[wrangler] ${line}`);
      }
    }
  };

  child.stdout.on("data", onLog);
  child.stderr.on("data", onLog);

  return { child, logTail };
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

function wait(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

function authHeaders(options) {
  if (!options.apiKey) {
    return {};
  }
  return {
    "x-api-key": options.apiKey
  };
}

async function isHealthy(baseUrl, headers) {
  try {
    const response = await fetch(new URL("/health", baseUrl), { headers });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForHealth(baseUrl, headers, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isHealthy(baseUrl, headers)) {
      return;
    }
    await wait(HEALTH_POLL_MS);
  }
  throw new Error(`Timed out waiting for worker at ${baseUrl}`);
}

function sanitizeFilePart(value) {
  return value.replaceAll(/[^A-Za-z0-9._-]+/g, "_").replaceAll(/^_+|_+$/g, "");
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

async function loadTemplateCatalogFromGeneratedAssets(formatFilter) {
  const raw = await readFile(GENERATED_ASSETS_PATH, "utf8");
  const generated = JSON.parse(raw);
  const pipelineConfig = generated?.pipeline_config ?? {};
  const templates = Array.isArray(pipelineConfig.templates) ? pipelineConfig.templates : [];
  const availableFormats = Object.keys(pipelineConfig.formats ?? {});
  const activeFormats = formatFilter.length > 0
    ? availableFormats.filter((formatId) => formatFilter.includes(formatId))
    : availableFormats;
  const formats = activeFormats.map((id) => ({ id }));
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

function loremWords(wordCount, seed = 0) {
  const count = Math.max(1, Math.floor(wordCount));
  const words = [];
  for (let index = 0; index < count; index += 1) {
    words.push(LOREM_WORDS[(seed + index) % LOREM_WORDS.length]);
  }
  return words.join(" ");
}

function loremSentence(wordCount, seed = 0) {
  const text = loremWords(wordCount, seed).trim();
  return `${text.slice(0, 1).toUpperCase()}${text.slice(1)}.`;
}

function loremParagraph(sentenceCount, wordsPerSentence, seed = 0) {
  const sentences = [];
  for (let index = 0; index < sentenceCount; index += 1) {
    sentences.push(loremSentence(wordsPerSentence, seed + index * 5));
  }
  return sentences.join(" ");
}

function truncateForQuery(text, maxChars = 220) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxChars) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`;
}

function buildStressCases(filterCaseIds) {
  const catalog = [
    {
      id: "plain-short",
      label: "Plain short",
      title: "Short copy sanity check",
      caption: loremSentence(14, 1),
      heading: "Short heading",
      body: loremSentence(18, 7),
      brandName: "Stress Lab",
      slotHeadline: "Concise headline",
      slotBody: loremSentence(16, 12),
      slotTag: "SHORT",
      slotCta: "Read",
      slotQuote: loremSentence(12, 17),
      slotByline: "QA Team",
      metricValue: "12",
      slide: "1",
      total: "5",
      slotFallbackPrefix: "Short"
    },
    {
      id: "plain-medium",
      label: "Plain medium",
      title: truncateForQuery(loremSentence(12, 21), 80),
      caption: truncateForQuery(loremParagraph(3, 20, 23), 320),
      heading: truncateForQuery(loremSentence(7, 29), 90),
      body: truncateForQuery(loremParagraph(2, 28, 31), 320),
      brandName: "Stress Lab",
      slotHeadline: truncateForQuery(loremSentence(8, 37), 140),
      slotBody: truncateForQuery(loremParagraph(2, 22, 41), 340),
      slotTag: "MEDIUM",
      slotCta: "Learn more",
      slotQuote: truncateForQuery(loremSentence(20, 47), 200),
      slotByline: "Growth Team",
      metricValue: "240",
      slide: "2",
      total: "7",
      slotFallbackPrefix: "Medium"
    },
    {
      id: "plain-long",
      label: "Plain long",
      title: truncateForQuery(loremSentence(18, 51), 160),
      caption: truncateForQuery(loremParagraph(4, 32, 53), 480),
      heading: truncateForQuery(loremSentence(12, 59), 160),
      body: truncateForQuery(loremParagraph(4, 30, 61), 520),
      brandName: "Stress Lab",
      slotHeadline: truncateForQuery(loremSentence(14, 67), 200),
      slotBody: truncateForQuery(loremParagraph(3, 30, 71), 520),
      slotTag: "LONG",
      slotCta: "Start now",
      slotQuote: truncateForQuery(loremParagraph(2, 26, 79), 420),
      slotByline: "Editorial QA",
      metricValue: "9.8K",
      slide: "3",
      total: "10",
      slotFallbackPrefix: "Long"
    },
    {
      id: "markdown-rich",
      label: "Markdown rich",
      title: "## Markdown stress heading",
      caption: truncateForQuery(
        "### Hook line\n- Bullet one explains context\n- Bullet two adds detail\n- Bullet three closes with CTA\n[Reference](https://example.com)",
        460
      ),
      heading: "**Bold heading** with _emphasis_",
      body: truncateForQuery(
        "Here is `inline code`, plus a quote:\n> Keep constraints explicit.\n\n1. Plan\n2. Draft\n3. Publish",
        520
      ),
      brandName: "Stress Lab",
      slotHeadline: "### Slot markdown headline",
      slotBody: truncateForQuery("- item alpha\n- item beta\n- item gamma", 240),
      slotTag: "`MARKDOWN`",
      slotCta: "[Open checklist](https://example.com/checklist)",
      slotQuote: "> Deterministic systems reduce surprises.",
      slotByline: "_Ops Team_",
      metricValue: "88",
      slide: "1",
      total: "6",
      slotFallbackPrefix: "Markdown"
    },
    {
      id: "math-heavy",
      label: "Math heavy",
      title: "Math stress: e^(i*pi)+1=0",
      caption: truncateForQuery(
        "Inline math: $a^2+b^2=c^2$. Block math: $$\\int_0^1 x^2 dx = 1/3$$ with explanatory sentence.",
        460
      ),
      heading: "KPI model y = m*x + b",
      body: truncateForQuery(
        "We test formulas: $\\sigma = \\sqrt{\\sum(x-\\mu)^2/N}$ and $$f(x)=\\frac{1}{1+e^{-x}}$$ for render safety.",
        520
      ),
      brandName: "Stress Lab",
      slotHeadline: "Formula coverage",
      slotBody: "Evaluate: $$\\sum_{i=1}^{n} i = n(n+1)/2$$",
      slotTag: "MATH",
      slotCta: "Validate model",
      slotQuote: "Constraint: $max_{fit}(text)$",
      slotByline: "Data Team",
      metricValue: "3.1415",
      slide: "4",
      total: "8",
      slotFallbackPrefix: "Math"
    },
    {
      id: "diagram-mermaid",
      label: "Mermaid diagram",
      title: "Diagram syntax stress",
      caption: truncateForQuery(
        "```mermaid\ngraph TD\nA[Input]-->B[Plan]\nB-->C[Render]\nC-->D[Review]\n```",
        460
      ),
      heading: "Flow graph validation",
      body: truncateForQuery(
        "```mermaid\nsequenceDiagram\nUser->>Agent: provide content\nAgent->>Renderer: choose template\nRenderer-->>User: output assets\n```",
        520
      ),
      brandName: "Stress Lab",
      slotHeadline: "Mermaid payload",
      slotBody: "```mermaid\ngraph LR\nX-->Y\nY-->Z\n```",
      slotTag: "DIAGRAM",
      slotCta: "Inspect graph",
      slotQuote: "Graph nodes should not break layout.",
      slotByline: "Systems Team",
      metricValue: "7",
      slide: "2",
      total: "4",
      slotFallbackPrefix: "Diagram"
    },
    {
      id: "mixed-stress",
      label: "Mixed stress",
      title: truncateForQuery("Mixed syntax stress case for markdown + math + diagrams", 170),
      caption: truncateForQuery(
        `${loremSentence(16, 83)} #stress #render #layout **bold** $x+y=z$`,
        420
      ),
      heading: "Mixed channel payload",
      body: truncateForQuery(
        `${loremParagraph(2, 20, 89)}\n\n- bullet a\n- bullet b\n\n$$\\alpha+\\beta=\\gamma$$\n\n\`\`\`mermaid\ngraph TD\nA-->B\n\`\`\``,
        560
      ),
      brandName: "Stress Lab",
      slotHeadline: "Mixed slot pressure test",
      slotBody: truncateForQuery(`${loremSentence(22, 101)} #hash #tags`, 260),
      slotTag: "MIXED",
      slotCta: "Run checklist",
      slotQuote: truncateForQuery(`${loremSentence(12, 107)} $f(x)$`, 220),
      slotByline: "QA Ops",
      metricValue: "4200",
      slide: "5",
      total: "9",
      slotFallbackPrefix: "Mixed"
    }
  ];

  if (!filterCaseIds || filterCaseIds.length === 0) {
    return catalog;
  }

  const selected = catalog.filter((item) => filterCaseIds.includes(item.id));
  const missing = filterCaseIds.filter((id) => !selected.some((item) => item.id === id));
  if (missing.length > 0) {
    throw new Error(`Unknown case id(s): ${missing.join(", ")}`);
  }
  return selected;
}

function humanizeKey(key) {
  return String(key)
    .replaceAll(/[_-]+/g, " ")
    .replaceAll(/\s+/g, " ")
    .trim();
}

function deriveSlotValue(field, stressCase, imageUrl) {
  const rawKey = String(field?.key ?? "").trim();
  const key = rawKey.toLowerCase();
  const defaultValue = typeof field?.default === "string" ? field.default.trim() : "";
  const type = typeof field?.type === "string" ? field.type : "text";

  if (type === "image_url" || type === "icon_url" || /(image|icon|photo|avatar|logo)/.test(key)) {
    return imageUrl;
  }
  if (type === "number" || /(count|number|value|metric|score|percent|pct|slide|total|index)/.test(key)) {
    return stressCase.metricValue;
  }
  if (/(visible|enabled|show|hide)/.test(key)) {
    return defaultValue || "1";
  }
  if (/(headline|title|heading|hook|claim|thesis)/.test(key)) {
    return stressCase.slotHeadline;
  }
  if (/(body|description|insight|detail|narrative|summary|copy|text)/.test(key)) {
    return stressCase.slotBody;
  }
  if (/(caption|subtitle|subhead|dek)/.test(key)) {
    return stressCase.caption;
  }
  if (/(tag|label|kicker|badge|meta|category|section)/.test(key)) {
    return stressCase.slotTag;
  }
  if (/(cta|action|button|prompt)/.test(key)) {
    return stressCase.slotCta;
  }
  if (/quote/.test(key)) {
    return stressCase.slotQuote;
  }
  if (/(author|name|speaker|source|brand)/.test(key)) {
    return stressCase.slotByline;
  }
  if (defaultValue.length > 0) {
    return defaultValue;
  }
  return `${stressCase.slotFallbackPrefix} ${humanizeKey(rawKey || "content")}`.slice(0, 120);
}

function buildRenderTasks(catalog, options, stressCases) {
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

      for (const stressCase of stressCases) {
        const slots = {};
        for (const field of fields) {
          const slotKey = String(field?.key ?? "").trim();
          if (!slotKey) continue;
          slots[slotKey] = truncateForQuery(deriveSlotValue(field, stressCase, options.imageUrl), 240);
        }
        tasks.push({
          formatId,
          templateId,
          templateVersion: String(template.version ?? "unknown"),
          caseId: stressCase.id,
          caseLabel: stressCase.label,
          payload: stressCase,
          slots
        });
      }
    }
  }

  return options.maxTasks > 0 ? tasks.slice(0, options.maxTasks) : tasks;
}

async function renderTask(task, options, outputRoot, headers, index, total) {
  const url = new URL("/preview/screenshot", options.baseUrl);
  url.searchParams.set("format", task.formatId);
  url.searchParams.set("templateId", task.templateId);
  url.searchParams.set("title", task.payload.title);
  url.searchParams.set("caption", task.payload.caption);
  url.searchParams.set("heading", task.payload.heading);
  url.searchParams.set("body", task.payload.body);
  url.searchParams.set("brandName", task.payload.brandName);
  url.searchParams.set("imageUrl", options.imageUrl);
  url.searchParams.set("slide", task.payload.slide);
  url.searchParams.set("total", task.payload.total);

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

    const bodyPreview = (await response.text()).slice(0, 220).replaceAll(/\s+/g, " ").trim();
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
    await wait(waitMs);
  }

  if (!response || !response.ok) {
    throw new Error("Failed to render screenshot after retry attempts");
  }

  const png = Buffer.from(await response.arrayBuffer());
  const fileName = [
    sanitizeFilePart(task.templateId),
    sanitizeFilePart(task.caseId),
    sanitizeFilePart(task.templateVersion.slice(0, 8))
  ].join("--") + ".png";
  const filePath = join(outputRoot, task.formatId, task.caseId, fileName);
  await mkdir(join(outputRoot, task.formatId, task.caseId), { recursive: true });
  await writeFile(filePath, png);

  console.log(
    `[${String(index + 1).padStart(4, "0")}/${String(total).padStart(4, "0")}] ${task.formatId} :: ${task.templateId} :: ${task.caseId} -> ${filePath}`
  );
  return filePath;
}

async function runWithConcurrency(tasks, concurrency, worker) {
  let cursor = 0;
  let completed = 0;
  let success = 0;
  const failures = [];
  const rendered = [];

  const workers = Array.from({ length: Math.min(concurrency, tasks.length) }, async () => {
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= tasks.length) return;

      try {
        const filePath = await worker(tasks[index], index, tasks.length);
        rendered.push({
          task: tasks[index],
          filePath
        });
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
  return { completed, success, failures, rendered };
}

function buildGalleryIndexHtml(args) {
  const entries = args.entries ?? [];
  const failures = args.failures ?? [];
  const summary = args.summary ?? {};
  const payloadJson = JSON.stringify({ entries, failures, summary }).replace(/</g, "\\u003c");

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Stress Render Gallery</title>
  <style>
    :root {
      --bg: #0f1117;
      --surface: #161a24;
      --surface-2: #1e2432;
      --text: #e7ebf3;
      --muted: #9ba8c7;
      --accent: #5ea0ff;
      --border: #2a3348;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Roboto, sans-serif;
      background: radial-gradient(1200px 600px at 20% -10%, #1b2440, transparent), var(--bg);
      color: var(--text);
    }
    .wrap {
      max-width: 1600px;
      margin: 0 auto;
      padding: 24px;
    }
    .header {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 20px;
    }
    .title {
      margin: 0;
      font-size: 1.4rem;
    }
    .sub {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .stats {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .chip {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 0.82rem;
      color: var(--muted);
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .control {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 8px 10px;
    }
    .control label {
      display: block;
      color: var(--muted);
      font-size: 0.75rem;
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .control input,
    .control select {
      width: 100%;
      background: var(--surface-2);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      padding: 8px;
      font-size: 0.9rem;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow: hidden;
      cursor: pointer;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: #3b4a6a;
    }
    .card img {
      width: 100%;
      aspect-ratio: 1/1;
      object-fit: cover;
      background: #080a10;
      display: block;
    }
    .meta {
      padding: 10px;
      display: grid;
      gap: 4px;
    }
    .meta strong {
      font-size: 0.86rem;
      line-height: 1.2;
    }
    .meta span {
      color: var(--muted);
      font-size: 0.76rem;
      line-height: 1.2;
    }
    .empty {
      margin: 20px 0;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .failures {
      margin-top: 26px;
      background: #261617;
      border: 1px solid #513032;
      border-radius: 12px;
      padding: 12px;
    }
    .failures h2 {
      margin: 0 0 8px;
      font-size: 0.95rem;
      color: #ffb3b8;
    }
    .failures ul {
      margin: 0;
      padding-left: 16px;
      color: #f5c8cc;
      font-size: 0.8rem;
      display: grid;
      gap: 6px;
      max-height: 220px;
      overflow: auto;
    }
    .modal {
      position: fixed;
      inset: 0;
      background: rgba(6, 8, 14, 0.85);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 9999;
    }
    .modal.open { display: flex; }
    .viewer {
      width: min(980px, 100%);
      background: #111522;
      border: 1px solid #2f3a56;
      border-radius: 16px;
      overflow: hidden;
      display: grid;
      grid-template-columns: minmax(220px, 58%) minmax(220px, 42%);
      max-height: 90vh;
    }
    .viewer-media {
      background: #05070d;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 280px;
    }
    .viewer-media img {
      max-width: 100%;
      max-height: 90vh;
      object-fit: contain;
      display: block;
    }
    .viewer-info {
      padding: 16px;
      overflow: auto;
      border-left: 1px solid #2f3a56;
    }
    .viewer-info h3 {
      margin: 0 0 10px;
      font-size: 1rem;
    }
    .viewer-info p {
      margin: 0 0 6px;
      font-size: 0.88rem;
      color: var(--muted);
    }
    .close {
      position: absolute;
      top: 18px;
      right: 22px;
      background: transparent;
      border: 0;
      color: #e9eefc;
      font-size: 1.8rem;
      cursor: pointer;
      line-height: 1;
    }
    @media (max-width: 860px) {
      .viewer {
        grid-template-columns: 1fr;
        max-height: 94vh;
      }
      .viewer-info {
        border-left: 0;
        border-top: 1px solid #2f3a56;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <div>
        <h1 class="title">Stress Render Gallery</h1>
        <p class="sub">Grid + Instagram-style click preview for rendered template stress cases.</p>
      </div>
      <div class="stats" id="stats"></div>
    </div>
    <div class="controls">
      <div class="control">
        <label for="search">Search</label>
        <input id="search" type="text" placeholder="template id / case / format" />
      </div>
      <div class="control">
        <label for="format">Format</label>
        <select id="format"></select>
      </div>
      <div class="control">
        <label for="case">Case</label>
        <select id="case"></select>
      </div>
      <div class="control">
        <label for="template">Template</label>
        <select id="template"></select>
      </div>
    </div>
    <div id="count" class="empty"></div>
    <div id="grid" class="grid"></div>
    <div id="failures" class="failures" style="display:none;">
      <h2>Failures</h2>
      <ul id="failure-list"></ul>
    </div>
  </div>

  <div id="modal" class="modal" aria-hidden="true">
    <button class="close" id="close" aria-label="Close">×</button>
    <div class="viewer">
      <div class="viewer-media"><img id="viewer-image" alt="" /></div>
      <div class="viewer-info">
        <h3 id="viewer-title"></h3>
        <p id="viewer-format"></p>
        <p id="viewer-template"></p>
        <p id="viewer-case"></p>
        <p id="viewer-file"></p>
      </div>
    </div>
  </div>

  <script>
    const payload = ${payloadJson};
    const entries = payload.entries || [];
    const failures = payload.failures || [];
    const summary = payload.summary || {};

    const stats = document.getElementById("stats");
    const grid = document.getElementById("grid");
    const count = document.getElementById("count");
    const search = document.getElementById("search");
    const formatSelect = document.getElementById("format");
    const caseSelect = document.getElementById("case");
    const templateSelect = document.getElementById("template");
    const failureBox = document.getElementById("failures");
    const failureList = document.getElementById("failure-list");

    const modal = document.getElementById("modal");
    const closeBtn = document.getElementById("close");
    const viewerImage = document.getElementById("viewer-image");
    const viewerTitle = document.getElementById("viewer-title");
    const viewerFormat = document.getElementById("viewer-format");
    const viewerTemplate = document.getElementById("viewer-template");
    const viewerCase = document.getElementById("viewer-case");
    const viewerFile = document.getElementById("viewer-file");

    function chip(label, value) {
      const el = document.createElement("div");
      el.className = "chip";
      el.textContent = label + ": " + value;
      return el;
    }

    stats.appendChild(chip("Tasks", summary.totals?.tasks ?? entries.length));
    stats.appendChild(chip("Passed", summary.totals?.passed ?? entries.length));
    stats.appendChild(chip("Failed", summary.totals?.failed ?? failures.length));
    stats.appendChild(chip("Duration", (summary.duration_seconds ?? 0) + "s"));

    function uniqueValues(items, key) {
      return [...new Set(items.map((item) => item[key]).filter(Boolean))].sort();
    }

    function fillSelect(select, values, label) {
      const all = document.createElement("option");
      all.value = "";
      all.textContent = "All " + label;
      select.appendChild(all);
      for (const value of values) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }
    }

    fillSelect(formatSelect, uniqueValues(entries, "formatId"), "formats");
    fillSelect(caseSelect, uniqueValues(entries, "caseId"), "cases");
    fillSelect(templateSelect, uniqueValues(entries, "templateId"), "templates");

    function matches(entry) {
      const q = search.value.trim().toLowerCase();
      if (q) {
        const haystack = [entry.templateId, entry.caseId, entry.caseLabel, entry.formatId, entry.file].join(" ").toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      if (formatSelect.value && entry.formatId !== formatSelect.value) return false;
      if (caseSelect.value && entry.caseId !== caseSelect.value) return false;
      if (templateSelect.value && entry.templateId !== templateSelect.value) return false;
      return true;
    }

    function openViewer(entry) {
      viewerImage.src = entry.file;
      viewerImage.alt = entry.templateId + " " + entry.caseId;
      viewerTitle.textContent = entry.caseLabel || entry.caseId;
      viewerFormat.textContent = "Format: " + entry.formatId;
      viewerTemplate.textContent = "Template: " + entry.templateId;
      viewerCase.textContent = "Case ID: " + entry.caseId;
      viewerFile.textContent = "File: " + entry.file;
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
    }

    function closeViewer() {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      viewerImage.src = "";
    }

    function renderGrid() {
      const visible = entries.filter(matches);
      grid.innerHTML = "";
      count.textContent = visible.length + " image(s) visible";

      if (visible.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No images match current filters.";
        grid.appendChild(empty);
        return;
      }

      for (const entry of visible) {
        const card = document.createElement("button");
        card.className = "card";
        card.type = "button";
        card.innerHTML = [
          '<img loading="lazy" src="' + entry.file + '" alt="' + entry.templateId + " " + entry.caseId + '">',
          '<div class="meta">',
          "<strong>" + entry.templateId + "</strong>",
          "<span>" + entry.formatId + "</span>",
          "<span>" + (entry.caseLabel || entry.caseId) + "</span>",
          "</div>"
        ].join("");
        card.addEventListener("click", () => openViewer(entry));
        grid.appendChild(card);
      }
    }

    search.addEventListener("input", renderGrid);
    formatSelect.addEventListener("change", renderGrid);
    caseSelect.addEventListener("change", renderGrid);
    templateSelect.addEventListener("change", renderGrid);

    closeBtn.addEventListener("click", closeViewer);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeViewer();
    });
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeViewer();
    });

    if (failures.length > 0) {
      failureBox.style.display = "block";
      for (const failure of failures.slice(0, 200)) {
        const li = document.createElement("li");
        li.textContent = [
          failure.task?.formatId || "unknown-format",
          failure.task?.templateId || "unknown-template",
          failure.task?.caseId || "unknown-case",
          failure.error || "unknown-error"
        ].join(" :: ");
        failureList.appendChild(li);
      }
    }

    renderGrid();
  </script>
</body>
</html>`;
}

function summarizeFailures(tasks, failures, startedAt, outputRoot) {
  const byCase = {};
  const byFormat = {};
  const byTemplate = {};
  const failedKeySet = new Set(failures.map((item) => `${item.task.formatId}|${item.task.templateId}|${item.task.caseId}`));

  for (const task of tasks) {
    const key = `${task.formatId}|${task.templateId}|${task.caseId}`;
    const failed = failedKeySet.has(key);
    byCase[task.caseId] ??= { total: 0, failed: 0 };
    byCase[task.caseId].total += 1;
    if (failed) byCase[task.caseId].failed += 1;

    byFormat[task.formatId] ??= { total: 0, failed: 0 };
    byFormat[task.formatId].total += 1;
    if (failed) byFormat[task.formatId].failed += 1;

    byTemplate[task.templateId] ??= { total: 0, failed: 0, formats: {} };
    byTemplate[task.templateId].total += 1;
    if (failed) byTemplate[task.templateId].failed += 1;
    byTemplate[task.templateId].formats[task.formatId] ??= { total: 0, failed: 0 };
    byTemplate[task.templateId].formats[task.formatId].total += 1;
    if (failed) byTemplate[task.templateId].formats[task.formatId].failed += 1;
  }

  return {
    generated_at: new Date().toISOString(),
    duration_seconds: Number(((Date.now() - startedAt) / 1000).toFixed(2)),
    output_root: outputRoot,
    totals: {
      tasks: tasks.length,
      failed: failures.length,
      passed: tasks.length - failures.length
    },
    by_case: byCase,
    by_format: byFormat,
    by_template: byTemplate
  };
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
      console.log("Running build before stress render...");
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

    const stressCases = buildStressCases(options.cases);
    const catalog = await loadTemplateCatalogFromGeneratedAssets(options.formats);
    const tasks = buildRenderTasks(catalog, options, stressCases);
    if (tasks.length === 0) {
      throw new Error("No tasks generated. Check --formats/--cases filters.");
    }

    await mkdir(outputRoot, { recursive: true });
    console.log(`Rendering ${tasks.length} stress screenshots (${stressCases.length} case(s))...`);
    const runSummary = await runWithConcurrency(tasks, options.concurrency, (task, index, total) =>
      renderTask(task, options, outputRoot, headers, index, total)
    );

    const summary = summarizeFailures(tasks, runSummary.failures, startedAt, outputRoot);
    const galleryEntries = runSummary.rendered.map((item) => ({
      formatId: item.task.formatId,
      templateId: item.task.templateId,
      caseId: item.task.caseId,
      caseLabel: item.task.caseLabel,
      file: relative(outputRoot, item.filePath).split("\\\\").join("/")
    }));

    await writeFile(join(outputRoot, "report.json"), JSON.stringify(summary, null, 2));
    await writeFile(join(outputRoot, "failures.json"), JSON.stringify(runSummary.failures, null, 2));
    await writeFile(
      join(outputRoot, "index.html"),
      buildGalleryIndexHtml({
        entries: galleryEntries,
        failures: runSummary.failures,
        summary
      })
    );

    console.log("");
    console.log("Stress render summary");
    console.log(`- Total tasks: ${summary.totals.tasks}`);
    console.log(`- Passed: ${summary.totals.passed}`);
    console.log(`- Failed: ${summary.totals.failed}`);
    console.log(`- Output: ${outputRoot}`);
    console.log(`- Report: ${join(outputRoot, "report.json")}`);
    console.log(`- Gallery: ${join(outputRoot, "index.html")}`);

    if (runSummary.failures.length > 0) {
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
