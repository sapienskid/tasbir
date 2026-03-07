import katex from "katex";
import MarkdownIt from "markdown-it";
import { PIPELINE_CONFIG, RUNTIME_SCRIPTS, TEMPLATE_CSS, TEMPLATE_FILES } from "./generated/template-assets";
import { generateIllustrationElement } from "./illustrator";

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
  selectionHints?: string;
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
const SLOT_TOKEN_PATTERN = /\{\{\s*SLOT(?:_RAW)?:([A-Za-z0-9_:-]+)\s*\}\}/gi;
const RICH_TEXT_TOKEN_KEYS = new Set(["TITLE", "CAPTION", "HEADING", "BODY", "BRAND_NAME", "SLIDE_LABEL", "KICKER_TEXT"]);
const BLOCK_RICH_TOKEN_KEYS = new Set(["CAPTION", "BODY"]);
const INLINE_SLOT_PATTERN =
  /(?:^|_)(cta|action|button|label|tag|badge|meta|date|index|number|count|score|percent|pct|step|total|slide|author|role|name|brand|icon|x|y|size|opacity|visible|url|prompt|rights)(?:_|$)/i;
const BLOCK_SLOT_PATTERN =
  /(?:^|_)(body|description|insight|detail|narrative|summary|copy|content|caption|callout|support_note)(?:_|$)/i;
const MARKDOWN_BLOCK_HINT_PATTERN = /(^|\n)\s*(?:[-*+]\s+\S+|\d+\.\s+\S+|>\s+\S+|#{1,6}\s+\S+|```|~~~|\$\$)/m;
const MERMAID_FENCE_PATTERN = /```mermaid\s*([\s\S]*?)```/gi;
const BLOCK_MATH_PATTERN = /\$\$([\s\S]+?)\$\$/g;
const INLINE_MATH_PATTERN = /(?<!\\)\$([^\n$]+?)(?<!\\)\$/g;
const COLOR_SWAP_SLOT_KEYS = [
  "color_swap",
  "swap_colors",
  "invert_colors",
  "invert_color_scheme",
  "foreground_background_swap",
  "bw_swap"
] as const;
const COLOR_SWAP_QUERY_KEYS = ["colorswap", "swapcolors", "invertcolors", "bwswap", "foregroundbackgroundswap"] as const;
const MARKDOWN = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false
});

const DEFAULT_VISUAL_LAYERS = {
  useBackgroundImageOnly: false
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
  const colorSwapMode = resolveColorSwapMode(slotValues);
  const providedIllustrationSeed = slotValues.illustration_seed?.trim() ?? "";
  const illustrationSeed = providedIllustrationSeed || buildDefaultIllustrationSeed(kind, selectedTemplate.id, params);
  const illustrationElement = illustrationSeed
    ? generateIllustrationElement({
      width: format.width,
      height: format.height,
      tone: frameTone,
      seed: illustrationSeed
    })
    : undefined;
  const hasIllustration = Boolean(illustrationElement);
  const brandIcon = resolveBrandIconLayerSettings(params.brandName, slotValues);
  const shouldInvertBrandIcon = frameTone === "dark" ? colorSwapMode === "normal" : colorSwapMode === "swap";
  const slotFieldTypeByKey = new Map(
    listTemplateFields(selectedTemplate.id).map((field) => [normalizeSlotKey(field.key), field.type] as const)
  );

  const tokens: Record<string, string> = {
    TITLE: params.title,
    CAPTION: params.caption,
    HEADING: kind === "carousel-post" ? (params as CarouselTemplateParams).heading : params.title,
    BODY: kind === "carousel-post" ? (params as CarouselTemplateParams).body : params.caption,
    IMAGE_URL: params.imageUrl,
    BRAND_NAME: params.brandName,
    SLIDE_LABEL: kind === "carousel-post"
      ? `${(params as CarouselTemplateParams).slideNumber}/${(params as CarouselTemplateParams).totalSlides}`
      : "",
    KICKER_TEXT: kind === "carousel-post" ? params.title : "",
    ILLUSTRATION_VISIBILITY_CLASS: hasIllustration ? "" : "hidden",
    ILLUSTRATION_ELEMENT_CLASS:
      illustrationElement?.elementClass ?? "top-[12%] right-[10%] rotate-12 text-black h-20 w-20 rounded-full border-[3px] border-current bg-transparent"
  };

  const templateMarkup = loadTemplateMarkup(selectedTemplate.id);
  const visualLayers = resolveVisualLayerSettings(selectedTemplate, templateMarkup);
  const content = interpolateTemplate(templateMarkup, tokens, slotValues, {
    renderSlot: (slotKey, value) => renderSlotRichText(slotKey, value, slotFieldTypeByKey.get(slotKey)),
    renderToken: (tokenKey, value) => renderTokenRichText(tokenKey, value)
  });

  return renderDocumentShell({
    width: format.width,
    height: format.height,
    templateId: selectedTemplate.id,
    frameTone,
    colorSwapMode,
    title: params.title,
    imageUrl: params.imageUrl,
    content,
    visualLayers,
    brandIcon,
    shouldInvertBrandIcon
  });
}

