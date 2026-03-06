import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { basename, dirname, extname, relative, resolve } from "node:path";
import { parse } from "yaml";

const projectRoot = process.cwd();
const configPath = resolve(projectRoot, "config/pipeline.config.yaml");
const outputPath = resolve(projectRoot, "src/generated/template-assets.json");
const templateCssPath = resolve(projectRoot, "src/generated/template.css");
const templatesDir = resolve(projectRoot, "templates");
const systemTemplateDir = resolve(templatesDir, "system");

// ─── Load config (formats / brand / runtime only — no templates array needed) ───

const loadedConfig = await loadConfigWithExtends(configPath);
const config = assertConfigShape(loadedConfig);
const templateCss = await readCompiledTemplateCss(templateCssPath);
const formatKeys = Object.keys(config.formats);

// ─── Auto-discover templates from templates/ directory ───────────────────────

const discoveredTemplates = await discoverTemplates(templatesDir, systemTemplateDir);
if (discoveredTemplates.length === 0) {
  throw new Error("No template HTML files found in templates/ directory");
}

// Validate default_template_id references exist
for (const [formatKey, format] of Object.entries(config.formats)) {
  const found = discoveredTemplates.find((t) => t.id === format.default_template_id);
  if (!found) {
    throw new Error(
      `Format "${formatKey}" references default_template_id "${format.default_template_id}" which was not found in templates/. ` +
      `Available template IDs: ${discoveredTemplates.map((t) => t.id).join(", ")}`
    );
  }
}

// Build templateFiles map: id → html content
const templateFiles = {};
for (const template of discoveredTemplates) {
  templateFiles[template.id] = template.html;
}

// Load system templates
const systemTemplateFiles = await loadSystemTemplateFiles(systemTemplateDir);
for (const [id, html] of Object.entries(systemTemplateFiles)) {
  templateFiles[id] = html;
}

// Strip html from template metadata before storing (it's already in templateFiles)
const templateMeta = discoveredTemplates.map(({ html: _html, ...meta }) => meta);

// Inject discovered templates into config
config.templates = templateMeta;

// ─── Write output ─────────────────────────────────────────────────────────────

const generated = JSON.stringify(
  {
    pipeline_config: config,
    template_files: templateFiles,
    template_css: templateCss
  },
  null,
  2
);

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, generated, "utf8");

console.log(
  `Generated ${toPosix(relative(projectRoot, outputPath))} ` +
  `from ${toPosix(relative(projectRoot, configPath))} ` +
  `— discovered ${discoveredTemplates.length} templates`
);

// ─── Template discovery ───────────────────────────────────────────────────────

/**
 * Recursively find all .html files in dir, excluding the system subdirectory.
 * Parse each file's front-matter comment and auto-discover slot tokens.
 *
 * Front-matter format (HTML comment at the very top of the file):
 *
 *   <!--
 *   @id: layout/my-template
 *   @label: My Template
 *   @description: A one-line description
 *   @frame_tone: default|dark
 *   @background_image: global|inline
 *
 *   @slot slot_key | type | Hint text for AI / docs | optional default value
 *   -->
 *
 * All fields are optional. Defaults:
 *  - id: derived from relative path, e.g. "templates/my-section/card.html" → "my-section/card"
 *  - label: humanized filename
 *  - description: ""
 *  - slots: auto-discovered from {{SLOT:key}} tokens (type=text, no hint)
 */
async function discoverTemplates(dir, systemDir) {
  const htmlFiles = await collectHtmlFiles(dir, systemDir);
  const idSet = new Set();
  const templates = [];

  for (const filePath of htmlFiles) {
    const html = await readFile(filePath, "utf8");
    const meta = parseTemplateFrontMatter(html, filePath, dir);

    if (idSet.has(meta.id)) {
      throw new Error(
        `Duplicate template id "${meta.id}" — found in both a previously scanned file and ${toPosix(relative(projectRoot, filePath))}`
      );
    }
    idSet.add(meta.id);

    // Merge declared fields with any auto-discovered {{SLOT:*}} tokens
    const declaredKeys = new Set(meta.fields.map((f) => f.key));
    const autoSlotKeys = extractSlotKeys(html);
    for (const key of autoSlotKeys) {
      if (!declaredKeys.has(key)) {
        meta.fields.push({ key, type: "text", hint: `Slot: ${key.replaceAll("_", " ")}`, default: "" });
        declaredKeys.add(key);
      }
    }

    const relFile = toPosix(relative(projectRoot, filePath));
    const compatibleFormats = Array.isArray(meta.formats) && meta.formats.length > 0 ? meta.formats : formatKeys;
    templates.push({ ...meta, file: relFile, html, formats: compatibleFormats });
  }

  // Sort for stable output
  templates.sort((a, b) => a.id.localeCompare(b.id));
  return templates;
}

