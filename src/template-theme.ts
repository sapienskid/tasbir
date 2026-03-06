import { PIPELINE_CONFIG, TEMPLATE_CSS, TEMPLATE_FILES } from "./generated/template-assets";

export type TemplateFormatKey = string;

export type ContentPosition = "top" | "center" | "bottom";
export type BrandIconPosition = "top-left" | "top-right" | "bottom-left" | "bottom-right";

export interface BrandTokenOverrides {
  primaryText?: string;
  secondaryText?: string;
  mutedText?: string;
  surfaceBase?: string;
  surfaceElevated?: string;
  borderSubtle?: string;
  accent?: string;
  accentForeground?: string;
}

export interface TemplateControl {
  showBrandBadge?: boolean;
  showSlideBadge?: boolean;
  showMetaFooter?: boolean;
  showTitleKicker?: boolean;
  showDecorLayers?: boolean;
  textAlign?: "left" | "center" | "justify";
  contentPosition?: ContentPosition;
  imageOpacity?: number;
  contentMaxWidth?: number;
  contentInset?: number;
  metaLeftText?: string;
  metaRightText?: string;
  brandIconUrl?: string;
  brandIconPosition?: BrandIconPosition;
}

export interface TemplateControlSet extends TemplateControl {
  formatOverrides?: Partial<Record<TemplateFormatKey, TemplateControl>>;
}

interface BrandTokens {
  primaryText: string;
  secondaryText: string;
  mutedText: string;
  surfaceBase: string;
  surfaceElevated: string;
  borderSubtle: string;
  accent: string;
  accentForeground: string;
  accentGlow: string;
  overlayStrong: string;
  shadowColor: string;
  radiusCard: string;
  radiusPill: string;
}

export interface BrandTheme {
  brandName: string;
  tokens: BrandTokens;
}

export interface ResolvedTemplateControl {
  showBrandBadge: boolean;
  showSlideBadge: boolean;
  showMetaFooter: boolean;
  showTitleKicker: boolean;
  showDecorLayers: boolean;
  textAlign: "left" | "center" | "justify";
  contentPosition: ContentPosition;
  imageOpacity?: number;
  contentMaxWidth: number;
  contentInset: number;
  metaLeftText?: string;
  metaRightText?: string;
  brandIconUrl: string;
  brandIconPosition: BrandIconPosition;
}

interface ThemingConfig {
  readable_light_text: string;
  readable_dark_text: string;
  color_engine: {
    surface_base_mix_target: string;
    surface_base_mix_ratio_from_target: number;
    surface_base_fallback: string;
    surface_elevated_mix_target: string;
    surface_elevated_mix_ratio_from_target: number;
    surface_elevated_fallback: string;
    border_subtle_mix_target: string;
    border_subtle_mix_ratio_from_target: number;
    border_subtle_fallback: string;
    secondary_text_mix_target: string;
    secondary_text_mix_ratio_from_target: number;
    secondary_text_fallback: string;
    muted_text_mix_target: string;
    muted_text_mix_ratio_from_target: number;
    muted_text_fallback: string;
    accent_glow_mix_target: string;
    accent_glow_mix_ratio_from_target: number;
    overlay_strong_mix_target: string;
    overlay_strong_mix_ratio_from_target: number;
    shadow_color_mix_target: string;
    shadow_color_mix_ratio_from_target: number;
    primary_text_min_contrast: number;
    secondary_text_min_contrast?: number;
    muted_text_min_contrast?: number;
    border_subtle_min_contrast?: number;
    accent_foreground_min_contrast: number;
  };
  radius: {
    card: string;
    pill: string;
  };
}

interface BrandConfig {
  default_name: string;
  default_color: string;
  default_icon?: string;
}

interface LayoutControlDefaults {
  contentMaxWidth: number;
  contentInset: number;
  textAlign: "left" | "center" | "justify";
  captionWidthAdd: number;
  captionWidthMax: number;
}

const DEFAULT_BRAND: BrandConfig = {
  default_name: "Brand",
  default_color: "#000000",
  default_icon: ""
};

