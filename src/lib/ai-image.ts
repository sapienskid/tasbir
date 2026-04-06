/**
 * AI Image Generation Service using Cloudflare Workers AI
 * 
 * Generates images based on content analysis to enhance social posts.
 * The AI decides what type of image best fits the content.
 */

import { generateObject } from "ai";
import { z } from "zod";
import { createFastModelChain, resolveProviderConfig, type ProviderConfig } from "../ai/providers";
import { createPromptConfig } from "./prompt-utils.js";
import type { WorkspaceSettings } from "./settings.js";

export type ImageType = "background" | "illustration" | "pattern" | "gradient" | "none";

export interface ImageDecision {
  shouldGenerate: boolean;
  imageType: ImageType;
  prompt: string;
  reasoning: string;
  style: string;
  mood: string;
}

export interface GeneratedImage {
  data: ArrayBuffer;
  prompt: string;
  imageType: ImageType;
}

const ImageDecisionSchema = z.object({
  shouldGenerate: z.boolean().describe("Whether an AI image would enhance this post"),
  imageType: z.enum(["background", "illustration", "pattern", "gradient", "none"]).describe("Type of image to generate"),
  prompt: z.string().describe("Image generation prompt if shouldGenerate is true"),
  reasoning: z.string().describe("Brief explanation of the decision"),
  style: z.string().describe("Visual style (e.g. minimalist, vibrant, editorial, abstract)"),
  mood: z.string().describe("Emotional mood (e.g. professional, energetic, calm, bold)"),
});

/**
 * AI decides what type of image (if any) would best complement the content.
 */
export async function decideImageGeneration(
  providerConfig: ProviderConfig,
  content: {
    title: string;
    excerpt: string;
    contentType?: string;
    brandTone?: string;
  },
  designHints?: {
    primaryColor?: string;
    style?: string;
  },
  settings?: WorkspaceSettings | null
): Promise<ImageDecision> {
  const models = createFastModelChain(providerConfig);
  const model = models[0];

  if (!model) {
    return {
      shouldGenerate: false,
      imageType: "none",
      prompt: "",
      reasoning: "No AI model available",
      style: "",
      mood: "",
    };
  }

  try {
    // Create enhanced prompt configuration
    const promptConfig = createPromptConfig(
      `You are a creative director for social media visual content.
Your job is to decide if and what type of AI-generated image would enhance a social post.

Guidelines:
- Background images: subtle, atmospheric visuals that complement text overlay
- Illustrations: conceptual graphics that represent the content theme
- Patterns: abstract geometric or organic patterns for visual interest
- Gradients: color transitions that create depth (when design tokens suggest gradients)
- None: when the content is best served by typography alone

Consider:
- Content type (quotes work well with backgrounds, data with illustrations)
- Brand tone (professional vs playful affects image style)
- Readability (images should not compete with text)`,
      settings,
      'imageGeneration'
    );

    const result = await generateObject({
      model,
      schema: ImageDecisionSchema,
      system: promptConfig.system,

      prompt: `Decide if this social post needs an AI-generated image:

CONTENT:
Title: ${content.title}
Excerpt: ${content.excerpt}
Type: ${content.contentType || "general"}

BRAND:
Tone: ${content.brandTone || "professional"}
${designHints?.primaryColor ? `Primary color: ${designHints.primaryColor}` : ""}
${designHints?.style ? `Design style: ${designHints.style}` : ""}

If an image would help, provide a detailed prompt for image generation.
The prompt should describe visual elements, NOT include any text.`,
      temperature: 0.4,
    });

    return result.object;
  } catch (error) {
    console.warn("[ai-image] Decision failed:", error);
    return {
      shouldGenerate: false,
      imageType: "none",
      prompt: "",
      reasoning: "AI decision failed",
      style: "",
      mood: "",
    };
  }
}

/**
 * Generate an image using Cloudflare Workers AI.
 */
export async function generateImage(
  ai: Ai,
  prompt: string,
  options?: {
    width?: number;
    height?: number;
    style?: string;
    negativePrompt?: string;
  }
): Promise<GeneratedImage | null> {
  const enhancedPrompt = buildEnhancedPrompt(prompt, options?.style);
  const width = options?.width || 1024;
  const height = options?.height || 1024;

  try {
    const form = new FormData();
    form.append('prompt', enhancedPrompt);
    form.append('width', String(width));
    form.append('height', String(height));

    const formResponse = new Response(form);
    const formStream = formResponse.body!;
    const formContentType = formResponse.headers.get('content-type')!;

    const result = await ai.run("@cf/black-forest-labs/flux-2-klein-9b", {
      multipart: {
        body: formStream,
        contentType: formContentType,
      },
    });

    if (!result || typeof result !== "object") {
      console.warn("[ai-image] Generation returned invalid result");
      return null;
    }

    const imageData = (result as any).image;
    if (!imageData) {
      console.warn("[ai-image] No image data in result");
      return null;
    }

    const arrayBuffer = typeof imageData === "string" 
      ? base64ToArrayBuffer(imageData)
      : imageData;

    return {
      data: arrayBuffer,
      prompt: enhancedPrompt,
      imageType: "background",
    };
  } catch (error) {
    console.error("[ai-image] Generation failed:", error);
    return null;
  }
}

/**
 * Generate multiple images for a post (e.g., different formats may need different images).
 */
export async function generateImagesForFormats(
  ai: Ai,
  decision: ImageDecision,
  formats: Array<{ name: string; width: number; height: number }>
): Promise<Map<string, GeneratedImage | null>> {
  const results = new Map<string, GeneratedImage | null>();

  if (!decision.shouldGenerate || decision.imageType === "none") {
    return results;
  }

  // Generate images in parallel for all formats
  const generatePromises = formats.map(async (format) => {
    const image = await generateImage(ai, decision.prompt, {
      width: format.width,
      height: format.height,
      style: decision.style,
    });
    return { format: format.name, image };
  });

  const generated = await Promise.all(generatePromises);
  
  for (const { format, image } of generated) {
    results.set(format, image);
  }

  return results;
}

/**
 * Build an enhanced prompt with style and quality modifiers.
 */
function buildEnhancedPrompt(basePrompt: string, style?: string): string {
  const styleModifiers = style ? `, ${style} style` : "";
  const qualityModifiers = "high quality, professional, clean composition, illustration style";
  
  // Add constraints for illustration-only (no text, no people, no photos)
  const constraints = [
    "no text",
    "no letters",
    "no words", 
    "no typography",
    "no watermarks",
    "no people",
    "no humans",
    "no faces",
    "no portraits",
    "no realistic photos",
    "no photographs",
    "illustration only",
    "abstract art",
    "geometric shapes",
    "modern design",
  ].join(", ");
  
  return `${basePrompt}, ${styleModifiers}, ${qualityModifiers}, ${constraints}`;
}

const DEFAULT_NEGATIVE_PROMPT = [
  "text", "letters", "words", "typography", "watermark", "logo",
  "signature", "caption", "label", "number", "symbol",
  "blurry", "low quality", "distorted", "ugly", "deformed",
  "person", "human", "face", "portrait", "photo", "photograph",
  "realistic", "skin", "eye", "nose", "mouth", "hair",
].join(", ");

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  // Handle data URL format
  const base64Data = base64.includes(",") ? base64.split(",")[1] : base64;
  const binaryString = atob(base64Data);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Convert image ArrayBuffer to base64 data URL for embedding in HTML.
 */
export function imageToDataUrl(imageData: ArrayBuffer, mimeType: string = "image/png"): string {
  const bytes = new Uint8Array(imageData);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return `data:${mimeType};base64,${btoa(binary)}`;
}
