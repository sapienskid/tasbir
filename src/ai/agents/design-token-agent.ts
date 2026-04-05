import { generateText, generateObject, type LanguageModel } from "ai";
import { z } from "zod";

const DESIGN_TOKEN_SCHEMA = z.object({
  colors: z.object({
    primary: z.object({
      "50": z.string(),
      "100": z.string(),
      "200": z.string(),
      "300": z.string(),
      "400": z.string(),
      "500": z.string(),
      "600": z.string(),
      "700": z.string(),
      "800": z.string(),
      "900": z.string(),
    }),
    secondary: z.object({
      "50": z.string(),
      "100": z.string(),
      "200": z.string(),
      "300": z.string(),
      "400": z.string(),
      "500": z.string(),
      "600": z.string(),
      "700": z.string(),
      "800": z.string(),
      "900": z.string(),
    }),
    accent: z.object({ 
      light: z.string(), 
      base: z.string(), 
      dark: z.string() 
    }),
    neutral: z.object({
      "50": z.string(),
      "100": z.string(),
      "200": z.string(),
      "300": z.string(),
      "400": z.string(),
      "500": z.string(),
      "600": z.string(),
      "700": z.string(),
      "800": z.string(),
      "900": z.string(),
    }),
    semantic: z.object({ 
      success: z.string(), 
      warning: z.string(), 
      error: z.string(), 
      info: z.string() 
    }),
    surface: z.object({ 
      base: z.string(), 
      subtle: z.string(), 
      elevated: z.string(), 
      overlay: z.string() 
    }),
    text: z.object({ 
      primary: z.string(), 
      secondary: z.string(), 
      muted: z.string(), 
      inverse: z.string(), 
      accent: z.string() 
    }),
  }),
  typography: z.object({
    fontSans: z.string(),
    fontSerif: z.string(),
    fontMono: z.string(),
    scale: z.object({
      xs: z.number(),
      sm: z.number(),
      base: z.number(),
      lg: z.number(),
      xl: z.number(),
      "2xl": z.number(),
      "3xl": z.number(),
      "4xl": z.number(),
      "5xl": z.number(),
      "6xl": z.number(),
      "7xl": z.number(),
    }),
    weights: z.object({
      light: z.number(),
      regular: z.number(),
      medium: z.number(),
      semibold: z.number(),
      bold: z.number(),
      black: z.number(),
    }),
    tracking: z.object({
      tight: z.string(),
      normal: z.string(),
      wide: z.string(),
      wider: z.string(),
      widest: z.string(),
    }),
    leading: z.object({
      tight: z.number(),
      snug: z.number(),
      normal: z.number(),
      relaxed: z.number(),
      loose: z.number(),
    }),
  }),
  spacing: z.object({ 
    base: z.number(), 
    scale: z.array(z.number()).length(15)
  }),
  border: z.object({
    width: z.object({
      hairline: z.string(),
      thin: z.string(),
      normal: z.string(),
      medium: z.string(),
      thick: z.string(),
    }),
    radius: z.object({
      none: z.string(),
      xs: z.string(),
      sm: z.string(),
      md: z.string(),
      lg: z.string(),
      xl: z.string(),
      "2xl": z.string(),
      "3xl": z.string(),
      full: z.string(),
    }),
  }),
  shadow: z.object({
    xs: z.string(),
    sm: z.string(),
    md: z.string(),
    lg: z.string(),
    xl: z.string(),
    inner: z.string(),
  }),
  gradient: z.object({
    primary: z.string(),
    hero: z.string(),
    subtle: z.string(),
    surface: z.string(),
  }),
  motion: z.object({
    duration: z.object({
      instant: z.string(),
      fast: z.string(),
      normal: z.string(),
      slow: z.string(),
      slower: z.string(),
    }),
    easing: z.object({
      default: z.string(),
      in: z.string(),
      out: z.string(),
      bounce: z.string(),
    }),
  }),
  component: z.object({
    button: z.object({
      height: z.union([z.string(), z.number()]),
      heightSm: z.union([z.string(), z.number()]),
      heightLg: z.union([z.string(), z.number()]),
      paddingX: z.union([z.string(), z.number()]),
      radius: z.union([z.string(), z.number()]),
      fontWeight: z.union([z.string(), z.number()]),
      fontSize: z.union([z.string(), z.number()]),
    }),
    card: z.object({
      padding: z.union([z.string(), z.number()]),
      paddingLg: z.union([z.string(), z.number()]),
      radius: z.union([z.string(), z.number()]),
      shadow: z.union([z.string(), z.number()]),
      border: z.union([z.string(), z.number()]),
    }),
    input: z.object({
      height: z.union([z.string(), z.number()]),
      paddingX: z.union([z.string(), z.number()]),
      paddingY: z.union([z.string(), z.number()]),
      radius: z.union([z.string(), z.number()]),
      borderWidth: z.union([z.string(), z.number()]),
    }),
    badge: z.object({
      height: z.union([z.string(), z.number()]),
      paddingX: z.union([z.string(), z.number()]),
      radius: z.union([z.string(), z.number()]),
      fontSize: z.union([z.string(), z.number()]),
      fontWeight: z.union([z.string(), z.number()]),
    }),
    nav: z.object({
      height: z.union([z.string(), z.number()]),
      paddingX: z.union([z.string(), z.number()]),
    }),
  }),
  meta: z.object({
    vibeName: z.string(),
    description: z.string(),
    aesthetic: z.string(),
    palette: z.string(),
    instructions: z.string(),
  }),
});