const FALLBACK_THEME: ThemingConfig = {
  readable_light_text: "#ffffff",
  readable_dark_text: "#000000",
  color_engine: {
    surface_base_mix_target: "#ffffff",
    surface_base_mix_ratio_from_target: 1.0,
    surface_base_fallback: "#ffffff",
    surface_elevated_mix_target: "#f5f5f5",
    surface_elevated_mix_ratio_from_target: 1.0,
    surface_elevated_fallback: "#f5f5f5",
    border_subtle_mix_target: "#000000",
    border_subtle_mix_ratio_from_target: 1.0,
    border_subtle_fallback: "#000000",
    secondary_text_mix_target: "#333333",
    secondary_text_mix_ratio_from_target: 1.0,
    secondary_text_fallback: "#333333",
    muted_text_mix_target: "#888888",
    muted_text_mix_ratio_from_target: 1.0,
    muted_text_fallback: "#888888",
    accent_glow_mix_target: "#000000",
    accent_glow_mix_ratio_from_target: 1.0,
    overlay_strong_mix_target: "#000000",
    overlay_strong_mix_ratio_from_target: 0.4,
    shadow_color_mix_target: "#000000",
    shadow_color_mix_ratio_from_target: 0.5,
    primary_text_min_contrast: 4.5,
    secondary_text_min_contrast: 3.8,
    muted_text_min_contrast: 3,
    border_subtle_min_contrast: 1.5,
    accent_foreground_min_contrast: 4
  },
  radius: {
    card: "0px",
    pill: "0px"
  }
};

const CONTROL_DEFAULTS = {
  showBrandBadge: true,
  showSlideBadge: false,
  showMetaFooter: false,
  showTitleKicker: true,
  showDecorLayers: false,
  textAlign: "left" as const,
  contentPosition: "bottom" as ContentPosition,
  brandIconPosition: "top-left" as BrandIconPosition
};

const FALLBACK_LAYOUT_DEFAULTS: LayoutControlDefaults = {
  contentMaxWidth: 1020,
  contentInset: 64,
  textAlign: "left",
  captionWidthAdd: 30,
  captionWidthMax: 980
};

const DESIGN_PROMPT_DIRECTIVES = [
  "Treat templates as structure-only skeletons and place all design decisions through CSS tokens.",
  "Fill slot_content comprehensively so every likely template slot has useful copy.",
  "Never request generated text in images; typography is always rendered by the template system.",
  "Keep slot values concise, specific, and directly usable without extra formatting."
] as const;

export function brandConfig(): BrandConfig {
  return ((PIPELINE_CONFIG as unknown as { brand?: BrandConfig }).brand ?? DEFAULT_BRAND) as BrandConfig;
}

function themingConfig(): ThemingConfig {
  return ((PIPELINE_CONFIG as unknown as { theming?: ThemingConfig }).theming ?? FALLBACK_THEME) as ThemingConfig;
}

export function layoutDefaultsForFormat(kind: TemplateFormatKey): LayoutControlDefaults {
  const formatConfig = PIPELINE_CONFIG.formats?.[kind] as
    | { layout?: Partial<LayoutControlDefaults & { content_max_width?: number; content_inset?: number; text_align?: string; caption_width_add?: number; caption_width_max?: number }> }
    | undefined;
  const layout = formatConfig?.layout;
  if (!layout) {
    return { ...FALLBACK_LAYOUT_DEFAULTS };
  }

  return {
    contentMaxWidth: layout.content_max_width ?? layout.contentMaxWidth ?? FALLBACK_LAYOUT_DEFAULTS.contentMaxWidth,
    contentInset: layout.content_inset ?? layout.contentInset ?? FALLBACK_LAYOUT_DEFAULTS.contentInset,
    textAlign: parseTextAlign(layout.text_align ?? layout.textAlign) ?? FALLBACK_LAYOUT_DEFAULTS.textAlign,
    captionWidthAdd: layout.caption_width_add ?? layout.captionWidthAdd ?? FALLBACK_LAYOUT_DEFAULTS.captionWidthAdd,
    captionWidthMax: layout.caption_width_max ?? layout.captionWidthMax ?? FALLBACK_LAYOUT_DEFAULTS.captionWidthMax
  };
}

