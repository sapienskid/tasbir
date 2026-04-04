import { PIPELINE_CONFIG, formatDesignTokensForPrompt } from "./config";
import { GoogleGenerativeAI } from "@google/generative-ai";

export interface LlmPromptOverrides {
  systemPrompt?: string | string[];
  userInstructions?: string | string[];
  userInstructionsAppend?: string;
  temperature?: number;
  maxTokens?: number;
}

export interface CarouselSlide {
  heading: string;
  body: string;
}

export interface LlmOutput {
  instagram_caption: string;
  twitter_caption: string;
  linkedin_caption: string;
  hashtags: string[];
  image_prompt: string;
  stock_search_query: string;
  use_feature_image: boolean;
  generated_html: string;
  carousel_slides: CarouselSlide[];
}

export interface LlmSourcePost {
  id: string;
  title: string;
  slug: string;
  url: string;
  html?: string;
  plaintext?: string;
  excerpt?: string;
  custom_excerpt?: string;
  feature_image?: string;
  tags?: Array<{ name?: string }>;
  primary_tag?: { name?: string };
}

const AGENT_CONFIG = (PIPELINE_CONFIG.generation?.agents ?? {}) as Record<string, any>;
const AGENT_MODELS = (AGENT_CONFIG.models ?? {}) as Record<string, any>;
const AGENT_RUNTIME = (AGENT_CONFIG.runtime ?? {}) as Record<string, any>;
const AGENT_PROMPTS = (AGENT_CONFIG.prompts ?? {}) as Record<string, any>;
const GEMINI_PROMPTS = {
  system_prompt: (PIPELINE_CONFIG.generation?.agents?.prompts?.gemini_html_generation_system_prompt ?? []) as unknown as string[],
  user_instructions: (PIPELINE_CONFIG.generation?.agents?.prompts?.gemini_html_generation_user_instructions ?? []) as unknown as string[],
};

const DEFAULT_LLM_MODEL = "gemini-2.0-flash";
const DEFAULT_COPY_TEMPERATURE = clampNumber(toFiniteNumber(AGENT_RUNTIME.copy_temperature), 0, 2, 0.2);
const DEFAULT_COPY_MAX_TOKENS = Math.round(clampNumber(toFiniteNumber(AGENT_RUNTIME.copy_max_tokens), 256, 4096, 2200));

function buildLlmJsonSchema(): Record<string, unknown> {
  return {
    type: "object",
    properties: {
      instagram_caption: { type: "string" },
      twitter_caption: { type: "string" },
      linkedin_caption: { type: "string" },
      carousel_slides: {
        type: "array",
        items: {
          type: "object",
          properties: {
            heading: { type: "string" },
            body: { type: "string" }
          },
          required: ["heading", "body"]
        }
      },
      hashtags: {
        type: "array",
        items: { type: "string" }
      },
      image_prompt: { type: "string" },
      stock_search_query: { type: "string" },
      use_feature_image: { type: "boolean" },
      generated_html: { type: "string" }
    },
    required: [
      "instagram_caption",
      "twitter_caption",
      "linkedin_caption",
      "carousel_slides",
      "hashtags",
      "image_prompt",
      "stock_search_query",
      "use_feature_image",
      "generated_html"
    ]
  } satisfies Record<string, unknown>;
}

