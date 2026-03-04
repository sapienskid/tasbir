import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, extname, relative, resolve } from "node:path";
import { parse } from "yaml";

const projectRoot = process.cwd();
const configPath = resolve(projectRoot, "config/pipeline.config.yaml");
const outputPath = resolve(projectRoot, "src/generated/template-assets.json");
const templateCssPath = resolve(projectRoot, "src/styles/template.css");

const loadedConfig = await loadConfigWithExtends(configPath);
const config = assertConfigShape(loadedConfig);
const templateCss = await readFile(templateCssPath, "utf8");

const configDir = dirname(configPath);
const templateFiles = {};
const templateIdSet = new Set();
const formatKeys = Object.keys(config.formats);
const systemTemplateDir = resolve(projectRoot, "templates/system");

for (const template of config.templates) {
  if (templateIdSet.has(template.id)) {
    throw new Error(`Duplicate template id: ${template.id}`);
  }
  templateIdSet.add(template.id);

  const templateFormats = resolveTemplateFormats(template, formatKeys);
  for (const format of templateFormats) {
    if (!config.formats[format]) {
      throw new Error(`Template ${template.id} references unknown format: ${format}`);
    }
  }

  const templatePath = resolve(configDir, template.file);
  const html = await readFile(templatePath, "utf8");
  templateFiles[template.id] = html;

  // Keep this as a stable, project-relative path for docs/debug output.
  template.file = toPosix(relative(projectRoot, templatePath));
  template.formats = templateFormats;
  delete template.format;
}

for (const [formatKey, format] of Object.entries(config.formats)) {
  const template = config.templates.find((entry) => entry.id === format.default_template_id);
  if (!template) {
    throw new Error(`Format ${formatKey} points to missing default_template_id: ${format.default_template_id}`);
  }
  if (!templateSupportsFormat(template, formatKey)) {
    throw new Error(`Format ${formatKey} default_template_id does not support this format: ${format.default_template_id}`);
  }
}

const systemTemplateFiles = await loadSystemTemplateFiles(systemTemplateDir);
for (const [id, html] of Object.entries(systemTemplateFiles)) {
  templateFiles[id] = html;
}

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

console.log(`Generated ${toPosix(relative(projectRoot, outputPath))} from ${toPosix(relative(projectRoot, configPath))}`);

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

  if (typeof config.brand.default_name !== "string" || typeof config.brand.default_color !== "string") {
    throw new Error("brand.default_name and brand.default_color are required");
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

  if (!Array.isArray(config.templates) || config.templates.length === 0) {
    throw new Error("pipeline.config.yaml must define a non-empty templates array");
  }

  for (const entry of config.templates) {
    if (!entry || typeof entry !== "object") {
      throw new Error("template entries must be objects");
    }
    if (typeof entry.id !== "string" || typeof entry.file !== "string") {
      throw new Error("template entries require id and file string fields");
    }
    if (entry.format !== undefined && typeof entry.format !== "string") {
      throw new Error(`template ${entry.id} optional format must be a string`);
    }
    if (entry.formats !== undefined) {
      if (!Array.isArray(entry.formats) || entry.formats.some((value) => typeof value !== "string")) {
        throw new Error(`template ${entry.id} optional formats must be a string array`);
      }
      if (entry.formats.length === 0) {
        throw new Error(`template ${entry.id} optional formats must not be empty`);
      }
    }
  }

  return config;
}

function toPosix(input) {
  return input.replaceAll("\\\\", "/");
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

function resolveTemplateFormats(template, formatKeys) {
  const fromArray = Array.isArray(template.formats) ? template.formats : [];
  const fromSingle = typeof template.format === "string" ? [template.format] : [];
  const normalized = [...fromArray, ...fromSingle]
    .map((format) => (typeof format === "string" ? format.trim() : ""))
    .filter(Boolean);

  if (normalized.length > 0) {
    return [...new Set(normalized)];
  }

  return [...formatKeys];
}

function templateSupportsFormat(template, formatKey) {
  const formats = Array.isArray(template.formats) ? template.formats : [];
  if (formats.length > 0) {
    return formats.includes(formatKey);
  }

  if (typeof template.format === "string") {
    return template.format === formatKey;
  }

  return false;
}

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

  if (!loaded["@system/head-shell"]) {
    throw new Error("Missing required system template: templates/system/head-shell.html");
  }
  if (!loaded["@system/frame-shell"]) {
    throw new Error("Missing required system template: templates/system/frame-shell.html");
  }

  assertSystemTemplateTokenSet(loaded["@system/head-shell"], "@system/head-shell", [
    "SAFE_TITLE",
    "TEMPLATE_CSS",
    "CANVAS_WIDTH",
    "CANVAS_HEIGHT",
    "TOKEN_PRIMARY_TEXT",
    "TOKEN_SECONDARY_TEXT",
    "TOKEN_MUTED_TEXT",
    "TOKEN_SURFACE_BASE",
    "TOKEN_SURFACE_ELEVATED",
    "TOKEN_BORDER_SUBTLE",
    "TOKEN_ACCENT",
    "TOKEN_ACCENT_FOREGROUND",
    "TOKEN_ACCENT_GLOW",
    "TOKEN_OVERLAY_STRONG",
    "TOKEN_RADIUS_CARD",
    "TOKEN_RADIUS_PILL"
  ]);

  assertSystemTemplateTokenSet(loaded["@system/frame-shell"], "@system/frame-shell", [
    "HEAD_HTML",
    "TEMPLATE_ID",
    "FRAME_TONE_CLASS",
    "FRAME_TONE",
    "ROOT_STYLE",
    "IMAGE_VISIBILITY_CLASS",
    "IMAGE_LAYER_STYLE",
    "OVERLAY_OPACITY",
    "OVERLAY_BACKGROUND",
    "ACCENT_SWEEP_OPACITY",
    "GRAIN_DOT_COLOR",
    "GRAIN_DOT_SIZE",
    "GRAIN_BG_SIZE",
    "BORDER_ALPHA_PERCENT",
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
