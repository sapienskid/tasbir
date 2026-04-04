import { generateObject, type LanguageModel } from "ai";
import { z } from "zod";

const HTML_LAYOUT_SCHEMA = z.object({
  generated_html: z.string(),
  instagram_caption: z.string(),
  twitter_caption: z.string(),
  linkedin_caption: z.string(),
  carousel_slides: z.array(z.object({ heading: z.string(), body: z.string() })).min(1),
  image_prompt: z.string(),
  stock_search_query: z.string(),
  use_feature_image: z.boolean(),
});

export type HtmlLayoutOutput = z.infer<typeof HTML_LAYOUT_SCHEMA>;

const HTML_LAYOUT_SYSTEM_PROMPT = `You are a master of Swiss-style layout design and modern web development.

Your task is to generate ONE COMPLETE, SELF-CONTAINED HTML document for a social media post.

Rules:
- The HTML must be a full standalone document with <!DOCTYPE html>, <html>, <head>, and <body>
- Use Tailwind CSS via CDN
- Configure Tailwind with the provided design tokens
- Use Tailwind utility classes for all styling
- The design must be exactly sized for the given width x height viewport
- Typography must be bold, professional, and highly readable
- The design must feel PREMIUM, DYNAMIC, and visually striking
- Never include text in generated images - all text is HTML/CSS
- No external libraries except Tailwind CDN
- Output should be the complete HTML document string`;

export async function generateHtmlLayout(
  models: LanguageModel[],
  args: {
    platform: string;
    width: number;
    height: number;
    title: string;
    excerpt: string;
    content: string;
    designTokens: string;
    userPrompt?: string;
  },
): Promise<HtmlLayoutOutput> {
  const errors: Error[] = [];

  for (const model of models) {
    try {
      const result = await generateObject({
        model,
        system: HTML_LAYOUT_SYSTEM_PROMPT,
        prompt: `Generate a social post design for the platform: ${args.platform} (${args.width}x${args.height}).

Design tokens: ${args.designTokens}

Source Content Title: ${args.title}
Source Content Excerpt: ${args.excerpt}

Source Content:
${args.content}

${args.userPrompt ? `User specifically asked for: ${args.userPrompt}` : ""}

Instructions: Create a high-impact visual design using the source content. Use Tailwind classes with the provided design tokens.

Return a JSON object with: generated_html, instagram_caption, twitter_caption, linkedin_caption, image_prompt, stock_search_query, use_feature_image, carousel_slides`,
        schema: HTML_LAYOUT_SCHEMA,
        temperature: 0.3,
      });
      return result.object;
    } catch (error) {
      errors.push(error instanceof Error ? error : new Error(String(error)));
      if (!isRetryableError(error)) throw error;
    }
  }

  throw new AggregateError(errors, "HTML layout generation failed across all providers");
}

function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return msg.includes("429") || msg.includes("too many requests") || msg.includes("quota exceeded") || msg.includes("rate limit") || msg.includes("500") || msg.includes("503");
  }
  return false;
}
