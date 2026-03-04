import { PIPELINE_CONFIG } from "./generated/template-assets";
import { TAILWIND_CSS } from "./styles/tailwind-css";

export type TemplateFormatKey = keyof typeof PIPELINE_CONFIG.formats;
export type TemplatePreset = keyof typeof PIPELINE_CONFIG.render.preset_styles;

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
  preset?: TemplatePreset;
  showBrandBadge?: boolean;
  showSlideBadge?: boolean;
  showMetaFooter?: boolean;
  showTitleKicker?: boolean;
  textAlign?: "left" | "center";
  imageOpacity?: number;
  contentMaxWidth?: number;
  contentInset?: number;
  metaLeftText?: string;
  metaRightText?: string;
}

export interface TemplateControlSet extends TemplateControl {
  formatOverrides?: Partial<Record<TemplateFormatKey, TemplateControl>>;
}

export interface TemplatePresetStyle {
  containerBackground: string;
  overlayTop: string;
  overlayBottom: string;
  vignette: string;
  brandPillBackground: string;
  brandPillBorder: string;
  brandPillText: string;
  titleShadow: string;
  captionShadow: string;
  grainOpacity: number;
  imageOpacity: number;
  typeScale: number;
  spaceScale: number;
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

interface ResolvedTemplateControl {
  preset: TemplatePreset;
  showBrandBadge: boolean;
  showSlideBadge: boolean;
  showMetaFooter: boolean;
  showTitleKicker: boolean;
  textAlign: "left" | "center";
  imageOpacity: number;
  contentMaxWidth: number;
  contentInset: number;
  metaLeftText?: string;
  metaRightText?: string;
}

export interface FontProfileOption {
  id: string;
  label: string;
  llmHint: string;
}

interface FontProfile {
  label: string;
  llm_hint: string;
  google_fonts_css2_query: string;
  display_font_css: string;
  body_font_css: string;
}

export function listFontProfiles(): FontProfileOption[] {
  const profiles = PIPELINE_CONFIG.typography.profiles as Record<string, FontProfile>;
  return Object.entries(profiles).map(([id, profile]) => ({
    id,
    label: profile.label,
    llmHint: profile.llm_hint
  }));
}

export function normalizeFontProfileId(value: string | undefined | null): string {
  const profiles = PIPELINE_CONFIG.typography.profiles as Record<string, FontProfile>;
  const fallback = PIPELINE_CONFIG.typography.default_font_profile;

  if (!value) {
    return fallback;
  }

  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return fallback;
  }

  return profiles[normalized] ? normalized : fallback;
}

export function resolveFontProfileId(args: {
  requested?: string;
  style?: string;
  archetype?: string;
}): string {
  if (args.requested) {
    return normalizeFontProfileId(args.requested);
  }

  const byStyle = PIPELINE_CONFIG.typography.selection.by_style as Record<string, string>;
  const byArchetype = PIPELINE_CONFIG.typography.selection.by_archetype as Record<string, string>;

  const style = args.style?.trim().toLowerCase() || "";
  const archetype = args.archetype?.trim().toLowerCase() || "";

  if (style && byStyle[style]) {
    return normalizeFontProfileId(byStyle[style]);
  }

  if (archetype && byArchetype[archetype]) {
    return normalizeFontProfileId(byArchetype[archetype]);
  }

  return normalizeFontProfileId(PIPELINE_CONFIG.typography.default_font_profile);
}

function getFontProfile(fontProfileId: string): FontProfile {
  const profiles = PIPELINE_CONFIG.typography.profiles as Record<string, FontProfile>;
  const normalized = normalizeFontProfileId(fontProfileId);
  return profiles[normalized];
}

