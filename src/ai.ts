import { listTemplateCompositionDirectives } from "./template-theme";
import { listSlotHints } from "./templates";
import { PIPELINE_CONFIG } from "./generated/template-assets";

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
  carousel_slides: CarouselSlide[];
  hashtags: string[];
  image_prompt: string;
  use_feature_image: boolean;
  slot_content: Record<string, string>;
}

export interface LlmSourcePost {
  title: string;
  html?: string;
  plaintext?: string;
  excerpt?: string;
  custom_excerpt?: string;
  feature_image?: string;
  tags?: Array<{ name?: string }>;
}

export interface TemplateChoiceCandidate {
  id: string;
  label: string;
  description?: string;
  requiredSlotKeys: string[];
}

const DEFAULT_LLM_MODEL = PIPELINE_CONFIG.generation.llm.default_model;
const DEFAULT_SOCIAL_COPY_SYSTEM_PROMPT = PIPELINE_CONFIG.generation.llm.system_prompt.join(" ");

function buildLlmJsonSchema(requiredSlotKeys: string[]): Record<string, unknown> {
  const normalizedRequiredSlotKeys = [...new Set(requiredSlotKeys.map((key) => key.trim()).filter(Boolean))];
  const slotProperties = Object.fromEntries(
    normalizedRequiredSlotKeys.map((slotKey) => [slotKey, { type: "string" }])
  );

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
      use_feature_image: { type: "boolean" },
      slot_content: {
        type: "object",
        properties: slotProperties,
        required: normalizedRequiredSlotKeys,
        additionalProperties: {
          type: "string"
        }
      }
    },
    required: [
      "instagram_caption",
      "twitter_caption",
      "linkedin_caption",
      "carousel_slides",
      "hashtags",
      "image_prompt",
      "use_feature_image",
      "slot_content"
    ]
  } satisfies Record<string, unknown>;
}

