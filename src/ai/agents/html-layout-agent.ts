import { generateText, type LanguageModel } from "ai";

export interface HtmlLayoutOutput {
  generated_html: string;
}

const HTML_LAYOUT_SYSTEM_PROMPT = `You are a master of Swiss-style layout design and modern web development.

Your task is to generate ONE COMPLETE, SELF-CONTAINED HTML document for a social media visual post.

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
- Return ONLY the HTML document as raw text
- Do not return JSON
- Do not return captions, notes, markdown fences, or explanations`;

export async function generateHtmlLayout(
  models: LanguageModel[],
  args: {
    platform: string;
    formatName?: string;
    formatInstruction?: string;
    width: number;
    height: number;
    title: string;
    excerpt: string;
    content: string;
    designTokens: string;
    userPrompt?: string;
    systemPrompt?: string;
    userInstructionsAppend?: string;
  },
): Promise<HtmlLayoutOutput> {
  const errors: Error[] = [];

  for (const model of models) {
    try {
      const result = await generateText({
        model,
        system: [HTML_LAYOUT_SYSTEM_PROMPT, args.systemPrompt || ""].filter(Boolean).join("\n\n"),
        prompt: `Generate a social post design for the platform: ${args.platform}${args.formatName ? ` (${args.formatName})` : ""} (${args.width}x${args.height}).

${args.formatInstruction ? `FORMAT-SPECIFIC CREATIVE DIRECTION:\n${args.formatInstruction}\n` : ""}

Design tokens: ${args.designTokens}

Source Content Title: ${args.title}
Source Content Excerpt: ${args.excerpt}

Source Content:
${args.content}

${args.userPrompt ? `User specifically asked for: ${args.userPrompt}` : ""}
${args.userInstructionsAppend ? `Additional rendering constraints:\n${args.userInstructionsAppend}` : ""}

Instructions: Create a high-impact visual design using the source content. Use Tailwind classes with the provided design tokens.

Return only one complete HTML document as raw text.`,
        temperature: 0.3,
      });

      const generatedHtml = extractHtml(result.text);
      return { generated_html: generatedHtml };
    } catch (error) {
      errors.push(error instanceof Error ? error : new Error(String(error)));
      if (!isRetryableError(error)) throw error;
    }
  }

  throw new AggregateError(errors, "HTML layout generation failed across all providers");
}

function extractHtml(text: string): string {
  const cleaned = text.trim().replace(/^```(?:html)?\s*/i, "").replace(/```\s*$/i, "").trim();
  if (/<!doctype html>/i.test(cleaned)) return cleaned;

  const htmlStart = cleaned.search(/<html[\s>]/i);
  const htmlEnd = cleaned.search(/<\/html>/i);
  if (htmlStart >= 0 && htmlEnd > htmlStart) {
    return `<!DOCTYPE html>\n${cleaned.slice(htmlStart, htmlEnd + 7).trim()}`;
  }

  return cleaned;
}

function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return msg.includes("429") || msg.includes("too many requests") || msg.includes("quota exceeded") || msg.includes("rate limit") || msg.includes("500") || msg.includes("503");
  }
  return false;
}