export function listTemplateCompositionDirectives(): string[] {
  return [...DESIGN_PROMPT_DIRECTIVES];
}

export function createBrandTheme(args: {
  brandName: string;
  brandColor: string;
  overrides?: BrandTokenOverrides;
}): BrandTheme {
  const theming = themingConfig();
  const engine = theming.color_engine;
  const lightText = theming.readable_light_text;
  const darkText = theming.readable_dark_text;

  const accent = normalizeHexColor(args.overrides?.accent ?? args.brandColor, brandConfig().default_color);
  const surfaceBase = normalizeHexColor(
    args.overrides?.surfaceBase ??
    mixHex(accent, engine.surface_base_mix_target, engine.surface_base_mix_ratio_from_target),
    engine.surface_base_fallback
  );
  const surfaceElevated = normalizeHexColor(
    args.overrides?.surfaceElevated ??
    mixHex(accent, engine.surface_elevated_mix_target, engine.surface_elevated_mix_ratio_from_target),
    engine.surface_elevated_fallback
  );
  const borderSubtle = normalizeHexColor(
    args.overrides?.borderSubtle ??
    mixHex(accent, engine.border_subtle_mix_target, engine.border_subtle_mix_ratio_from_target),
    engine.border_subtle_fallback
  );

  const primaryText = normalizeHexColor(
    args.overrides?.primaryText ?? pickReadableText(surfaceBase, lightText, darkText, engine.primary_text_min_contrast),
    lightText
  );
  const secondaryText = normalizeHexColor(
    args.overrides?.secondaryText ??
    mixHex(primaryText, engine.secondary_text_mix_target, engine.secondary_text_mix_ratio_from_target),
    engine.secondary_text_fallback
  );
  const mutedText = normalizeHexColor(
    args.overrides?.mutedText ?? mixHex(secondaryText, engine.muted_text_mix_target, engine.muted_text_mix_ratio_from_target),
    engine.muted_text_fallback
  );
  const accentForeground = normalizeHexColor(
    args.overrides?.accentForeground ??
    pickReadableText(accent, lightText, darkText, engine.accent_foreground_min_contrast),
    lightText
  );

  const secondaryMinContrast =
    typeof engine.secondary_text_min_contrast === "number" ? engine.secondary_text_min_contrast : 3.8;
  const mutedMinContrast =
    typeof engine.muted_text_min_contrast === "number" ? engine.muted_text_min_contrast : 3;
  const borderMinContrast =
    typeof engine.border_subtle_min_contrast === "number" ? engine.border_subtle_min_contrast : 1.5;

  const safePrimaryText = ensureReadableColor(surfaceBase, primaryText, engine.primary_text_min_contrast, lightText, darkText);
  const safeSecondaryText = ensureReadableColor(
    surfaceBase,
    secondaryText,
    secondaryMinContrast,
    safePrimaryText,
    pickReadableText(surfaceBase, lightText, darkText, secondaryMinContrast)
  );
  const safeMutedText = ensureReadableColor(
    surfaceBase,
    mutedText,
    mutedMinContrast,
    safeSecondaryText,
    pickReadableText(surfaceBase, lightText, darkText, mutedMinContrast)
  );
  const safeAccentForeground = ensureReadableColor(
    accent,
    accentForeground,
    engine.accent_foreground_min_contrast,
    lightText,
    darkText
  );
  const safeBorderSubtle = ensureReadableColor(
    surfaceBase,
    borderSubtle,
    borderMinContrast,
    mixHex(safePrimaryText, surfaceBase, 0.7),
    mixHex(safePrimaryText, surfaceBase, 0.8)
  );

  const tokens: BrandTokens = {
    primaryText: safePrimaryText,
    secondaryText: safeSecondaryText,
    mutedText: safeMutedText,
    surfaceBase,
    surfaceElevated,
    borderSubtle: safeBorderSubtle,
    accent,
    accentForeground: safeAccentForeground,
    accentGlow: mixHex(accent, engine.accent_glow_mix_target, engine.accent_glow_mix_ratio_from_target),
    overlayStrong: mixHex(surfaceBase, engine.overlay_strong_mix_target, engine.overlay_strong_mix_ratio_from_target),
    shadowColor: mixHex(accent, engine.shadow_color_mix_target, engine.shadow_color_mix_ratio_from_target),
    radiusCard: theming.radius.card,
    radiusPill: theming.radius.pill
  };

  return {
    brandName: args.brandName,
    tokens
  };
}

