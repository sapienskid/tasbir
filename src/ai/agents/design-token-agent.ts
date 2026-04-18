import { generateObject, generateText, type LanguageModel } from "ai";
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
    semanticBrief: z.string().optional(),
  }),
});

export type DesignTokens = z.infer<typeof DESIGN_TOKEN_SCHEMA>;

import { DESIGN_TOKEN_SYSTEM_PROMPT } from "../../prompts.js";

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
    - semanticBrief: A compact (3-5 sentence) natural language summary of this design system for AI agents generating content. Describe: (1) color mood and personality, (2) typography feel, (3) spacing density, (4) overall visual style. Use descriptive terms like "bold saturated colors with high contrast", "airy generous whitespace", "tight compact layout", "playful rounded corners", "sharp brutalist edges". This brief enables AI to make design-aligned decisions WITHOUT seeing full token values.

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
      console.warn("[design-token-agent] generateObject failed, trying generateText fallback:", error);
      try {
        const textResult = await generateText({
          model,
          system: DESIGN_TOKEN_SYSTEM_PROMPT,
          prompt: `Generate a complete design token system for this vibe: "${vibe}"

Return ONLY valid JSON matching the schema. No markdown, no explanation.`,
          temperature: 0.9,
        });

        const jsonStr = extractJsonFromText(textResult.text);
        if (jsonStr) {
          const parsed = JSON.parse(jsonStr);
          const validated = DESIGN_TOKEN_SCHEMA.safeParse(parsed);
          if (validated.success) {
            return validated.data;
          }
          console.warn("[design-token-agent] JSON extracted but validation failed:", validated.error);
        }
      } catch (textError) {
        console.warn("[design-token-agent] generateText fallback also failed:", textError);
      }
      const errMsg = error instanceof Error ? error.message : String(error);
      errors.push(error instanceof Error ? error : new Error(errMsg));
    }
  }

  const errorDetails = errors.map(e => e.message).join('; ');
  throw new Error(`Design token generation failed across all providers: ${errorDetails}`);
}
