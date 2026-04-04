import { generateText, generateObject, type LanguageModel } from "ai";
import { z } from "zod";

const DESIGN_TOKEN_SCHEMA = z.object({
  colors: z.object({
    primary: z.record(z.string(), z.string()),
    secondary: z.record(z.string(), z.string()),
    accent: z.object({ light: z.string(), base: z.string(), dark: z.string() }),
    neutral: z.record(z.string(), z.string()),
    semantic: z.object({ success: z.string(), warning: z.string(), error: z.string(), info: z.string() }),
    surface: z.object({ base: z.string(), subtle: z.string(), elevated: z.string(), overlay: z.string() }),
    text: z.object({ primary: z.string(), secondary: z.string(), muted: z.string(), inverse: z.string(), accent: z.string() }),
  }),
  typography: z.object({
    fontSans: z.string(),
    fontSerif: z.string(),
    fontMono: z.string(),
    scale: z.record(z.string(), z.number()),
    weights: z.record(z.string(), z.number()),
    tracking: z.record(z.string(), z.string()),
    leading: z.record(z.string(), z.number()),
  }),
  spacing: z.object({ base: z.number(), scale: z.array(z.number()) }),
  border: z.object({
    width: z.record(z.string(), z.string()),
    radius: z.record(z.string(), z.string()),
  }),
  shadow: z.record(z.string(), z.string()),
  gradient: z.record(z.string(), z.string()),
  motion: z.object({
    duration: z.record(z.string(), z.string()),
    easing: z.record(z.string(), z.string()),
  }),
  component: z.object({
    button: z.record(z.string(), z.union([z.string(), z.number()])),
    card: z.record(z.string(), z.union([z.string(), z.number()])),
    input: z.record(z.string(), z.union([z.string(), z.number()])),
    badge: z.record(z.string(), z.union([z.string(), z.number()])),
    nav: z.record(z.string(), z.union([z.string(), z.number()])),
  }),
  meta: z.object({
    vibeName: z.string(),
    description: z.string(),
    aesthetic: z.string(),
    palette: z.string(),
  }),
});

export type DesignTokens = z.infer<typeof DESIGN_TOKEN_SCHEMA>;

const DESIGN_TOKEN_SYSTEM_PROMPT = `You are an expert design system architect with a bold, creative eye for color and typography. Generate a complete, production-ready design token system.

CRITICAL RULES FOR COLOR DIVERSITY:
- NEVER use generic blue (#3b82f6), gray, or safe corporate colors unless specifically requested
- Create DISTINCTIVE, MEMORABLE color palettes that perfectly match the vibe
- Primary and secondary colors should be HARMONIOUS but CLEARLY DIFFERENT hues
- Semantic colors (success, warning, error, info) should HARMONIZE with the primary palette - they should feel like they belong together, not generic green/amber/red/blue
- Each vibe should produce a UNIQUE palette - "luxury" should be different from "tech", "organic" should feel natural, etc.
- Be BOLD with color choices - unexpected but beautiful combinations are encouraged
- Surface colors should create proper contrast with text colors
- Consider the aesthetic: warm vs cool, saturated vs muted, dark vs light

TYPOGRAPHY RULES:
- Choose fonts that genuinely match the vibe (don't default to Inter/Roboto unless appropriate)
- Serif for editorial/luxury, display fonts for bold vibes, geometric sans for tech/minimal
- Font weights and tracking should complement the personality

GENERAL RULES:
- All color values must be valid hex codes (#RRGGBB)
- Font names must be real Google Fonts names
- The system must be internally consistent and professionally designed
- Gradients should use colors from the primary/secondary palette
- Return ONLY valid JSON matching the schema, no markdown, no explanation`;

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
        prompt: `Generate a complete, UNIQUE design token system for this vibe: "${vibe}"

Create a distinctive palette that someone would immediately recognize as matching "${vibe}". 
Avoid generic or safe choices - be creative and bold while maintaining professional quality.
The colors, typography, and overall aesthetic should feel cohesive and memorable.`,
        schema: DESIGN_TOKEN_SCHEMA,
        temperature: 0.7,
      });
      return result.object;
    } catch (error) {
      errors.push(error instanceof Error ? error : new Error(String(error)));
      if (!isRetryableError(error)) throw error;
    }
  }

  throw new AggregateError(errors, "Design token generation failed across all providers");
}

function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return msg.includes("429") || msg.includes("too many requests") || msg.includes("quota exceeded") || msg.includes("rate limit") || msg.includes("500") || msg.includes("503");
  }
  return false;
}
