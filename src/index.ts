import puppeteer from "@cloudflare/puppeteer";
import { listFontProfiles, normalizeFontProfileId } from "./design-system";
import {
  getTemplateDimensions,
  isTemplateKind,
  listPostArchetypes,
  listSlotHints,
  listTemplateKinds,
  listTemplateStyles,
  normalizePostArchetype,
  normalizeTemplateStyle,
  previewParamsFromUrl,
  renderTemplate,
  type BrandTokenOverrides,
  type BaseTemplateParams,
  type CarouselTemplateParams,
  type TemplateControlSet,
  type TemplateKind
} from "./templates";
import { PIPELINE_CONFIG } from "./generated/template-assets";

interface Env {
  AI: Ai;
  BROWSER: Fetcher;
  OUTPUT_BUCKET: R2Bucket;
  GHOST_API_URL: string;
  GHOST_CONTENT_API_KEY: string;
  GHOST_WEBHOOK_TOKEN?: string;
  PEXELS_API_KEY?: string;
  R2_PUBLIC_BASE_URL?: string;
  DEFAULT_BRAND_COLOR?: string;
  BRAND_NAME?: string;
  LLM_MODEL?: string;
  IMAGE_MODEL?: string;
  R2_KEY_PREFIX?: string;
  NOTIFY_WEBHOOK_URL?: string;
}

interface GenerateRequestBody {
  slug?: string;
  url?: string;
  brandingColor?: string;
  brandName?: string;
  templateStyle?: string;
  postArchetype?: string;
  fontProfile?: string;
  templateIds?: Partial<Record<TemplateKind, string>>;
  slotOverrides?: Record<string, string>;
  brandTokens?: BrandTokenOverrides;
  design?: TemplateControlSet;
  storage?: StorageOptions;
  notifyUrl?: string;
}

interface DirectContentRequestBody {
  title?: string;
  excerpt?: string;
  content?: string;
  body?: string;
  slug?: string;
  url?: string;
  feature_image?: string;
  tags?: string[] | string;
  primary_tag?: string;
  brandingColor?: string;
  brandName?: string;
  templateStyle?: string;
  postArchetype?: string;
  fontProfile?: string;
  templateIds?: Partial<Record<TemplateKind, string>>;
  slotOverrides?: Record<string, string>;
  brandTokens?: BrandTokenOverrides;
  design?: TemplateControlSet;
  storage?: StorageOptions;
  notifyUrl?: string;
}

interface StorageOptions {
  mode?: "overwrite" | "versioned";
  includeDate?: boolean;
  runId?: string;
}

interface GhostWebhookPost {
  current?: {
    slug?: string;
    url?: string;
  };
  slug?: string;
  url?: string;
}

interface GhostWebhookPayload {
  post?: GhostWebhookPost;
  slug?: string;
  url?: string;
}

interface GhostPost {
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

interface CarouselSlide {
  heading: string;
  body: string;
}

interface LlmOutput {
  instagram_caption: string;
  twitter_caption: string;
  linkedin_caption: string;
  carousel_slides: CarouselSlide[];
  hashtags: string[];
  image_prompt: string;
  use_feature_image: boolean;
  template_style: string;
  post_archetype: string;
  font_profile: string;
  slot_content: Record<string, string>;
}

interface SelectedImage {
  source: "feature" | "stock" | "ai" | "none";
  imageUrl: string;
  attribution?: string;
  sourceUrl?: string;
}

interface StoredAsset {
  format: string;
  key: string;
  url: string | null;
}

interface GenerationResult {
  ok: true;
  slug: string;
  post_url: string;
  image_source: SelectedImage;
  llm_output: LlmOutput;
  assets: {
    instagram_post: StoredAsset;
    instagram_story: StoredAsset;
    twitter_card: StoredAsset;
    linkedin_post: StoredAsset;
    carousel: StoredAsset[];
  };
}

const DEFAULT_LLM_MODEL = PIPELINE_CONFIG.generation.llm.default_model;
const DEFAULT_IMAGE_MODEL = PIPELINE_CONFIG.generation.image.default_model;
const REQUIRED_CAROUSEL_SLIDES = PIPELINE_CONFIG.generation.carousel_required_slides;
const STOCK_TOPIC_PATTERN = createTopicKeywordPattern(PIPELINE_CONFIG.generation.stock_topic_keywords);
const SOCIAL_COPY_SYSTEM_PROMPT = PIPELINE_CONFIG.generation.llm.system_prompt.join(" ");

const LLM_JSON_SCHEMA: Record<string, unknown> = {
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
    template_style: {
      type: "string",
      enum: listTemplateStyles().map((style) => style.id)
    },
    post_archetype: {
      type: "string",
      enum: listPostArchetypes().map((archetype) => archetype.id)
    },
    font_profile: {
      type: "string",
      enum: listFontProfiles().map((profile) => profile.id)
    },
    slot_content: {
      type: "object",
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
    "template_style",
    "post_archetype",
    "font_profile",
    "slot_content"
  ]
};

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname.startsWith("/template/")) {
      if (!PIPELINE_CONFIG.features.enable_template_preview) {
        return json({ error: "Template preview route is disabled by configuration" }, 403);
      }
      return handleTemplatePreview(url);
    }

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true });
    }

    if (request.method === "POST" && url.pathname === "/generate") {
      try {
        const body = await readJsonBody<GenerateRequestBody>(request);
        const result = await runPipeline(body, env);
        const notifyUrl = resolveNotifyUrl(body.notifyUrl, env.NOTIFY_WEBHOOK_URL);
        if (notifyUrl && PIPELINE_CONFIG.features.enable_notifications) {
          ctx.waitUntil(sendNotification(notifyUrl, result));
        }
        return json(result);
      } catch (error) {
        return handleError(error);
      }
    }

    if (request.method === "POST" && url.pathname === "/generate-from-content") {
      try {
        const body = await readJsonBody<DirectContentRequestBody>(request);
        const post = buildPostFromDirectContent(body);
        const result = await runPipelineFromPost(post, env, body);
        const notifyUrl = resolveNotifyUrl(body.notifyUrl, env.NOTIFY_WEBHOOK_URL);
        if (notifyUrl && PIPELINE_CONFIG.features.enable_notifications) {
          ctx.waitUntil(sendNotification(notifyUrl, result));
        }
        return json(result);
      } catch (error) {
        return handleError(error);
      }
    }

    if (request.method === "POST" && url.pathname === "/webhook/ghost") {
      try {
        const expected = env.GHOST_WEBHOOK_TOKEN?.trim();
        if (expected) {
          const provided = request.headers.get("x-webhook-token")?.trim();
          if (!provided || provided !== expected) {
            return json({ error: "Unauthorized webhook token" }, 401);
          }
        }

        const payload = await readJsonBody<GhostWebhookPayload>(request);
        const slug = extractSlugFromWebhook(payload);
        if (!slug) {
          return json({ error: "Could not resolve slug from Ghost webhook payload" }, 400);
        }

        const result = await runPipeline({ slug }, env);
        if (env.NOTIFY_WEBHOOK_URL && PIPELINE_CONFIG.features.enable_notifications) {
          ctx.waitUntil(sendNotification(env.NOTIFY_WEBHOOK_URL, result));
        }
        return json(result);
      } catch (error) {
        return handleError(error);
      }
    }

    return json(
      {
        error: "Not found",
        routes: [
          "POST /generate",
          "POST /generate-from-content",
          "POST /webhook/ghost",
          ...listTemplateKinds().map((kind) => `GET /template/${kind}?...`)
        ]
      },
      404
    );
  }
};