function buildDefaultIllustrationSeed(
  kind: TemplateKind,
  templateId: string,
  params: BaseTemplateParams | CarouselTemplateParams
): string {
  const parts = [
    kind,
    templateId,
    params.title,
    params.caption,
    params.imageUrl,
    params.brandName
  ];
  if (kind === "carousel-post") {
    const carouselParams = params as CarouselTemplateParams;
    parts.push(carouselParams.heading, carouselParams.body, String(carouselParams.slideNumber), String(carouselParams.totalSlides));
  }
  return parts
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .join("|")
    .slice(0, 220);
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
  // Dark-first default across templates unless a template explicitly opts into "default".
  return "dark";
}

function normalizeFrameTone(value: unknown): "default" | "dark" | undefined {
  if (value === "default" || value === "dark") {
    return value;
  }
  return undefined;
}

function interpolateTemplate(
  template: string,
  tokens: Record<string, string>,
  slots: Record<string, string>,
  options?: {
    renderToken?: (tokenKey: string, value: string) => string;
    renderSlot?: (slotKey: string, value: string) => string;
  }
): string {
  return template.replace(/\{\{\s*([A-Za-z0-9_:-]+)\s*\}\}/g, (_match, rawKey: string) => {
    const key = rawKey.trim();
    const slotRawMatch = key.match(/^slot_raw:(.+)$/i);
    if (slotRawMatch?.[1]) {
      const slotKey = normalizeSlotKey(slotRawMatch[1]);
      const slotValue = slots[slotKey] ?? "";
      return escapeHtml(slotValue);
    }

    const slotMatch = key.match(/^slot:(.+)$/i);
    if (slotMatch?.[1]) {
      const slotKey = normalizeSlotKey(slotMatch[1]);
      const slotValue = slots[slotKey] ?? "";
      return options?.renderSlot ? options.renderSlot(slotKey, slotValue) : escapeHtml(slotValue);
    }

    const normalizedTokenKey = key.toUpperCase();
    const tokenValue = tokens[normalizedTokenKey] ?? "";
    return options?.renderToken ? options.renderToken(normalizedTokenKey, tokenValue) : tokenValue;
  });
}

type RichRenderMode = "inline" | "block";
type ColorSwapMode = "normal" | "swap";

function renderTokenRichText(tokenKey: string, value: string): string {
  const rawValue = value.trim();
  if (!rawValue) {
    return "";
  }
  if (!RICH_TEXT_TOKEN_KEYS.has(tokenKey)) {
    return escapeHtml(value);
  }
  const mode: RichRenderMode = BLOCK_RICH_TOKEN_KEYS.has(tokenKey) ? "block" : "inline";
  return renderRichText(value, mode);
}

function renderSlotRichText(
  slotKey: string,
  value: string,
  fieldType?: TemplateFieldDeclaration["type"]
): string {
  const rawValue = value.trim();
  if (!rawValue) {
    return "";
  }
  if (fieldType && fieldType !== "text") {
    return escapeHtml(rawValue);
  }
  const mode = resolveSlotRenderMode(slotKey, rawValue);
  return renderRichText(rawValue, mode);
}

