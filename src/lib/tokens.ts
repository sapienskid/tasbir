import { createAdvancedModelChain, resolveProviderConfig } from "../ai";
import { generateDesignTokens } from "../ai/agents/design-token-agent";

// Re-export everything from the shared token package
export {
  type DesignTokens,
  tokensToCSS,
  tokensToCSSFromRaw,
  fontImportFromTokens,
  buildTailwindConfigFromTokens,
  stripInjectedDesignTokens,
  formatDesignTokensForPromptFromObject,
  formatSemanticBriefForPrompt,
  generateSemanticBriefFromTokens,
  generateSemanticUtilityCSS,
  getDefaultDesignTokens,
  normalizeDesignTokensForRendering,
} from "../../shared/tokens";

import { normalizeDesignTokensForRendering, type DesignTokens } from "../../shared/tokens";

/**
 * Generates design tokens using AI via Cloudflare AI Gateway.
 * Uses dynamic routes configured in AI Gateway for model selection and fallbacks.
 * Only requires AI_GATEWAY_TOKEN as a wrangler secret.
 */
export async function generateTokensAI(
  vibe: string,
  aiBinding: Ai,
  googleApiKey?: string,
  primaryHint?: string,
  secondaryHint?: string,
): Promise<DesignTokens> {
  const providerConfig = resolveProviderConfig(aiBinding, googleApiKey);
  const models = createAdvancedModelChain(providerConfig);

  let enhancedVibe = vibe;
  if (primaryHint || secondaryHint) {
    enhancedVibe = `${vibe}\n\nCOLOR REQUIREMENTS (you MUST use these exact colors as the base for your scales):\n`;
    if (primaryHint) enhancedVibe += `- Primary color 500 level MUST BE EXACTLY: ${primaryHint}\n`;
    if (secondaryHint) enhancedVibe += `- Secondary color 500 level MUST BE EXACTLY: ${secondaryHint}\n`;
  }

  const result = await generateDesignTokens(models, enhancedVibe);
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

function generateScale(base: string, isDark: boolean): {
  "50": string;
  "100": string;
  "200": string;
  "300": string;
  "400": string;
  "500": string;
  "600": string;
  "700": string;
  "800": string;
  "900": string;
} {
  const { h, s, l } = hexToHSL(base);
  const steps = isDark
    ? [97, 90, 80, 70, 55, 40, 28, 18, 10, 5]
    : [5, 10, 18, 28, 40, 55, 70, 80, 90, 97];

  return {
    "50": hslToHex(h, Math.max(s - 10, 5), steps[0]),
    "100": hslToHex(h, Math.max(s - 10, 5), steps[1]),
    "200": hslToHex(h, Math.max(s - 10, 5), steps[2]),
    "300": hslToHex(h, Math.max(s - 10, 5), steps[3]),
    "400": hslToHex(h, Math.max(s - 10, 5), steps[4]),
    "500": hslToHex(h, Math.max(s - 10, 5), steps[5]),
    "600": hslToHex(h, Math.max(s - 10, 5), steps[6]),
    "700": hslToHex(h, Math.max(s - 10, 5), steps[7]),
    "800": hslToHex(h, Math.max(s - 10, 5), steps[8]),
    "900": hslToHex(h, Math.max(s - 10, 5), steps[9]),
  };
}

function generateSemanticColor(primaryHue: number, targetHue: number, isDark: boolean): string {
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

  const semanticColors = {
    success: generateSemanticColor(primaryHSL.h, 142, isDark),
    warning: generateSemanticColor(primaryHSL.h, 38, isDark),
    error: generateSemanticColor(primaryHSL.h, 0, isDark),
    info: generateSemanticColor(primaryHSL.h, 210, isDark),
  };
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

  const baseTokens: DesignTokens = {
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
      palette: isDark ? 'dark' : 'light',
      instructions: ''
    }
  };

  return normalizeDesignTokensForRendering(baseTokens as unknown as Record<string, unknown>) as unknown as DesignTokens;
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