export function resolveTemplateControl(
  kind: TemplateFormatKey,
  set?: TemplateControlSet
): ResolvedTemplateControl {
  const layout = layoutDefaultsForFormat(kind);
  const defaultIconUrl = brandConfig().default_icon ?? "";

  const base: ResolvedTemplateControl = {
    showBrandBadge: CONTROL_DEFAULTS.showBrandBadge,
    showSlideBadge: CONTROL_DEFAULTS.showSlideBadge,
    showMetaFooter: CONTROL_DEFAULTS.showMetaFooter,
    showTitleKicker: CONTROL_DEFAULTS.showTitleKicker,
    showDecorLayers: CONTROL_DEFAULTS.showDecorLayers,
    textAlign: layout.textAlign,
    contentPosition: CONTROL_DEFAULTS.contentPosition,
    contentMaxWidth: layout.contentMaxWidth,
    contentInset: layout.contentInset,
    brandIconUrl: defaultIconUrl,
    brandIconPosition: CONTROL_DEFAULTS.brandIconPosition
  };

  const mergedGlobal = mergeControl(base, set);
  const mergedFormat = mergeControl(mergedGlobal, set?.formatOverrides?.[kind]);

  return {
    ...mergedFormat,
    imageOpacity:
      typeof mergedFormat.imageOpacity === "number" ? clamp(mergedFormat.imageOpacity, 0, 1) : undefined
  };
}

export function renderTemplateHead(args: {
  safeTitle: string;
  width: number;
  height: number;
  theme: BrandTheme;
}): string {
  const t = args.theme.tokens;
  const safeCss = TEMPLATE_CSS.replaceAll("</style", "<\\/style");
  return renderSystemTemplate("@system/head-shell", {
    SAFE_TITLE: args.safeTitle,
    TEMPLATE_CSS: safeCss,
    CANVAS_WIDTH: String(args.width),
    CANVAS_HEIGHT: String(args.height),
    TOKEN_PRIMARY_TEXT: t.primaryText,
    TOKEN_SECONDARY_TEXT: t.secondaryText,
    TOKEN_MUTED_TEXT: t.mutedText,
    TOKEN_SURFACE_BASE: t.surfaceBase,
    TOKEN_SURFACE_ELEVATED: t.surfaceElevated,
    TOKEN_BORDER_SUBTLE: t.borderSubtle,
    TOKEN_ACCENT: t.accent,
    TOKEN_ACCENT_FOREGROUND: t.accentForeground,
    TOKEN_ACCENT_GLOW: t.accentGlow,
    TOKEN_OVERLAY_STRONG: t.overlayStrong,
    TOKEN_SHADOW_COLOR: t.shadowColor,
    TOKEN_RADIUS_CARD: t.radiusCard,
    TOKEN_RADIUS_PILL: t.radiusPill
  });
}

export function tokenOverridesFromQuery(searchParams: URLSearchParams): BrandTokenOverrides | undefined {
  const overrides: BrandTokenOverrides = {
    primaryText: searchParams.get("tokenPrimaryText") ?? undefined,
    secondaryText: searchParams.get("tokenSecondaryText") ?? undefined,
    mutedText: searchParams.get("tokenMutedText") ?? undefined,
    surfaceBase: searchParams.get("tokenSurfaceBase") ?? undefined,
    surfaceElevated: searchParams.get("tokenSurfaceElevated") ?? undefined,
    borderSubtle: searchParams.get("tokenBorderSubtle") ?? undefined,
    accent: searchParams.get("tokenAccent") ?? undefined,
    accentForeground: searchParams.get("tokenAccentForeground") ?? undefined
  };

  const hasAny = Object.values(overrides).some((value) => typeof value === "string" && value.trim().length > 0);
  return hasAny ? overrides : undefined;
}

