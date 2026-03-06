import { PIPELINE_CONFIG, TEMPLATE_CSS, TEMPLATE_FILES } from "./generated/template-assets";

export type TemplateKind = string;

export interface TemplateFieldDeclaration {
  key: string;
  type: "text" | "image_url" | "icon_url" | "number";
  hint: string;
  default: string;
}

interface TemplateDefinition {
  id: string;
  format?: TemplateKind;
  formats?: readonly TemplateKind[];
  label: string;
  description?: string;
  file: string;
  frameTone?: "default" | "dark";
  backgroundImage?: "global" | "inline";
  fields?: TemplateFieldDeclaration[];
}

export interface SlotHintOption {
  id: string;
  type: string;
  hint: string;
  defaultValue: string;
}

export interface BaseTemplateParams {
  title: string;
  caption: string;
  imageUrl: string;
  brandName: string;
  templateId?: string;
  slots?: Record<string, string>;
}

export interface CarouselTemplateParams extends BaseTemplateParams {
  heading: string;
  body: string;
  slideNumber: number;
  totalSlides: number;
}

const TEMPLATE_DEFINITIONS = PIPELINE_CONFIG.templates as readonly TemplateDefinition[];
const TEMPLATE_SLOT_KEY_CACHE = new Map<string, string[]>();
const TEMPLATE_FIELD_CACHE = new Map<string, TemplateFieldDeclaration[]>();
const SLOT_TOKEN_PATTERN = /\{\{\s*SLOT:([A-Za-z0-9_:-]+)\s*\}\}/gi;

const DEFAULT_VISUAL_LAYERS = {
  useBackgroundImageOnly: true
} as const;

export function listTemplateKinds(): TemplateKind[] {
  return Object.keys(PIPELINE_CONFIG.formats) as TemplateKind[];
}

export function isTemplateKind(value: string): value is TemplateKind {
  return listTemplateKinds().includes(value as TemplateKind);
}

export function getTemplateDimensions(kind: TemplateKind): { width: number; height: number } {
  const format = PIPELINE_CONFIG.formats[kind];
  return {
    width: format.width,
    height: format.height
  };
}

