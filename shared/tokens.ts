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
    text: { primary: string; secondary: string; muted: string; inverse: string; accent: string };
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
  };
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
  const L = [':root {', '  /* COLOR */'];
  const c = t.colors || {};
  ['primary', 'secondary', 'accent', 'neutral'].forEach((g) => {
    const group = c[g as keyof typeof c];
    if (!group || typeof group !== 'object') return;
    Object.entries(group).forEach(([k, v]) => L.push(`  --color-${g}-${k}: ${v};`));
  });
  Object.entries(c.semantic || {}).forEach(([k, v]) => L.push(`  --color-${k}: ${v};`));
  Object.entries(c.surface || {}).forEach(([k, v]) => L.push(`  --surface-${k}: ${v};`));
  Object.entries(c.text || {}).forEach(([k, v]) => L.push(`  --text-${k}: ${v};`));
  const ty = t.typography || {};
  L.push('', '  /* TYPOGRAPHY */');
  if (ty.fontSans) L.push(`  --font-sans: '${ty.fontSans}', sans-serif;`);
  if (ty.fontSerif) L.push(`  --font-serif: '${ty.fontSerif}', serif;`);
  if (ty.fontMono) L.push(`  --font-mono: '${ty.fontMono}', monospace;`);
  Object.entries(ty.scale || {}).forEach(([k, v]) => L.push(`  --text-${k}: ${v}px;`));
  Object.entries(ty.weights || {}).forEach(([k, v]) => L.push(`  --font-weight-${k}: ${v};`));
  Object.entries(ty.tracking || {}).forEach(([k, v]) => L.push(`  --tracking-${k}: ${v};`));
  Object.entries(ty.leading || {}).forEach(([k, v]) => L.push(`  --leading-${k}: ${v};`));
  L.push('', '  /* SPACING */');
  (t.spacing?.scale || []).forEach((v, i) => L.push(`  --space-${i + 1}: ${v}px;`));
  L.push('', '  /* BORDER */');
  Object.entries(t.border?.width || {}).forEach(([k, v]) => L.push(`  --border-${k}: ${v};`));
  Object.entries(t.border?.radius || {}).forEach(([k, v]) => L.push(`  --radius-${k}: ${v};`));
  L.push('', '  /* SHADOW */');
  Object.entries(t.shadow || {}).forEach(([k, v]) => {
    L.push(`  --shadow-${k}: ${normalizeShadowValue(v, k)};`);
  });
  L.push('', '  /* GRADIENT */');
  Object.entries(t.gradient || {}).forEach(([k, v]) => L.push(`  --gradient-${k}: ${v};`));
  L.push('', '  /* MOTION */');
  Object.entries(t.motion?.duration || {}).forEach(([k, v]) => L.push(`  --duration-${k}: ${v};`));
  Object.entries(t.motion?.easing || {}).forEach(([k, v]) => L.push(`  --easing-${k}: ${v};`));
  L.push('', '  /* COMPONENT */');
  Object.entries(t.component || {}).forEach(([name, vals]) => {
    Object.entries(vals).forEach(([k, v]) => L.push(`  --${name}-${k}: ${v};`));
  });
  L.push('}');
  return L.join('\n');
}

// ─── tokensToCSS for Record<string, unknown> (server-side raw JSON) ──────────

export function tokensToCSSFromRaw(t: Record<string, unknown>): string {
  const L = [':root {', '  /* COLOR */'];
  const c = (t.colors || {}) as Record<string, Record<string, string>>;
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
  const ty = (t.typography || {}) as Record<string, unknown>;
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
  const spacing = (t.spacing || {}) as { scale?: number[] };
  (spacing.scale || []).forEach((v, i) => L.push(`  --space-${i + 1}: ${v}px;`));
  L.push('', '  /* BORDER */');
  const border = (t.border || {}) as Record<string, Record<string, string>>;
  Object.entries(border.width || {}).forEach(([k, v]) => L.push(`  --border-${k}: ${v};`));
  Object.entries(border.radius || {}).forEach(([k, v]) => L.push(`  --radius-${k}: ${v};`));
  L.push('', '  /* SHADOW */');
  const shadow = (t.shadow || {}) as Record<string, string>;
  Object.entries(shadow).forEach(([k, v]) => {
    L.push(`  --shadow-${k}: ${normalizeShadowValue(v, k)};`);
  });
  L.push('', '  /* GRADIENT */');
  const gradient = (t.gradient || {}) as Record<string, string>;
  Object.entries(gradient).forEach(([k, v]) => L.push(`  --gradient-${k}: ${v};`));
  L.push('', '  /* MOTION */');
  const motion = (t.motion || {}) as Record<string, Record<string, string>>;
  Object.entries(motion.duration || {}).forEach(([k, v]) => L.push(`  --duration-${k}: ${v};`));
  Object.entries(motion.easing || {}).forEach(([k, v]) => L.push(`  --easing-${k}: ${v};`));
  L.push('', '  /* COMPONENT */');
  const component = (t.component || {}) as Record<string, Record<string, string | number>>;
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
  const colors = (tokens.colors || {}) as Record<string, unknown>;
  const border = (tokens.border || {}) as Record<string, unknown>;
  const ty = (tokens.typography || {}) as Record<string, unknown>;

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

  const spacingScale = ((tokens.spacing as { scale?: number[] } | undefined)?.scale || []) as number[];
  const spacing: Record<string, string> = {};
  spacingScale.forEach((v, i) => {
    spacing[String(i + 1)] = `${v}px`;
  });

  return {
    theme: {
      extend: {
        colors: themeColors,
        fontFamily: fontFamilies,
        spacing,
        borderRadius: toColorObj((border.radius || {}) as Record<string, string>),
        borderWidth: toColorObj((border.width || {}) as Record<string, string>),
      },
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
  const parts: string[] = [];
  parts.push('Token JSON:');
  parts.push(JSON.stringify(tokens, null, 2));
  parts.push('\nToken CSS Variables (use these names directly with var(--...)): ');
  parts.push(tokensToCSSFromRaw(tokens));
  parts.push('\nCanonical Tailwind token classes expected:');
  parts.push('- background: bg-surface-base, bg-surface-elevated');
  parts.push('- text: text-content-primary, text-content-secondary, text-primary-500');
  parts.push('- font: font-sans, font-serif, font-mono');
  parts.push('\nImplementation requirements:');
  parts.push('- Add these CSS variables to :root in your <style> block.');
  parts.push('- Prefer var(--color-...), var(--surface-...), var(--text-...), var(--gradient-...), var(--font-sans).\n');
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
    },
  };
}