export async function generateHtmlWithGemini(args: {
  apiKey: string;
  post: LlmSourcePost;
  platform: string;
  width: number;
  height: number;
  userPrompt?: string;
  llmOverrides?: LlmPromptOverrides;
}): Promise<LlmOutput> {
  const genAI = new GoogleGenerativeAI(args.apiKey);
  const model = genAI.getGenerativeModel({
    model: DEFAULT_LLM_MODEL,
    generationConfig: {
      responseMimeType: "application/json",
    }
  });

  const designTokens = formatDesignTokensForPrompt();

  const systemPrompt = normalizePromptLines(GEMINI_PROMPTS.system_prompt).join("\n");
  const userInstructions = normalizePromptLines(GEMINI_PROMPTS.user_instructions).join("\n")
    .replace("<platform>", args.platform)
    .replace("<width>", String(args.width))
    .replace("<height>", String(args.height))
    .replace("<title>", args.post.title)
    .replace("<excerpt>", args.post.custom_excerpt || args.post.excerpt || "")
    .replace("<design_tokens>", designTokens);

  const prompt = [
    userInstructions,
    args.userPrompt ? `User specifically asked for: ${args.userPrompt}` : "",
    "Source Content:",
    args.post.plaintext || args.post.html || "",
  ].filter(Boolean).join("\n\n");

  const result = await model.generateContent({
    contents: [
      { role: "user", parts: [{ text: `${systemPrompt}\n\n${prompt}` }] }
    ]
  });

  const response = await result.response;
  const text = response.text();
  const parsed = JSON.parse(text);

  return normalizeLlmOutput(parsed, {
    title: args.post.title,
    fallbackText: args.post.custom_excerpt || args.post.excerpt || args.post.plaintext || "",
    hasFeatureImage: Boolean(args.post.feature_image)
  });
}

function normalizeLlmOutput(
  payload: Record<string, unknown>,
  args: {
    title: string;
    fallbackText: string;
    hasFeatureImage: boolean;
  }
): LlmOutput {
  const limits = PIPELINE_CONFIG.generation.limits;
  const cleanedFallbackText = normalizeSourceContent(args.fallbackText) || args.fallbackText;
  const captions = normalizePlatformCaptions(
    {
      instagram: toText(payload.instagram_caption),
      twitter: toText(payload.twitter_caption),
      linkedin: toText(payload.linkedin_caption)
    },
    {
      title: args.title,
      fallbackText: cleanedFallbackText
    }
  );

  const rawHashtags = Array.isArray(payload.hashtags) ? payload.hashtags : [];
  const hashtags = normalizeHashtags(rawHashtags, args.title, cleanedFallbackText);

  const imagePromptFallbackTemplate = (PIPELINE_CONFIG.generation.image as any).prompt_fallback || "<title>, modern editorial photo, clean composition, natural lighting, no text overlay";
  const imagePromptFallback = imagePromptFallbackTemplate.replace("<title>", args.title);
  const imagePrompt = ensureLength(toText(payload.image_prompt), limits.image_prompt_max_chars, imagePromptFallback);

  const stockSearchQueryFallback = args.title.replace(/[^a-zA-Z0-9\s]/g, " ").slice(0, 100);
  const stockSearchQuery = ensureLength(toText(payload.stock_search_query), 200, stockSearchQueryFallback);

  return {
    instagram_caption: captions.instagram,
    twitter_caption: captions.twitter,
    linkedin_caption: captions.linkedin,
    hashtags,
    image_prompt: imagePrompt,
    stock_search_query: stockSearchQuery,
    use_feature_image: args.hasFeatureImage && Boolean(payload.use_feature_image),
    generated_html: toText(payload.generated_html),
    carousel_slides: (payload.carousel_slides as any) || []
  };
}

function normalizePlatformCaptions(
  captions: { instagram: string; twitter: string; linkedin: string },
  context: { title: string; fallbackText: string }
): { instagram: string; twitter: string; linkedin: string } {
  const limits = PIPELINE_CONFIG.generation.limits;
  const fallbackCaption = normalizeSourceContent(context.fallbackText) || context.title;

  return {
    instagram: normalizeCaptionText(captions.instagram, context.title, limits.instagram_caption_max_chars, fallbackCaption),
    twitter: normalizeCaptionText(captions.twitter, context.title, limits.twitter_caption_max_chars, fallbackCaption),
    linkedin: normalizeCaptionText(captions.linkedin, context.title, limits.linkedin_caption_max_chars, fallbackCaption)
  };
}

function normalizeCaptionText(rawText: string, title: string, maxChars: number, fallbackText: string): string {
  const cleaned = removeTitlePrefix(normalizeSourceContent(rawText), title);
  const fallback = removeTitlePrefix(normalizeSourceContent(fallbackText), title) || normalizeSourceContent(title);
  const source = cleaned || fallback || title;
  return ensureLength(source, maxChars, fallback || title);
}