async function collectHtmlFiles(dir, systemDir) {
  const results = [];
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return results;
  }

  for (const entry of entries) {
    const fullPath = resolve(dir, entry.name);
    if (entry.isDirectory()) {
      // Skip the system/ directory — those are shell templates, not user templates
      if (fullPath === systemDir) continue;
      const nested = await collectHtmlFiles(fullPath, systemDir);
      results.push(...nested);
    } else if (entry.isFile() && extname(entry.name).toLowerCase() === ".html") {
      results.push(fullPath);
    }
  }

  return results.sort();
}

/**
 * Parse the optional front-matter comment block at the very start of an HTML file.
 * Returns a template metadata object with all discovered fields.
 */
function parseTemplateFrontMatter(html, filePath, templatesDir) {
  // Default: derive id from relative file path
  const relPath = relative(templatesDir, filePath);
  const fallbackId = toPosix(relPath.replace(/\.html$/i, ""));
  const fallbackLabel = humanizeFilename(basename(filePath, ".html"));

  const defaults = {
    id: fallbackId,
    label: fallbackLabel,
    description: "",
    frameTone: undefined,
    backgroundImage: undefined,
    fields: [],
    formats: undefined
  };

  // Match the first HTML comment block (must start at or near the top)
  const preamble = html.slice(0, 2048); // only scan the first 2 KB
  const commentMatch = preamble.match(/^[\s\S]*?<!--([\s\S]*?)-->/);
  if (!commentMatch) return defaults;

  const comment = commentMatch[1];

  // Check if it looks like our @-directive front-matter
  if (!/@(id|label|description|frame_tone|background_image|slot)\b/.test(comment)) return defaults;

  const result = { ...defaults };

  // Parse simple @key: value directives
  const idMatch = comment.match(/^[ \t]*@id[ \t]*:[ \t]*(.+)$/m);
  if (idMatch?.[1]?.trim()) result.id = idMatch[1].trim();

  const labelMatch = comment.match(/^[ \t]*@label[ \t]*:[ \t]*(.+)$/m);
  if (labelMatch?.[1]?.trim()) result.label = labelMatch[1].trim();

  const descMatch = comment.match(/^[ \t]*@description[ \t]*:[ \t]*(.+)$/m);
  if (descMatch?.[1]?.trim()) result.description = descMatch[1].trim();

  const frameToneMatch = comment.match(/^[ \t]*@frame_tone[ \t]*:[ \t]*(.+)$/m);
  if (frameToneMatch?.[1]?.trim()) {
    const frameToneValue = frameToneMatch[1].trim().toLowerCase();
    if (frameToneValue === "default" || frameToneValue === "dark") {
      result.frameTone = frameToneValue;
    }
  }

  const backgroundImageMatch = comment.match(/^[ \t]*@background_image[ \t]*:[ \t]*(.+)$/m);
  if (backgroundImageMatch?.[1]?.trim()) {
    const backgroundImageValue = backgroundImageMatch[1].trim().toLowerCase();
    if (backgroundImageValue === "global" || backgroundImageValue === "inline") {
      result.backgroundImage = backgroundImageValue;
    }
  }

  const formatsMatch = comment.match(/^[ \t]*@formats[ \t]*:[ \t]*(.+)$/m);
  if (formatsMatch?.[1]?.trim()) {
    const parsedFormats = formatsMatch[1]
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)
      .filter((entry, index, list) => list.indexOf(entry) === index)
      .filter((entry) => formatKeys.includes(entry));
    if (parsedFormats.length > 0) {
      result.formats = parsedFormats;
    }
  }

  // Parse @slot directives: @slot key | type | hint | default
  const slotPattern = /^[ \t]*@slot[ \t]+(.+)$/gm;
  let slotMatch;
  const seenSlotKeys = new Set();
  while ((slotMatch = slotPattern.exec(comment)) !== null) {
    const parts = slotMatch[1].split("|").map((s) => s.trim());
    const key = normalizeSlotKey(parts[0] ?? "");
    if (!key) continue;
    if (seenSlotKeys.has(key)) {
      console.warn(`  ⚠ Template ${result.id}: duplicate @slot declaration for "${key}"`);
      continue;
    }
    seenSlotKeys.add(key);

    const rawType = (parts[1] ?? "text").toLowerCase();
    const validTypes = ["text", "image_url", "icon_url", "number"];
    const type = validTypes.includes(rawType) ? rawType : "text";

    result.fields.push({
      key,
      type,
      hint: parts[2] ?? `Slot: ${key.replaceAll("_", " ")}`,
      default: parts[3] ?? ""
    });
  }

  return result;
}

