import { createModelChain, resolveProviderConfig } from "../ai";
import { generateDesignTokens, type DesignTokens as AIDesignTokens } from "../ai/agents/design-token-agent";

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

export async function generateTokensAI(vibe: string, env: Record<string, string | undefined>): Promise<DesignTokens> {
  const providerConfig = resolveProviderConfig(env);
  const models = createModelChain(providerConfig);
  const result = await generateDesignTokens(models, vibe);
  return result as DesignTokens;
}

function hexToHSL(hex: string): { h: number; s: number; l: number } {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0, l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

function hslToHex(h: number, s: number, l: number): string {
  s /= 100; l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function generateScale(base: string, isDark: boolean): Record<string, string> {
  const { h, s, l } = hexToHSL(base);
  const steps = isDark
    ? [97, 90, 80, 70, 55, 40, 28, 18, 10, 5]
    : [5, 10, 18, 28, 40, 55, 70, 80, 90, 97];
  const result: Record<string, string> = {};
  ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900'].forEach((key, i) => {
    result[key] = hslToHex(h, Math.max(s - 10, 5), steps[i]);
  });
  return result;
}

// Generate semantic color that harmonizes with the primary hue
function generateSemanticColor(primaryHue: number, targetHue: number, isDark: boolean): string {
  // Blend toward target hue while maintaining some harmony with primary
  const blendedHue = (targetHue + primaryHue * 0.15) % 360;
  const saturation = 65;
  const lightness = isDark ? 55 : 45;
  return hslToHex(blendedHue, saturation, lightness);
}

export function generateTokensComputational(primary: string, secondary: string, vibe?: string): DesignTokens {
  const primaryHSL = hexToHSL(primary);
  const isDark = primaryHSL.l < 50;

  const primaryScale = generateScale(primary, isDark);
  const secondaryScale = generateScale(secondary, isDark);
  const accentHSL = { h: (primaryHSL.h + 30) % 360, s: Math.min(primaryHSL.s + 10, 90), l: primaryHSL.l };

  // Generate semantic colors that harmonize with the primary palette
  const semanticColors = {
    success: generateSemanticColor(primaryHSL.h, 142, isDark), // Green-ish
    warning: generateSemanticColor(primaryHSL.h, 38, isDark),  // Amber-ish
    error: generateSemanticColor(primaryHSL.h, 0, isDark),     // Red-ish
    info: generateSemanticColor(primaryHSL.h, 210, isDark),    // Blue-ish
  };
  // Light mode: 50 is lightest, 900 is darkest (normal)
  // Dark mode: 50 is darkest, 900 is lightest (inverted for dark UIs)
  const neutralScale = isDark
    ? { '50': '#171717', '100': '#262626', '200': '#404040', '300': '#525252', '400': '#737373', '500': '#a3a3a3', '600': '#d4d4d4', '700': '#e5e5e5', '800': '#f5f5f5', '900': '#fafafa' }
    : { '50': '#fafafa', '100': '#f5f5f5', '200': '#e5e5e5', '300': '#d4d4d4', '400': '#a3a3a3', '500': '#737373', '600': '#525252', '700': '#404040', '800': '#262626', '900': '#171717' };

  const bgBase = isDark ? neutralScale['900'] : neutralScale['50'];
  const bgSubtle = isDark ? neutralScale['800'] : neutralScale['100'];
  const bgElevated = isDark ? neutralScale['700'] : neutralScale['200'];

  const textPrimary = isDark ? neutralScale['50'] : neutralScale['900'];
  const textSecondary = isDark ? neutralScale['300'] : neutralScale['600'];
  const textMuted = isDark ? neutralScale['500'] : neutralScale['400'];

  const vibeName = vibe ? vibe.toUpperCase().slice(0, 30) : 'COMPUTATIONAL';

  return {
    colors: {
      primary: primaryScale,
      secondary: secondaryScale,
      accent: {
        light: hslToHex(accentHSL.h, accentHSL.s, Math.min(accentHSL.l + 20, 95)),
        base: hslToHex(accentHSL.h, accentHSL.s, accentHSL.l),
        dark: hslToHex(accentHSL.h, accentHSL.s, Math.max(accentHSL.l - 20, 5))
      },
      neutral: neutralScale,
      semantic: semanticColors,
      surface: {
        base: bgBase,
        subtle: bgSubtle,
        elevated: bgElevated,
        overlay: isDark ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0.3)'
      },
      text: {
        primary: textPrimary,
        secondary: textSecondary,
        muted: textMuted,
        inverse: isDark ? neutralScale['900'] : neutralScale['50'],
        accent: primaryScale['500']
      }
    },
    typography: {
      fontSans: 'Inter',
      fontSerif: 'Georgia',
      fontMono: 'Fira Code',
      scale: { xs: 11, sm: 13, base: 16, lg: 18, xl: 20, '2xl': 24, '3xl': 30, '4xl': 36, '5xl': 48, '6xl': 64, '7xl': 80 },
      weights: { light: 300, regular: 400, medium: 500, semibold: 600, bold: 700, black: 900 },
      tracking: { tight: '-0.03em', normal: '0', wide: '0.04em', wider: '0.1em', widest: '0.2em' },
      leading: { tight: 1.1, snug: 1.3, normal: 1.5, relaxed: 1.7, loose: 2.0 }
    },
    spacing: { base: 4, scale: [2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128] },
    border: {
      width: { hairline: '0.5px', thin: '1px', normal: '1.5px', medium: '2px', thick: '3px' },
      radius: { none: '0', xs: '2px', sm: '4px', md: '8px', lg: '12px', xl: '16px', '2xl': '24px', '3xl': '32px', full: '9999px' }
    },
    shadow: {
      xs: '0 1px 2px rgba(0,0,0,0.05)',
      sm: '0 2px 4px rgba(0,0,0,0.08)',
      md: '0 4px 12px rgba(0,0,0,0.12)',
      lg: '0 8px 24px rgba(0,0,0,0.16)',
      xl: '0 16px 48px rgba(0,0,0,0.22)',
      inner: 'inset 0 2px 4px rgba(0,0,0,0.08)'
    },
    gradient: {
      primary: `linear-gradient(135deg, ${primaryScale['400']} 0%, ${primaryScale['600']} 100%)`,
      hero: `linear-gradient(135deg, ${primaryScale['300']} 0%, ${secondaryScale['500']} 50%, ${primaryScale['700']} 100%)`,
      subtle: `linear-gradient(180deg, ${bgSubtle} 0%, ${bgBase} 100%)`,
      surface: `linear-gradient(135deg, ${bgElevated} 0%, ${bgSubtle} 100%)`
    },
    motion: {
      duration: { instant: '50ms', fast: '100ms', normal: '200ms', slow: '350ms', slower: '500ms' },
      easing: { default: 'cubic-bezier(0.4,0,0.2,1)', in: 'cubic-bezier(0.4,0,1,1)', out: 'cubic-bezier(0,0,0.2,1)', bounce: 'cubic-bezier(0.34,1.56,0.64,1)' }
    },
    component: {
      button: { height: '40px', heightSm: '32px', heightLg: '48px', paddingX: '16px', radius: '8px', fontWeight: 600, fontSize: '14px' },
      card: { padding: '24px', paddingLg: '32px', radius: '16px', shadow: 'md', border: 'hairline' },
      input: { height: '40px', paddingX: '12px', paddingY: '10px', radius: '8px', borderWidth: '1.5px' },
      badge: { height: '24px', paddingX: '10px', radius: '9999px', fontSize: '11px', fontWeight: 600 },
      nav: { height: '64px', paddingX: '24px' }
    },
    meta: {
      vibeName,
      description: `Computationally generated design system from ${primary} + ${secondary}`,
      aesthetic: isDark ? 'dark' : 'light',
      palette: isDark ? 'dark' : 'light'
    }
  };
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
  Object.entries(ty.tracking || {}).forEach(([k, v]) => L.push(`  --tracking-${k}: ${v};`));
  Object.entries(ty.leading || {}).forEach(([k, v]) => L.push(`  --leading-${k}: ${v};`));
  L.push('', '  /* SPACING */');
  (t.spacing?.scale || []).forEach((v, i) => L.push(`  --space-${i + 1}: ${v}px;`));
  L.push('', '  /* BORDER */');
  Object.entries(t.border?.width || {}).forEach(([k, v]) => L.push(`  --border-${k}: ${v};`));
  Object.entries(t.border?.radius || {}).forEach(([k, v]) => L.push(`  --radius-${k}: ${v};`));
  L.push('', '  /* SHADOW */');
  Object.entries(t.shadow || {}).forEach(([k, v]) => L.push(`  --shadow-${k}: ${v};`));
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