export async function generateStructuredCopy(args: {
  ai: Ai;
  llmModel?: string;
  post: LlmSourcePost;
  requiredCarouselSlides: number;
  requiredSlotKeys: string[];
  userPrompt?: string;
  llmOverrides?: LlmPromptOverrides;
  normalizeSlotContent: (raw: unknown, args: { title: string; fallbackText: string; requiredSlotKeys: string[] }) => Record<string, string>;
}): Promise<LlmOutput> {
  const textModel = (args.llmModel || DEFAULT_LLM_MODEL) as keyof AiModels;
  const requiredSlotKeySet = new Set(args.requiredSlotKeys.map((key) => key.trim().toLowerCase()).filter(Boolean));
  const slotHints = listSlotHints()
    .filter((slot) => requiredSlotKeySet.size === 0 || requiredSlotKeySet.has(slot.id))
    .map((slot) => `${slot.id}: ${slot.hint}`)
    .join(" | ");

  const limits = PIPELINE_CONFIG.generation.limits;
  const templateCompositionPromptHints = listTemplateCompositionDirectives()
    .slice(0, 12)
    .map((line) => `- ${line}`)
    .join("\n");
  const userInstructionsTemplate = buildPromptTemplate(
    args.llmOverrides?.userInstructions,
    PIPELINE_CONFIG.generation.llm.user_instructions
  );
  const userInstructions = userInstructionsTemplate
    .replace("<required_carousel_slides>", String(args.requiredCarouselSlides))
    .replace("<instagram_caption_max_chars>", String(limits.instagram_caption_max_chars))
    .replace("<twitter_caption_max_chars>", String(limits.twitter_caption_max_chars))
    .replace("<linkedin_caption_max_chars>", String(limits.linkedin_caption_max_chars))
    .replace("<carousel_heading_max_chars>", String(limits.carousel_heading_max_chars))
    .replace("<carousel_body_max_chars>", String(limits.carousel_body_max_chars))
    .replace("<hashtag_min_count>", String(limits.hashtag_min_count))
    .replace("<hashtag_max_count>", String(limits.hashtag_max_count))
    .replace("<available_slot_keys>", slotHints || args.requiredSlotKeys.join(", "))
    .replace("<required_slot_keys>", args.requiredSlotKeys.join(", "))
    .replace(
      "<template_composition_directives>",
      templateCompositionPromptHints || "- Use deterministic HTML template composition."
    );
  const userBrief =
    typeof args.userPrompt === "string" && args.userPrompt.trim().length > 0
      ? `- user campaign brief: ${args.userPrompt.trim()}`
      : "";
  const slotCoverageDirective = `- slot_content contract: include every key from ${args.requiredSlotKeys.join(", ")} with concrete copy that can render directly.`;
  const appendedInstructions = normalizePromptAppend(args.llmOverrides?.userInstructionsAppend);
  const mergedBaseInstructions = [userInstructions, userBrief, slotCoverageDirective].filter(Boolean).join("\n");
  const mergedInstructions = appendedInstructions
    ? `${mergedBaseInstructions}\n${appendedInstructions}`
    : mergedBaseInstructions;
  const systemPrompt = buildPromptTemplate(args.llmOverrides?.systemPrompt, PIPELINE_CONFIG.generation.llm.system_prompt);
  const title = args.post.title.trim();
  const excerpt = (args.post.custom_excerpt || args.post.excerpt || "").trim();
  const plainBody = (args.post.plaintext || stripHtml(args.post.html || "")).trim();
  const postText =
    plainBody.length > limits.post_text_max_chars
      ? `${plainBody.slice(0, limits.post_text_max_chars)}...`
      : plainBody;
  const topTags = (args.post.tags ?? [])
    .map((tag) => tag.name ?? "")
    .filter(Boolean)
    .slice(0, 6)
    .join(", ");

  const prompt = [
    mergedInstructions,
    "",
    "Template contract:",
    `<required_slot_keys>${args.requiredSlotKeys.join(", ")}</required_slot_keys>`,
    "",
    "Blog post source:",
    `<title>${title}</title>`,
    `<excerpt>${excerpt || "(none)"}</excerpt>`,
    `<tags>${topTags || "(none)"}</tags>`,
    `<has_feature_image>${Boolean(args.post.feature_image)}</has_feature_image>`,
    "<body>",
    postText,
    "</body>"
  ].join("\n");

  const raw = await args.ai.run(textModel, {
    messages: [
      {
        role: "system",
        content: systemPrompt || DEFAULT_SOCIAL_COPY_SYSTEM_PROMPT
      },
      {
        role: "user",
        content: prompt
      }
    ],
    response_format: {
      type: "json_schema",
      json_schema: buildLlmJsonSchema(args.requiredSlotKeys)
    },
    temperature: clampNumber(args.llmOverrides?.temperature, 0, 2, PIPELINE_CONFIG.generation.llm.temperature),
    max_tokens: Math.round(
      clampNumber(args.llmOverrides?.maxTokens, 256, 4096, PIPELINE_CONFIG.generation.llm.max_tokens)
    )
  });

  const parsed = parseModelJson(raw);
  return normalizeLlmOutput(parsed, {
    hasFeatureImage: Boolean(args.post.feature_image),
    title,
    fallbackText: excerpt || postText,
    requiredCarouselSlides: args.requiredCarouselSlides,
    requiredSlotKeys: args.requiredSlotKeys,
    normalizeSlotContent: args.normalizeSlotContent
  });
}