/** Extract all {{SLOT:key}} token keys from an HTML string */
function extractSlotKeys(html) {
  const results = new Set();
  const pattern = /\{\{\s*SLOT:([A-Za-z0-9_:-]+)\s*\}\}/gi;
  let match;
  while ((match = pattern.exec(html)) !== null) {
    const key = normalizeSlotKey(match[1] ?? "");
    if (key) results.add(key);
  }
  return [...results];
}

function normalizeSlotKey(input) {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function humanizeFilename(name) {
  return name
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ─── Config Loading & Validation ──────────────────────────────────────────────

function assertConfigShape(value) {
  if (!value || typeof value !== "object") {
    throw new Error("pipeline.config.yaml must be an object");
  }

  const config = value;
  if (typeof config.schema_version !== "number") {
    throw new Error("pipeline.config.yaml must define numeric schema_version");
  }
  if (!config.brand || typeof config.brand !== "object") {
    throw new Error("pipeline.config.yaml must define brand");
  }
  if (typeof config.brand.default_name !== "string") {
    throw new Error("brand.default_name is required");
  }
  if (!config.generation || typeof config.generation !== "object") {
    throw new Error("pipeline.config.yaml must define generation");
  }
  if (!config.runtime || typeof config.runtime !== "object") {
    throw new Error("pipeline.config.yaml must define runtime");
  }
  if (!config.security || typeof config.security !== "object") {
    throw new Error("pipeline.config.yaml must define security");
  }
  if (!config.security.api_auth || typeof config.security.api_auth !== "object") {
    throw new Error("security.api_auth must be a map");
  }
  if (!config.security.cors || typeof config.security.cors !== "object") {
    throw new Error("security.cors must be a map");
  }
  if (!Array.isArray(config.security.cors.allowed_origins)) {
    throw new Error("security.cors.allowed_origins must be an array");
  }
  if (!Array.isArray(config.security.cors.allowed_headers)) {
    throw new Error("security.cors.allowed_headers must be an array");
  }
  if (!Array.isArray(config.security.cors.allowed_methods)) {
    throw new Error("security.cors.allowed_methods must be an array");
  }
  if (!config.security.request_limits || typeof config.security.request_limits !== "object") {
    throw new Error("security.request_limits must be a map");
  }
  if (!config.security.rate_limit || typeof config.security.rate_limit !== "object") {
    throw new Error("security.rate_limit must be a map");
  }
  if (!config.security.outbound || typeof config.security.outbound !== "object") {
    throw new Error("security.outbound must be a map");
  }
  if (!Array.isArray(config.security.outbound.allowed_notify_hosts)) {
    throw new Error("security.outbound.allowed_notify_hosts must be an array");
  }
  if (!Array.isArray(config.security.outbound.allowed_image_hosts)) {
    throw new Error("security.outbound.allowed_image_hosts must be an array");
  }
  if (!Number.isInteger(config.generation.carousel_required_slides) || config.generation.carousel_required_slides < 1) {
    throw new Error("generation.carousel_required_slides must be a positive integer");
  }
  if (!config.generation.limits || typeof config.generation.limits !== "object") {
    throw new Error("generation.limits must be a map");
  }
  if (!config.generation.fallbacks || typeof config.generation.fallbacks !== "object") {
    throw new Error("generation.fallbacks must be a map");
  }
  if (!config.formats || typeof config.formats !== "object") {
    throw new Error("pipeline.config.yaml must define formats map");
  }

  // templates array is injected by the build script from auto-discovered files
  // so we do NOT validate it here — it is always present after discovery

  return config;
}

// ─── System Templates ─────────────────────────────────────────────────────────

async function loadSystemTemplateFiles(directoryPath) {
  const entries = await readdir(directoryPath, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && extname(entry.name).toLowerCase() === ".html")
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b));

  const loaded = {};
  for (const fileName of files) {
    const templateId = `@system/${fileName.slice(0, -5)}`;
    const fullPath = resolve(directoryPath, fileName);
    loaded[templateId] = await readFile(fullPath, "utf8");
  }

  if (!loaded["@system/content-shell"]) {
    throw new Error("Missing required system template: templates/system/content-shell.html");
  }

  assertSystemTemplateTokenSet(loaded["@system/content-shell"], "@system/content-shell", [
    "SAFE_TITLE",
    "TEMPLATE_CSS",
    "CANVAS_WIDTH",
    "CANVAS_HEIGHT",
    "TEMPLATE_ID",
    "TEMPLATE_TONE",
    "IMAGE_VISIBILITY_CLASS",
    "IMAGE_URL",
    "CONTENT"
  ]);

  return loaded;
}