export function createBrandTheme(args: {
  brandName: string;
  brandColor: string;
  overrides?: BrandTokenOverrides;
}): BrandTheme {
  const engine = PIPELINE_CONFIG.theming.color_engine;
  const lightText = PIPELINE_CONFIG.theming.readable_light_text;
  const darkText = PIPELINE_CONFIG.theming.readable_dark_text;

  const accent = normalizeHexColor(args.overrides?.accent ?? args.brandColor, PIPELINE_CONFIG.brand.default_color);
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
    radiusCard: PIPELINE_CONFIG.theming.radius.card,
    radiusPill: PIPELINE_CONFIG.theming.radius.pill
  };

  return {
    brandName: args.brandName,
    tokens
  };
}

export function resolveTemplateControl(
  kind: TemplateFormatKey,
  set?: TemplateControlSet,
  templateStyle?: string
): ResolvedTemplateControl {
  const baseDefaults = PIPELINE_CONFIG.render.control_defaults;
  const formatDefaults = PIPELINE_CONFIG.render.format_control_defaults[kind];
  const formatPreset = parsePreset(formatDefaults.default_preset) ?? firstPreset();
  const stylePresetMap = ((PIPELINE_CONFIG.render as unknown as { style_preset_map?: Record<string, string> }).style_preset_map ??
    {}) as Record<string, string>;
  const normalizedStyle = templateStyle?.trim().toLowerCase() ?? "";
  const stylePreset = normalizedStyle ? parsePreset(stylePresetMap[normalizedStyle]) : undefined;
  const basePreset = stylePreset ?? formatPreset;
  const presetStyle = getPresetStyle(basePreset);

  const base: ResolvedTemplateControl = {
    preset: basePreset,
    showBrandBadge: baseDefaults.showBrandBadge,
    showSlideBadge: baseDefaults.showSlideBadge,
    showMetaFooter: baseDefaults.showMetaFooter,
    showTitleKicker: baseDefaults.showTitleKicker,
    textAlign: parseTextAlign(formatDefaults.textAlign) ?? parseTextAlign(baseDefaults.textAlign) ?? "left",
    imageOpacity: presetStyle.imageOpacity,
    contentMaxWidth: Number(formatDefaults.contentMaxWidth),
    contentInset: Number(formatDefaults.contentInset)
  };

  const mergedGlobal = mergeControl(base, set);
  const mergedFormat = mergeControl(mergedGlobal, set?.formatOverrides?.[kind]);

  const resolvedPreset = parsePreset(mergedFormat.preset) ?? basePreset;
  return {
    ...mergedFormat,
    preset: resolvedPreset,
    imageOpacity: clamp(mergedFormat.imageOpacity, 0, 1)
  };
}

export function getPresetStyle(preset: TemplatePreset): TemplatePresetStyle {
  const presetStyles = PIPELINE_CONFIG.render.preset_styles as Record<string, TemplatePresetStyle>;
  const resolved = presetStyles[preset] ?? presetStyles[firstPreset()];
  return {
    ...resolved,
    typeScale: typeof resolved.typeScale === "number" ? resolved.typeScale : 1,
    spaceScale: typeof resolved.spaceScale === "number" ? resolved.spaceScale : 1
  };
}

