import {
  createBrandTheme,
  getPresetStyle,
  renderTemplateHead,
  resolveFontProfileId,
  resolveTemplateControl,
  templateControlSetFromQuery,
  tokenOverridesFromQuery,
  type BrandTokenOverrides,
  type TemplateControlSet,
  type TemplateFormatKey
} from "./design-system";
import { PIPELINE_CONFIG, TEMPLATE_FILES } from "./generated/template-assets";

export type { BrandTokenOverrides, TemplateControlSet };

export type TemplateKind = TemplateFormatKey;
export type TemplateStyleId = keyof typeof PIPELINE_CONFIG.template_styles.styles;

interface TemplateDefinition {
  id: string;
  format: TemplateKind;
  style: string;
  label: string;
  default_for_style?: boolean;
  archetypes?: string[];
  file: string;
}

export interface TemplateStyleOption {
  id: string;
  label: string;
  description: string;
  llmHint: string;
}

export interface PostArchetypeOption {
  id: string;
  label: string;
  description: string;
  llmHint: string;
}

export interface SlotHintOption {
  id: string;
  hint: string;
  defaultValue: string;
}

export interface BaseTemplateParams {
  title: string;
  caption: string;
  imageUrl: string;
  brandColor: string;
  brandName: string;
  templateStyle?: string;
  templateId?: string;
  templateArchetype?: string;
  fontProfile?: string;
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

export function getDefaultTemplateStyle(): string {
  return PIPELINE_CONFIG.template_styles.default_style;
}

export function normalizeTemplateStyle(value: string | undefined | null): string {
  if (!value) {
    return getDefaultTemplateStyle();
  }

  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return getDefaultTemplateStyle();
  }

  const styles = PIPELINE_CONFIG.template_styles.styles as Record<string, unknown>;
  return styles[normalized] ? normalized : getDefaultTemplateStyle();
}

export function listTemplateStyles(): TemplateStyleOption[] {
  const styles = PIPELINE_CONFIG.template_styles.styles;
  return Object.entries(styles).map(([id, detail]) => ({
    id,
    label: detail.label,
    description: detail.description,
    llmHint: detail.llm_hint
  }));
}

export function getDefaultPostArchetype(): string {
  return PIPELINE_CONFIG.post_archetypes.default_archetype;
}

export function normalizePostArchetype(value: string | undefined | null): string {
  if (!value) {
    return getDefaultPostArchetype();
  }

  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return getDefaultPostArchetype();
  }

  const archetypes = PIPELINE_CONFIG.post_archetypes.archetypes as Record<string, unknown>;
  return archetypes[normalized] ? normalized : getDefaultPostArchetype();
}

export function listPostArchetypes(): PostArchetypeOption[] {
  const archetypes = PIPELINE_CONFIG.post_archetypes.archetypes;
  return Object.entries(archetypes).map(([id, detail]) => ({
    id,
    label: detail.label,
    description: detail.description,
    llmHint: detail.llm_hint
  }));
}

export function listSlotHints(): SlotHintOption[] {
  const hints = PIPELINE_CONFIG.slot_schema.slot_hints as Record<string, string>;
  const defaults = PIPELINE_CONFIG.slot_schema.defaults as Record<string, string>;
  return Object.entries(hints).map(([id, hint]) => ({
    id,
    hint,
    defaultValue: defaults[id] ?? ""
  }));
}

export function resolveTemplateId(kind: TemplateKind, options?: { templateStyle?: string; templateId?: string; templateArchetype?: string }): string {
  return selectTemplateDefinition(kind, options?.templateStyle, options?.templateId, options?.templateArchetype).id;
}

