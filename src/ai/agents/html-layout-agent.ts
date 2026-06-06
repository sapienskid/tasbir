import { generateText, streamText, type LanguageModel } from "ai";
import { createPromptConfig, type PromptConfig } from "../../lib/prompt-utils.js";
import type { WorkspaceSettings } from "../../lib/settings.js";

import { HTML_LAYOUT_SYSTEM_PROMPT } from "../../prompts.js";
import { fillTemplateSlots } from "../../lib/templates.js";

export interface HtmlLayoutOutput {
  generated_html: string;
  template_html?: string;
  slot_values?: Record<string, string>;
}

export interface StreamCallbacks {
  onChunk?: (chunk: string) => void;
  onComplete?: (html: string) => void;
  onError?: (error: Error) => void;
}


export interface HtmlLayoutArgs {
  platform: string;
  formatName?: string;
  formatInstruction?: string;
  width: number;
  height: number;
  title: string;
  excerpt: string;
  content: string;
  /**
   * Design brief for the AI - can be either:
   * - Semantic brief (lightweight, ~500 tokens) from formatSemanticBriefForPrompt()
   * - Full token dump (heavy, ~3000 tokens) from formatDesignTokensForPromptFromObject()
   * 
   * Prefer semantic brief for token efficiency.
   */
  designBrief: string;
  /** @deprecated Use designBrief instead */
  designTokens?: string;
  userPrompt?: string;
  systemPrompt?: string;
  userInstructions?: string | string[];
  userInstructionsAppend?: string;
  settings?: WorkspaceSettings | null;
  /** Generated AI image for this post */
  generatedImage?: {
    dataUrl: string;
    imageType: string;
    prompt: string;
  };
  /** Image specification from orchestrator */
  imageSpec?: {
    type: string;
    position: string;
    count: number;
  };
}