export function templateControlSetFromQuery(searchParams: URLSearchParams): TemplateControlSet | undefined {
  const control: TemplateControlSet = {
    showBrandBadge: parseBoolean(searchParams.get("showBrandBadge")),
    showSlideBadge: parseBoolean(searchParams.get("showSlideBadge")),
    showMetaFooter: parseBoolean(searchParams.get("showMetaFooter")),
    showTitleKicker: parseBoolean(searchParams.get("showTitleKicker")),
    showDecorLayers: parseBoolean(searchParams.get("showDecorLayers")),
    textAlign: parseTextAlign(searchParams.get("textAlign")),
    contentPosition: parseContentPosition(searchParams.get("contentPosition")),
    imageOpacity: parseNumber(searchParams.get("imageOpacity")),
    contentMaxWidth: parseNumber(searchParams.get("contentMaxWidth")),
    contentInset: parseNumber(searchParams.get("contentInset")),
    metaLeftText: searchParams.get("metaLeftText") ?? undefined,
    metaRightText: searchParams.get("metaRightText") ?? undefined,
    brandIconUrl: searchParams.get("brandIconUrl") ?? undefined,
    brandIconPosition: parseBrandIconPosition(searchParams.get("brandIconPosition"))
  };

  const hasAny = Object.entries(control).some(([key, value]) => key !== "formatOverrides" && value !== undefined);
  return hasAny ? control : undefined;
}

function mergeControl(base: ResolvedTemplateControl, override?: TemplateControl): ResolvedTemplateControl {
  if (!override) {
    return base;
  }

  return {
    ...base,
    showBrandBadge: override.showBrandBadge ?? base.showBrandBadge,
    showSlideBadge: override.showSlideBadge ?? base.showSlideBadge,
    showMetaFooter: override.showMetaFooter ?? base.showMetaFooter,
    showTitleKicker: override.showTitleKicker ?? base.showTitleKicker,
    showDecorLayers: override.showDecorLayers ?? base.showDecorLayers,
    textAlign: parseTextAlign(override.textAlign) ?? base.textAlign,
    contentPosition: parseContentPosition(override.contentPosition) ?? base.contentPosition,
    imageOpacity: override.imageOpacity ?? base.imageOpacity,
    contentMaxWidth: override.contentMaxWidth ?? base.contentMaxWidth,
    contentInset: override.contentInset ?? base.contentInset,
    metaLeftText: override.metaLeftText ?? base.metaLeftText,
    metaRightText: override.metaRightText ?? base.metaRightText,
    brandIconUrl: override.brandIconUrl ?? base.brandIconUrl,
    brandIconPosition: parseBrandIconPosition(override.brandIconPosition) ?? base.brandIconPosition
  };
}

function parseTextAlign(value: string | null | undefined): "left" | "center" | "justify" | undefined {
  if (!value) {
    return undefined;
  }

  const normalized = value.trim().toLowerCase();
  if (normalized === "left" || normalized === "center" || normalized === "justify") {
    return normalized;
  }
  return undefined;
}

function parseContentPosition(value: string | null | undefined): ContentPosition | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "top" || normalized === "center" || normalized === "bottom") {
    return normalized;
  }
  return undefined;
}

function parseBrandIconPosition(value: string | null | undefined): BrandIconPosition | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (
    normalized === "top-left" ||
    normalized === "top-right" ||
    normalized === "bottom-left" ||
    normalized === "bottom-right"
  ) {
    return normalized as BrandIconPosition;
  }
  return undefined;
}