export function tokensToPrompt(t: DesignTokens): string {
  if (!t) return 'No tokens generated.';
  const c = t.colors || {}, ty = t.typography || {};
  return `DESIGN SYSTEM — ${t.meta?.vibeName || 'CUSTOM'}
${t.meta?.description || ''}  |  Aesthetic: ${t.meta?.aesthetic || ''}  |  Mode: ${t.meta?.palette || ''}

━━ COLORS ━━
Primary: ${Object.values(c.primary || {}).join(' → ')}
Secondary: ${Object.values(c.secondary || {}).join(' → ')}
Accent: ${Object.values(c.accent || {}).join(' / ')}
Neutral: ${Object.values(c.neutral || {}).join(' → ')}
Semantic: success ${c.semantic?.success} | warning ${c.semantic?.warning} | error ${c.semantic?.error} | info ${c.semantic?.info}
Surfaces: ${Object.entries(c.surface || {}).map(([k, v]) => `${k}: ${v}`).join(' | ')}
Text: ${Object.entries(c.text || {}).map(([k, v]) => `${k}: ${v}`).join(' | ')}

━━ TYPOGRAPHY ━━
Sans: ${ty.fontSans} | Serif: ${ty.fontSerif} | Mono: ${ty.fontMono}
Scale: ${Object.entries(ty.scale || {}).map(([k, v]) => `${k}:${v}px`).join(', ')}

━━ SPACING ━━
Base: ${t.spacing?.base}px | Scale: ${(t.spacing?.scale || []).join(', ')}px

━━ BORDER RADIUS ━━
${Object.entries((t.border?.radius) || {}).map(([k, v]) => `${k}: ${v}`).join(' | ')}

━━ SHADOWS ━━
${Object.entries(t.shadow || {}).map(([k, v]) => `${k}: ${v}`).join('\n')}

━━ GRADIENTS ━━
${Object.entries(t.gradient || {}).map(([k, v]) => `${k}: ${v}`).join('\n')}

━━ USAGE RULES ━━
- Use ONLY the colors, fonts, spacing, and sizing values above
- Background scheme: ${t.meta?.palette}. Personality: ${t.meta?.aesthetic}`;
}
