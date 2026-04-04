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

const SHADOW_FALLBACKS: Record<string, string> = {
  xs: '0 1px 2px rgba(2, 6, 23, 0.18)',
  sm: '0 2px 6px rgba(2, 6, 23, 0.2)',
  md: '0 8px 16px rgba(2, 6, 23, 0.22)',
  lg: '0 14px 28px rgba(2, 6, 23, 0.24)',
  xl: '0 24px 44px rgba(2, 6, 23, 0.28)',
  inner: 'inset 0 2px 6px rgba(2, 6, 23, 0.2)',
}

function normalizeShadowValue(value: unknown, keyHint: string): string {
  const fallback = SHADOW_FALLBACKS[keyHint] || SHADOW_FALLBACKS.md
  if (typeof value !== 'string') return fallback

  const trimmed = value.trim()
  if (!trimmed) return fallback
  if (trimmed === 'none') return 'none'

  const named = trimmed.toLowerCase()
  if (SHADOW_FALLBACKS[named]) return SHADOW_FALLBACKS[named]

  const hasLength = /\d+px/.test(trimmed)
  const hasColor = /(rgba?\(|hsla?\(|#[0-9a-f]{3,8})/i.test(trimmed)
  if (hasLength && hasColor) return trimmed

  return fallback
}

export function tokensToCSS(t: DesignTokens): string {
  const L = [':root {', '  /* COLOR */'];
  const c = t.colors || {};
  ['primary', 'secondary', 'accent', 'neutral'].forEach(g => {
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
    L.push(`  --shadow-${k}: ${normalizeShadowValue(v, k)};`)
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