function resolveSlotRenderMode(slotKey: string, value: string): RichRenderMode {
  if (INLINE_SLOT_PATTERN.test(slotKey)) {
    return "inline";
  }
  if (BLOCK_SLOT_PATTERN.test(slotKey)) {
    return "block";
  }
  if (MARKDOWN_BLOCK_HINT_PATTERN.test(value)) {
    return "block";
  }
  return "inline";
}

function renderRichText(value: string, mode: RichRenderMode): string {
  const normalized = value.trim();
  if (!normalized) {
    return "";
  }

  const { markdownSource, replacements } = buildRichTextReplacements(normalized, mode);
  const rendered = mode === "block" ? MARKDOWN.render(markdownSource) : MARKDOWN.renderInline(markdownSource);
  let html = rendered.trim();

  for (const [token, replacement] of replacements.entries()) {
    html = html.replaceAll(token, replacement);
  }

  if (!html) {
    return "";
  }
  if (mode === "block") {
    return `<div class="rich-text rich-text-block">${html}</div>`;
  }
  return `<span class="rich-text rich-text-inline">${html}</span>`;
}

function buildRichTextReplacements(
  input: string,
  mode: RichRenderMode
): {
  markdownSource: string;
  replacements: Map<string, string>;
} {
  let markdownSource = input;
  const replacements = new Map<string, string>();
  let markerId = 0;
  const nextMarker = (name: string) => `@@${name}_${markerId++}@@`;

  markdownSource = markdownSource.replace(MERMAID_FENCE_PATTERN, (_match, rawCode: string) => {
    const marker = nextMarker("MERMAID");
    const code = rawCode.trim();
    if (!code) {
      replacements.set(marker, "");
      return marker;
    }
    const modeClass = mode === "block" ? "rich-mermaid-block" : "rich-mermaid-inline";
    replacements.set(
      marker,
      `<span class="rich-mermaid ${modeClass}" data-mermaid="${encodeURIComponent(code)}"></span>`
    );
    return marker;
  });

  markdownSource = markdownSource.replace(BLOCK_MATH_PATTERN, (_match, expression: string) => {
    const marker = nextMarker("MATH_BLOCK");
    replacements.set(marker, renderMathMarkup(expression, true));
    return marker;
  });

  markdownSource = markdownSource.replace(INLINE_MATH_PATTERN, (_match, expression: string) => {
    const marker = nextMarker("MATH_INLINE");
    replacements.set(marker, renderMathMarkup(expression, false));
    return marker;
  });

  return { markdownSource, replacements };
}