function parseBoolean(value: string | null): boolean | undefined {
  if (value === null) {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (["true", "1", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["false", "0", "no", "off"].includes(normalized)) {
    return false;
  }
  return undefined;
}

function parseNumber(value: string | null): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }
  return parsed;
}
function normalizeHexColor(value: string | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }
  const trimmed = value.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) {
    return trimmed.toLowerCase();
  }
  if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
    return `#${trimmed
      .slice(1)
      .split("")
      .map((part) => part + part)
      .join("")
      .toLowerCase()}`;
  }
  return fallback;
}

function mixHex(colorA: string, colorB: string, ratioFromB: number): string {
  const a = hexToRgb(colorA);
  const b = hexToRgb(colorB);
  if (!a || !b) {
    return colorA;
  }

  const t = clamp(ratioFromB, 0, 1);
  return rgbToHex({
    r: Math.round(a.r * (1 - t) + b.r * t),
    g: Math.round(a.g * (1 - t) + b.g * t),
    b: Math.round(a.b * (1 - t) + b.b * t)
  });
}

function pickReadableText(background: string, light: string, dark: string, minimumRatio: number): string {
  const lightRatio = contrastRatio(background, light);
  const darkRatio = contrastRatio(background, dark);

  if (lightRatio >= minimumRatio && lightRatio >= darkRatio) {
    return light;
  }
  if (darkRatio >= minimumRatio) {
    return dark;
  }
  return lightRatio >= darkRatio ? light : dark;
}

function ensureReadableColor(
  background: string,
  candidate: string,
  minimumRatio: number,
  fallbackA: string,
  fallbackB: string
): string {
  const candidateRatio = contrastRatio(background, candidate);
  if (candidateRatio >= minimumRatio) {
    return candidate;
  }
  const aRatio = contrastRatio(background, fallbackA);
  if (aRatio >= minimumRatio) {
    return fallbackA;
  }
  const bRatio = contrastRatio(background, fallbackB);
  if (bRatio >= minimumRatio) {
    return fallbackB;
  }

  if (candidateRatio >= aRatio && candidateRatio >= bRatio) {
    return candidate;
  }
  return aRatio >= bRatio ? fallbackA : fallbackB;
}

function contrastRatio(firstHex: string, secondHex: string): number {
  const first = hexToRgb(firstHex);
  const second = hexToRgb(secondHex);
  if (!first || !second) {
    return 1;
  }

  const l1 = relativeLuminance(first);
  const l2 = relativeLuminance(second);
  const brightest = Math.max(l1, l2);
  const darkest = Math.min(l1, l2);
  return (brightest + 0.05) / (darkest + 0.05);
}

function relativeLuminance(rgb: { r: number; g: number; b: number }): number {
  const normalized = [rgb.r, rgb.g, rgb.b].map((value) => {
    const channel = value / 255;
    if (channel <= 0.03928) {
      return channel / 12.92;
    }
    return Math.pow((channel + 0.055) / 1.055, 2.4);
  });

  return normalized[0] * 0.2126 + normalized[1] * 0.7152 + normalized[2] * 0.0722;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const normalized = normalizeHexColor(hex, "");
  if (!/^#[0-9a-f]{6}$/.test(normalized)) {
    return null;
  }
  const int = Number.parseInt(normalized.slice(1), 16);
  return {
    r: (int >> 16) & 255,
    g: (int >> 8) & 255,
    b: int & 255
  };
}

function rgbToHex(rgb: { r: number; g: number; b: number }): string {
  const toHexPart = (value: number) => clamp(Math.round(value), 0, 255).toString(16).padStart(2, "0");
  return `#${toHexPart(rgb.r)}${toHexPart(rgb.g)}${toHexPart(rgb.b)}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function renderSystemTemplate(templateId: string, tokens: Record<string, string>): string {
  const template = TEMPLATE_FILES[templateId];
  if (!template) {
    throw new Error(`Missing system template: ${templateId}`);
  }

  return template.replace(/\{\{\s*([A-Z0-9_:-]+)\s*\}\}/g, (_match, rawKey: string) => {
    const key = rawKey.trim().toUpperCase();
    return tokens[key] ?? "";
  });
}