export type DesignTokens = z.infer<typeof DESIGN_TOKEN_SCHEMA>;

const DESIGN_TOKEN_SYSTEM_PROMPT = `You are an expert design system architect with deep knowledge of color theory, typography, and visual design principles. Generate a complete, production-ready design token system that is both aesthetically beautiful and functionally correct.

═══════════════════════════════════════════════════════════════
CRITICAL: COLOR REQUIREMENTS MUST BE FOLLOWED EXACTLY
═══════════════════════════════════════════════════════════════

When the user provides specific color hints (e.g., "Primary color 500 level MUST BE EXACTLY: #ff0000"):
- You MUST use that EXACT hex code for the specified level
- Build the rest of the scale around that exact color
- Do NOT adjust, modify, or "improve" the user's chosen colors
- The 500 level is the base - generate lighter tints (50-400) and darker shades (600-900)

═══════════════════════════════════════════════════════════════
COLOR THEORY & HARMONY RULES
═══════════════════════════════════════════════════════════════

1. COLOR RELATIONSHIPS:
   - If user provides both primary and secondary, respect both exactly
   - If only one color provided, choose complementary (180° apart) or analogous (30-60° apart) for the other
   - Accent color should be 30-60° from primary for visual interest

2. COLOR SCALE GENERATION (10 steps: 50, 100, 200, 300, 400, 500, 600, 700, 800, 900):
   - 500: The base color (use user's hint if provided)
   - 50: Very light tint (~95% lightness)
   - 100-400: Progressive darkening toward 500
   - 600-900: Progressive darkening from 500
   - Maintain consistent saturation across scale (±10%)

3. CONTRAST REQUIREMENTS (WCAG):
   - text.primary on surface.base: minimum 7:1 (AAA)
   - text.secondary on surface.base: minimum 4.5:1 (AA)
   - ALL text must be readable on their backgrounds

4. SEMANTIC COLORS:
   - success: green-family (hue 100-160)
   - warning: amber/orange-family (hue 30-50)
   - error: red-family (hue 0-20 or 340-360)
   - info: blue-family (hue 200-230)
   - Must work on both surface.base AND surface.elevated

═══════════════════════════════════════════════════════════════
TYPOGRAPHY SYSTEM RULES
═══════════════════════════════════════════════════════════════

1. FONT SELECTION (Real Google Fonts only):
   - Luxury/Editorial: Playfair Display, Cormorant, Libre Baskerville, Lora
   - Tech/Modern: Inter, Manrope, DM Sans, Space Grotesk, Plus Jakarta Sans
   - Brutalist: Bebas Neue, Oswald, Anton, Rubik Mono One
   - Organic/Warm: Source Sans Pro, Nunito, Open Sans, Rubik
   - Playful: Nunito, Quicksand, Comfortaa, Poppins
   - Mono: Fira Code, JetBrains Mono, Source Code Pro, IBM Plex Mono

2. TYPE SCALE (use mathematical ratio 1.125-1.333):
   - Each step MUST be noticeably larger than the previous
   - xs: 11-12px, sm: 13-14px, base: 15-18px
   - lg: 18-21px, xl: 20-24px, 2xl: 24-30px
   - 3xl: 30-36px, 4xl: 36-48px, 5xl: 48-60px
   - 6xl: 60-72px, 7xl: 72-96px
   - Example with 1.25 ratio: xs=12, sm=14, base=16, lg=20, xl=24, 2xl=30, 3xl=36, 4xl=48, 5xl=60, 6xl=72, 7xl=96
   - NEVER make consecutive sizes the same or nearly identical - each must be at least 10% larger

3. WEIGHTS: Must include light (300), regular (400), medium (500), semibold (600), bold (700), black (900)

4. LINE HEIGHT: tight (1.1), snug (1.3), normal (1.5), relaxed (1.7), loose (2.0)

═══════════════════════════════════════════════════════════════
SPACING & COMPONENT RULES
═══════════════════════════════════════════════════════════════

1. SPACING BASE: Use 4px base unit
2. SCALE: Exactly [2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128]

3. COMPONENTS:
   - Button height: 36-48px (touch target 44px minimum)
   - Input height: Match button height
   - Badge height: 20-28px
   - Card padding: 16-32px
   - Nav height: 56-72px

═══════════════════════════════════════════════════════════════
SHADOW SYSTEM RULES (MUST HAVE PROGRESSIVE DEPTH)
═══════════════════════════════════════════════════════════════

Shadows MUST progressively increase in size and blur. Examples:
- xs: "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
- sm: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)"
- md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)"
- lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)"
- xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)"
- inner: "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)"

Each level MUST be visually distinct from the others!

═══════════════════════════════════════════════════════════════
MOTION TIMING RULES (MUST USE PROPER CSS VALUES)
═══════════════════════════════════════════════════════════════

Duration - MUST be CSS time values:
- instant: "0ms" or "50ms"
- fast: "150ms"
- normal: "250ms"
- slow: "400ms"
- slower: "600ms"

Easing - MUST be valid CSS easing functions:
- default: "cubic-bezier(0.4, 0, 0.2, 1)" or "ease-in-out"
- in: "cubic-bezier(0.4, 0, 1, 1)" or "ease-in"
- out: "cubic-bezier(0, 0, 0.2, 1)" or "ease-out"
- bounce: "cubic-bezier(0.68, -0.55, 0.265, 1.55)"

═══════════════════════════════════════════════════════════════
COMPONENT TOKEN RULES (MUST USE ACTUAL VALUES)
═══════════════════════════════════════════════════════════════

Component tokens MUST be concrete CSS values (with units), NOT references:
- button.height: "44px" (NOT "var(--space-10)")
- button.paddingX: "24px" (NOT "var(--space-6)")
- button.radius: "8px" (NOT "var(--radius-md)")
- button.fontSize: "16px" or "1rem"
- button.fontWeight: 600 (number)
- card.padding: "24px"
- card.shadow: "0 4px 6px rgba(0,0,0,0.1)" (full shadow value)
- input.borderWidth: "1px"

═══════════════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════════════════════════════════════

- Return ONLY valid JSON matching the schema
- All color values: valid hex codes (#RRGGBB)
- All numbers: actual numbers, not strings
- Font names: real Google Fonts only
- Every field in the schema MUST be present
- No markdown formatting, no explanation, only JSON`;