export function normalizeSourceContent(input: string): string {
  if (!input) {
    return "";
  }

  return input
    .replace(/\r\n/g, "\n")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+[.)]\s+/gm, "")
    .replace(/^[#]+(?=\S)/gm, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{2,}/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function removeTitlePrefix(value: string, title: string): string {
  if (!value) {
    return "";
  }
  const safeTitle = normalizeSourceContent(title);
  if (!safeTitle) {
    return value.trim();
  }

  const titlePattern = new RegExp(`^${escapeRegExp(safeTitle)}(?:\\s*[:\\-–—|]\\s*|\\s+)`, "i");
  const stripped = value.replace(titlePattern, "").trim();
  if (stripped && canonicalText(value).startsWith(canonicalText(safeTitle))) {
    return stripped;
  }
  return value.trim();
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function canonicalText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeHashtags(rawTags: unknown[], title: string, fallbackText: string): string[] {
  const limits = PIPELINE_CONFIG.generation.limits;
  const seeded = [
    ...rawTags.map((tag) => toText(tag)),
    ...title
      .split(/\s+/)
      .map((word) => word.replace(/[^\p{L}\p{N}]/gu, ""))
      .filter((word) => word.length >= limits.title_keyword_min_chars),
    ...fallbackText
      .split(/\s+/)
      .map((word) => word.replace(/[^\p{L}\p{N}]/gu, ""))
      .filter((word) => word.length >= limits.fallback_keyword_min_chars)
  ];

  const unique: string[] = [];
  for (const raw of seeded) {
    if (!raw) {
      continue;
    }
    const cleaned = raw
      .toLowerCase()
      .replace(/^#+/, "")
      .replace(/[^\p{L}\p{N}]/gu, "");
    if (!cleaned || cleaned.length < limits.hashtag_min_token_chars) {
      continue;
    }
    const tag = `#${cleaned}`;
    if (!unique.includes(tag)) {
      unique.push(tag);
    }
    if (unique.length >= limits.hashtag_max_count) {
      break;
    }
  }

  while (unique.length < limits.hashtag_min_count) {
    unique.push(`#insight${unique.length + 1}`);
  }

  return unique.slice(0, limits.hashtag_max_count);
}

function stripHtml(html: string): string {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function toText(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function toFiniteNumber(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return undefined;
  }
  return value;
}

function toSingleSentence(text: string): string {
  const maxChars = PIPELINE_CONFIG.generation.limits.single_sentence_max_chars;
  const normalized = text.replace(/\s+/g, " ").trim();
  const match = normalized.match(/^(.+?[.!?])(?:\s|$)/);
  if (match?.[1]) {
    return ensureLength(match[1].trim(), maxChars, normalized);
  }
  return ensureLength(normalized, maxChars, normalized);
}

function ensureLength(value: string, max: number, fallback: string): string {
  const source = value.trim() || fallback.trim() || PIPELINE_CONFIG.generation.fallbacks.untitled_text;
  if (source.length <= max) {
    return source;
  }

  const sentenceWindow = source.slice(0, max);
  const sentenceBoundary = Math.max(
    sentenceWindow.lastIndexOf("."),
    sentenceWindow.lastIndexOf("!"),
    sentenceWindow.lastIndexOf("?")
  );
  if (sentenceBoundary >= Math.floor(max * 0.55)) {
    return source.slice(0, sentenceBoundary + 1).trimEnd();
  }

  const maxBody = Math.max(1, max - 1);
  const sliced = source.slice(0, maxBody);
  const wordBoundary = sliced.lastIndexOf(" ");
  const cutoff = wordBoundary >= Math.floor(max * 0.55) ? sliced.slice(0, wordBoundary) : sliced;
  return `${cutoff.trimEnd()}…`;
}

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const numeric = typeof value === "number" && Number.isFinite(value) ? value : fallback;
  return Math.min(max, Math.max(min, numeric));
}

function normalizePromptLines(input: unknown): string[] {
  if (!input) {
    return [];
  }
  const rawLines = Array.isArray(input) ? input : [input];
  return rawLines
    .map((line) => (typeof line === "string" ? line.trim() : ""))
    .filter(Boolean)
    .slice(0, 80)
    .map((line) => ensureLength(line, 200, line));
}

export { stripHtml, toSingleSentence, ensureLength, clampNumber };