export async function chooseTemplateAssignments(args: {
  ai: Ai;
  llmModel?: string;
  post: LlmSourcePost;
  requestedFormats: string[];
  templateCandidates: Record<string, TemplateChoiceCandidate[]>;
  userPrompt?: string;
}): Promise<Record<string, string>> {
  const textModel = (args.llmModel || DEFAULT_LLM_MODEL) as keyof AiModels;
  const requestedFormats = [...new Set(args.requestedFormats.map((format) => format.trim()).filter(Boolean))];
  if (requestedFormats.length === 0) {
    return {};
  }

  const promptLines = requestedFormats.map((format) => {
    const candidates = args.templateCandidates[format] ?? [];
    const candidateLines = candidates
      .map((candidate) => {
        const slotSummary =
          candidate.requiredSlotKeys.length > 0 ? candidate.requiredSlotKeys.join(", ") : "(no explicit SLOT keys)";
        const description = candidate.description ? ` - ${candidate.description}` : "";
        return `  - ${candidate.id}: ${candidate.label}${description}; slots: ${slotSummary}`;
      })
      .join("\n");
    return `format: ${format}\n${candidateLines}`;
  });

  const excerpt = (args.post.custom_excerpt || args.post.excerpt || "").trim();
  const plainBody = (args.post.plaintext || stripHtml(args.post.html || "")).trim();
  const postText =
    plainBody.length > PIPELINE_CONFIG.generation.limits.post_text_max_chars
      ? `${plainBody.slice(0, PIPELINE_CONFIG.generation.limits.post_text_max_chars)}...`
      : plainBody;
  const userBrief =
    typeof args.userPrompt === "string" && args.userPrompt.trim().length > 0
      ? `\n<user_brief>${args.userPrompt.trim()}</user_brief>`
      : "";

  const prompt = [
    "Choose one best template per requested format based on source content.",
    "Rules:",
    "- Return strict JSON only.",
    "- Use only template ids listed under each format.",
    "- Prefer templates whose slot requirements fit the content naturally.",
    "- Ensure all requested formats have one selected template id.",
    "",
    "Requested formats and candidate templates:",
    promptLines.join("\n\n"),
    "",
    "Source content:",
    `<title>${args.post.title.trim()}</title>`,
    `<excerpt>${excerpt || "(none)"}</excerpt>`,
    "<body>",
    postText,
    "</body>",
    userBrief
  ]
    .filter(Boolean)
    .join("\n");

  try {
    const raw = await args.ai.run(textModel, {
      messages: [
        {
          role: "system",
          content: "You are an expert template planner for social content automation."
        },
        {
          role: "user",
          content: prompt
        }
      ],
      response_format: {
        type: "json_schema",
        json_schema: buildTemplateAssignmentSchema(requestedFormats, args.templateCandidates)
      },
      temperature: 0.1,
      max_tokens: 900
    });

    const parsed = parseModelJson(raw);
    const templateIdsRaw = parsed.template_ids;
    if (!templateIdsRaw || typeof templateIdsRaw !== "object") {
      throw new Error("Template planner did not return template_ids object");
    }

    const selected: Record<string, string> = {};
    const templateIds = templateIdsRaw as Record<string, unknown>;
    for (const format of requestedFormats) {
      const candidates = args.templateCandidates[format] ?? [];
      const candidateIdSet = new Set(candidates.map((candidate) => candidate.id));
      const requestedTemplateId = toText(templateIds[format]);
      if (requestedTemplateId && candidateIdSet.has(requestedTemplateId)) {
        selected[format] = requestedTemplateId;
        continue;
      }
      if (candidates[0]) {
        selected[format] = candidates[0].id;
      }
    }

    return selected;
  } catch {
    const fallback: Record<string, string> = {};
    for (const format of requestedFormats) {
      const first = args.templateCandidates[format]?.[0];
      if (first) {
        fallback[format] = first.id;
      }
    }
    return fallback;
  }
}

function buildTemplateAssignmentSchema(
  requestedFormats: string[],
  templateCandidates: Record<string, TemplateChoiceCandidate[]>
): Record<string, unknown> {
  const properties: Record<string, unknown> = {};
  for (const format of requestedFormats) {
    const candidates = templateCandidates[format] ?? [];
    const candidateIds = [...new Set(candidates.map((candidate) => candidate.id).filter(Boolean))];
    properties[format] = {
      type: "string",
      enum: candidateIds
    };
  }

  return {
    type: "object",
    properties: {
      template_ids: {
        type: "object",
        properties,
        required: requestedFormats,
        additionalProperties: false
      }
    },
    required: ["template_ids"]
  };
}

function parseModelJson(raw: unknown): Record<string, unknown> {
  if (typeof raw === "string") {
    return parseJsonLike(raw);
  }

  if (raw && typeof raw === "object") {
    const object = raw as Record<string, unknown>;

    if (object.response && typeof object.response === "object") {
      return object.response as Record<string, unknown>;
    }

    if (typeof object.response === "string") {
      return parseJsonLike(object.response);
    }

    return object;
  }

  throw new Error("LLM returned an unexpected payload");
}

function parseJsonLike(input: string): Record<string, unknown> {
  const direct = input.trim();
  try {
    return JSON.parse(direct) as Record<string, unknown>;
  } catch {
    const fencedMatch = direct.match(/```json\s*([\s\S]*?)```/i) ?? direct.match(/```([\s\S]*?)```/);
    if (fencedMatch?.[1]) {
      return JSON.parse(fencedMatch[1].trim()) as Record<string, unknown>;
    }
    throw new Error("Model output is not valid JSON");
  }
}

function buildPromptTemplate(override: string | string[] | undefined, fallbackLines: readonly string[]): string {
  const lines = normalizePromptLines(override);
  if (lines.length === 0) {
    return fallbackLines.join("\n");
  }
  return lines.join("\n");
}