function renderMathMarkup(expression: string, displayMode: boolean): string {
  const formula = expression.trim();
  if (!formula) {
    return "";
  }
  try {
    const rendered = katex.renderToString(formula, {
      displayMode,
      throwOnError: false,
      strict: "ignore",
      output: "mathml"
    });
    const modeClass = displayMode ? "rich-math-block" : "rich-math-inline";
    return `<span class="rich-math ${modeClass}">${rendered}</span>`;
  } catch {
    const fallback = displayMode ? `$$${formula}$$` : `$${formula}$`;
    return `<span class="rich-math-fallback">${escapeHtml(fallback)}</span>`;
  }
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
  colorSwapMode: ColorSwapMode;
  title: string;
  imageUrl: string;
  content: string;
  visualLayers: VisualLayerSettings;
  brandIcon: BrandIconLayerSettings;
  shouldInvertBrandIcon: boolean;
}): string {
  const safeTitle = escapeHtml(args.title);
  const safeImageUrl = escapeHtml(args.imageUrl.trim());
  const hasImage = safeImageUrl.length > 0;
  const shouldRenderBackgroundImage = hasImage && args.visualLayers.useBackgroundImageOnly;
  const imageVisibilityClass = shouldRenderBackgroundImage ? "" : "hidden";
  const safeCss = TEMPLATE_CSS.replaceAll("</style", "<\\/style");
  const safeMermaidRuntime = (RUNTIME_SCRIPTS.mermaid ?? "").replaceAll("</script", "<\\/script");
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
      COLOR_SWAP_MODE: args.colorSwapMode,
      IMAGE_VISIBILITY_CLASS: imageVisibilityClass,
      IMAGE_URL: shouldRenderBackgroundImage ? safeImageUrl : "",
      BRAND_ICON_URL: escapeHtml(args.brandIcon.url),
      BRAND_ICON_TEXT: escapeHtml(args.brandIcon.text),
      BRAND_ICON_LEFT: formatCssNumber(args.brandIcon.left),
      BRAND_ICON_TOP: formatCssNumber(args.brandIcon.top),
      BRAND_ICON_SIZE: formatCssNumber(args.brandIcon.size),
      BRAND_ICON_OPACITY: formatCssNumber(args.brandIcon.opacity),
      BRAND_ICON_VISIBILITY_CLASS: args.brandIcon.visible ? "" : "hidden",
      BRAND_ICON_IMAGE_VISIBILITY_CLASS: args.brandIcon.useImage ? "" : "hidden",
      BRAND_ICON_INVERT_CLASS: args.shouldInvertBrandIcon ? "invert" : "",
      BRAND_ICON_TEXT_VISIBILITY_CLASS: args.brandIcon.useImage ? "hidden" : "",
      CONTENT: args.content,
      MERMAID_RUNTIME_JS: safeMermaidRuntime
    },
    {}
  );
}

interface VisualLayerSettings {
  useBackgroundImageOnly: boolean;
}

interface BrandIconLayerSettings {
  url: string;
  text: string;
  left: number;
  top: number;
  size: number;
  opacity: number;
  visible: boolean;
  useImage: boolean;
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

function resolveBrandIconLayerSettings(
  brandName: string,
  slots: Record<string, string>
): BrandIconLayerSettings {
  const defaultIconUrl = resolveDefaultBrandIconUrl();
  const resolvedIconUrl = sanitizeBrandIconUrl(slots.brand_icon_url, defaultIconUrl);
  const fallbackText = deriveBrandIconText(brandName);
  return {
    url: resolvedIconUrl,
    text: sanitizeBrandIconText(slots.brand_icon, fallbackText),
    left: parseClampedNumber(slots.brand_icon_x, 95.6, 0, 100),
    top: parseClampedNumber(slots.brand_icon_y, 96.3, 0, 100),
    size: parseClampedNumber(slots.brand_icon_size, 34, 18, 220),
    opacity: parseClampedNumber(slots.brand_icon_opacity, 0.95, 0.15, 1),
    visible: parseBooleanFlag(slots.brand_icon_visible, true),
    useImage: resolvedIconUrl.length > 0
  };
}

function resolveDefaultBrandIconUrl(): string {
  const brandConfig = (PIPELINE_CONFIG.brand ?? {}) as Record<string, unknown>;
  const configured =
    readStringValue(brandConfig.icon_svg_url) ??
    readStringValue(brandConfig.icon_url) ??
    "/images/brand/icon.svg";
  return sanitizeBrandIconUrl(configured, "/images/brand/icon.svg");
}

function readStringValue(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function sanitizeBrandIconUrl(rawValue: string | undefined, fallback: string): string {
  const fallbackTrimmed = fallback.trim();
  const candidate = rawValue?.trim() ?? "";
  const value = candidate || fallbackTrimmed;
  if (!value) {
    return "";
  }
  if (value.startsWith("/")) {
    return value;
  }
  if (/^https?:\/\/[A-Za-z0-9._~:/?#[\]@!$&'()*+,;=%-]+$/i.test(value)) {
    return value;
  }
  return fallbackTrimmed;
}

function deriveBrandIconText(brandName: string): string {
  const cleaned = brandName
    .replace(/[^A-Za-z0-9 ]+/g, " ")
    .trim();
  if (!cleaned) {
    return "BR";
  }

  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }
  return `${words[0][0] ?? ""}${words[1][0] ?? ""}`.toUpperCase();
}

function sanitizeBrandIconText(rawValue: string | undefined, fallback: string): string {
  if (!rawValue) {
    return fallback;
  }
  const cleaned = rawValue
    .trim()
    .replace(/[^A-Za-z0-9&+.-]/g, "")
    .slice(0, 6);
  return cleaned || fallback;
}

function parseClampedNumber(
  rawValue: string | undefined,
  fallback: number,
  min: number,
  max: number
): number {
  if (!rawValue) {
    return fallback;
  }
  const parsed = Number.parseFloat(rawValue.trim());
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, parsed));
}

