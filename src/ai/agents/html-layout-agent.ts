import { generateText, streamText, type LanguageModel } from "ai";
import { createPromptConfig, type PromptConfig } from "../../lib/prompt-utils.js";
import type { WorkspaceSettings } from "../../lib/settings.js";

export interface HtmlLayoutOutput {
  generated_html: string;
}

export interface StreamCallbacks {
  onChunk?: (chunk: string) => void;
  onComplete?: (html: string) => void;
  onError?: (error: Error) => void;
}

const HTML_LAYOUT_SYSTEM_PROMPT = `You are an elite social media visual designer and modern web layout engineer.

Your task is to generate ONE COMPLETE, SELF-CONTAINED HTML document for a social media visual post.

Rules:
- The HTML must be a full standalone document with <!DOCTYPE html>, <html>, <head>, and <body>
- Use Tailwind CSS via CDN: <script src="https://cdn.tailwindcss.com"></script>
- Use normal Tailwind utility classes for all styling (e.g. bg-gray-900, text-white, font-bold, p-8)
- Write clean, professional HTML like a normal web developer would
- The design must be exactly sized for the given width x height viewport
- Prioritize platform-native composition that performs well as an image in social feeds
- Build strong visual hierarchy with clear focal point, fast scannability, and thumbnail legibility
- Typography must be bold, professional, and highly readable at first glance
- The design must feel premium, dynamic, and conversion-oriented
- Never include text in generated images - all text is HTML/CSS
- No external libraries except Tailwind CDN
- Return ONLY the HTML document as raw text
- Do not return JSON
- Do not return captions, notes, markdown fences, or explanations`;

export interface HtmlLayoutArgs {
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
  userInstructions?: string | string[];
  userInstructionsAppend?: string;
  settings?: WorkspaceSettings | null;
  generatedImage?: {
    dataUrl: string;
    imageType: string;
    prompt: string;
  };
}

function buildPrompt(args: HtmlLayoutArgs): string {
  const renderedUserInstructionBlock = renderUserInstructionBlock(args);
  
  return `Generate a social post design for the platform: ${args.platform}${args.formatName ? ` (${args.formatName})` : ""} (${args.width}x${args.height}).

${args.formatInstruction ? `FORMAT-SPECIFIC CREATIVE DIRECTION:\n${args.formatInstruction}\n` : ""}

Source Content Title: ${args.title}
Source Content Excerpt: ${args.excerpt}

Source Content:
${args.content}

${args.generatedImage ? `GENERATED IMAGE AVAILABLE:
- Image Type: ${args.generatedImage.imageType}
- Generation Prompt: ${args.generatedImage.prompt}
- Data URL: ${args.generatedImage.dataUrl}

IMPORTANT: Use this generated image in your HTML as a background or prominent visual element. Use it as src attribute for an <img> tag or as a CSS background-image.
` : ""}

${args.userPrompt ? `User specifically asked for: ${args.userPrompt}` : ""}
${args.userInstructionsAppend ? `Additional rendering constraints:\n${args.userInstructionsAppend}` : ""}

${renderedUserInstructionBlock}

Instructions:
- Create a high-impact visual design using the source content.
- Use normal Tailwind classes for styling.
- Keep typography highly readable with clear hierarchy.
${args.generatedImage ? "- Incorporate the generated image effectively in the design layout." : ""}

Return only one complete HTML document as raw text.`;
}

export async function generateHtmlLayout(
  models: LanguageModel[],
  args: HtmlLayoutArgs,
): Promise<HtmlLayoutOutput> {
  const errors: Error[] = [];
  
  // Create enhanced prompt configuration
  const promptConfig = createPromptConfig(
    HTML_LAYOUT_SYSTEM_PROMPT,
    args.settings,
    'htmlGeneration'
  );
  
  // Combine system prompts: base + custom + additional system prompt
  const finalSystemPrompt = [
    promptConfig.system,
    args.systemPrompt
  ].filter(Boolean).join("\n\n");

  for (const model of models) {
    try {
      const result = await generateText({
        model,
        system: finalSystemPrompt,
        prompt: buildPrompt(args),
        temperature: 0.7,
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

/**
 * STREAMING: Generate HTML layout with streaming support for real-time progress.
 * Returns an async generator that yields chunks as they arrive.
 */
export async function* streamHtmlLayout(
  models: LanguageModel[],
  args: HtmlLayoutArgs,
): AsyncGenerator<{ type: "chunk" | "complete" | "error"; data: string }> {
  const errors: Error[] = [];
  
  // Create enhanced prompt configuration
  const promptConfig = createPromptConfig(
    HTML_LAYOUT_SYSTEM_PROMPT,
    args.settings,
    'htmlGeneration'
  );
  
  // Combine system prompts: base + custom + additional system prompt
  const finalSystemPrompt = [
    promptConfig.system,
    args.systemPrompt
  ].filter(Boolean).join("\n\n");

  for (const model of models) {
    try {
      const result = streamText({
        model,
        system: finalSystemPrompt,
        prompt: buildPrompt(args),
        temperature: 0.7,
      });

      let fullText = "";
      
      for await (const chunk of result.textStream) {
        fullText += chunk;
        yield { type: "chunk", data: chunk };
      }

      const generatedHtml = extractHtml(fullText);
      yield { type: "complete", data: generatedHtml };
      return;
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      errors.push(err);
      if (!isRetryableError(error)) {
        yield { type: "error", data: err.message };
        throw error;
      }
    }
  }

  const aggregateError = new AggregateError(errors, "HTML layout generation failed across all providers");
  yield { type: "error", data: aggregateError.message };
  throw aggregateError;
}

function renderUserInstructionBlock(args: {
  platform: string;
  formatName?: string;
  width: number;
  height: number;
  title: string;
  excerpt: string;
  content: string;
  designTokens: string;
  userInstructions?: string | string[];
}): string {
  const lines = toLines(args.userInstructions);
  if (lines.length === 0) return "";

  const replacements: Record<string, string> = {
    "<platform>": `${args.platform}${args.formatName ? ` (${args.formatName})` : ""}`,
    "<width>": String(args.width),
    "<height>": String(args.height),
    "<title>": args.title,
    "<excerpt>": args.excerpt,
    "<content>": args.content,
    "<design_tokens>": args.designTokens,
  };

  const rendered = lines
    .map((line) => {
      let next = line;
      for (const [token, value] of Object.entries(replacements)) {
        next = next.split(token).join(value);
      }
      return next;
    })
    .join("\n")
    .trim();

  return rendered ? `Configured layout instructions:\n${rendered}` : "";
}

function toLines(value: string | string[] | undefined): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.map((line) => String(line).trim()).filter(Boolean);
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
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