function buildPrompt(args: HtmlLayoutArgs): string {
  // Support both new designBrief and legacy designTokens
  const designInfo = args.designBrief || args.designTokens || '';
  const renderedUserInstructionBlock = renderUserInstructionBlock({
    ...args,
    designTokens: designInfo, // For template replacement compatibility
  });
  
  return `Generate a social post design for the platform: ${args.platform}${args.formatName ? ` (${args.formatName})` : ""} (${args.width}x${args.height}).

${args.formatInstruction ? `FORMAT-SPECIFIC CREATIVE DIRECTION:\n${args.formatInstruction}\n` : ""}

Source Content Title: ${args.title}
Source Content Excerpt: ${args.excerpt}

Source Content:
${args.content}

${designInfo}

  ${args.settings?.brand ? `BRAND GUIDELINES (MANDATORY - FOLLOW THESE CLOSELY):
- Brand Name: ${args.settings.brand.name || 'Not specified'}
- Brand Tone: ${args.settings.brand.tone || 'Not specified'}
- Target Audience: ${args.settings.brand.audience || 'Not specified'}
${args.settings.brand.logo_url ? `- Brand Logo: AVAILABLE - You MUST include the logo using exactly this variable: {{brand_logo}}
- Example: <img src="{{brand_logo}}" class="w-12 h-12 object-contain" alt="${args.settings.brand.name || 'Brand'} Logo">` : '- Brand Logo: Not provided'}
${args.settings.campaign?.cta ? `- Default CTA: "${args.settings.campaign.cta}" - Use this or a contextually appropriate variation` : ''}
${args.settings.campaign?.framework ? `- Copywriting Framework: ${args.settings.campaign.framework}` : ''}
${args.settings.campaign?.goal ? `- Campaign Goal: ${args.settings.campaign.goal}` : ''}
${args.settings.campaign?.hashtags?.style && args.settings.campaign.hashtags.style !== "none" && (args.settings.campaign.hashtags.count || 0) > 0 ? `- Hashtag Style: ${args.settings.campaign.hashtags.style} (max ${args.settings.campaign.hashtags.count})` : ''}
` : ""}

  ${args.generatedImage ? `GENERATED IMAGE AVAILABLE:
- Image Type: ${args.generatedImage.imageType}
- Position: ${args.imageSpec?.position || 'background'}
- Count: ${args.imageSpec?.count || 1}

IMAGE USAGE RULES (MANDATORY - YOU MUST INCLUDE THE IMAGE):
- You MUST include the generated image in your HTML design. Do NOT omit it.
- Embed the generated image using exactly this variable for the src/url: {{image_url}}
- Example (img tag): <img src="{{image_url}}" class="w-full h-full object-cover">
- Example (css bg): <div style="background-image: url('{{image_url}}');" class="bg-cover bg-center"></div>
- Position: ${args.imageSpec?.position || 'background'} (background | hero | left | right | overlay)
- For background: use as full-bleed background with text overlay on top (add gradient overlay for text readability)
- For hero: place image at top, text below in content area
- For left/right: split layout with image on one side, text on other
- For overlay: place image behind text with gradient overlay for readability
- NEVER put text INSIDE the image - text goes in HTML elements on top
- Never use placeholder domains or fake urls. Use EXACTLY {{image_url}}
- The image will be provided at render time - your HTML MUST contain {{image_url}} placeholder
` : ""}

${args.userPrompt ? `User specifically asked for: ${args.userPrompt}` : ""}
${args.userInstructionsAppend ? `Additional rendering constraints:\n${args.userInstructionsAppend}` : ""}

${renderedUserInstructionBlock}

CRITICAL LAYOUT RULES:
- The canvas size is EXACTLY ${args.width}x${args.height} pixels
- Use overflow-hidden on the root container to prevent content from spilling
- All content must fit within the ${args.width}x${args.height} frame - NO overflow, NO scrollbars
- Use proper spacing (p-4, p-6, p-8) to create breathing room
- Text should be readable without being too small or too large
- For multi-line text, use line-clamp or truncate if needed
- PREVENT TEXT OVERLAPPING: Always use adequate line-height (leading-relaxed/leading-loose), proper margins between text elements (mb-2, mb-4, mb-6), and padding
- Use flex/grid layouts with gap (gap-4, gap-6) instead of absolute positioning for text elements
- Ensure text containers have max-width (max-w-xs, max-w-md, max-w-lg) to prevent overly wide lines
- Use truncate or line-clamp-2/line-clamp-3 for long text that might overflow
- Minimum font size for body text: 14px (text-base). Headlines: 24px+ (text-2xl+)
- Never stack text elements directly without margin/padding between them

Instructions:
- Create a high-impact social post visual using the source content.
- Keep it as a single-frame composition, not a webpage.
- Use semantic Tailwind classes from the design system (bg-surface-base, text-content-primary, etc.).
- CSS variables (var(--color-...), var(--surface-...), etc.) will be injected at render time.
- Ensure content fits the fixed frame with no overflow, clipping, or hidden text.
- Keep typography highly readable with clear hierarchy.
- Match the requested style and content density while preserving legibility and composition balance.
${args.generatedImage ? "- Incorporate the generated image effectively in the design layout per the specified position." : ""}

Return only one complete HTML document as raw text.`;
}