function normalizePromptAppend(value: string | undefined): string {
  if (!value) {
    return "";
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  return ensureLength(trimmed, 2_000, trimmed);
}

function normalizePromptLines(input: string | string[] | undefined): string[] {
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

function normalizeLlmOutput(
  payload: Record<string, unknown>,
  args: {
    hasFeatureImage: boolean;
    title: string;
    fallbackText: string;
    requiredCarouselSlides: number;
    requiredSlotKeys: string[];
    normalizeSlotContent: (raw: unknown, args: { title: string; fallbackText: string; requiredSlotKeys: string[] }) => Record<string, string>;
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

  const rawSlides = Array.isArray(payload.carousel_slides) ? payload.carousel_slides : [];
  const sourceSentences = sentencePoolFromSource(`${args.title}. ${cleanedFallbackText}`);
  const normalizedSlides = normalizeCarouselSlides(rawSlides, {
    title: args.title,
    fallbackText: cleanedFallbackText,
    requiredSlides: args.requiredCarouselSlides,
    sourceSentences
  });

  const rawHashtags = Array.isArray(payload.hashtags) ? payload.hashtags : [];
  const hashtags = normalizeHashtags(rawHashtags, args.title, cleanedFallbackText);

  const imagePromptFallback = `${args.title}, modern editorial photo, clean composition, natural lighting, no text overlay`;
  const imagePrompt = ensureLength(toText(payload.image_prompt), limits.image_prompt_max_chars, imagePromptFallback);

  const useFeatureImage = args.hasFeatureImage && Boolean(payload.use_feature_image);
  const slotContent = args.normalizeSlotContent(payload.slot_content, {
    title: args.title,
    fallbackText: cleanedFallbackText,
    requiredSlotKeys: args.requiredSlotKeys
  });

  return {
    instagram_caption: captions.instagram,
    twitter_caption: captions.twitter,
    linkedin_caption: captions.linkedin,
    carousel_slides: normalizedSlides,
    hashtags,
    image_prompt: imagePrompt,
    use_feature_image: useFeatureImage,
    slot_content: slotContent
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

function normalizeCarouselSlides(
  rawSlides: unknown[],
  args: { title: string; fallbackText: string; requiredSlides: number; sourceSentences: string[] }
): CarouselSlide[] {
  const limits = PIPELINE_CONFIG.generation.limits;
  const usedSentenceIndexes = new Set<number>();
  const seenBodyKeys = new Set<string>();
  const seenHeadingKeys = new Set<string>();
  const fallbackSentence = toSingleSentence(ensureLength(args.fallbackText, limits.carousel_body_max_chars, args.title));

  const nextSentence = (): string => {
    for (const [index, sentence] of args.sourceSentences.entries()) {
      if (!usedSentenceIndexes.has(index)) {
        usedSentenceIndexes.add(index);
        return sentence;
      }
    }
    return "";
  };

  const ensureBody = (rawBody: string): string => {
    const cleanedBody = normalizeSourceContent(rawBody);
    const fallbackBody = nextSentence() || fallbackSentence;
    let body = toSingleSentence(ensureLength(cleanedBody, limits.carousel_body_max_chars, fallbackBody));
    let bodyKey = canonicalText(body);

    if (!bodyKey || seenBodyKeys.has(bodyKey)) {
      const alternative = nextSentence();
      if (alternative) {
        body = toSingleSentence(ensureLength(alternative, limits.carousel_body_max_chars, fallbackBody));
        bodyKey = canonicalText(body);
      }
    }

    if (bodyKey) {
      seenBodyKeys.add(bodyKey);
    }
    return body;
  };

  const slides: CarouselSlide[] = [];
  for (const [index, rawSlide] of rawSlides.entries()) {
    if (slides.length >= args.requiredSlides) {
      break;
    }
    if (!rawSlide || typeof rawSlide !== "object") {
      continue;
    }

    const entry = rawSlide as Record<string, unknown>;
    const body = ensureBody(toText(entry.body));
    const heading = ensureCarouselHeading(toText(entry.heading), {
      body,
      title: args.title,
      index,
      total: args.requiredSlides,
      usedHeadingKeys: seenHeadingKeys
    });

    slides.push({ heading, body });
  }

  while (slides.length < args.requiredSlides) {
    const index = slides.length;
    const body = ensureBody("");
    const heading = ensureCarouselHeading("", {
      body,
      title: args.title,
      index,
      total: args.requiredSlides,
      usedHeadingKeys: seenHeadingKeys
    });
    slides.push({ heading, body });
  }

  return slides;
}

function ensureCarouselHeading(
  rawHeading: string,
  args: {
    body: string;
    title: string;
    index: number;
    total: number;
    usedHeadingKeys: Set<string>;
  }
): string {
  const limits = PIPELINE_CONFIG.generation.limits;
  const phase = getCarouselPhase(args.index, args.total);
  const fallback = defaultHeadingForPhase(phase, args.index);
  const candidates = [
    normalizeSourceContent(rawHeading),
    deriveHeadingFromBody(args.body, args.title, phase),
    deriveHeadingFromBody(args.title, args.title, phase),
    ...defaultHeadingVariantsForPhase(phase)
  ];

  for (const candidate of candidates) {
    const heading = normalizeCarouselHeadingCandidate(candidate, limits.carousel_heading_max_chars, fallback);
    const key = canonicalText(heading);
    if (!key || args.usedHeadingKeys.has(key) || isGenericCarouselHeading(heading)) {
      continue;
    }
    args.usedHeadingKeys.add(key);
    return heading;
  }

  const fallbackHeading = normalizeCarouselHeadingCandidate(fallback, limits.carousel_heading_max_chars, fallback);
  const fallbackKey = canonicalText(fallbackHeading);
  if (fallbackKey) {
    args.usedHeadingKeys.add(fallbackKey);
  }
  return fallbackHeading;
}

function deriveHeadingFromBody(body: string, title: string, phase: "intro" | "middle" | "conclusion"): string {
  const source = normalizeSourceContent(body) || normalizeSourceContent(title);
  if (!source) {
    return defaultHeadingForPhase(phase, 0);
  }

  const clause = source
    .replace(/[–—]/g, " ")
    .split(/[.!?;:]/)[0]
    ?.trim() || "";
  const words = clause
    .split(/\s+/)
    .map((word) => word.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter(Boolean)
    .filter((word) => word.length > 1);
  const selected = words.slice(0, 7);
  const candidate = toHeadlineCase(selected.join(" "));
  if (candidate && !isGenericCarouselHeading(candidate)) {
    return candidate;
  }
  return defaultHeadingForPhase(phase, 0);
}

function defaultHeadingForPhase(phase: "intro" | "middle" | "conclusion", index: number): string {
  if (phase === "intro") {
    return index % 2 === 0 ? "The Main Idea" : "Why This Matters";
  }
  if (phase === "conclusion") {
    return index % 2 === 0 ? "What To Do Next" : "Final Takeaway";
  }
  return index % 2 === 0 ? "Key Insight" : "How To Apply It";
}

function defaultHeadingVariantsForPhase(phase: "intro" | "middle" | "conclusion"): string[] {
  if (phase === "intro") {
    return ["Big Picture", "Why It Matters"];
  }
  if (phase === "conclusion") {
    return ["Next Move", "Put It Into Practice"];
  }
  return ["Proof In Practice", "What Changes"];
}

function normalizeCarouselHeadingCandidate(value: string, maxChars: number, fallback: string): string {
  const cleaned = ensureLength(value, maxChars, fallback)
    .replace(/[.!?]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) {
    return fallback;
  }
  return cleaned;
}

function getCarouselPhase(index: number, total: number): "intro" | "middle" | "conclusion" {
  if (index <= 0) {
    return "intro";
  }
  if (index >= total - 1) {
    return "conclusion";
  }
  return "middle";
}

function isGenericCarouselHeading(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  if (/^(insight|slide|point|tip|step|idea|key point|takeaway)\s*\d*$/i.test(normalized)) {
    return true;
  }
  if (/^(start here|core insight|how it works|what to do next)\s*\d*$/i.test(normalized)) {
    return true;
  }
  return /^([a-z]+\s*){1,3}\d+$/.test(normalized);
}

function sentencePoolFromSource(value: string): string[] {
  const limits = PIPELINE_CONFIG.generation.limits;
  const source = normalizeSourceContent(value);
  if (!source) {
    return [];
  }

  const rawSentences = source.split(/(?<=[.!?])\s+/g).map((sentence) => sentence.trim()).filter(Boolean);
  const deduped: string[] = [];
  const seen = new Set<string>();

  for (const sentence of rawSentences) {
    const single = toSingleSentence(ensureLength(sentence, limits.carousel_body_max_chars, sentence));
    const key = canonicalText(single);
    if (!key || key.length < 12 || seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(single);
    if (deduped.length >= 24) {
      break;
    }
  }

  return deduped;
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

function toHeadlineCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
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