export function listSlotHints(): SlotHintOption[] {
  const keySet = new Set<string>([
    ...listAllTemplateSlotKeys()
  ]);

  return [...keySet]
    .map((rawKey) => normalizeSlotKey(rawKey))
    .filter(Boolean)
    .map((id) => {
      const field = findFieldDeclaration(id);
      return {
        id,
        type: field?.type ?? "text",
        hint: field?.hint ?? `Template slot used by one or more layouts: ${id.replaceAll("_", " ")}`,
        defaultValue: field?.default ?? ""
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

export function listTemplateFields(templateId: string): TemplateFieldDeclaration[] {
  const cached = TEMPLATE_FIELD_CACHE.get(templateId);
  if (cached) {
    return cached;
  }

  const definition = TEMPLATE_DEFINITIONS.find((d) => d.id === templateId);
  if (definition?.fields && definition.fields.length > 0) {
    TEMPLATE_FIELD_CACHE.set(templateId, definition.fields);
    return definition.fields;
  }

  const slotKeys = listTemplateSlotKeys(templateId);
  const autoFields: TemplateFieldDeclaration[] = slotKeys.map((key) => ({
    key,
    type: "text" as const,
    hint: `Template slot: ${key.replaceAll("_", " ")}`,
    default: ""
  }));
  TEMPLATE_FIELD_CACHE.set(templateId, autoFields);
  return autoFields;
}

export function listRequiredSlotKeys(
  kind: TemplateKind,
  options?: { templateId?: string }
): string[] {
  const templateId = resolveTemplateId(kind, options);
  return listTemplateSlotKeys(templateId);
}

export function resolveTemplateId(kind: TemplateKind, options?: { templateId?: string }): string {
  return selectTemplateDefinition(kind, options?.templateId).id;
}

export function renderTemplate(kind: TemplateKind, params: BaseTemplateParams | CarouselTemplateParams): string {
  const format = PIPELINE_CONFIG.formats[kind];
  const selectedTemplate = selectTemplateDefinition(kind, params.templateId);
  const frameTone = resolveFrameTone(selectedTemplate);
  const slotValues = resolveSlotValues(kind, params, selectedTemplate.id);

  const tokens: Record<string, string> = {
    TITLE: escapeHtml(params.title),
    CAPTION: escapeHtml(params.caption),
    HEADING: escapeHtml(kind === "carousel-post" ? (params as CarouselTemplateParams).heading : params.title),
    BODY: escapeHtml(kind === "carousel-post" ? (params as CarouselTemplateParams).body : params.caption),
    IMAGE_URL: escapeHtml(params.imageUrl),
    BRAND_NAME: escapeHtml(params.brandName),
    SLIDE_LABEL: escapeHtml(
      kind === "carousel-post" ? `${(params as CarouselTemplateParams).slideNumber}/${(params as CarouselTemplateParams).totalSlides}` : ""
    ),
    KICKER_TEXT: escapeHtml(kind === "carousel-post" ? params.title : "")
  };

  const templateMarkup = loadTemplateMarkup(selectedTemplate.id);
  const visualLayers = resolveVisualLayerSettings(selectedTemplate, templateMarkup);
  const content = interpolateTemplate(templateMarkup, tokens, slotValues);

  return renderDocumentShell({
    width: format.width,
    height: format.height,
    templateId: selectedTemplate.id,
    frameTone,
    title: params.title,
    imageUrl: params.imageUrl,
    content,
    visualLayers
  });
}

function selectTemplateDefinition(
  kind: TemplateKind,
  requestedTemplateId?: string
): TemplateDefinition {
  if (TEMPLATE_DEFINITIONS.length === 0) {
    throw new Error("No templates found. Add HTML files to the templates/ directory.");
  }

  if (requestedTemplateId) {
    const direct = TEMPLATE_DEFINITIONS.find(
      (d) => d.id === requestedTemplateId.trim() && templateSupportsFormat(d, kind)
    );
    if (direct) return direct;
    console.warn(`Unknown templateId "${requestedTemplateId}" — falling back to format default`);
  }

  const defaultId = PIPELINE_CONFIG.formats[kind].default_template_id;
  const defaultTemplate = TEMPLATE_DEFINITIONS.find((d) => d.id === defaultId && templateSupportsFormat(d, kind));
  if (defaultTemplate) return defaultTemplate;

  const compatible = TEMPLATE_DEFINITIONS.find((definition) => templateSupportsFormat(definition, kind));
  if (compatible) {
    return compatible;
  }
  return TEMPLATE_DEFINITIONS[0];
}

function templateSupportsFormat(definition: TemplateDefinition, kind: TemplateKind): boolean {
  if (definition.format) {
    return definition.format === kind;
  }
  if (Array.isArray(definition.formats) && definition.formats.length > 0) {
    return definition.formats.includes(kind);
  }
  return true;
}

function loadTemplateMarkup(templateId: string): string {
  const key = templateId as keyof typeof TEMPLATE_FILES;
  const content = TEMPLATE_FILES[key];
  if (!content) {
    throw new Error(`Template file not found for id ${templateId}`);
  }
  return content;
}

function normalizeBackgroundImageMode(value: unknown): "global" | "inline" | undefined {
  if (value === "global" || value === "inline") {
    return value;
  }
  return undefined;
}

function resolveFrameTone(template: TemplateDefinition): "default" | "dark" {
  const explicitTone = normalizeFrameTone(template.frameTone);
  if (explicitTone) {
    return explicitTone;
  }
  return "default";
}

function normalizeFrameTone(value: unknown): "default" | "dark" | undefined {
  if (value === "default" || value === "dark") {
    return value;
  }
  return undefined;
}

function interpolateTemplate(template: string, tokens: Record<string, string>, slots: Record<string, string>): string {
  return template.replace(/\{\{\s*([A-Za-z0-9_:-]+)\s*\}\}/g, (_match, rawKey: string) => {
    const key = rawKey.trim();
    const slotMatch = key.match(/^slot:(.+)$/i);
    if (slotMatch?.[1]) {
      const slotKey = normalizeSlotKey(slotMatch[1]);
      return escapeHtml(slots[slotKey] ?? "");
    }

    const normalizedTokenKey = key.toUpperCase();
    return tokens[normalizedTokenKey] ?? "";
  });
}

function resolveSlotValues(
  kind: TemplateKind,
  params: BaseTemplateParams | CarouselTemplateParams,
  templateId: string
): Record<string, string> {
  const resolved: Record<string, string> = {};

  const fields = listTemplateFields(templateId);
  for (const field of fields) {
    const normalizedKey = normalizeSlotKey(field.key);
    if (normalizedKey && field.default) {
      resolved[normalizedKey] = field.default;
    }
  }

  resolved.headline = params.title;
  resolved.subheadline = params.caption;
  resolved.short_hook = params.title;
  resolved.supporting_line = params.caption;
  resolved.insight_line = params.caption;
  resolved.heading = params.title;
  resolved.body = params.caption;
  resolved.item_title = params.title;
  resolved.item_body = params.caption;
  resolved.item_meta = "";

  if (kind === "carousel-post") {
    const carouselParams = params as CarouselTemplateParams;
    resolved.headline = carouselParams.heading;
    resolved.body = carouselParams.body;
    resolved.item_title = carouselParams.heading;
    resolved.item_body = carouselParams.body;
    resolved.step_number = String(carouselParams.slideNumber);
    resolved.step_total = String(carouselParams.totalSlides);
  }

  if (params.slots) {
    for (const [slotKey, slotValue] of Object.entries(params.slots)) {
      const normalizedKey = normalizeSlotKey(slotKey);
      const value = slotValue.trim();
      if (!normalizedKey || !value) {
        continue;
      }
      resolved[normalizedKey] = value;
    }
  }

  return resolved;
}

function normalizeSlotKey(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function findFieldDeclaration(slotKey: string): TemplateFieldDeclaration | undefined {
  const normalizedTarget = normalizeSlotKey(slotKey);
  for (const def of TEMPLATE_DEFINITIONS) {
    if (!def.fields) {
      continue;
    }
    for (const field of def.fields) {
      if (normalizeSlotKey(field.key) === normalizedTarget) {
        return field;
      }
    }
  }
  return undefined;
}

function listAllTemplateSlotKeys(): string[] {
  const keySet = new Set<string>();
  for (const template of TEMPLATE_DEFINITIONS) {
    for (const key of listTemplateSlotKeys(template.id)) {
      keySet.add(key);
    }
  }
  return [...keySet];
}

function listTemplateSlotKeys(templateId: string): string[] {
  const cached = TEMPLATE_SLOT_KEY_CACHE.get(templateId);
  if (cached) {
    return cached;
  }

  const templateMarkup = loadTemplateMarkup(templateId);
  const keySet = new Set<string>();
  let match = SLOT_TOKEN_PATTERN.exec(templateMarkup);
  while (match) {
    const normalized = normalizeSlotKey(match[1] ?? "");
    if (normalized) {
      keySet.add(normalized);
    }
    match = SLOT_TOKEN_PATTERN.exec(templateMarkup);
  }
  SLOT_TOKEN_PATTERN.lastIndex = 0;

  const keys = [...keySet];
  TEMPLATE_SLOT_KEY_CACHE.set(templateId, keys);
  return keys;
}

function renderDocumentShell(args: {
  width: number;
  height: number;
  templateId: string;
  frameTone: "default" | "dark";
  title: string;
  imageUrl: string;
  content: string;
  visualLayers: VisualLayerSettings;
}): string {
  const safeTitle = escapeHtml(args.title);
  const safeImageUrl = escapeHtml(args.imageUrl.trim());
  const hasImage = safeImageUrl.length > 0;
  const shouldRenderBackgroundImage = hasImage && args.visualLayers.useBackgroundImageOnly;
  const imageVisibilityClass = shouldRenderBackgroundImage ? "" : "hidden";
  const safeCss = TEMPLATE_CSS.replaceAll("</style", "<\\/style");
  const shell = loadTemplateMarkup("@system/content-shell");

  return interpolateTemplate(
    shell,
    {
      SAFE_TITLE: safeTitle,
      TEMPLATE_CSS: safeCss,
      CANVAS_WIDTH: String(args.width),
      CANVAS_HEIGHT: String(args.height),
      TEMPLATE_ID: escapeHtml(args.templateId),
      TEMPLATE_TONE: args.frameTone,
      IMAGE_VISIBILITY_CLASS: imageVisibilityClass,
      IMAGE_URL: safeImageUrl,
      CONTENT: args.content
    },
    {}
  );
}

interface VisualLayerSettings {
  useBackgroundImageOnly: boolean;
}

function resolveVisualLayerSettings(
  template: TemplateDefinition,
  templateMarkup: string
): VisualLayerSettings {
  const configured: VisualLayerSettings = {
    useBackgroundImageOnly: DEFAULT_VISUAL_LAYERS.useBackgroundImageOnly
  };

  const explicitBackgroundMode = normalizeBackgroundImageMode(template.backgroundImage);
  if (explicitBackgroundMode === "inline") {
    configured.useBackgroundImageOnly = false;
    return configured;
  }
  if (explicitBackgroundMode === "global") {
    configured.useBackgroundImageOnly = true;
    return configured;
  }

  if (/\{\{\s*IMAGE_URL\s*\}\}/i.test(templateMarkup)) {
    configured.useBackgroundImageOnly = false;
  }

  return configured;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function previewParamsFromUrl(kind: TemplateKind, url: URL): BaseTemplateParams | CarouselTemplateParams {
  const defaults = PIPELINE_CONFIG.preview_defaults;
  const slotValues = slotValuesFromQuery(url.searchParams);

  const base: BaseTemplateParams = {
    title: url.searchParams.get("title") ?? defaults.title,
    caption: url.searchParams.get("caption") ?? defaults.caption,
    imageUrl: url.searchParams.get("imageUrl") ?? "",
    brandName: url.searchParams.get("brand") ?? url.searchParams.get("brandName") ?? PIPELINE_CONFIG.brand.default_name,
    templateId: url.searchParams.get("templateId") ?? undefined,
    slots: slotValues
  };

  if (kind !== "carousel-post") {
    return base;
  }

  const slideNumber = Number.parseInt(url.searchParams.get("slide") ?? String(defaults.slide_number), 10);
  const totalSlides = Number.parseInt(url.searchParams.get("total") ?? String(defaults.total_slides), 10);

  return {
    ...base,
    heading: url.searchParams.get("heading") ?? defaults.heading,
    body: url.searchParams.get("body") ?? defaults.body,
    slideNumber: Number.isFinite(slideNumber) ? slideNumber : defaults.slide_number,
    totalSlides: Number.isFinite(totalSlides) ? totalSlides : defaults.total_slides
  };
}

function slotValuesFromQuery(searchParams: URLSearchParams): Record<string, string> | undefined {
  const slots: Record<string, string> = {};

  for (const [rawKey, rawValue] of searchParams.entries()) {
    const value = rawValue.trim();
    if (!value) {
      continue;
    }

    if (rawKey.startsWith("slot.")) {
      const key = normalizeSlotKey(rawKey.slice(5));
      if (key) {
        slots[key] = value;
      }
      continue;
    }

    if (rawKey.startsWith("slot_")) {
      const key = normalizeSlotKey(rawKey.slice(5));
      if (key) {
        slots[key] = value;
      }
    }
  }

  return Object.keys(slots).length > 0 ? slots : undefined;
}