function extractSlotsFromResponse(text: string): Record<string, string> {
  // Strategy 1: Look for ```json ... ``` code block
  const jsonBlockMatch = text.match(/```json\s*(\{[\s\S]*?\})\s*```/i);
  if (jsonBlockMatch) {
    try { return JSON.parse(jsonBlockMatch[1]); } catch {}
  }
  
  // Strategy 2: Look for ``` ... ``` code block with JSON-like content
  const codeBlockMatch = text.match(/```\s*(\{[\s\S]*?\})\s*```/);
  if (codeBlockMatch) {
    try { return JSON.parse(codeBlockMatch[1]); } catch {}
  }
  
  // Strategy 3: Find the last complete JSON object in the text
  const bracePositions: number[] = [];
  let depth = 0;
  let start = -1;
  
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '{') {
      if (depth === 0) start = i;
      depth++;
    } else if (text[i] === '}') {
      if (depth > 0) {
        depth--;
        if (depth === 0 && start >= 0) {
          bracePositions.push(start);
          start = -1;
        }
      }
    }
  }
  
  // Try from the last complete JSON object backwards
  for (let i = bracePositions.length - 1; i >= 0; i--) {
    const startPos = bracePositions[i];
    // Find matching closing brace
    let depth2 = 0;
    for (let j = startPos; j < text.length; j++) {
      if (text[j] === '{') depth2++;
      else if (text[j] === '}') {
        depth2--;
        if (depth2 === 0) {
          try {
            const candidate = text.slice(startPos, j + 1);
            const parsed = JSON.parse(candidate);
            // Verify it looks like slot values (string key-value pairs)
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
              const allStrings = Object.values(parsed).every(v => typeof v === 'string');
              if (allStrings || Object.keys(parsed).length === 0) {
                return parsed;
              }
            }
          } catch {}
          break;
        }
      }
    }
  }
  
  // Strategy 4: Try to find key-value patterns in the text
  const slotPattern = /\{\{(\w+)\}\}/g;
  const slots = new Set<string>();
  let match;
  while ((match = slotPattern.exec(text)) !== null) {
    slots.add(match[1]);
  }
  
  // If we found slot placeholders but no values, return empty object
  // The caller will fill them with provided values
  return {};
}

