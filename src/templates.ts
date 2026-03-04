import {
  createBrandTheme,
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
  format?: TemplateKind;
  formats?: readonly TemplateKind[];
  style?: string;
  styles?: readonly string[];
  label: string;
  default_for_style?: boolean;
  archetypes?: readonly string[];
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
  const requestedTemplateStyle = normalizeTemplateStyle(params.templateStyle);
  const selectedTemplate = selectTemplateDefinition(kind, requestedTemplateStyle, params.templateId, params.templateArchetype);
  const resolvedTemplateStyle = resolveTemplateStyleForTemplate(selectedTemplate, requestedTemplateStyle);
  const control = resolveTemplateControl(kind, params.design, resolvedTemplateStyle);
  const normalizedArchetype = normalizePostArchetype(params.templateArchetype);
  const fontProfileId = resolveFontProfileId({
    requested: params.fontProfile,
    style: resolvedTemplateStyle,
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
      ? `<p class="kicker content-max">${escapeHtml(params.title)}</p>`
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
    ALIGN_CLASS: alignmentClassName(control.textAlign)
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
    resolvedTemplateStyle,
    normalizedArchetype
  );
}

function selectTemplateDefinition(
  kind: TemplateKind,
  style?: string,
  requestedTemplateId?: string,
  archetype?: string
): TemplateDefinition {
  const byFormat = TEMPLATE_DEFINITIONS.filter((definition) => templateSupportsFormat(definition, kind));
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

  const styleAndExactArchetype = byFormat.filter(
    (definition) => templateSupportsStyle(definition, normalizedStyle) && templateHasExplicitArchetype(definition, normalizedArchetype)
  );
  const styleAndExactArchetypePreferred = pickPreferredTemplate(styleAndExactArchetype, normalizedStyle);
  if (styleAndExactArchetypePreferred) {
    return styleAndExactArchetypePreferred;
  }

  const styleAndArchetype = byFormat.filter(
    (definition) => templateSupportsStyle(definition, normalizedStyle) && templateSupportsArchetype(definition, normalizedArchetype)
  );
  const styleAndArchetypePreferred = pickPreferredTemplate(styleAndArchetype, normalizedStyle);
  if (styleAndArchetypePreferred) {
    return styleAndArchetypePreferred;
  }

  const exactArchetype = byFormat.filter((definition) => templateHasExplicitArchetype(definition, normalizedArchetype));
  const exactArchetypePreferred = pickPreferredTemplate(exactArchetype, normalizedStyle);
  if (exactArchetypePreferred) {
    return exactArchetypePreferred;
  }

  const byArchetype = byFormat.filter((definition) => templateSupportsArchetype(definition, normalizedArchetype));
  const archetypePreferred = pickPreferredTemplate(byArchetype, normalizedStyle);
  if (archetypePreferred) {
    return archetypePreferred;
  }

  const byStyle = byFormat.filter((definition) => templateSupportsStyle(definition, normalizedStyle));
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
    (definition) => templateSupportsStyle(definition, preferredStyle) && definition.default_for_style
  );
  if (styleDefault) {
    return styleDefault;
  }

  const styleMatch = definitions.find((definition) => templateSupportsStyle(definition, preferredStyle));
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

function templateHasExplicitArchetype(definition: TemplateDefinition, archetype: string): boolean {
  if (!definition.archetypes || definition.archetypes.length === 0) {
    return false;
  }
  return definition.archetypes.includes(archetype);
}

function templateSupportsFormat(definition: TemplateDefinition, kind: TemplateKind): boolean {
  const formats = definition.formats?.map((format) => format.trim()).filter(Boolean) ?? [];
  if (formats.length > 0) {
    return formats.includes(kind);
  }

  if (definition.format) {
    return definition.format === kind;
  }

  return true;
}

function templateSupportsStyle(definition: TemplateDefinition, style: string): boolean {
  return templateStyles(definition).includes(style);
}

function resolveTemplateStyleForTemplate(definition: TemplateDefinition, requestedStyle: string): string {
  if (templateSupportsStyle(definition, requestedStyle)) {
    return requestedStyle;
  }

  const styles = templateStyles(definition);
  return styles[0] ?? getDefaultTemplateStyle();
}

function templateStyles(definition: TemplateDefinition): string[] {
  const normalizedStyles = (definition.styles ?? [])
    .map((style) => style.trim().toLowerCase())
    .filter(Boolean);

  if (normalizedStyles.length > 0) {
    return [...new Set(normalizedStyles)];
  }

  if (definition.style) {
    const style = definition.style.trim().toLowerCase();
    if (style) {
      return [style];
    }
  }

  return [getDefaultTemplateStyle()];
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

function styleClassForTemplateStyle(templateStyle: string): string {
  const normalized = normalizeTemplateStyle(templateStyle);
  const styleClassMap: Record<string, string> = {
    editorial: "style-editorial",
    illustration: "style-illustration",
    minimal: "style-minimal",
    bold: "style-bold",
    data: "style-data",
    "monochrome-swiss": "style-monochrome-swiss",
    brutal: "style-brutal"
  };

  return styleClassMap[normalized] ?? "style-default";
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

  const widthScale = args.width / 1080;
  const heightScale = args.height / 1080;
  const layoutScale = Math.max(0.55, Math.min(1.9, Math.min(widthScale, heightScale)));
  const contentMax = args.control.contentMaxWidth;
  const captionMax = captionMaxWidth(args.kind, contentMax);
  const styleClass = styleClassForTemplateStyle(templateStyle);

  const safeTitle = escapeHtml(args.params.title);
  const safeImageUrl = escapeHtml(args.params.imageUrl.trim());
  const hasImage = safeImageUrl.length > 0;
  const visualLayers = resolveVisualLayerSettings(templateStyle);
  const shouldRenderBackgroundImage = hasImage && visualLayers.useBackgroundImageOnly;
  const isDataImage = safeImageUrl.startsWith("data:image/");
  const imageFilter = isDataImage ? "blur(1.8px) saturate(0.88)" : "none";
  const imageTransform = isDataImage ? "scale(1.04)" : "none";
  const overlayOpacity = shouldRenderBackgroundImage ? (isDataImage ? 0.84 : 0.72) : 0.56;
  const overlayBackground = shouldRenderBackgroundImage
    ? "var(--frame-overlay-top), var(--frame-overlay-bottom), var(--frame-vignette)"
    : "var(--frame-overlay-top), var(--frame-vignette)";
  const accentSweepOpacity = shouldRenderBackgroundImage ? 0.42 : 0.16;
  const decorLayerMarkup =
    args.control.showDecorLayers && visualLayers.useHtmlDecorLayers
      ? renderDecorativeHtmlLayers({
          profile: visualLayers.styleProfile,
          kind: args.kind,
          hasBackgroundImage: shouldRenderBackgroundImage
        })
      : "";

  const rootVars = [
    `--content-inset:${args.control.contentInset}px`,
    `--content-max-width:${contentMax}px`,
    `--caption-max-width:${captionMax}px`,
    `--layout-scale:${layoutScale.toFixed(4)}`,
    `--layout-width-scale:${widthScale.toFixed(4)}`,
    `--layout-height-scale:${heightScale.toFixed(4)}`
  ];
  if (typeof args.control.imageOpacity === "number") {
    rootVars.push(`--frame-image-opacity:${args.control.imageOpacity}`);
  }
  const rootStyle = `width: ${args.width}px; height: ${args.height}px; ${rootVars.join(";")}`;

  return `
    <!doctype html>
    <html>
      ${renderTemplateHead({ safeTitle, width: args.width, height: args.height, theme, fontProfileId: args.fontProfileId })}
      <body>
        <div class="relative isolate overflow-hidden ${styleClass}" data-template-id="${escapeHtml(templateId)}" data-template-style="${escapeHtml(templateStyle)}" data-template-archetype="${escapeHtml(templateArchetype)}" style="${rootStyle}">
          <div class="absolute inset-0" style="background: var(--frame-bg);"></div>

          ${
            shouldRenderBackgroundImage
              ? `<div class="absolute inset-0 bg-cover bg-center" style="background-image: url('${safeImageUrl}'); opacity: var(--frame-image-opacity); filter: ${imageFilter}; transform: ${imageTransform};"></div>`
              : ""
          }
          ${decorLayerMarkup}

          <div class="absolute inset-0" style="opacity: ${overlayOpacity}; background: ${overlayBackground};"></div>
          <div class="absolute inset-0" style="background: linear-gradient(140deg, color-mix(in srgb, var(--color-brand-accent) 18%, transparent), transparent 56%); opacity: ${accentSweepOpacity};"></div>

          <div class="absolute inset-0" style="opacity: var(--frame-grain-opacity); background-image: radial-gradient(${PIPELINE_CONFIG.render.frame_decor.grain_dot_color} ${PIPELINE_CONFIG.render.frame_decor.grain_dot_size_px}px, transparent ${PIPELINE_CONFIG.render.frame_decor.grain_dot_size_px}px); background-size: ${PIPELINE_CONFIG.render.frame_decor.grain_bg_size_px}px ${PIPELINE_CONFIG.render.frame_decor.grain_bg_size_px}px;"></div>

          <div class="absolute inset-0 border" style="border-color: color-mix(in srgb, var(--color-border-subtle) ${PIPELINE_CONFIG.render.frame_decor.border_alpha_percent}%, transparent);"></div>

          ${args.content}
        </div>
      </body>
    </html>
  `;
}

interface VisualLayerSettings {
  useBackgroundImageOnly: boolean;
  useHtmlDecorLayers: boolean;
  styleProfile: string;
}

function resolveVisualLayerSettings(templateStyle: string): VisualLayerSettings {
  const defaults: VisualLayerSettings = {
    useBackgroundImageOnly: true,
    useHtmlDecorLayers: true,
    styleProfile: "soft-orbital"
  };

  const renderConfig = PIPELINE_CONFIG.render as unknown as {
    visual_layers?: {
      use_background_image_only?: boolean;
      use_html_decor_layers?: boolean;
      style_profiles?: Record<string, string>;
    };
  };
  const visual = renderConfig.visual_layers;
  if (!visual) {
    return defaults;
  }

  const styleProfiles = visual.style_profiles ?? {};
  const normalizedStyle = normalizeTemplateStyle(templateStyle);
  const styleProfile = styleProfiles[normalizedStyle] ?? styleProfiles[getDefaultTemplateStyle()] ?? defaults.styleProfile;

  return {
    useBackgroundImageOnly: visual.use_background_image_only ?? defaults.useBackgroundImageOnly,
    useHtmlDecorLayers: visual.use_html_decor_layers ?? defaults.useHtmlDecorLayers,
    styleProfile: styleProfile.trim() || defaults.styleProfile
  };
}

function renderDecorativeHtmlLayers(args: {
  profile: string;
  kind: TemplateKind;
  hasBackgroundImage: boolean;
}): string {
  const opacityBoost = args.hasBackgroundImage ? 0.76 : 1;
  const profile = args.profile.trim().toLowerCase();

  if (profile === "playful-blobs") {
    return `
      <div class="absolute inset-0" style="opacity: ${0.62 * opacityBoost};">
        <div class="absolute" style="left: -14%; top: -8%; width: calc(560px * var(--layout-scale)); height: calc(560px * var(--layout-scale)); border-radius: 42% 58% 38% 62%; background: radial-gradient(circle at 28% 32%, color-mix(in srgb, var(--color-brand-glow) 68%, transparent), transparent 64%);"></div>
        <div class="absolute" style="right: -10%; bottom: -12%; width: calc(460px * var(--layout-scale)); height: calc(460px * var(--layout-scale)); border-radius: 62% 38% 58% 42%; background: radial-gradient(circle at 56% 44%, color-mix(in srgb, var(--color-brand-accent) 56%, transparent), transparent 62%);"></div>
      </div>
    `;
  }

  if (profile === "subtle-grid") {
    return `
      <div class="absolute inset-0" style="opacity: ${0.42 * opacityBoost}; background-image: linear-gradient(to right, color-mix(in srgb, var(--color-border-subtle) 28%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in srgb, var(--color-border-subtle) 24%, transparent) 1px, transparent 1px); background-size: calc(78px * var(--layout-scale)) calc(78px * var(--layout-scale));"></div>
      <div class="absolute inset-0" style="opacity: ${0.24 * opacityBoost}; background: radial-gradient(circle at 18% 12%, color-mix(in srgb, var(--color-brand-accent) 22%, transparent), transparent 48%);"></div>
    `;
  }

  if (profile === "angular-burst") {
    return `
      <div class="absolute inset-0" style="opacity: ${0.64 * opacityBoost};">
        <div class="absolute" style="right: -16%; top: -18%; width: calc(680px * var(--layout-scale)); height: calc(560px * var(--layout-scale)); background: linear-gradient(140deg, color-mix(in srgb, var(--color-brand-accent) 46%, transparent), transparent 68%); transform: rotate(-14deg);"></div>
        <div class="absolute" style="left: -18%; bottom: -20%; width: calc(560px * var(--layout-scale)); height: calc(420px * var(--layout-scale)); background: linear-gradient(28deg, color-mix(in srgb, var(--color-brand-glow) 40%, transparent), transparent 72%); transform: rotate(8deg);"></div>
      </div>
    `;
  }

  if (profile === "metric-grid") {
    const vertical = args.kind === "instagram-story" ? 16 : 10;
    return `
      <div class="absolute inset-0" style="opacity: ${0.5 * opacityBoost}; background-image: linear-gradient(to right, color-mix(in srgb, var(--color-border-subtle) 32%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in srgb, var(--color-border-subtle) 26%, transparent) 1px, transparent 1px); background-size: calc(88px * var(--layout-scale)) calc(88px * var(--layout-scale));"></div>
      <div class="absolute inset-0" style="opacity: ${0.34 * opacityBoost}; background: repeating-linear-gradient(90deg, color-mix(in srgb, var(--color-brand-accent) 28%, transparent) 0 calc(${vertical}px * var(--layout-scale)), transparent calc(${vertical}px * var(--layout-scale)) calc(${vertical * 2}px * var(--layout-scale)));"></div>
    `;
  }

  if (profile === "swiss-grid") {
    return `
      <div class="absolute inset-0" style="opacity: ${0.34 * opacityBoost}; background-image: linear-gradient(to right, color-mix(in srgb, #ffffff 30%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in srgb, #ffffff 24%, transparent) 1px, transparent 1px); background-size: calc(70px * var(--layout-scale)) calc(70px * var(--layout-scale));"></div>
      <div class="absolute" style="left: 0; top: 50%; width: 100%; height: 1px; opacity: ${0.32 * opacityBoost}; background: color-mix(in srgb, #ffffff 36%, transparent);"></div>
      <div class="absolute" style="left: 50%; top: 0; width: 1px; height: 100%; opacity: ${0.32 * opacityBoost}; background: color-mix(in srgb, #ffffff 36%, transparent);"></div>
    `;
  }

  if (profile === "cutout-noise") {
    return `
      <div class="absolute inset-0" style="opacity: ${0.62 * opacityBoost};">
        <div class="absolute" style="left: -12%; top: 12%; width: calc(520px * var(--layout-scale)); height: calc(180px * var(--layout-scale)); background: linear-gradient(102deg, color-mix(in srgb, var(--color-brand-accent) 56%, transparent), transparent 72%); transform: rotate(-8deg);"></div>
        <div class="absolute" style="right: -14%; bottom: 14%; width: calc(580px * var(--layout-scale)); height: calc(210px * var(--layout-scale)); background: linear-gradient(284deg, color-mix(in srgb, #ffffff 26%, transparent), transparent 70%); transform: rotate(9deg);"></div>
      </div>
    `;
  }

  return `
    <div class="absolute inset-0" style="opacity: ${0.52 * opacityBoost};">
      <div class="absolute" style="left: -10%; top: -14%; width: calc(540px * var(--layout-scale)); height: calc(540px * var(--layout-scale)); border-radius: 999px; background: radial-gradient(circle at 42% 34%, color-mix(in srgb, var(--color-brand-glow) 52%, transparent), transparent 66%);"></div>
      <div class="absolute" style="right: -16%; bottom: -18%; width: calc(620px * var(--layout-scale)); height: calc(620px * var(--layout-scale)); border-radius: 999px; background: radial-gradient(circle at 46% 48%, color-mix(in srgb, var(--color-brand-accent) 34%, transparent), transparent 68%);"></div>
    </div>
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
    <div class="meta-footer">
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
  return `<span class="brand-pill">${escapeHtml(label)}</span>`;
}

function alignmentClassName(alignment: "left" | "center"): string {
  if (alignment === "center") {
    return "align-center";
  }
  return "align-left";
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
