// Central design token types and utilities — single source of truth for server and UI

// ─── Types ───────────────────────────────────────────────────────────────────

export interface DesignTokens {
  colors: {
    primary: Record<string, string>;
    secondary: Record<string, string>;
    accent: { light: string; base: string; dark: string };
    neutral: Record<string, string>;
    semantic: { success: string; warning: string; error: string; info: string };
    surface: { base: string; subtle: string; elevated: string; overlay: string };
    text: { primary: string; secondary: string; muted: string; inverse: string; accent: string; [key: string]: string };
  };
  typography: {
    fontSans: string;
    fontSerif: string;
    fontMono: string;
    scale: Record<string, number>;
    weights: Record<string, number>;
    tracking: Record<string, string>;
    leading: Record<string, number>;
  };
  spacing: { base: number; scale: number[] };
  border: {
    width: Record<string, string>;
    radius: Record<string, string>;
  };
  shadow: Record<string, string>;
  gradient: Record<string, string>;
  motion: {
    duration: Record<string, string>;
    easing: Record<string, string>;
  };
  component: {
    button: Record<string, string | number>;
    card: Record<string, string | number>;
    input: Record<string, string | number>;
    badge: Record<string, string | number>;
    nav: Record<string, string | number>;
  };
  meta: {
    vibeName: string;
    description: string;
    aesthetic: string;
    palette: string;
    instructions: string;
  };
}

const WCAG_AA_NORMAL_CONTRAST = 4.5;

function normalizeHexColor(value: string): string | null {
  const input = value.trim();
  const shortHex = /^#([0-9a-f]{3})$/i.exec(input);
  if (shortHex) {
    const [r, g, b] = shortHex[1].split("");
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  const longHex = /^#([0-9a-f]{6})$/i.exec(input);
  if (longHex) return `#${longHex[1].toLowerCase()}`;
  return null;
}

function relativeLuminance(hex: string): number {
  const normalized = normalizeHexColor(hex);
  if (!normalized) return 0;

  const r = parseInt(normalized.slice(1, 3), 16) / 255;
  const g = parseInt(normalized.slice(3, 5), 16) / 255;
  const b = parseInt(normalized.slice(5, 7), 16) / 255;
  const srgbToLinear = (channel: number): number =>
    channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);

  const rl = srgbToLinear(r);
  const gl = srgbToLinear(g);
  const bl = srgbToLinear(b);
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
}

function contrastRatio(foreground: string, background: string): number {
  const fg = normalizeHexColor(foreground);
  const bg = normalizeHexColor(background);
  if (!fg || !bg) return 1;
  const l1 = relativeLuminance(fg);
  const l2 = relativeLuminance(bg);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function pickBestForeground(background: string, candidates: string[]): { color: string; ratio: number } {
  let best = { color: "#000000", ratio: 1 };
  for (const candidate of candidates) {
    const normalizedCandidate = normalizeHexColor(candidate);
    if (!normalizedCandidate) continue;
    const ratio = contrastRatio(normalizedCandidate, background);
    if (ratio > best.ratio) best = { color: normalizedCandidate, ratio };
  }
  return best;
}

function ensureReadableTokenColor(
  existingColor: string | undefined,
  background: string | undefined,
  candidates: string[],
  minimumContrast = WCAG_AA_NORMAL_CONTRAST,
): string {
  const normalizedBg = background ? normalizeHexColor(background) : null;
  const normalizedExisting = existingColor ? normalizeHexColor(existingColor) : null;
  if (!normalizedBg) return normalizedExisting || "#000000";

  if (normalizedExisting && contrastRatio(normalizedExisting, normalizedBg) >= minimumContrast) {
    return normalizedExisting;
  }

  const fallbackCandidates = [...candidates, "#ffffff", "#111111"];
  const best = pickBestForeground(normalizedBg, fallbackCandidates);
  return best.color;
}

function cloneTokenRecord(tokens: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(tokens || {})) as Record<string, unknown>;
}