function assertSystemTemplateTokenSet(template, templateId, requiredTokens) {
  for (const token of requiredTokens) {
    const marker = `{{${token}}}`;
    if (!template.includes(marker)) {
      throw new Error(`${templateId} is missing required token placeholder ${marker}`);
    }
  }
}

// ─── Config Merging Utilities ─────────────────────────────────────────────────

function toPosix(input) {
  return input.replaceAll("\\", "/");
}

async function loadConfigWithExtends(entryPath, stack = new Set()) {
  const absolutePath = resolve(entryPath);
  if (stack.has(absolutePath)) {
    throw new Error(`Circular config extends detected at ${toPosix(relative(projectRoot, absolutePath))}`);
  }

  stack.add(absolutePath);
  const raw = await readFile(absolutePath, "utf8");
  const parsed = parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`Config file must contain a YAML object: ${toPosix(relative(projectRoot, absolutePath))}`);
  }

  const current = cloneValue(parsed);
  const baseDir = dirname(absolutePath);
  const extendsEntries = Array.isArray(current.extends) ? current.extends : [];
  if (current.extends !== undefined && !Array.isArray(current.extends)) {
    throw new Error(`extends must be an array in ${toPosix(relative(projectRoot, absolutePath))}`);
  }

  let merged = {};
  for (const entry of extendsEntries) {
    if (typeof entry !== "string" || !entry.trim()) {
      throw new Error(`extends entries must be non-empty strings in ${toPosix(relative(projectRoot, absolutePath))}`);
    }
    const childPath = resolve(baseDir, entry.trim());
    const childConfig = await loadConfigWithExtends(childPath, stack);
    merged = deepMerge(merged, childConfig);
  }

  delete current.extends;
  merged = deepMerge(merged, current);
  stack.delete(absolutePath);
  return merged;
}

async function readCompiledTemplateCss(filePath) {
  try {
    return await readFile(filePath, "utf8");
  } catch (error) {
    throw new Error(
      `Compiled stylesheet not found at ${toPosix(relative(projectRoot, filePath))}. ` +
      "Run `pnpm run build:styles` before embedding template assets."
    );
  }
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function cloneValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => cloneValue(item));
  }
  if (isPlainObject(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cloneValue(item)]));
  }
  return value;
}

function deepMerge(base, override) {
  if (Array.isArray(override)) {
    return cloneValue(override);
  }
  if (isPlainObject(base) && isPlainObject(override)) {
    const result = { ...cloneValue(base) };
    for (const [key, value] of Object.entries(override)) {
      const existing = result[key];
      if (isPlainObject(existing) && isPlainObject(value)) {
        result[key] = deepMerge(existing, value);
        continue;
      }
      result[key] = cloneValue(value);
    }
    return result;
  }
  return cloneValue(override);
}