function parseBooleanFlag(rawValue: string | undefined, fallback: boolean): boolean {
  if (!rawValue) {
    return fallback;
  }
  const normalized = rawValue.trim().toLowerCase();
  if (["0", "false", "off", "no", "hidden"].includes(normalized)) {
    return false;
  }
  if (["1", "true", "on", "yes", "show"].includes(normalized)) {
    return true;
  }
  return fallback;
}

function resolveColorSwapMode(slots: Record<string, string>): ColorSwapMode {
  for (const slotKey of COLOR_SWAP_SLOT_KEYS) {
    const parsed = parseBooleanSlot(slots[slotKey]);
    if (parsed === true) {
      return "swap";
    }
    if (parsed === false) {
      return "normal";
    }
  }
  return "normal";
}

function parseBooleanSlot(rawValue: string | undefined): boolean | undefined {
  if (!rawValue) {
    return undefined;
  }
  const normalized = rawValue.trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }
  if (["1", "true", "on", "yes", "swap", "invert", "black"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "off", "no", "normal", "default", "white"].includes(normalized)) {
    return false;
  }
  return undefined;
}

function formatCssNumber(value: number): string {
  return Number(value.toFixed(2)).toString();
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
  const defaultImageUrl = typeof defaults.image_url === "string" ? defaults.image_url : "";
  const slotValues = slotValuesFromQuery(url.searchParams) ?? {};
  const colorSwapOverride = colorSwapValueFromQuery(url.searchParams);
  if (colorSwapOverride) {
    slotValues.color_swap = colorSwapOverride;
  }
  const templateId = url.searchParams.get("templateId") ?? undefined;
  const title = url.searchParams.get("title") ?? defaults.title;
  const caption = url.searchParams.get("caption") ?? defaults.caption;
  if (!slotValues.illustration_seed) {
    const heading = kind === "carousel-post" ? url.searchParams.get("heading") ?? defaults.heading : "";
    const body = kind === "carousel-post" ? url.searchParams.get("body") ?? defaults.body : "";
    slotValues.illustration_seed = buildPreviewIllustrationSeed({
      kind,
      templateId,
      title,
      caption,
      heading,
      body
    });
  }
  const resolvedSlotValues = Object.keys(slotValues).length > 0 ? slotValues : undefined;

  const base: BaseTemplateParams = {
    title,
    caption,
    imageUrl: url.searchParams.get("imageUrl") ?? defaultImageUrl,
    brandName: url.searchParams.get("brand") ?? url.searchParams.get("brandName") ?? PIPELINE_CONFIG.brand.default_name,
    templateId,
    slots: resolvedSlotValues
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

function buildPreviewIllustrationSeed(args: {
  kind: TemplateKind;
  templateId?: string;
  title: string;
  caption: string;
  heading?: string;
  body?: string;
}): string {
  return [
    args.kind,
    args.templateId ?? "",
    args.title,
    args.caption,
    args.heading ?? "",
    args.body ?? ""
  ]
    .filter((part) => part.trim().length > 0)
    .join("|")
    .slice(0, 180);
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

function colorSwapValueFromQuery(searchParams: URLSearchParams): string | undefined {
  for (const [rawKey, rawValue] of searchParams.entries()) {
    const normalizedKey = rawKey.trim().toLowerCase();
    if (!(COLOR_SWAP_QUERY_KEYS as readonly string[]).includes(normalizedKey)) {
      continue;
    }
    const value = rawValue.trim();
    if (value) {
      return value;
    }
  }
  return undefined;
}