export async function generateHtmlLayout(
  models: LanguageModel[],
  args: HtmlLayoutArgs,
): Promise<HtmlLayoutOutput> {
  const errors: Error[] = [];
  
  const promptConfig = createPromptConfig(
    HTML_LAYOUT_SYSTEM_PROMPT,
    args.settings,
    'htmlGeneration'
  );
  
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

      const templateHtml = extractHtml(result.text);
      let slots: Record<string, string> = {};
      
      slots = extractSlotsFromResponse(result.text);

      if (args.generatedImage?.dataUrl) {
         slots['image_url'] = args.generatedImage.dataUrl;
       }
       if (args.settings?.brand?.logo_url) {
         slots['brand_logo'] = args.settings.brand.logo_url;
       }

       // If slots were successfully extracted, use them, otherwise return raw content as fallback
       let generatedHtml = Object.keys(slots).length > 0 
          ? fillTemplateSlots(templateHtml, slots) 
          : templateHtml;

       // PROGRAMMATIC FIX: Ensure image is embedded even if AI forgot the placeholder
       if (args.generatedImage?.dataUrl && !generatedHtml.includes('{{image_url}}') && !generatedHtml.includes(args.generatedImage.dataUrl)) {
         // Inject image based on position spec
         const position = args.imageSpec?.position || 'background';
         generatedHtml = injectImageIntoHtml(generatedHtml, args.generatedImage.dataUrl, position, args.width, args.height);
       }

       // PROGRAMMATIC FIX: Ensure brand logo is embedded if provided
       if (args.settings?.brand?.logo_url && !generatedHtml.includes('{{brand_logo}}') && !generatedHtml.includes(args.settings.brand.logo_url)) {
         generatedHtml = injectBrandLogoIntoHtml(generatedHtml, args.settings.brand.logo_url, args.settings.brand.name || 'Brand');
       }

      return { 
         generated_html: generatedHtml,
         template_html: templateHtml,
         slot_values: slots
      };
    } catch (error) {
      console.warn("[html-layout-agent] Attempt failed:", error);
      errors.push(error instanceof Error ? error : new Error(String(error)));
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
  
  const promptConfig = createPromptConfig(
    HTML_LAYOUT_SYSTEM_PROMPT,
    args.settings,
    'htmlGeneration'
  );
  
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

      const templateHtml = extractHtml(fullText);
      let slots: Record<string, string> = {};
      
      slots = extractSlotsFromResponse(fullText);

      if (args.generatedImage?.dataUrl) {
         slots['image_url'] = args.generatedImage.dataUrl;
       }
       if (args.settings?.brand?.logo_url) {
         slots['brand_logo'] = args.settings.brand.logo_url;
       }
       let generatedHtml = Object.keys(slots).length > 0 
          ? fillTemplateSlots(templateHtml, slots) 
          : templateHtml;

       // PROGRAMMATIC FIX: Ensure image is embedded even if AI forgot the placeholder
       if (args.generatedImage?.dataUrl && !generatedHtml.includes('{{image_url}}') && !generatedHtml.includes(args.generatedImage.dataUrl)) {
         const position = args.imageSpec?.position || 'background';
         generatedHtml = injectImageIntoHtml(generatedHtml, args.generatedImage.dataUrl, position, args.width, args.height);
       }

       // PROGRAMMATIC FIX: Ensure brand logo is embedded if provided
       if (args.settings?.brand?.logo_url && !generatedHtml.includes('{{brand_logo}}') && !generatedHtml.includes(args.settings.brand.logo_url)) {
         generatedHtml = injectBrandLogoIntoHtml(generatedHtml, args.settings.brand.logo_url, args.settings.brand.name || 'Brand');
       }

      yield { type: "complete", data: generatedHtml };
      return;
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      errors.push(err);
      console.warn("[html-layout-agent] Streaming attempt failed:", err);
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
  designTokens?: string;
  designBrief?: string;
  userInstructions?: string | string[];
}): string {
  const lines = toLines(args.userInstructions);
  if (lines.length === 0) return "";

  const designInfo = args.designBrief || args.designTokens || '';
  const replacements: Record<string, string> = {
    "<platform>": `${args.platform}${args.formatName ? ` (${args.formatName})` : ""}`,
    "<width>": String(args.width),
    "<height>": String(args.height),
    "<title>": args.title,
    "<excerpt>": args.excerpt,
    "<content>": args.content,
    "<design_tokens>": designInfo,
    "<design_brief>": designInfo,
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

function injectImageIntoHtml(html: string, imageDataUrl: string, position: string, width: number, height: number): string {
  const imgTag = `<img src="${imageDataUrl}" class="w-full h-full object-cover" alt="" />`;
  const bgStyle = `background-image: url('${imageDataUrl}'); background-size: cover; background-position: center;`;
  
  let result = html;
  
  // Try to find a suitable container to inject the image
  if (position === 'background' || position === 'overlay') {
    // Add as background to the main container
    result = result.replace(
      /<body[^>]*>/i,
      (match) => `${match}\n<div style="${bgStyle}" class="absolute inset-0 -z-10"></div>`
    );
    // Also add gradient overlay for text readability
    result = result.replace(
      /<div style="background-image: url\('[^']+'\); background-size: cover; background-position: center;" class="absolute inset-0 -z-10"><\/div>/i,
      (match) => `${match}\n<div class="absolute inset-0 -z-10 bg-gradient-to-t from-black/60 via-transparent to-transparent"></div>`
    );
  } else if (position === 'hero') {
    // Insert at the top of the content area
    result = result.replace(
      /<body[^>]*>/i,
      (match) => `${match}\n<div class="w-full h-1/2">${imgTag}</div>`
    );
  } else if (position === 'left' || position === 'right') {
    // Split layout - add to a flex container
    const isLeft = position === 'left';
    const flexContainer = `<div class="flex ${isLeft ? '' : 'flex-row-reverse'} h-full">${imgTag}<div class="flex-1 p-8 flex flex-col justify-center"></div></div>`;
    result = result.replace(
      /<body[^>]*>/i,
      (match) => `${match}\n${flexContainer}`
    );
  }
  
  return result;
}

function injectBrandLogoIntoHtml(html: string, logoUrl: string, brandName: string): string {
  const logoTag = `<img src="${logoUrl}" class="w-12 h-12 object-contain" alt="${brandName} Logo" />`;
  
  // Try to insert logo at the top of the body
  return html.replace(
    /<body[^>]*>/i,
    (match) => `${match}\n<div class="absolute top-4 left-4 z-10">${logoTag}</div>`
  );
}