export function normalizeDesignTokensForRendering(tokens: Record<string, unknown>): Record<string, unknown> {
  const next = cloneTokenRecord(tokens);
  const colors = ((next.colors as Record<string, unknown> | undefined) || {}) as Record<string, unknown>;
  next.colors = colors;

  const neutral = ((colors.neutral as Record<string, unknown> | undefined) || {}) as Record<string, string>;
  const primary = ((colors.primary as Record<string, unknown> | undefined) || {}) as Record<string, string>;
  const secondary = ((colors.secondary as Record<string, unknown> | undefined) || {}) as Record<string, string>;
  const semantic = ((colors.semantic as Record<string, unknown> | undefined) || {}) as Record<string, string>;
  const accent = ((colors.accent as Record<string, unknown> | undefined) || {}) as Record<string, string>;
  const surface = ((colors.surface as Record<string, unknown> | undefined) || {}) as Record<string, string>;
  const text = ((colors.text as Record<string, unknown> | undefined) || {}) as Record<string, string>;

  colors.text = text;

  const baseCandidates = [
    text.primary,
    text.secondary,
    text.inverse,
    neutral["50"],
    neutral["100"],
    neutral["800"],
    neutral["900"],
  ].filter((v): v is string => typeof v === "string");

  const surfaceBase = typeof surface.base === "string" ? surface.base : undefined;
  const surfaceSubtle = typeof surface.subtle === "string" ? surface.subtle : surfaceBase;
  const surfaceElevated = typeof surface.elevated === "string" ? surface.elevated : surfaceSubtle;

  text.primary = ensureReadableTokenColor(text.primary, surfaceBase, baseCandidates);
  text.secondary = ensureReadableTokenColor(text.secondary, surfaceBase, baseCandidates);
  text.muted = ensureReadableTokenColor(text.muted, surfaceBase, baseCandidates, 3.0);
  text.inverse = ensureReadableTokenColor(text.inverse, text.primary, [neutral["50"], neutral["900"], "#ffffff", "#111111"]);

  text["on-surface-base"] = ensureReadableTokenColor(text["on-surface-base"], surfaceBase, baseCandidates);
  text["on-surface-subtle"] = ensureReadableTokenColor(text["on-surface-subtle"], surfaceSubtle, baseCandidates);
  text["on-surface-elevated"] = ensureReadableTokenColor(text["on-surface-elevated"], surfaceElevated, baseCandidates);

  text["on-primary"] = ensureReadableTokenColor(text["on-primary"], primary["500"], baseCandidates);
  text["on-secondary"] = ensureReadableTokenColor(text["on-secondary"], secondary["500"], baseCandidates);
  text["on-accent"] = ensureReadableTokenColor(text["on-accent"], accent.base, baseCandidates);
  text["on-success"] = ensureReadableTokenColor(text["on-success"], semantic.success, baseCandidates);
  text["on-warning"] = ensureReadableTokenColor(text["on-warning"], semantic.warning, baseCandidates);
  text["on-error"] = ensureReadableTokenColor(text["on-error"], semantic.error, baseCandidates);
  text["on-info"] = ensureReadableTokenColor(text["on-info"], semantic.info, baseCandidates);

  const accentCandidates = [text.accent, primary["500"], primary["600"], secondary["500"]].filter(
    (v): v is string => typeof v === "string",
  );
  text.accent = ensureReadableTokenColor(text.accent, surfaceBase, accentCandidates);

  return next;
}

// ─── Shadow fallbacks ────────────────────────────────────────────────────────