export function renderTemplateHead(args: {
  safeTitle: string;
  width: number;
  height: number;
  theme: BrandTheme;
  fontProfileId?: string;
}): string {
  const t = args.theme.tokens;
  const safeTailwind = TAILWIND_CSS.replaceAll("</style", "<\\/style");
  const fontProfile = getFontProfile(args.fontProfileId ?? PIPELINE_CONFIG.typography.default_font_profile);
  const fontHref = `https://fonts.googleapis.com/css2?${fontProfile.google_fonts_css2_query}&display=swap`;

  return `
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>${args.safeTitle}</title>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
      <link href="${fontHref}" rel="stylesheet" />
      <style>${safeTailwind}</style>
      <style>
        :root {
          --canvas-width: ${args.width}px;
          --canvas-height: ${args.height}px;
          --font-display: ${fontProfile.display_font_css};
          --font-body: ${fontProfile.body_font_css};
          --color-text-primary: ${t.primaryText};
          --color-text-secondary: ${t.secondaryText};
          --color-text-muted: ${t.mutedText};
          --color-surface-base: ${t.surfaceBase};
          --color-surface-elevated: ${t.surfaceElevated};
          --color-border-subtle: ${t.borderSubtle};
          --color-brand-accent: ${t.accent};
          --color-brand-accent-foreground: ${t.accentForeground};
          --color-brand-glow: ${t.accentGlow};
          --color-overlay-strong: ${t.overlayStrong};
          --shadow-soft: 0 32px 88px color-mix(in srgb, ${t.shadowColor} 72%, transparent);
          --radius-card: ${t.radiusCard};
          --radius-pill: ${t.radiusPill};
        }
        * {
          box-sizing: border-box;
        }
        html,
        body {
          margin: 0;
          width: var(--canvas-width);
          height: var(--canvas-height);
          overflow: hidden;
          font-family: var(--font-body);
          background: var(--color-surface-base);
          color: var(--color-text-primary);
          text-rendering: optimizeLegibility;
          -webkit-font-smoothing: antialiased;
        }
        .text-balance {
          text-wrap: balance;
        }
        h1,
        h2,
        h3,
        p,
        li {
          overflow-wrap: anywhere;
          word-break: break-word;
        }
        .tabular-nums {
          font-variant-numeric: tabular-nums;
        }
      </style>
    </head>
  `;
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
    preset: parsePreset(searchParams.get("preset")),
    showBrandBadge: parseBoolean(searchParams.get("showBrandBadge")),
    showSlideBadge: parseBoolean(searchParams.get("showSlideBadge")),
    showMetaFooter: parseBoolean(searchParams.get("showMetaFooter")),
    showTitleKicker: parseBoolean(searchParams.get("showTitleKicker")),
    textAlign: parseTextAlign(searchParams.get("textAlign")),
    imageOpacity: parseNumber(searchParams.get("imageOpacity")),
    contentMaxWidth: parseNumber(searchParams.get("contentMaxWidth")),
    contentInset: parseNumber(searchParams.get("contentInset")),
    metaLeftText: searchParams.get("metaLeftText") ?? undefined,
    metaRightText: searchParams.get("metaRightText") ?? undefined
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
    preset: parsePreset(override.preset) ?? base.preset,
    showBrandBadge: override.showBrandBadge ?? base.showBrandBadge,
    showSlideBadge: override.showSlideBadge ?? base.showSlideBadge,
    showMetaFooter: override.showMetaFooter ?? base.showMetaFooter,
    showTitleKicker: override.showTitleKicker ?? base.showTitleKicker,
    textAlign: parseTextAlign(override.textAlign) ?? base.textAlign,
    imageOpacity: override.imageOpacity ?? base.imageOpacity,
    contentMaxWidth: override.contentMaxWidth ?? base.contentMaxWidth,
    contentInset: override.contentInset ?? base.contentInset,
    metaLeftText: override.metaLeftText ?? base.metaLeftText,
    metaRightText: override.metaRightText ?? base.metaRightText
  };
}

function parsePreset(value: string | null | undefined): TemplatePreset | undefined {
  if (!value) {
    return undefined;
  }

  const normalized = value.trim();
  const presets = PIPELINE_CONFIG.render.preset_styles as Record<string, unknown>;
  return (presets[normalized] ? normalized : undefined) as TemplatePreset | undefined;
}

function firstPreset(): TemplatePreset {
  const presets = Object.keys(PIPELINE_CONFIG.render.preset_styles);
  return presets[0] as TemplatePreset;
}

function parseTextAlign(value: string | null | undefined): "left" | "center" | undefined {
  if (!value) {
    return undefined;
  }

  const normalized = value.trim().toLowerCase();
  if (normalized === "left" || normalized === "center") {
    return normalized;
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
