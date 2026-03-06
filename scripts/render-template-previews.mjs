#!/usr/bin/env node

import { access, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { execFile as execFileCallback } from "node:child_process";
import { promisify } from "node:util";
import { pathToFileURL } from "node:url";

const execFile = promisify(execFileCallback);

const projectRoot = process.cwd();
const baseUrl = process.env.BASE_URL?.trim() || "http://127.0.0.1:8787";
const outDir = resolve(projectRoot, process.env.OUT_DIR?.trim() || "artifacts/previews/all");
const chromeBin = process.env.CHROME_BIN?.trim() || "google-chrome-stable";
const magickBin = process.env.MAGICK_BIN?.trim() || "magick";
const viewportPadding = Number.parseInt(process.env.PREVIEW_VIEWPORT_PADDING || "140", 10);
const previewImageUrl = process.env.PREVIEW_IMAGE_URL?.trim() || "";
const formatOnly = process.env.FORMAT_ONLY?.trim() || "";

const apiKey = process.env.API_KEY?.trim() || (await readApiKeyFromDevVars(resolve(projectRoot, ".dev.vars")));
if (!apiKey) {
  throw new Error("Could not resolve API key. Set API_KEY or configure API_KEYS in .dev.vars.");
}

await assertExecutable(chromeBin, ["--version"], "Chrome");
await assertExecutable(magickBin, ["-version"], "ImageMagick");

const catalog = await fetchJson(`${baseUrl}/template-catalog`, {
  headers: {
    "x-api-key": apiKey
  }
});

const allFormats = normalizeFormats(catalog.formats);
const formats = formatOnly
  ? allFormats.filter((format) => format.id === formatOnly)
  : allFormats;
if (formatOnly && formats.length === 0) {
  throw new Error(`FORMAT_ONLY=${formatOnly} did not match any catalog format`);
}
const templatesByFormat = normalizeTemplatesByFormat(catalog.templates_by_format);
const templateMap = normalizeTemplateMap(catalog.templates);
const generatedAtIso = new Date().toISOString();
const manifest = {
  generated_at: generatedAtIso,
  base_url: baseUrl,
  output_dir: outDir,
  total_renders: 0,
  formats: {}
};

await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });

let renderCount = 0;
for (const format of formats) {
  const templateIds = templatesByFormat.get(format.id) ?? [];
  if (templateIds.length === 0) {
    continue;
  }
  manifest.formats[format.id] = {
    width: format.width,
    height: format.height,
    templates: []
  };

  const formatDir = resolve(outDir, format.id);
  const htmlDir = resolve(formatDir, "html");
  const pngDir = resolve(formatDir, "png");
  const metaDir = resolve(formatDir, "meta");
  await mkdir(htmlDir, { recursive: true });
  await mkdir(pngDir, { recursive: true });
  await mkdir(metaDir, { recursive: true });

  for (const templateId of templateIds) {
    const template = templateMap.get(templateId);
    const baseName = templateId.replaceAll("/", "__");
    const htmlPath = resolve(htmlDir, `${baseName}.html`);
    const pngPath = resolve(pngDir, `${baseName}.png`);
    const rawPath = resolve(pngDir, `${baseName}.raw.png`);
    const metaPath = resolve(metaDir, `${baseName}.meta.txt`);

    await mkdir(dirname(htmlPath), { recursive: true });
    await mkdir(dirname(rawPath), { recursive: true });
    await mkdir(dirname(metaPath), { recursive: true });

    const html = await fetchText(
      buildTemplatePreviewUrl(baseUrl, format.id, {
        templateId,
        title: "Monochromatic Swiss Content System - Local Stress Preview",
        caption:
          "Rendered by automation to validate typography, spacing, and token consistency across every format while exercising longer copy lengths and dense slot coverage.",
        heading: "One source article, many coherent outputs",
        body:
          "This preview intentionally uses longer narrative copy to test text wrapping, line rhythm, and readability boundaries without breaking the frame structure or token-driven layout behavior.",
        imageUrl: previewImageUrl,
        brandName: "Tasbir Blog",
        brandingColor: "#111111",
        slots: {
          headline: "Editorial structure with deterministic composition",
          subheadline: "Generate copy once, map it across templates, and keep platform voice aligned.",
          supporting_line: "Design tokens control tone globally, so template additions never fragment the system.",
          insight_line: "Long-form testing confirms wrapping behavior before production publishing.",
          cta_text: "Read the full framework",
          metric_value: "12.4x",
          metric_label: "Faster iteration velocity",
          quote_text:
            "A reliable content pipeline is not about writing more - it is about preserving intent, consistency, and clarity at scale.",
          quote_author: "Tasbir Team",
          author_role: "Editorial Systems",
          series_label: "Content Ops / Vol 01",
          slide_index: "03",
          step_1: "Define one campaign angle from the source content.",
          step_2: "Extract high-signal points that map cleanly to template slots.",
          step_3: "Render every output with shared tokens and format-aware copy.",
          step_4: "Review contrast, spacing, and truncation before publishing."
        }
      }),
      {
        headers: {
          "x-api-key": apiKey
        }
      }
    );

    await writeFile(htmlPath, html, "utf8");

    // `--window-size` in Chrome CLI can produce a shorter content viewport than expected.
    // Capture a taller frame and crop to exact target dimensions to remove bottom bars.
    await execFile(chromeBin, [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--force-device-scale-factor=1",
      `--window-size=${format.width},${format.height + Math.max(viewportPadding, 80)}`,
      "--virtual-time-budget=3500",
      `--screenshot=${rawPath}`,
      pathToFileURL(htmlPath).href
    ]);

    await execFile(magickBin, [
      rawPath,
      "-crop",
      `${format.width}x${format.height}+0+0`,
      "+repage",
      pngPath
    ]);
    await rm(rawPath, { force: true });

    const summary = [
      `template_id=${templateId}`,
      `label=${template?.label ?? ""}`,
      `format=${format.id}`,
      `width=${format.width}`,
      `height=${format.height}`
    ].join("\n");
    await writeFile(metaPath, `${summary}\n`, "utf8");
    manifest.formats[format.id].templates.push({
      id: templateId,
      label: template?.label ?? "",
      html: toPosix(relative(outDir, htmlPath)),
      png: toPosix(relative(outDir, pngPath)),
      meta: toPosix(relative(outDir, metaPath))
    });
    renderCount += 1;
  }
}