function handleTemplatePreview(url: URL): Response {
  const kind = matchTemplateKind(url.pathname);
  if (!kind) {
    return json({ error: "Unknown template type" }, 404);
  }

  const params = previewParamsFromUrl(kind, url);
  const html = renderTemplate(kind, params);
  return new Response(html, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}

function matchTemplateKind(pathname: string): TemplateKind | null {
  const candidate = pathname.replace(/^\/template\//, "").replace(/\/+$/, "").trim();
  return isTemplateKind(candidate) ? candidate : null;
}

async function runPipeline(input: GenerateRequestBody, env: Env): Promise<GenerationResult> {
  assertRequiredEnv(env);

  const slug = resolveSlug(input);
  if (!slug) {
    throw new HttpError(400, "Request must include either slug or url");
  }

  const post = await fetchGhostPost(env, slug);
  return runPipelineFromPost(post, env, input);
}

async function runPipelineFromPost(
  post: GhostPost,
  env: Env,
  brandInput: {
    brandingColor?: string;
    brandName?: string;
    templateStyle?: string;
    postArchetype?: string;
    fontProfile?: string;
    templateIds?: Partial<Record<TemplateKind, string>>;
    slotOverrides?: Record<string, string>;
    brandTokens?: BrandTokenOverrides;
    design?: TemplateControlSet;
    storage?: StorageOptions;
  }
): Promise<GenerationResult> {
  const llmOutput = await generateStructuredCopy(env, post);
  const selectedTemplateStyle = normalizeTemplateStyle(brandInput.templateStyle ?? llmOutput.template_style);
  const selectedPostArchetype = normalizePostArchetype(brandInput.postArchetype ?? llmOutput.post_archetype);
  const selectedFontProfile = normalizeFontProfileId(brandInput.fontProfile ?? llmOutput.font_profile);
  const mergedSlotContent = mergeSlotContent(
    llmOutput.slot_content,
    normalizeSlotContent(brandInput.slotOverrides, {
      title: post.title,
      fallbackText: post.custom_excerpt || post.excerpt || post.plaintext || ""
    })
  );
  const selectedImage = await chooseImageSource(env, post, llmOutput);

  const brandColor = brandInput.brandingColor ?? env.DEFAULT_BRAND_COLOR ?? PIPELINE_CONFIG.brand.default_color;
  const brandName = brandInput.brandName ?? env.BRAND_NAME ?? PIPELINE_CONFIG.brand.default_name;

  const renderAssets = await renderAndStoreAssets(env, {
    slug: post.slug,
    postTitle: post.title,
    imageUrl: selectedImage.imageUrl,
    llmOutput: {
      ...llmOutput,
      template_style: selectedTemplateStyle,
      post_archetype: selectedPostArchetype,
      font_profile: selectedFontProfile,
      slot_content: mergedSlotContent
    },
    brandColor,
    brandName,
    templateStyle: selectedTemplateStyle,
    templateArchetype: selectedPostArchetype,
    fontProfile: selectedFontProfile,
    templateIds: brandInput.templateIds,
    slotContent: mergedSlotContent,
    brandTokens: brandInput.brandTokens,
    design: brandInput.design,
    storage: brandInput.storage
  });

  return {
    ok: true,
    slug: post.slug,
    post_url: post.url,
    image_source: selectedImage,
    llm_output: {
      ...llmOutput,
      template_style: selectedTemplateStyle,
      post_archetype: selectedPostArchetype,
      font_profile: selectedFontProfile,
      slot_content: mergedSlotContent
    },
    assets: renderAssets
  };
}

function buildPostFromDirectContent(input: DirectContentRequestBody): GhostPost {
  const title = (input.title ?? "").trim();
  if (!title) {
    throw new HttpError(400, "title is required for /generate-from-content");
  }

  const plainContent = (input.content ?? input.body ?? "").trim();
  if (!plainContent) {
    throw new HttpError(400, "content (or body) is required for /generate-from-content");
  }

  const derivedSlug = sanitizeSlug(input.slug ?? slugify(title));
  if (!derivedSlug) {
    throw new HttpError(400, "Could not derive a valid slug from title");
  }

  const tags = normalizeTags(input.tags);
  const excerpt = (input.excerpt ?? plainContent.slice(0, PIPELINE_CONFIG.generation.limits.direct_excerpt_default_max_chars)).trim();
  const url = input.url?.trim() || `https://local.test/${derivedSlug}/`;

  return {
    id: crypto.randomUUID(),
    title,
    slug: derivedSlug,
    url,
    plaintext: plainContent,
    excerpt,
    custom_excerpt: excerpt,
    feature_image: input.feature_image?.trim() || undefined,
    tags: tags.map((name) => ({ name })),
    primary_tag: input.primary_tag ? { name: input.primary_tag } : tags[0] ? { name: tags[0] } : undefined
  };
}

function normalizeTags(input: string[] | string | undefined): string[] {
  if (!input) {
    return [];
  }
  const rawItems = Array.isArray(input) ? input : input.split(",");
  return rawItems
    .map((item) => item.trim())
    .map((item) => item.replace(/[^a-zA-Z0-9\s-]/g, ""))
    .filter((item) => item.length > 1)
    .slice(0, PIPELINE_CONFIG.generation.limits.input_tags_max_count);
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

function resolveSlug(input: GenerateRequestBody): string | null {
  if (typeof input.slug === "string" && input.slug.trim().length > 0) {
    return sanitizeSlug(input.slug);
  }
  if (typeof input.url === "string" && input.url.trim().length > 0) {
    return parseSlugFromUrl(input.url);
  }
  return null;
}

function extractSlugFromWebhook(payload: GhostWebhookPayload): string | null {
  const direct =
    payload.post?.current?.slug ?? payload.post?.slug ?? payload.slug ?? parseSlugFromUrl(payload.post?.current?.url ?? "") ?? parseSlugFromUrl(payload.url ?? "");
  if (!direct) {
    return null;
  }
  return sanitizeSlug(direct);
}

function sanitizeSlug(value: string): string {
  return value
    .trim()
    .replace(/^\/+|\/+$/g, "")
    .replace(/[^a-zA-Z0-9\-_/]/g, "")
    .split("/")
    .filter(Boolean)
    .at(-1)
    ?.toLowerCase() ?? "";
}

function parseSlugFromUrl(rawUrl: string): string | null {
  try {
    const url = new URL(rawUrl);
    const segments = url.pathname.split("/").filter(Boolean);
    if (segments.length === 0) {
      return null;
    }
    return sanitizeSlug(segments[segments.length - 1]);
  } catch {
    return null;
  }
}

async function fetchGhostPost(env: Env, slug: string): Promise<GhostPost> {
  const base = env.GHOST_API_URL.replace(/\/+$/, "");
  const endpoint = `${base}/posts/slug/${encodeURIComponent(slug)}/?key=${encodeURIComponent(
    env.GHOST_CONTENT_API_KEY
  )}&include=tags,authors&formats=html,plaintext`;

  const response = await fetch(endpoint, {
    headers: { accept: "application/json" }
  });

  if (!response.ok) {
    const details = await response.text();
    throw new HttpError(
      response.status,
      `Ghost Content API failed: ${details.slice(0, PIPELINE_CONFIG.runtime.ghost_error_preview_chars)}`
    );
  }

  const data = (await response.json()) as { posts?: GhostPost[] };
  const post = data.posts?.[0];
  if (!post) {
    throw new HttpError(404, `No post found for slug: ${slug}`);
  }

  return post;
}

async function generateStructuredCopy(env: Env, post: GhostPost): Promise<LlmOutput> {
  const textModel = (env.LLM_MODEL || DEFAULT_LLM_MODEL) as keyof AiModels;
  const styleHints = listTemplateStyles()
    .map((style) => `${style.id}: ${style.llmHint}`)
    .join(" | ");
  const archetypeHints = listPostArchetypes()
    .map((archetype) => `${archetype.id}: ${archetype.llmHint}`)
    .join(" | ");
  const fontHints = listFontProfiles()
    .map((profile) => `${profile.id}: ${profile.llmHint}`)
    .join(" | ");
  const slotHints = listSlotHints()
    .map((slot) => `${slot.id}: ${slot.hint}`)
    .join(" | ");
  const limits = PIPELINE_CONFIG.generation.limits;
  const userInstructions = PIPELINE_CONFIG.generation.llm.user_instructions
    .join("\n")
    .replace("<required_carousel_slides>", String(REQUIRED_CAROUSEL_SLIDES))
    .replace("<instagram_caption_max_chars>", String(limits.instagram_caption_max_chars))
    .replace("<twitter_caption_max_chars>", String(limits.twitter_caption_max_chars))
    .replace("<linkedin_caption_max_chars>", String(limits.linkedin_caption_max_chars))
    .replace("<hashtag_min_count>", String(limits.hashtag_min_count))
    .replace("<hashtag_max_count>", String(limits.hashtag_max_count))
    .replace("<available_template_styles>", styleHints)
    .replace("<available_post_archetypes>", archetypeHints)
    .replace("<available_font_profiles>", fontHints)
    .replace("<available_slot_keys>", slotHints);
  const title = post.title.trim();
  const excerpt = (post.custom_excerpt || post.excerpt || "").trim();
  const plainBody = (post.plaintext || stripHtml(post.html || "")).trim();
  const postText =
    plainBody.length > limits.post_text_max_chars
      ? `${plainBody.slice(0, limits.post_text_max_chars)}...`
      : plainBody;
  const topTags = (post.tags ?? [])
    .map((tag) => tag.name ?? "")
    .filter(Boolean)
    .slice(0, 6)
    .join(", ");

  const prompt = [
    userInstructions,
    "",
    "Blog post source:",
    `<title>${title}</title>`,
    `<excerpt>${excerpt || "(none)"}</excerpt>`,
    `<tags>${topTags || "(none)"}</tags>`,
    `<has_feature_image>${Boolean(post.feature_image)}</has_feature_image>`,
    "<body>",
    postText,
    "</body>"
  ].join("\n");

  const raw = await env.AI.run(textModel, {
    messages: [
      {
        role: "system",
        content: SOCIAL_COPY_SYSTEM_PROMPT
      },
      {
        role: "user",
        content: prompt
      }
    ],
    response_format: {
      type: "json_schema",
      json_schema: LLM_JSON_SCHEMA
    },
    temperature: PIPELINE_CONFIG.generation.llm.temperature,
    max_tokens: PIPELINE_CONFIG.generation.llm.max_tokens
  });

  const parsed = parseModelJson(raw);
  return normalizeLlmOutput(parsed, Boolean(post.feature_image), title, excerpt || postText);
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

function normalizeLlmOutput(
  payload: Record<string, unknown>,
  hasFeatureImage: boolean,
  title: string,
  fallbackText: string
): LlmOutput {
  const limits = PIPELINE_CONFIG.generation.limits;
  const fallbacks = PIPELINE_CONFIG.generation.fallbacks;
  const instagramCaption = ensureLength(toText(payload.instagram_caption), limits.instagram_caption_max_chars, fallbackText);
  const twitterCaption = ensureLength(toText(payload.twitter_caption), limits.twitter_caption_max_chars, fallbackText);
  const linkedinCaption = ensureLength(toText(payload.linkedin_caption), limits.linkedin_caption_max_chars, fallbackText);

  const rawSlides = Array.isArray(payload.carousel_slides) ? payload.carousel_slides : [];
  const normalizedSlides: CarouselSlide[] = rawSlides
    .map((slide) => {
      if (!slide || typeof slide !== "object") {
        return null;
      }
      const entry = slide as Record<string, unknown>;
      const heading = ensureLength(toText(entry.heading), limits.carousel_heading_max_chars, fallbacks.carousel_heading);
      const body = toSingleSentence(ensureLength(toText(entry.body), limits.carousel_body_max_chars, fallbackText));
      if (!heading || !body) {
        return null;
      }
      return { heading, body };
    })
    .filter((slide): slide is CarouselSlide => slide !== null)
    .slice(0, REQUIRED_CAROUSEL_SLIDES);

  while (normalizedSlides.length < REQUIRED_CAROUSEL_SLIDES) {
    const index = normalizedSlides.length + 1;
    normalizedSlides.push({
      heading: `${fallbacks.carousel_heading_prefix} ${index}`,
      body: toSingleSentence(ensureLength(fallbackText, limits.carousel_body_max_chars, fallbackText))
    });
  }

  const rawHashtags = Array.isArray(payload.hashtags) ? payload.hashtags : [];
  const hashtags = normalizeHashtags(rawHashtags, title, fallbackText);

  const imagePromptFallback = `${title}, modern editorial photo, clean composition, natural lighting, no text overlay`;
  const imagePrompt = ensureLength(toText(payload.image_prompt), limits.image_prompt_max_chars, imagePromptFallback);

  const useFeatureImage = hasFeatureImage && Boolean(payload.use_feature_image);
  const templateStyle = normalizeTemplateStyle(toText(payload.template_style));
  const postArchetype = normalizePostArchetype(toText(payload.post_archetype));
  const fontProfile = normalizeFontProfileId(toText(payload.font_profile));
  const slotContent = normalizeSlotContent(payload.slot_content, {
    title,
    fallbackText
  });

  return {
    instagram_caption: instagramCaption,
    twitter_caption: twitterCaption,
    linkedin_caption: linkedinCaption,
    carousel_slides: normalizedSlides,
    hashtags,
    image_prompt: imagePrompt,
    use_feature_image: useFeatureImage,
    template_style: templateStyle,
    post_archetype: postArchetype,
    font_profile: fontProfile,
    slot_content: slotContent
  };
}

function normalizeHashtags(rawTags: unknown[], title: string, fallbackText: string): string[] {
  const limits = PIPELINE_CONFIG.generation.limits;
  const seeded = [
    ...rawTags.map((tag) => toText(tag)),
    ...title
      .split(/\s+/)
      .map((word) => word.replace(/[^a-zA-Z0-9]/g, ""))
      .filter((word) => word.length >= limits.title_keyword_min_chars),
    ...fallbackText
      .split(/\s+/)
      .map((word) => word.replace(/[^a-zA-Z0-9]/g, ""))
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
      .replace(/[^a-z0-9]/g, "");
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

async function chooseImageSource(env: Env, post: GhostPost, llmOutput: LlmOutput): Promise<SelectedImage> {
  const featureImage = post.feature_image?.trim() || "";

  if (
    PIPELINE_CONFIG.features.prefer_feature_image &&
    llmOutput.use_feature_image &&
    featureImage.length > 0
  ) {
    return {
      source: "feature",
      imageUrl: featureImage
    };
  }

  const topicText = `${post.title} ${(post.primary_tag?.name ?? "")} ${(post.tags ?? [])
    .map((tag) => tag.name ?? "")
    .join(" ")} ${llmOutput.image_prompt}`.toLowerCase();

  const concreteTopic = STOCK_TOPIC_PATTERN ? STOCK_TOPIC_PATTERN.test(topicText) : false;

  if (PIPELINE_CONFIG.features.enable_stock_image_search && concreteTopic && env.PEXELS_API_KEY?.trim()) {
    const stockImage = await searchPexelsImage(post.title, env.PEXELS_API_KEY.trim());
    if (stockImage) {
      return stockImage;
    }
  }

  if (PIPELINE_CONFIG.features.enable_ai_image_generation) {
    const aiImage = await generateAiImage(env, llmOutput.image_prompt);
    if (aiImage) {
      return aiImage;
    }
  }

  if (featureImage.length > 0) {
    return {
      source: "feature",
      imageUrl: featureImage
    };
  }

  return {
    source: "none",
    imageUrl: ""
  };
}

async function searchPexelsImage(title: string, apiKey: string): Promise<SelectedImage | null> {
  const query = title
    .replace(/[^a-zA-Z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, PIPELINE_CONFIG.generation.limits.stock_query_term_max_count)
    .join(" ");

  const endpoint = `https://api.pexels.com/v1/search?query=${encodeURIComponent(
    query || PIPELINE_CONFIG.generation.fallbacks.stock_search_query
  )}&per_page=1&orientation=landscape&size=large`;

  const response = await fetch(endpoint, {
    headers: {
      Authorization: apiKey,
      accept: "application/json"
    }
  });

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as {
    photos?: Array<{
      url?: string;
      photographer?: string;
      src?: {
        large2x?: string;
        original?: string;
      };
    }>;
  };

  const photo = data.photos?.[0];
  const imageUrl = photo?.src?.large2x ?? photo?.src?.original;
  if (!imageUrl) {
    return null;
  }

  return {
    source: "stock",
    imageUrl,
    sourceUrl: photo?.url,
    attribution: photo?.photographer ? `Photo by ${photo.photographer} via Pexels` : "Photo via Pexels"
  };
}

async function generateAiImage(env: Env, prompt: string): Promise<SelectedImage | null> {
  const model = (env.IMAGE_MODEL || DEFAULT_IMAGE_MODEL) as keyof AiModels;
  const imagePrompt = [...PIPELINE_CONFIG.generation.image.prompt_prefix, `Scene: ${prompt}`].join(" ");

  try {
    const raw = await env.AI.run(model, {
      prompt: imagePrompt
    });

    const dataUrl = toDataUrl(raw);
    if (!dataUrl) {
      return null;
    }

    return {
      source: "ai",
      imageUrl: dataUrl
    };
  } catch {
    return null;
  }
}

function toDataUrl(value: unknown): string | null {
  if (!value) {
    return null;
  }

  if (typeof value === "string") {
    if (value.startsWith("data:image/")) {
      return value;
    }
    return null;
  }

  if (value instanceof ArrayBuffer) {
    return `data:image/png;base64,${arrayBufferToBase64(new Uint8Array(value))}`;
  }

  if (ArrayBuffer.isView(value)) {
    const view = value as ArrayBufferView;
    const bytes = new Uint8Array(view.buffer, view.byteOffset, view.byteLength);
    return `data:image/png;base64,${arrayBufferToBase64(bytes)}`;
  }

  if (typeof value === "object") {
    const object = value as Record<string, unknown>;
    if (typeof object.image === "string" && object.image.length > 0) {
      return `data:image/jpeg;base64,${object.image}`;
    }
    if (typeof object.result === "string" && object.result.startsWith("data:image/")) {
      return object.result;
    }
  }

  return null;
}

async function renderAndStoreAssets(
  env: Env,
  args: {
    slug: string;
    postTitle: string;
    imageUrl: string;
    llmOutput: LlmOutput;
    brandColor: string;
    brandName: string;
    templateStyle: string;
    templateArchetype: string;
    fontProfile: string;
    templateIds?: Partial<Record<TemplateKind, string>>;
    slotContent: Record<string, string>;
    brandTokens?: BrandTokenOverrides;
    design?: TemplateControlSet;
    storage?: StorageOptions;
  }
): Promise<GenerationResult["assets"]> {
  const keyPrefix = buildR2KeyPrefix(env, args.slug, args.storage);
  const sharedSlots = buildSharedSlotContent(args);

  const commonTemplateValues: BaseTemplateParams = {
    title: args.postTitle,
    caption: args.llmOutput.instagram_caption,
    imageUrl: args.imageUrl,
    brandColor: args.brandColor,
    brandName: args.brandName,
    templateStyle: args.templateStyle,
    templateArchetype: args.templateArchetype,
    fontProfile: args.fontProfile,
    slots: sharedSlots,
    brandTokens: args.brandTokens,
    design: args.design
  };

  const browser = await puppeteer.launch(env.BROWSER, { keep_alive: PIPELINE_CONFIG.runtime.browser_keep_alive_ms });

  try {
    const instagramPostAsset = await renderStoreSingleAsset(env, browser, {
      key: `${keyPrefix}/instagram-post.png`,
      kind: "instagram-post",
      params: {
        ...commonTemplateValues,
        templateId: args.templateIds?.["instagram-post"],
        slots: {
          ...sharedSlots,
          headline: sharedSlots.headline || args.postTitle,
          subheadline: sharedSlots.subheadline || args.llmOutput.instagram_caption
        },
        caption: withHashtags(
          args.llmOutput.instagram_caption,
          args.llmOutput.hashtags,
          PIPELINE_CONFIG.formats["instagram-post"].hashtag_count
        )
      },
      formatLabel: "instagram-post"
    });

    const instagramStoryAsset = await renderStoreSingleAsset(env, browser, {
      key: `${keyPrefix}/instagram-story.png`,
      kind: "instagram-story",
      params: {
        ...commonTemplateValues,
        templateId: args.templateIds?.["instagram-story"],
        slots: {
          ...sharedSlots,
          headline: sharedSlots.headline || args.postTitle,
          supporting_line: sharedSlots.supporting_line || args.llmOutput.instagram_caption
        },
        caption: withHashtags(
          args.llmOutput.instagram_caption,
          args.llmOutput.hashtags,
          PIPELINE_CONFIG.formats["instagram-story"].hashtag_count
        )
      },
      formatLabel: "instagram-story"
    });

    const twitterCardAsset = await renderStoreSingleAsset(env, browser, {
      key: `${keyPrefix}/twitter-card.png`,
      kind: "twitter-card",
      params: {
        ...commonTemplateValues,
        templateId: args.templateIds?.["twitter-card"],
        slots: {
          ...sharedSlots,
          headline: sharedSlots.headline || args.postTitle,
          supporting_line: sharedSlots.supporting_line || args.llmOutput.twitter_caption
        },
        caption: withHashtags(
          args.llmOutput.twitter_caption,
          args.llmOutput.hashtags,
          PIPELINE_CONFIG.formats["twitter-card"].hashtag_count
        )
      },
      formatLabel: "twitter-card"
    });

    const linkedInAsset = await renderStoreSingleAsset(env, browser, {
      key: `${keyPrefix}/linkedin-post.png`,
      kind: "linkedin-post",
      params: {
        ...commonTemplateValues,
        templateId: args.templateIds?.["linkedin-post"],
        slots: {
          ...sharedSlots,
          headline: sharedSlots.headline || args.postTitle,
          supporting_line: sharedSlots.supporting_line || args.llmOutput.linkedin_caption
        },
        caption: withHashtags(
          args.llmOutput.linkedin_caption,
          args.llmOutput.hashtags,
          PIPELINE_CONFIG.formats["linkedin-post"].hashtag_count
        )
      },
      formatLabel: "linkedin-post"
    });

    const carousel: StoredAsset[] = [];
    for (const [index, slide] of args.llmOutput.carousel_slides.entries()) {
      const slideAsset = await renderStoreSingleAsset(env, browser, {
        key: `${keyPrefix}/carousel-slide-${index + 1}.png`,
        kind: "carousel-slide",
        params: {
          ...commonTemplateValues,
          templateId: args.templateIds?.["carousel-slide"],
          slots: {
            ...sharedSlots,
            headline: slide.heading,
            body: slide.body,
            short_hook: slide.heading,
            supporting_line: slide.body,
            step_number: String(index + 1),
            step_total: String(args.llmOutput.carousel_slides.length)
          },
          heading: slide.heading,
          body: slide.body,
          slideNumber: index + 1,
          totalSlides: args.llmOutput.carousel_slides.length
        },
        formatLabel: `carousel-slide-${index + 1}`
      });
      carousel.push(slideAsset);
    }

    return {
      instagram_post: instagramPostAsset,
      instagram_story: instagramStoryAsset,
      twitter_card: twitterCardAsset,
      linkedin_post: linkedInAsset,
      carousel
    };
  } finally {
    await browser.close();
  }
}

async function renderStoreSingleAsset(
  env: Env,
  browser: Awaited<ReturnType<typeof puppeteer.launch>>,
  args: {
    key: string;
    kind: TemplateKind;
    params: BaseTemplateParams | CarouselTemplateParams;
    formatLabel: string;
  }
): Promise<StoredAsset> {
  const size = getTemplateDimensions(args.kind);
  const html = renderTemplate(args.kind, args.params);
  const png = await renderPng(browser, html, size.width, size.height);

  await env.OUTPUT_BUCKET.put(args.key, png, {
    httpMetadata: {
      contentType: "image/png",
      cacheControl: PIPELINE_CONFIG.runtime.asset_cache_control
    }
  });

  return {
    format: args.formatLabel,
    key: args.key,
    url: buildPublicUrl(env, args.key)
  };
}

async function renderPng(
  browser: Awaited<ReturnType<typeof puppeteer.launch>>,
  html: string,
  width: number,
  height: number
): Promise<Uint8Array> {
  const page = await browser.newPage();

  try {
    await page.setViewport({ width, height, deviceScaleFactor: 1 });
    await page.setContent(html, {
      waitUntil: PIPELINE_CONFIG.runtime.page_set_content_wait_until as "load" | "domcontentloaded" | "networkidle0"
    });

    await page.evaluate(`
      (async () => {
        await document.fonts.ready;
        const images = Array.from(document.images);
        await Promise.all(
          images.map(async (image) => {
            try {
              await image.decode();
            } catch {}
          })
        );
      })();
    `);

    const screenshot = await page.screenshot({
      type: "png",
      clip: { x: 0, y: 0, width, height }
    });

    if (screenshot instanceof Uint8Array) {
      return screenshot;
    }

    return new Uint8Array(screenshot as ArrayBuffer);
  } finally {
    await page.close();
  }
}

function buildR2KeyPrefix(env: Env, slug: string, storage?: StorageOptions): string {
  const basePrefix = (env.R2_KEY_PREFIX || PIPELINE_CONFIG.storage.default_key_prefix).replace(/\/+$/, "");
  const mode = storage?.mode ?? PIPELINE_CONFIG.storage.default_mode;

  if (mode === "overwrite") {
    return `${basePrefix}/${slug}`;
  }

  const includeDate = storage?.includeDate ?? PIPELINE_CONFIG.storage.versioned_include_date;
  const runId = sanitizeRunId(storage?.runId) ?? crypto.randomUUID().split("-")[0];
  const datePart = includeDate ? `/${new Date().toISOString().slice(0, 10)}` : "";
  return `${basePrefix}/${slug}${datePart}/${runId}`;
}

function sanitizeRunId(input: string | undefined): string | null {
  if (!input) {
    return null;
  }
  const cleaned = input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-_]/g, "");
  if (!cleaned) {
    return null;
  }
  return cleaned.slice(0, PIPELINE_CONFIG.generation.limits.storage_run_id_max_chars);
}

function buildPublicUrl(env: Env, key: string): string | null {
  const base = env.R2_PUBLIC_BASE_URL?.trim();
  if (!base) {
    return null;
  }
  const normalizedBase = base.replace(/\/+$/, "");
  const encodedPath = key
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${normalizedBase}/${encodedPath}`;
}

async function sendNotification(url: string, payload: GenerationResult): Promise<void> {
  try {
    await fetch(url, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  } catch {
    // Notification failures should not break generation.
  }
}

function resolveNotifyUrl(bodyValue: string | undefined, envValue: string | undefined): string | null {
  const candidate = (bodyValue ?? envValue)?.trim();
  if (!candidate) {
    return null;
  }
  return candidate;
}

function createTopicKeywordPattern(keywords: readonly string[]): RegExp | null {
  const safeKeywords = keywords
    .map((keyword) => keyword.trim().toLowerCase())
    .filter(Boolean)
    .map((keyword) => keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));

  if (safeKeywords.length === 0) {
    return null;
  }

  return new RegExp(`\\b(${safeKeywords.join("|")})\\b`, "i");
}

function normalizeSlotContent(
  value: unknown,
  args: {
    title: string;
    fallbackText: string;
  }
): Record<string, string> {
  const limits = PIPELINE_CONFIG.generation.limits;
  const slotDefaults = PIPELINE_CONFIG.slot_schema.defaults as Record<string, string>;
  const untitled = PIPELINE_CONFIG.generation.fallbacks.untitled_text;
  const normalized: Record<string, string> = {};

  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [rawKey, rawValue] of Object.entries(value as Record<string, unknown>)) {
      const key = normalizeSlotKey(rawKey);
      const text = toText(rawValue);
      if (!key || !text) {
        continue;
      }
      normalized[key] = ensureLength(text, limits.slot_text_max_chars, text);
    }
  }

  const fallbackLine = toSingleSentence(ensureLength(args.fallbackText, limits.slot_fallback_line_max_chars, args.title));

  const resolveSlotDefault = (slotKey: string): string => {
    const raw = slotDefaults[slotKey] ?? "";
    if (!raw) {
      return "";
    }
    return raw
      .replaceAll("{{TITLE}}", args.title)
      .replaceAll("{{CAPTION}}", fallbackLine)
      .replaceAll("{{BRAND_NAME}}", PIPELINE_CONFIG.brand.default_name);
  };

  normalized.headline = normalized.headline || ensureLength(args.title, limits.slot_headline_max_chars, untitled);
  normalized.subheadline = normalized.subheadline || fallbackLine;
  normalized.short_hook = normalized.short_hook || ensureLength(args.title, limits.slot_headline_max_chars, args.title);
  normalized.supporting_line = normalized.supporting_line || fallbackLine;
  normalized.insight_line = normalized.insight_line || fallbackLine;
  normalized.quote_text = normalized.quote_text || resolveSlotDefault("quote_text") || fallbackLine;
  normalized.quote_author =
    normalized.quote_author || resolveSlotDefault("quote_author") || PIPELINE_CONFIG.generation.fallbacks.default_quote_author;
  normalized.cta_text = normalized.cta_text || resolveSlotDefault("cta_text");
  normalized.kicker = normalized.kicker || resolveSlotDefault("kicker");
  normalized.metric_value = normalized.metric_value || resolveSlotDefault("metric_value");
  normalized.metric_label = normalized.metric_label || resolveSlotDefault("metric_label");
  normalized.step_1 = normalized.step_1 || resolveSlotDefault("step_1");
  normalized.step_2 = normalized.step_2 || resolveSlotDefault("step_2");
  normalized.step_3 = normalized.step_3 || resolveSlotDefault("step_3");
  normalized.step_4 = normalized.step_4 || resolveSlotDefault("step_4");

  return normalized;
}

function mergeSlotContent(base: Record<string, string>, overrides: Record<string, string>): Record<string, string> {
  const merged: Record<string, string> = { ...base };
  for (const [key, value] of Object.entries(overrides)) {
    const normalizedKey = normalizeSlotKey(key);
    const normalizedValue = value.trim();
    if (!normalizedKey || !normalizedValue) {
      continue;
    }
    merged[normalizedKey] = normalizedValue;
  }
  return merged;
}

function buildSharedSlotContent(args: {
  postTitle: string;
  llmOutput: LlmOutput;
  brandName: string;
  templateArchetype: string;
  slotContent: Record<string, string>;
}): Record<string, string> {
  const limits = PIPELINE_CONFIG.generation.limits;
  const slotDefaults = PIPELINE_CONFIG.slot_schema.defaults as Record<string, string>;
  const slots = {
    ...args.slotContent
  };

  slots.headline = slots.headline || args.postTitle;
  slots.subheadline = slots.subheadline || args.llmOutput.linkedin_caption;
  slots.short_hook = slots.short_hook || ensureLength(args.postTitle, limits.slot_headline_max_chars, args.postTitle);
  slots.supporting_line = slots.supporting_line || args.llmOutput.instagram_caption;
  slots.insight_line = slots.insight_line || args.llmOutput.twitter_caption;
  slots.quote_text = slots.quote_text || args.llmOutput.linkedin_caption;
  slots.quote_author = slots.quote_author || args.brandName;
  slots.cta_text = slots.cta_text || slotDefaults.cta_text || "";
  slots.kicker = slots.kicker || slotDefaults.kicker || args.templateArchetype.toUpperCase();

  const firstSlide = args.llmOutput.carousel_slides[0];
  const secondSlide = args.llmOutput.carousel_slides[1];
  const thirdSlide = args.llmOutput.carousel_slides[2];
  const fourthSlide = args.llmOutput.carousel_slides[3];

  slots.step_1 = slots.step_1 || firstSlide?.heading || slotDefaults.step_1 || "";
  slots.step_2 = slots.step_2 || secondSlide?.heading || slotDefaults.step_2 || "";
  slots.step_3 = slots.step_3 || thirdSlide?.heading || slotDefaults.step_3 || "";
  slots.step_4 = slots.step_4 || fourthSlide?.heading || slotDefaults.step_4 || "";
  slots.metric_value = slots.metric_value || slotDefaults.metric_value || "";
  slots.metric_label = slots.metric_label || slotDefaults.metric_label || "";

  return slots;
}

function normalizeSlotKey(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function withHashtags(caption: string, hashtags: string[], count: number): string {
  const compactTags = hashtags.slice(0, count).join(" ");
  return ensureLength(
    `${caption} ${compactTags}`.trim(),
    PIPELINE_CONFIG.generation.limits.caption_with_hashtags_max_chars,
    caption
  );
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
  return `${source.slice(0, Math.max(1, max - 1)).trimEnd()}...`;
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

function arrayBufferToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function assertRequiredEnv(env: Env): void {
  if (!env.GHOST_API_URL?.trim()) {
    throw new HttpError(500, "Missing env var GHOST_API_URL");
  }
  if (!env.GHOST_CONTENT_API_KEY?.trim()) {
    throw new HttpError(500, "Missing env var GHOST_CONTENT_API_KEY");
  }
}

async function readJsonBody<T>(request: Request): Promise<T> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    throw new HttpError(400, "Invalid JSON body");
  }
  return body as T;
}

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8"
    }
  });
}

function handleError(error: unknown): Response {
  if (error instanceof HttpError) {
    return json({ error: error.message }, error.status);
  }

  const message = error instanceof Error ? error.message : "Unexpected error";
  return json({ error: message }, 500);
}

class HttpError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
