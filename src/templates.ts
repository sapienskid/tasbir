import {
  brandConfig,
  createBrandTheme,
  renderTemplateHead,
  resolveTemplateControl,
  templateControlSetFromQuery,
  tokenOverridesFromQuery,
  type BrandIconPosition,
  type BrandTokenOverrides,
  type ResolvedTemplateControl,
  type TemplateControlSet,
  type TemplateFormatKey
} from "./template-theme";
import { PIPELINE_CONFIG, TEMPLATE_FILES } from "./generated/template-assets";

export type { BrandTokenOverrides, TemplateControlSet };

export type TemplateKind = TemplateFormatKey;

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

type FrameTone = "default" | "dark";

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
  brandColor: string;
  brandName: string;
  templateId?: string;
  slots?: Record<string, string>;
  brandTokens?: BrandTokenOverrides;
  design?: TemplateControlSet;
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
  useBackgroundImageOnly: true,
  useHtmlDecorLayers: true
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

  // Auto-discover from slot tokens in HTML
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
  const control = resolveTemplateControl(kind, params.design);
  const safeImageUrl = escapeHtml(params.imageUrl);

  const header = renderTopBar(
    kind,
    control,
    params.brandName,
    kind === "carousel-post" ? `${(params as CarouselTemplateParams).slideNumber}/${(params as CarouselTemplateParams).totalSlides}` : undefined
  );
  const footer = renderMetaFooter(kind, control, defaultMetaLeft(kind), defaultMetaRight(kind));
  const kicker = renderKicker(kind, control, params.title);

  const slotValues = resolveSlotValues(kind, params, selectedTemplate.id);

  const tokens: Record<string, string> = {
    TITLE: escapeHtml(params.title),
    CAPTION: escapeHtml(params.caption),
    HEADING: escapeHtml(kind === "carousel-post" ? (params as CarouselTemplateParams).heading : params.title),
    BODY: escapeHtml(kind === "carousel-post" ? (params as CarouselTemplateParams).body : params.caption),
    IMAGE_URL: safeImageUrl,
    BRAND_NAME: escapeHtml(params.brandName),
    HEADER: header,
    FOOTER: footer,
    KICKER: kicker
  };

  const templateMarkup = loadTemplateMarkup(selectedTemplate.id);
  const frameTone = resolveFrameTone(selectedTemplate);
  const visualLayers = resolveVisualLayerSettings(selectedTemplate, templateMarkup);
  const content = interpolateTemplate(templateMarkup, tokens, slotValues);

  return renderFrame(
    {
      kind,
      width: format.width,
      height: format.height,
      params,
      control,
      content,
      frameTone,
      visualLayers
    },
    selectedTemplate.id
  );
}