export async function generateDesignTokens(
  models: LanguageModel[],
  vibe: string,
): Promise<DesignTokens> {
  const errors: Error[] = [];

  for (const model of models) {
    try {
      const result = await generateObject({
        model,
        system: DESIGN_TOKEN_SYSTEM_PROMPT,
        prompt: `Generate a complete design token system for this vibe: "${vibe}"

CRITICAL REQUIREMENTS - YOU MUST GENERATE ALL OF THESE:

1. COLORS - COMPLETE 10-STEP SCALES:
   - primary: Must have ALL keys: 50, 100, 200, 300, 400, 500, 600, 700, 800, 900 (all valid hex colors)
   - secondary: Must have ALL keys: 50, 100, 200, 300, 400, 500, 600, 700, 800, 900 (all valid hex colors)
   - accent: Must have light, base, dark (all valid hex colors)
   - neutral: Must have ALL keys: 50, 100, 200, 300, 400, 500, 600, 700, 800, 900 (all valid hex colors)
   - semantic: Must have success, warning, error, info (all valid hex colors)
   - surface: Must have base, subtle, elevated, overlay (all valid hex colors or rgba)
   - text: Must have primary, secondary, muted, inverse, accent (all valid hex colors)

2. TYPOGRAPHY - COMPLETE SYSTEM:
   - fontSans: Real Google Font name (e.g., "Inter", "Manrope", "DM Sans")
   - fontSerif: Real Google Font name (e.g., "Playfair Display", "Lora")
   - fontMono: Real Google Font name (e.g., "Fira Code", "JetBrains Mono")
   - scale: Must have xs, sm, base, lg, xl, 2xl, 3xl, 4xl, 5xl, 6xl, 7xl (all numbers in pixels)
   - IMPORTANT: Each step must be noticeably larger - use 1.25 ratio minimum
   - Example: xs=12, sm=14, base=16, lg=20, xl=24, 2xl=30, 3xl=38, 4xl=48, 5xl=60, 6xl=72, 7xl=96
   - weights: Must have light, regular, medium, semibold, bold, black (all numbers 300-900)
   - tracking: Must have tight, normal, wide, wider, widest (all CSS em values like "-0.03em")
   - leading: Must have tight, snug, normal, relaxed, loose (all numbers like 1.1, 1.3, 1.5)

3. SPACING - COMPLETE SCALE:
   - base: A number (4 or 8)
   - scale: Array of 15 numbers [2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128]

4. BORDER - COMPLETE SETS:
   - width: Must have hairline, thin, normal, medium, thick (all CSS values like "1px")
   - radius: Must have none, xs, sm, md, lg, xl, 2xl, 3xl, full (all CSS values like "8px")

5. SHADOW - COMPLETE SET (MUST BE PROGRESSIVELY DIFFERENT):
   - Must have: xs, sm, md, lg, xl, inner (all DIFFERENT CSS box-shadow values)
   - xs must be subtle, xl must be dramatic - EACH MUST BE VISUALLY DISTINCT
   - Example: xs="0 1px 2px rgba(0,0,0,0.05)", lg="0 10px 15px rgba(0,0,0,0.1)"

6. GRADIENT - COMPLETE SET:
   - Must have: primary, hero, subtle, surface (all CSS gradient values)

7. MOTION - COMPLETE TIMING (USE PROPER CSS VALUES):
   - duration: Must have instant, fast, normal, slow, slower (CSS time: "150ms", "250ms", etc)
   - easing: Must have default, in, out, bounce (CSS easing: "ease-in-out", "cubic-bezier(...)", etc)

8. COMPONENT - COMPLETE TOKENS (USE CONCRETE VALUES WITH UNITS):
   - button: Must have height, heightSm, heightLg, paddingX, radius, fontWeight, fontSize (e.g., height="44px")
   - card: Must have padding, paddingLg, radius, shadow, border (e.g., padding="24px", shadow="0 4px 6px rgba(0,0,0,0.1)")
   - input: Must have height, paddingX, paddingY, radius, borderWidth (e.g., borderWidth="1px")
   - badge: Must have height, paddingX, radius, fontSize, fontWeight (e.g., fontSize="14px")
   - nav: Must have height, paddingX (e.g., height="64px")

9. META - REQUIRED INFO:
    - vibeName: Short name for this system
    - description: One sentence description
    - aesthetic: The overall aesthetic (e.g., "dark", "light", "bold")
    - palette: Color mode (e.g., "dark", "light", "colorful")
    - instructions: Design instructions for HTML generation - specific guidance on layout style, composition patterns, visual hierarchy, spacing preferences, and any creative direction that should be followed when generating social media posts with this design system. Write 2-4 sentences of actionable guidance.

VALIDATION RULES:
- Every field listed above MUST be present in your response
- All hex colors must be valid 6-character hex codes like #ff0000
- All numbers must be actual numbers, not strings
- Apply proper color theory - use harmonious relationships
- Ensure text/surface contrast meets WCAG AA (4.5:1 minimum)
- Return ONLY valid JSON matching the exact schema, no explanation`,
        schema: DESIGN_TOKEN_SCHEMA,
        temperature: 0.9,
      });
      return result.object;
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : String(error);
      console.error(`[design-token-agent] Provider failed:`, errMsg);
      errors.push(error instanceof Error ? error : new Error(String(error)));
      if (!isRetryableError(error)) throw error;
    }
  }

  const errorDetails = errors.map(e => e.message).join('; ');
  throw new Error(`Design token generation failed across all providers: ${errorDetails}`);
}

function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return msg.includes("429") || msg.includes("too many requests") || msg.includes("quota exceeded") || msg.includes("rate limit") || msg.includes("500") || msg.includes("503");
  }
  return false;
}