export function renderTemplate(kind: TemplateKind, params: BaseTemplateParams | CarouselTemplateParams): string {
  const format = PIPELINE_CONFIG.formats[kind];
  const selectedTemplate = selectTemplateDefinition(kind, params.templateStyle, params.templateId, params.templateArchetype);
  const control = resolveTemplateControl(kind, params.design, selectedTemplate.style);
  const normalizedArchetype = normalizePostArchetype(params.templateArchetype);
  const fontProfileId = resolveFontProfileId({
    requested: params.fontProfile,
    style: selectedTemplate.style,
    archetype: normalizedArchetype
  });

  const header = renderTopBar(
    kind,
    control,
    params.brandName,
    kind === "carousel-slide" ? `${(params as CarouselTemplateParams).slideNumber}/${(params as CarouselTemplateParams).totalSlides}` : undefined
  );
  const footer = renderMetaFooter(kind, control, defaultMetaLeft(kind), defaultMetaRight(kind));
  const kicker =
    kind === "carousel-slide" && control.showTitleKicker
      ? `<p class="text-[24px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]" style="max-width: ${control.contentMaxWidth}px;">${escapeHtml(params.title)}</p>`
      : "";

  const slotValues = resolveSlotValues(kind, params);

  const tokens: Record<string, string> = {
    TITLE: escapeHtml(params.title),
    CAPTION: escapeHtml(params.caption),
    HEADING: escapeHtml(kind === "carousel-slide" ? (params as CarouselTemplateParams).heading : params.title),
    BODY: escapeHtml(kind === "carousel-slide" ? (params as CarouselTemplateParams).body : params.caption),
    BRAND_NAME: escapeHtml(params.brandName),
    TEMPLATE_ARCHETYPE: escapeHtml(normalizedArchetype),
    HEADER: header,
    FOOTER: footer,
    KICKER: kicker,
    CONTENT_INSET: String(control.contentInset),
    CONTENT_MAX_WIDTH: String(control.contentMaxWidth),
    CAPTION_MAX_WIDTH: String(captionMaxWidth(kind, control.contentMaxWidth)),
    ALIGNMENT_STYLE: alignmentContainerStyle(control.textAlign)
  };

  const templateMarkup = loadTemplateMarkup(selectedTemplate.id);
  const content = interpolateTemplate(templateMarkup, tokens, slotValues);

  return renderFrame(
    {
      kind,
      width: format.width,
      height: format.height,
      params,
      control,
      content,
      fontProfileId
    },
    selectedTemplate.id,
    selectedTemplate.style,
    normalizedArchetype
  );
}

function selectTemplateDefinition(
  kind: TemplateKind,
  style?: string,
  requestedTemplateId?: string,
  archetype?: string
): TemplateDefinition {
  const byFormat = TEMPLATE_DEFINITIONS.filter((definition) => definition.format === kind);
  if (byFormat.length === 0) {
    throw new Error(`No templates configured for format ${kind}`);
  }

  if (requestedTemplateId) {
    const direct = byFormat.find((definition) => definition.id === requestedTemplateId.trim());
    if (direct) {
      return direct;
    }
  }

  const normalizedStyle = normalizeTemplateStyle(style);
  const normalizedArchetype = normalizePostArchetype(archetype);

  const styleAndArchetype = byFormat.filter(
    (definition) => definition.style === normalizedStyle && templateSupportsArchetype(definition, normalizedArchetype)
  );
  const styleAndArchetypePreferred = pickPreferredTemplate(styleAndArchetype, normalizedStyle);
  if (styleAndArchetypePreferred) {
    return styleAndArchetypePreferred;
  }

  const byArchetype = byFormat.filter((definition) => templateSupportsArchetype(definition, normalizedArchetype));
  const archetypePreferred = pickPreferredTemplate(byArchetype, normalizedStyle);
  if (archetypePreferred) {
    return archetypePreferred;
  }

  const byStyle = byFormat.filter((definition) => definition.style === normalizedStyle);
  const byStylePreferred = pickPreferredTemplate(byStyle, normalizedStyle);
  if (byStylePreferred) {
    return byStylePreferred;
  }

  const defaultId = PIPELINE_CONFIG.formats[kind].default_template_id;
  const defaultTemplate = byFormat.find((definition) => definition.id === defaultId);
  if (defaultTemplate) {
    return defaultTemplate;
  }

  return byFormat[0];
}

function pickPreferredTemplate(definitions: TemplateDefinition[], preferredStyle: string): TemplateDefinition | null {
  if (definitions.length === 0) {
    return null;
  }

  const styleDefault = definitions.find(
    (definition) => definition.style === preferredStyle && definition.default_for_style
  );
  if (styleDefault) {
    return styleDefault;
  }

  const styleMatch = definitions.find((definition) => definition.style === preferredStyle);
  if (styleMatch) {
    return styleMatch;
  }

  const genericDefault = definitions.find((definition) => definition.default_for_style);
  if (genericDefault) {
    return genericDefault;
  }

  return definitions[0];
}