function selectTemplateDefinition(
  kind: TemplateKind,
  requestedTemplateId?: string
): TemplateDefinition {
  if (TEMPLATE_DEFINITIONS.length === 0) {
    throw new Error(`No templates found. Add HTML files to the templates/ directory.`);
  }

  // If user/AI explicitly requests a template by ID, honour it
  if (requestedTemplateId) {
    const direct = TEMPLATE_DEFINITIONS.find(
      (d) => d.id === requestedTemplateId.trim() && templateSupportsFormat(d, kind)
    );
    if (direct) return direct;
    // Unknown ID — fall through to format default (don't 404)
    console.warn(`Unknown templateId "${requestedTemplateId}" — falling back to format default`);
  }

  // Use the format's configured default
  const defaultId = PIPELINE_CONFIG.formats[kind].default_template_id;
  const defaultTemplate = TEMPLATE_DEFINITIONS.find((d) => d.id === defaultId && templateSupportsFormat(d, kind));
  if (defaultTemplate) return defaultTemplate;

  // Ultimate fallback: first template compatible with this format
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

function resolveFrameTone(template: TemplateDefinition): FrameTone {
  const explicitTone = normalizeFrameTone(template.frameTone);
  if (explicitTone) {
    return explicitTone;
  }
  return "default";
}

function normalizeFrameTone(value: unknown): FrameTone | undefined {
  if (value === "default" || value === "dark") {
    return value;
  }
  return undefined;
}

function normalizeBackgroundImageMode(value: unknown): "global" | "inline" | undefined {
  if (value === "global" || value === "inline") {
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

  // 1. Apply field defaults from template declaration
  const fields = listTemplateFields(templateId);
  for (const field of fields) {
    const normalizedKey = normalizeSlotKey(field.key);
    if (normalizedKey && field.default) {
      resolved[normalizedKey] = field.default;
    }
  }

  // 2. Apply structural fallbacks (heading/body/headline/subheadline)
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

  // 3. Apply carousel-specific overrides
  if (kind === "carousel-post") {
    const carouselParams = params as CarouselTemplateParams;
    resolved.headline = carouselParams.heading;
    resolved.body = carouselParams.body;
    resolved.item_title = carouselParams.heading;
    resolved.item_body = carouselParams.body;
    resolved.step_number = String(carouselParams.slideNumber);
    resolved.step_total = String(carouselParams.totalSlides);
  }

  // 4. Apply user-provided slot overrides (highest priority)
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

function renderFrame(
  args: {
    kind: TemplateKind;
    width: number;
    height: number;
    params: BaseTemplateParams;
    control: ResolvedTemplateControl;
    content: string;
    frameTone: FrameTone;
    visualLayers: VisualLayerSettings;
  },
  templateId: string
): string {
  const theme = createBrandTheme({
    brandName: args.params.brandName,
    brandColor: args.params.brandColor,
    overrides: args.params.brandTokens
  });
  applyFrameToneToTheme(theme, args.frameTone);

  const safeTitle = escapeHtml(args.params.title);
  const safeImageUrl = escapeHtml(args.params.imageUrl.trim());
  const hasImage = safeImageUrl.length > 0;
  const shouldRenderBackgroundImage = hasImage && args.visualLayers.useBackgroundImageOnly;
  const imageVisibilityClass = shouldRenderBackgroundImage ? "" : "hidden";

  const brandIconUrl = escapeHtml(args.control.brandIconUrl.trim());
  const hasBrandIcon = brandIconUrl.length > 0;
  const brandIconCornerClass = hasBrandIcon
    ? brandIconCornerClassName(args.control.brandIconPosition)
    : "hidden";

  const frameShell = loadTemplateMarkup("@system/frame-shell");
  return interpolateTemplate(
    frameShell,
    {
      HEAD_HTML: renderTemplateHead({ safeTitle, width: args.width, height: args.height, theme }),
      TEMPLATE_ID: escapeHtml(templateId),
      FRAME_TONE: args.frameTone,
      IMAGE_VISIBILITY_CLASS: imageVisibilityClass,
      IMAGE_URL: safeImageUrl,
      BRAND_ICON_CORNER_CLASS: brandIconCornerClass,
      BRAND_ICON_URL: brandIconUrl,
      CONTENT: args.content
    },
    {}
  );
}

function applyFrameToneToTheme(
  theme: ReturnType<typeof createBrandTheme>,
  frameTone: FrameTone
): void {
  if (frameTone !== "dark") {
    return;
  }

  theme.tokens.primaryText = "#f2f2f2";
  theme.tokens.secondaryText = "#d1d1d1";
  theme.tokens.mutedText = "#9a9a9a";
  theme.tokens.surfaceBase = "#070707";
  theme.tokens.surfaceElevated = "#131313";
  theme.tokens.borderSubtle = "#2b2b2b";
}

interface VisualLayerSettings {
  useBackgroundImageOnly: boolean;
  useHtmlDecorLayers: boolean;
}

function resolveVisualLayerSettings(
  template: TemplateDefinition,
  templateMarkup: string
): VisualLayerSettings {
  const defaults: VisualLayerSettings = {
    useBackgroundImageOnly: DEFAULT_VISUAL_LAYERS.useBackgroundImageOnly,
    useHtmlDecorLayers: DEFAULT_VISUAL_LAYERS.useHtmlDecorLayers
  };

  const renderConfig = (PIPELINE_CONFIG as unknown as {
    render?: {
      visual_layers?: {
        use_background_image_only?: boolean;
        use_html_decor_layers?: boolean;
      };
    };
  }).render;
  const visual = renderConfig?.visual_layers;
  const configured: VisualLayerSettings = {
    useBackgroundImageOnly: visual?.use_background_image_only ?? defaults.useBackgroundImageOnly,
    useHtmlDecorLayers: visual?.use_html_decor_layers ?? defaults.useHtmlDecorLayers
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

  // Fallback when metadata is missing: templates with inline IMAGE_URL usage disable global background image.
  if (/\{\{\s*IMAGE_URL\s*\}\}/i.test(templateMarkup)) {
    configured.useBackgroundImageOnly = false;
  }

  return configured;
}

function renderTopBar(
  kind: TemplateKind,
  control: ResolvedTemplateControl,
  brandName: string,
  slideLabel?: string
): string {
  const showLeft = control.showBrandBadge;
  const showRight = kind === "carousel-post" && control.showSlideBadge && Boolean(slideLabel?.trim());
  const showTopBar = showLeft || showRight;
  const brandIconUrl = escapeHtml(control.brandIconUrl.trim());
  const hasBrandIcon = brandIconUrl.length > 0;

  return renderSystemFragment("@system/top-bar-shell", {
    TOP_BAR_VISIBILITY_CLASS: showTopBar ? "" : "hidden",
    LEFT_PILL_VISIBILITY_CLASS: showLeft ? "" : "hidden",
    RIGHT_PILL_VISIBILITY_CLASS: showRight ? "" : "hidden",
    LEFT_LABEL: escapeHtml(brandName),
    RIGHT_LABEL: escapeHtml(slideLabel ?? ""),
    BRAND_ICON_VISIBILITY_CLASS: hasBrandIcon ? "" : "hidden",
    BRAND_ICON_URL: brandIconUrl
  });
}

function renderMetaFooter(
  kind: TemplateKind,
  control: ResolvedTemplateControl,
  defaultLeft: string,
  defaultRight: string
): string {
  const left = control.metaLeftText ?? defaultLeft;
  const right = control.metaRightText ?? defaultRight;

  return renderSystemFragment("@system/meta-footer-shell", {
    META_FOOTER_VISIBILITY_CLASS: control.showMetaFooter ? "" : "hidden",
    META_LEFT_LABEL: escapeHtml(left),
    META_RIGHT_LABEL: escapeHtml(right)
  });
}

function renderKicker(
  kind: TemplateKind,
  control: ResolvedTemplateControl,
  title: string
): string {
  const shouldShowKicker = kind === "carousel-post" && control.showTitleKicker;
  return renderSystemFragment("@system/kicker-shell", {
    KICKER_VISIBILITY_CLASS: shouldShowKicker ? "" : "hidden",
    KICKER_TEXT: escapeHtml(title)
  });
}

function defaultMetaLeft(kind: TemplateKind): string {
  const formatConfig = PIPELINE_CONFIG.formats?.[kind] as { meta_left_label?: string } | undefined;
  return formatConfig?.meta_left_label ?? "";
}

function defaultMetaRight(kind: TemplateKind): string {
  const formatConfig = PIPELINE_CONFIG.formats?.[kind] as { meta_right_label?: string } | undefined;
  return formatConfig?.meta_right_label ?? "";
}

function brandIconCornerClassName(position: BrandIconPosition): string {
  switch (position) {
    case "top-left":
      return "top-0 left-0";
    case "top-right":
      return "top-0 right-0";
    case "bottom-left":
      return "bottom-0 left-0";
    case "bottom-right":
      return "bottom-0 right-0";
    default:
      return "top-0 left-0";
  }
}

function renderSystemFragment(templateId: string, tokens: Record<string, string>): string {
  const template = loadTemplateMarkup(templateId);
  return template.replace(/\{\{\s*([A-Z0-9_:-]+)\s*\}\}/g, (_match, rawKey: string) => {
    const key = rawKey.trim().toUpperCase();
    return tokens[key] ?? "";
  });
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
    brandColor: url.searchParams.get("brandingColor") ?? PIPELINE_CONFIG.brand.default_color,
    brandName: url.searchParams.get("brand") ?? url.searchParams.get("brandName") ?? PIPELINE_CONFIG.brand.default_name,
    templateId: url.searchParams.get("templateId") ?? undefined,
    slots: slotValues,
    brandTokens: tokenOverridesFromQuery(url.searchParams),
    design: templateControlSetFromQuery(url.searchParams)
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