manifest.total_renders = renderCount;
await writeFile(resolve(outDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

console.log(`Rendered ${renderCount} template previews into ${outDir}`);

async function assertExecutable(binary, args, label) {
  try {
    await execFile(binary, args, { timeout: 15_000 });
  } catch (error) {
    throw new Error(`${label} binary is not available: ${binary}`);
  }
}

async function readApiKeyFromDevVars(devVarsPath) {
  try {
    await access(devVarsPath, fsConstants.R_OK);
  } catch {
    return null;
  }

  const raw = await readFile(devVarsPath, "utf8");
  const line = raw
    .split(/\r?\n/g)
    .find((entry) => entry.trim().startsWith("API_KEYS="));
  if (!line) {
    return null;
  }
  const match = line.match(/^API_KEYS\s*=\s*(.+)$/);
  const value = match?.[1]?.trim();
  if (!value) {
    return null;
  }
  const unquoted = value.replace(/^["']|["']$/g, "");
  const first = unquoted
    .split(",")
    .map((entry) => entry.trim())
    .find(Boolean);
  return first || null;
}

async function fetchJson(url, init) {
  const response = await fetchWithRetry(url, init);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${url}`);
  }
  return response.json();
}

async function fetchText(url, init) {
  const response = await fetchWithRetry(url, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}) for ${url}: ${body.slice(0, 300)}`);
  }
  return response.text();
}

async function fetchWithRetry(url, init, maxAttempts = 12) {
  let attempt = 0;
  let lastResponse = null;
  while (attempt < maxAttempts) {
    attempt += 1;
    const response = await fetch(url, init);
    lastResponse = response;
    if (response.status !== 429 && response.status < 500) {
      return response;
    }

    const retryAfterSeconds = Number.parseInt(response.headers.get("retry-after") || "", 10);
    const waitMs = Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0 ? retryAfterSeconds * 1000 : 2_000;
    await sleep(waitMs);
  }

  return lastResponse;
}

function sleep(ms) {
  return new Promise((resolvePromise) => {
    setTimeout(resolvePromise, Math.max(ms, 1));
  });
}

function normalizeFormats(input) {
  if (!Array.isArray(input)) {
    return [];
  }
  return input
    .map((entry) => ({
      id: asText(entry?.id),
      width: Number(entry?.width),
      height: Number(entry?.height)
    }))
    .filter((entry) => entry.id && Number.isFinite(entry.width) && Number.isFinite(entry.height));
}

function normalizeTemplatesByFormat(input) {
  const map = new Map();
  if (!input || typeof input !== "object") {
    return map;
  }

  for (const [format, templateIds] of Object.entries(input)) {
    if (!Array.isArray(templateIds)) {
      continue;
    }
    map.set(
      format,
      templateIds.map((id) => asText(id)).filter(Boolean)
    );
  }
  return map;
}

function normalizeTemplateMap(input) {
  const map = new Map();
  if (!Array.isArray(input)) {
    return map;
  }
  for (const template of input) {
    const id = asText(template?.id);
    if (!id) {
      continue;
    }
    map.set(id, {
      id,
      label: asText(template?.label)
    });
  }
  return map;
}

function asText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function buildTemplatePreviewUrl(base, format, args) {
  const url = new URL(`/template/${format}`, base);
  if (args.templateId) {
    url.searchParams.set("templateId", args.templateId);
  }
  if (args.title) {
    url.searchParams.set("title", args.title);
  }
  if (args.caption) {
    url.searchParams.set("caption", args.caption);
  }
  if (args.heading) {
    url.searchParams.set("heading", args.heading);
  }
  if (args.body) {
    url.searchParams.set("body", args.body);
  }
  if (args.imageUrl) {
    url.searchParams.set("imageUrl", args.imageUrl);
  }
  if (args.brandName) {
    url.searchParams.set("brandName", args.brandName);
  }
  if (args.brandingColor) {
    url.searchParams.set("brandingColor", args.brandingColor);
  }

  for (const [slotKey, slotValue] of Object.entries(args.slots ?? {})) {
    if (!slotKey || !slotValue) {
      continue;
    }
    url.searchParams.set(`slot.${slotKey}`, slotValue);
  }

  return url.toString();
}

function toPosix(value) {
  return value.replaceAll("\\", "/");
}