const SHADOW_FALLBACKS: Record<string, string> = {
  xs: '0 1px 2px rgba(2, 6, 23, 0.18)',
  sm: '0 2px 6px rgba(2, 6, 23, 0.2)',
  md: '0 8px 16px rgba(2, 6, 23, 0.22)',
  lg: '0 14px 28px rgba(2, 6, 23, 0.24)',
  xl: '0 24px 44px rgba(2, 6, 23, 0.28)',
  inner: 'inset 0 2px 6px rgba(2, 6, 23, 0.2)',
};

function normalizeShadowValue(value: unknown, keyHint: string): string {
  const fallback = SHADOW_FALLBACKS[keyHint] || SHADOW_FALLBACKS.md;
  if (typeof value !== 'string') return fallback;

  const trimmed = value.trim();
  if (!trimmed) return fallback;
  if (trimmed === 'none') return 'none';

  const named = trimmed.toLowerCase();
  if (SHADOW_FALLBACKS[named]) return SHADOW_FALLBACKS[named];

  const hasLength = /\d+px/.test(trimmed);
  const hasColor = /(rgba?\(|hsla?\(|#[0-9a-f]{3,8})/i.test(trimmed);
  if (hasLength && hasColor) return trimmed;

  return fallback;
}

// ─── tokensToCSS (single implementation used everywhere) ─────────────────────

export function tokensToCSS(t: DesignTokens): string {
  const normalized = normalizeDesignTokensForRendering(t as unknown as Record<string, unknown>) as unknown as DesignTokens;
  const L = [':root {', '  /* COLOR */'];
  const c = normalized.colors || {};
  ['primary', 'secondary', 'accent', 'neutral'].forEach((g) => {
    const group = c[g as keyof typeof c];
    if (!group || typeof group !== 'object') return;
    Object.entries(group).forEach(([k, v]) => L.push(`  --color-${g}-${k}: ${v};`));
  });
  Object.entries(c.semantic || {}).forEach(([k, v]) => L.push(`  --color-${k}: ${v};`));
  Object.entries(c.surface || {}).forEach(([k, v]) => L.push(`  --surface-${k}: ${v};`));
  Object.entries(c.text || {}).forEach(([k, v]) => L.push(`  --text-${k}: ${v};`));
  const ty = normalized.typography || {};
  L.push('', '  /* TYPOGRAPHY */');
  if (ty.fontSans) L.push(`  --font-sans: '${ty.fontSans}', sans-serif;`);
  if (ty.fontSerif) L.push(`  --font-serif: '${ty.fontSerif}', serif;`);
  if (ty.fontMono) L.push(`  --font-mono: '${ty.fontMono}', monospace;`);
  Object.entries(ty.scale || {}).forEach(([k, v]) => L.push(`  --text-${k}: ${v}px;`));
  Object.entries(ty.weights || {}).forEach(([k, v]) => L.push(`  --font-weight-${k}: ${v};`));
  Object.entries(ty.tracking || {}).forEach(([k, v]) => L.push(`  --tracking-${k}: ${v};`));
  Object.entries(ty.leading || {}).forEach(([k, v]) => L.push(`  --leading-${k}: ${v};`));
  L.push('', '  /* SPACING */');
  (normalized.spacing?.scale || []).forEach((v, i) => L.push(`  --space-${i + 1}: ${v}px;`));
  L.push('', '  /* BORDER */');
  Object.entries(normalized.border?.width || {}).forEach(([k, v]) => L.push(`  --border-${k}: ${v};`));
  Object.entries(normalized.border?.radius || {}).forEach(([k, v]) => L.push(`  --radius-${k}: ${v};`));
  L.push('', '  /* SHADOW */');
  Object.entries(normalized.shadow || {}).forEach(([k, v]) => {
    L.push(`  --shadow-${k}: ${normalizeShadowValue(v, k)};`);
  });
  L.push('', '  /* GRADIENT */');
  Object.entries(normalized.gradient || {}).forEach(([k, v]) => L.push(`  --gradient-${k}: ${v};`));
  L.push('', '  /* MOTION */');
  Object.entries(normalized.motion?.duration || {}).forEach(([k, v]) => L.push(`  --duration-${k}: ${v};`));
  Object.entries(normalized.motion?.easing || {}).forEach(([k, v]) => L.push(`  --easing-${k}: ${v};`));
  L.push('', '  /* COMPONENT */');
  Object.entries(normalized.component || {}).forEach(([name, vals]) => {
    Object.entries(vals).forEach(([k, v]) => L.push(`  --${name}-${k}: ${v};`));
  });
  L.push('}');
  return L.join('\n');
}

// ─── tokensToCSS for Record<string, unknown> (server-side raw JSON) ──────────

export function tokensToCSSFromRaw(t: Record<string, unknown>): string {
  const normalized = normalizeDesignTokensForRendering(t);
  const L = [':root {', '  /* COLOR */'];
  const c = (normalized.colors || {}) as Record<string, Record<string, string>>;
  ['primary', 'secondary', 'accent', 'neutral'].forEach((g) => {
    const group = c[g];
    if (!group || typeof group !== 'object') return;
    Object.entries(group).forEach(([k, v]) => L.push(`  --color-${g}-${k}: ${v};`));
  });
  const semantic = (c.semantic || {}) as Record<string, string>;
  Object.entries(semantic).forEach(([k, v]) => L.push(`  --color-${k}: ${v};`));
  const surface = (c.surface || {}) as Record<string, string>;
  Object.entries(surface).forEach(([k, v]) => L.push(`  --surface-${k}: ${v};`));
  const text = (c.text || {}) as Record<string, string>;
  Object.entries(text).forEach(([k, v]) => L.push(`  --text-${k}: ${v};`));
  const ty = (normalized.typography || {}) as Record<string, unknown>;
  L.push('', '  /* TYPOGRAPHY */');
  const fontSans = ty.fontSans as string | undefined;
  if (fontSans) L.push(`  --font-sans: '${fontSans}', sans-serif;`);
  const fontSerif = ty.fontSerif as string | undefined;
  if (fontSerif) L.push(`  --font-serif: '${fontSerif}', serif;`);
  const fontMono = ty.fontMono as string | undefined;
  if (fontMono) L.push(`  --font-mono: '${fontMono}', monospace;`);
  const scale = (ty.scale || {}) as Record<string, number>;
  Object.entries(scale).forEach(([k, v]) => L.push(`  --text-${k}: ${v}px;`));
  const weights = (ty.weights || {}) as Record<string, number>;
  Object.entries(weights).forEach(([k, v]) => L.push(`  --font-weight-${k}: ${v};`));
  const tracking = (ty.tracking || {}) as Record<string, string>;
  Object.entries(tracking).forEach(([k, v]) => L.push(`  --tracking-${k}: ${v};`));
  const leading = (ty.leading || {}) as Record<string, number>;
  Object.entries(leading).forEach(([k, v]) => L.push(`  --leading-${k}: ${v};`));
  L.push('', '  /* SPACING */');
  const spacing = (normalized.spacing || {}) as { scale?: number[] };
  (spacing.scale || []).forEach((v, i) => L.push(`  --space-${i + 1}: ${v}px;`));
  L.push('', '  /* BORDER */');
  const border = (normalized.border || {}) as Record<string, Record<string, string>>;
  Object.entries(border.width || {}).forEach(([k, v]) => L.push(`  --border-${k}: ${v};`));
  Object.entries(border.radius || {}).forEach(([k, v]) => L.push(`  --radius-${k}: ${v};`));
  L.push('', '  /* SHADOW */');
  const shadow = (normalized.shadow || {}) as Record<string, string>;
  Object.entries(shadow).forEach(([k, v]) => {
    L.push(`  --shadow-${k}: ${normalizeShadowValue(v, k)};`);
  });
  L.push('', '  /* GRADIENT */');
  const gradient = (normalized.gradient || {}) as Record<string, string>;
  Object.entries(gradient).forEach(([k, v]) => L.push(`  --gradient-${k}: ${v};`));
  L.push('', '  /* MOTION */');
  const motion = (normalized.motion || {}) as Record<string, Record<string, string>>;
  Object.entries(motion.duration || {}).forEach(([k, v]) => L.push(`  --duration-${k}: ${v};`));
  Object.entries(motion.easing || {}).forEach(([k, v]) => L.push(`  --easing-${k}: ${v};`));
  L.push('', '  /* COMPONENT */');
  const component = (normalized.component || {}) as Record<string, Record<string, string | number>>;
  Object.entries(component).forEach(([name, vals]) => {
    Object.entries(vals).forEach(([k, v]) => L.push(`  --${name}-${k}: ${v};`));
  });
  L.push('}');
  return L.join('\n');
}

// ─── Font imports from tokens ────────────────────────────────────────────────

export function fontImportFromTokens(t: Record<string, unknown>): string {
  const ty = (t.typography || {}) as Record<string, unknown>;
  const fonts = [ty.fontSans, ty.fontSerif, ty.fontMono].filter(
    (f): f is string => typeof f === 'string' && f.length > 0,
  );
  if (!fonts.length) return '';
  const q = fonts
    .map(
      (f) =>
        `family=${encodeURIComponent(f)}:ital,wght@0,300;0,400;0,500;0,600;0,700;0,900;1,400`,
    )
    .join('&');
  return `<link id="tasbir-font-preconnect" rel="preconnect" href="https://fonts.googleapis.com"><link id="tasbir-font-preconnect-cross" rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link id="tasbir-fonts" href="https://fonts.googleapis.com/css2?${q}&display=swap" rel="stylesheet">`;
}

// ─── Tailwind config from tokens ─────────────────────────────────────────────

export function buildTailwindConfigFromTokens(tokens: Record<string, unknown>): Record<string, unknown> {
  const normalized = normalizeDesignTokensForRendering(tokens);
  const colors = (normalized.colors || {}) as Record<string, unknown>;
  const border = (normalized.border || {}) as Record<string, unknown>;
  const ty = (normalized.typography || {}) as Record<string, unknown>;
  const shadow = (normalized.shadow || {}) as Record<string, unknown>;
  const gradient = (normalized.gradient || {}) as Record<string, unknown>;
  const motion = (normalized.motion || {}) as Record<string, unknown>;

  const toColorObj = (obj: unknown): Record<string, string> => {
    if (typeof obj !== 'object' || obj === null) return {};
    return obj as Record<string, string>;
  };

  const themeColors: Record<string, unknown> = {
    primary: toColorObj(colors.primary),
    secondary: toColorObj(colors.secondary),
    accent: toColorObj(colors.accent),
    neutral: toColorObj(colors.neutral),
    semantic: toColorObj(colors.semantic),
    surface: toColorObj(colors.surface),
    content: toColorObj(colors.text),
  };

  const fontFamilies: Record<string, string[]> = {};
  const fontSans = ty.fontSans as string | undefined;
  if (fontSans) fontFamilies.sans = [fontSans, 'system-ui', 'sans-serif'];
  const fontSerif = ty.fontSerif as string | undefined;
  if (fontSerif) fontFamilies.serif = [fontSerif, 'Georgia', 'serif'];
  const fontMono = ty.fontMono as string | undefined;
  if (fontMono) fontFamilies.mono = [fontMono, 'monospace'];

  const spacingScale = ((normalized.spacing as { scale?: number[] } | undefined)?.scale || []) as number[];
  const spacing: Record<string, string> = {};
  spacingScale.forEach((v, i) => {
    spacing[String(i + 1)] = `${v}px`;
  });

  const toStringObj = (obj: unknown): Record<string, string> => {
    if (typeof obj !== 'object' || obj === null) return {};
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).filter(([, value]) => typeof value === 'string') as Array<[
        string,
        string,
      ]>,
    );
  };

  return {
    theme: {
      colors: themeColors,
      fontFamily: fontFamilies,
      spacing,
      borderRadius: toColorObj((border.radius || {}) as Record<string, string>),
      borderWidth: toColorObj((border.width || {}) as Record<string, string>),
      boxShadow: toStringObj(shadow),
      backgroundImage: toStringObj(gradient),
      transitionDuration: toStringObj((motion.duration || {}) as Record<string, string>),
      transitionTimingFunction: toStringObj((motion.easing || {}) as Record<string, string>),
    },
  };
}

// ─── Token stripping (for re-injection) ──────────────────────────────────────

export function stripInjectedDesignTokens(html: string): string {
  let next = html;
  next = next.replace(/<style[^>]*id=["']tasbir-design-tokens["'][^>]*>[\s\S]*?<\/style>/gi, '');
  next = next.replace(/<script[^>]*id=["']tasbir-tailwind-config["'][^>]*>[\s\S]*?<\/script>/gi, '');
  next = next.replace(/<link[^>]*id=["']tasbir-font-preconnect["'][^>]*>/gi, '');
  next = next.replace(/<link[^>]*id=["']tasbir-font-preconnect-cross["'][^>]*>/gi, '');
  next = next.replace(/<link[^>]*id=["']tasbir-fonts["'][^>]*>/gi, '');
  return next;
}

// ─── Prompt formatting ───────────────────────────────────────────────────────

export function formatDesignTokensForPromptFromObject(tokens: Record<string, unknown>): string {
  const normalized = normalizeDesignTokensForRendering(tokens);
  const parts: string[] = [];
  parts.push('Token JSON:');
  parts.push(JSON.stringify(normalized, null, 2));
  parts.push('\nToken CSS Variables (use these names directly with var(--...)): ');
  parts.push(tokensToCSSFromRaw(normalized));
  parts.push('\nTailwind theme config (token-backed):');
  parts.push(JSON.stringify(buildTailwindConfigFromTokens(normalized), null, 2));
  parts.push('\nCanonical Tailwind token classes expected:');
  parts.push('- background: bg-surface-base, bg-surface-subtle, bg-surface-elevated');
  parts.push('- foreground: text-content-primary, text-content-on-surface-base, text-content-on-primary');
  parts.push('- emphasis: bg-primary-500 + text-content-on-primary; bg-secondary-500 + text-content-on-secondary');
  parts.push('- font: font-sans, font-serif, font-mono');
  parts.push('- spacing/radius/shadow: p-1..p-15, rounded-md etc from token config, shadow-sm/md/lg from token config');
  parts.push('\nImplementation requirements:');
  parts.push('- Add these CSS variables to :root in your <style> block.');
  parts.push('- Prefer var(--color-...), var(--surface-...), var(--text-...), var(--gradient-...), var(--font-sans).');
  parts.push('- Do not use hardcoded color literals (#hex, rgb, rgba, hsl, hsla) when a token exists.');
  parts.push('- Do not use arbitrary color classes (for example text-[#fff], bg-[rgb(...)]) - use token theme classes only.');
  parts.push('- Ensure readable contrast by using matching foreground/background token pairs (on-* tokens for colored backgrounds).\n');
  return parts.join('\n');
}

// ─── Default tokens (15-element spacing scale) ───────────────────────────────

export function getDefaultDesignTokens(): DesignTokens {
  return {
    colors: {
      primary: {
        '50': '#eff6ff',
        '100': '#dbeafe',
        '200': '#bfdbfe',
        '300': '#93c5fd',
        '400': '#60a5fa',
        '500': '#3b82f6',
        '600': '#2563eb',
        '700': '#1d4ed8',
        '800': '#1e40af',
        '900': '#1e3a8a',
      },
      secondary: {
        '50': '#f5f3ff',
        '100': '#ede9fe',
        '200': '#ddd6fe',
        '300': '#c4b5fd',
        '400': '#a78bfa',
        '500': '#8b5cf6',
        '600': '#7c3aed',
        '700': '#6d28d9',
        '800': '#5b21b6',
        '900': '#4c1d95',
      },
      accent: { light: '#60a5fa', base: '#3b82f6', dark: '#1d4ed8' },
      neutral: {
        '50': '#fafafa',
        '100': '#f5f5f5',
        '200': '#e5e5e5',
        '300': '#d4d4d4',
        '400': '#a3a3a3',
        '500': '#737373',
        '600': '#525252',
        '700': '#404040',
        '800': '#262626',
        '900': '#171717',
      },
      semantic: { success: '#22c55e', warning: '#f59e0b', error: '#ef4444', info: '#3b82f6' },
      surface: { base: '#0b0b0b', subtle: '#171717', elevated: '#1f1f1f', overlay: 'rgba(0, 0, 0, 0.8)' },
      text: { primary: '#f5f5f5', secondary: '#a3a3a3', muted: '#737373', inverse: '#0b0b0b', accent: '#60a5fa' },
    },
    typography: {
      fontSans: 'Inter',
      fontSerif: 'Georgia',
      fontMono: 'JetBrains Mono',
      scale: { xs: 12, sm: 14, base: 16, lg: 18, xl: 20, '2xl': 24, '3xl': 30, '4xl': 36, '5xl': 48, '6xl': 60, '7xl': 72 },
      weights: { light: 300, regular: 400, medium: 500, semibold: 600, bold: 700, black: 900 },
      tracking: { tight: '-0.025em', normal: '0em', wide: '0.025em', wider: '0.05em', widest: '0.1em' },
      leading: { tight: 1.25, snug: 1.375, normal: 1.5, relaxed: 1.625, loose: 2 },
    },
    spacing: { base: 4, scale: [2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128] },
    border: {
      width: { hairline: '0.5px', thin: '1px', normal: '2px', medium: '3px', thick: '4px' },
      radius: { none: '0', xs: '2px', sm: '4px', md: '6px', lg: '8px', xl: '12px', '2xl': '16px', '3xl': '24px', full: '9999px' },
    },
    shadow: {
      xs: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
      sm: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
      md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
      lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
      xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
      inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)',
    },
    gradient: {
      primary: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
      hero: 'linear-gradient(180deg, rgba(59, 130, 246, 0.15) 0%, transparent 50%)',
      subtle: 'linear-gradient(180deg, rgba(255, 255, 255, 0.05) 0%, transparent 100%)',
      surface: 'linear-gradient(180deg, #171717 0%, #0b0b0b 100%)',
    },
    motion: {
      duration: { instant: '50ms', fast: '150ms', normal: '300ms', slow: '500ms', slower: '700ms' },
      easing: { default: 'cubic-bezier(0.4, 0, 0.2, 1)', in: 'cubic-bezier(0.4, 0, 1, 1)', out: 'cubic-bezier(0, 0, 0.2, 1)', bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)' },
    },
    component: {
      button: { height: '40px', heightSm: '32px', heightLg: '48px', paddingX: '16px', radius: '6px', fontWeight: 500, fontSize: '14px' },
      card: { padding: '24px', paddingLg: '32px', radius: '12px', shadow: 'md', border: '1px' },
      input: { height: '40px', paddingX: '12px', paddingY: '8px', radius: '6px', borderWidth: '1px' },
      badge: { height: '24px', paddingX: '8px', radius: '4px', fontSize: '12px', fontWeight: 500 },
      nav: { height: '64px', paddingX: '24px' },
    },
    meta: {
      vibeName: 'Default Dark',
      description: 'A clean, modern dark theme with blue accents',
      aesthetic: 'minimal',
      palette: 'dark',
      instructions: '',
    },
  };
}