function templateSupportsArchetype(definition: TemplateDefinition, archetype: string): boolean {
  if (!definition.archetypes || definition.archetypes.length === 0) {
    return true;
  }
  return definition.archetypes.includes(archetype);
}

function loadTemplateMarkup(templateId: string): string {
  const key = templateId as keyof typeof TEMPLATE_FILES;
  const content = TEMPLATE_FILES[key];
  if (!content) {
    throw new Error(`Template file not found for id ${templateId}`);
  }
  return content;
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

function resolveSlotValues(kind: TemplateKind, params: BaseTemplateParams | CarouselTemplateParams): Record<string, string> {
  const defaults = PIPELINE_CONFIG.slot_schema.defaults as Record<string, string>;
  const resolved: Record<string, string> = {};

  for (const [slotKey, slotValue] of Object.entries(defaults)) {
    const normalizedKey = normalizeSlotKey(slotKey);
    resolved[normalizedKey] = expandSlotDefault(slotValue, kind, params);
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

  resolved.headline = resolved.headline || params.title;
  resolved.subheadline = resolved.subheadline || params.caption;
  resolved.short_hook = resolved.short_hook || params.title;
  resolved.supporting_line = resolved.supporting_line || params.caption;
  resolved.insight_line = resolved.insight_line || params.caption;
  resolved.heading = resolved.heading || params.title;
  resolved.body = resolved.body || params.caption;

  if (kind === "carousel-slide") {
    const carouselParams = params as CarouselTemplateParams;
    resolved.headline = carouselParams.heading;
    resolved.body = carouselParams.body;
    resolved.step_number = resolved.step_number || String(carouselParams.slideNumber);
    resolved.step_total = resolved.step_total || String(carouselParams.totalSlides);
  }

  return resolved;
}

function expandSlotDefault(value: string, kind: TemplateKind, params: BaseTemplateParams | CarouselTemplateParams): string {
  const source = value.trim();
  if (!source) {
    return "";
  }

  return source.replace(/\{\{\s*([A-Z_]+)\s*\}\}/g, (_match, rawToken: string) => {
    if (rawToken === "TITLE") {
      return params.title;
    }
    if (rawToken === "CAPTION") {
      return params.caption;
    }
    if (rawToken === "BRAND_NAME") {
      return params.brandName;
    }
    if (rawToken === "HEADING") {
      return kind === "carousel-slide" ? (params as CarouselTemplateParams).heading : params.title;
    }
    if (rawToken === "BODY") {
      return kind === "carousel-slide" ? (params as CarouselTemplateParams).body : params.caption;
    }
    return "";
  });
}

function normalizeSlotKey(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function captionMaxWidth(kind: TemplateKind, contentMaxWidth: number): number {
  const rules = PIPELINE_CONFIG.render.caption_width_rules[kind];
  return Math.min(Number(rules.max), contentMaxWidth + Number(rules.add));
}

function renderFrame(
  args: {
    kind: TemplateKind;
    width: number;
    height: number;
    params: BaseTemplateParams;
    control: ReturnType<typeof resolveTemplateControl>;
    content: string;
    fontProfileId: string;
  },
  templateId: string,
  templateStyle: string,
  templateArchetype: string
): string {
  const theme = createBrandTheme({
    brandName: args.params.brandName,
    brandColor: args.params.brandColor,
    overrides: args.params.brandTokens
  });

  const preset = getPresetStyle(args.control.preset);

  const safeTitle = escapeHtml(args.params.title);
  const safeImageUrl = escapeHtml(args.params.imageUrl.trim());
  const hasImage = safeImageUrl.length > 0;

  const rootVars = [
    `--frame-bg:${preset.containerBackground}`,
    `--frame-overlay-top:${preset.overlayTop}`,
    `--frame-overlay-bottom:${preset.overlayBottom}`,
    `--frame-vignette:${preset.vignette}`,
    `--frame-brand-pill-bg:${preset.brandPillBackground}`,
    `--frame-brand-pill-border:${preset.brandPillBorder}`,
    `--frame-brand-pill-text:${preset.brandPillText}`,
    `--frame-title-shadow:${preset.titleShadow}`,
    `--frame-caption-shadow:${preset.captionShadow}`,
    `--frame-grain-opacity:${preset.grainOpacity}`,
    `--frame-image-opacity:${args.control.imageOpacity}`
  ].join(";");

  return `
    <!doctype html>
    <html>
      ${renderTemplateHead({ safeTitle, width: args.width, height: args.height, theme, fontProfileId: args.fontProfileId })}
      <body>
        <div class="relative isolate overflow-hidden" data-template-id="${escapeHtml(templateId)}" data-template-style="${escapeHtml(templateStyle)}" data-template-archetype="${escapeHtml(templateArchetype)}" style="width: ${args.width}px; height: ${args.height}px; ${rootVars}">
          <div class="absolute inset-0" style="background: var(--frame-bg);"></div>

          ${
            hasImage
              ? `<div class="absolute inset-0 bg-cover bg-center" style="background-image: url('${safeImageUrl}'); opacity: var(--frame-image-opacity);"></div>`
              : ""
          }

          <div class="absolute inset-0" style="background: var(--frame-overlay-top), var(--frame-overlay-bottom), var(--frame-vignette);"></div>

          <div class="absolute inset-0" style="opacity: var(--frame-grain-opacity); background-image: radial-gradient(${PIPELINE_CONFIG.render.frame_decor.grain_dot_color} ${PIPELINE_CONFIG.render.frame_decor.grain_dot_size_px}px, transparent ${PIPELINE_CONFIG.render.frame_decor.grain_dot_size_px}px); background-size: ${PIPELINE_CONFIG.render.frame_decor.grain_bg_size_px}px ${PIPELINE_CONFIG.render.frame_decor.grain_bg_size_px}px;"></div>

          <div class="absolute inset-0 border" style="border-color: color-mix(in srgb, var(--color-border-subtle) ${PIPELINE_CONFIG.render.frame_decor.border_alpha_percent}%, transparent);"></div>

          ${args.content}
        </div>
      </body>
    </html>
  `;
}

function renderTopBar(
  kind: TemplateKind,
  control: ReturnType<typeof resolveTemplateControl>,
  brandName: string,
  slideLabel?: string
): string {
  const left = control.showBrandBadge ? renderBrandPill(brandName) : "";
  const showSlide = kind === "carousel-slide" && control.showSlideBadge && slideLabel;
  const right = showSlide ? renderBrandPill(slideLabel as string) : "";

  if (!left && !right) {
    return "";
  }

  return `<div class="flex w-full items-center justify-between gap-5">${left}<span class="ml-auto">${right}</span></div>`;
}

function renderMetaFooter(
  kind: TemplateKind,
  control: ReturnType<typeof resolveTemplateControl>,
  defaultLeft: string,
  defaultRight: string
): string {
  if (!control.showMetaFooter) {
    return "";
  }

  const left = control.metaLeftText ?? defaultLeft;
  const right = control.metaRightText ?? defaultRight;

  return `
    <div class="mt-auto flex w-full items-center justify-between text-[18px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
      <span>${escapeHtml(left)}</span>
      <span>${escapeHtml(right)}</span>
    </div>
  `;
}

function defaultMetaLeft(kind: TemplateKind): string {
  return PIPELINE_CONFIG.render.meta_left_labels[kind] ?? "";
}

function defaultMetaRight(_kind: TemplateKind): string {
  return PIPELINE_CONFIG.render.meta_right_labels[_kind] ?? "";
}

function renderBrandPill(label: string): string {
  return `<span class="inline-flex w-fit items-center rounded-full border px-4 py-2 text-[16px] font-semibold uppercase tracking-[0.08em]" style="border-color: var(--frame-brand-pill-border); color: var(--frame-brand-pill-text); background: var(--frame-brand-pill-bg);">${escapeHtml(label)}</span>`;
}

function alignmentContainerStyle(alignment: "left" | "center"): string {
  if (alignment === "center") {
    return "align-items: center; text-align: center;";
  }
  return "align-items: flex-start; text-align: left;";
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
    templateStyle: url.searchParams.get("templateStyle") ?? undefined,
    templateId: url.searchParams.get("templateId") ?? undefined,
    templateArchetype: url.searchParams.get("templateArchetype") ?? url.searchParams.get("archetype") ?? undefined,
    fontProfile: url.searchParams.get("fontProfile") ?? undefined,
    slots: slotValues,
    brandTokens: tokenOverridesFromQuery(url.searchParams),
    design: templateControlSetFromQuery(url.searchParams)
  };

  if (kind !== "carousel-slide") {
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
