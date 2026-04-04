export interface FormatConfig {
  width: number;
  height: number;
}

export interface PipelineConfig {
  formats: Record<string, FormatConfig>;
  generation: {
    carousel_required_slides: number;
    agents: {
      default_mode: string;
      default_prompt_profile: string;
      models: {
        orchestrator_model: string;
        copy_model: string;
      };
      runtime: {
        copy_temperature: number;
        copy_max_tokens: number;
      };
      prompts: {
        copy_system_prompt: string[];
        copy_user_instructions: string[];
        gemini_html_generation_system_prompt: string[];
        gemini_html_generation_user_instructions: string[];
      };
      render_policy: {
        allow_markdown: boolean;
        allow_math: boolean;
        allow_diagrams: boolean;
        allow_text_in_ai_images: boolean;
      };
      prompt_profiles: Record<string, any>;
    };
    limits: Record<string, number>;
    fallbacks: Record<string, string>;
    image: {
      default_model: string;
      prompt_fallback: string;
      prompt_prefix: string[];
      negative_clauses: string[];
    };
  };
  runtime: {
    browser_keep_alive_ms: number;
    page_set_content_wait_until: string;
    asset_cache_control: string;
    ghost_error_preview_chars: number;
  };
  features: {
    enable_agentic_orchestration: boolean;
    enable_ai_image_generation: boolean;
    prefer_feature_image: boolean;
    enable_notifications: boolean;
  };
  storage: {
    default_key_prefix: string;
    default_mode: string;
    versioned_include_date: boolean;
  };
}

export const DEFAULT_CONFIG: PipelineConfig = {
  formats: {
    "instagram-portrait": { width: 1080, height: 1350 },
    "instagram-square": { width: 1080, height: 1080 },
    "instagram-story": { width: 1080, height: 1920 },
    "carousel-post": { width: 1080, height: 1350 },
    "twitter-card": { width: 1200, height: 628 },
    "linkedin-post": { width: 1200, height: 627 },
  },
  generation: {
    carousel_required_slides: 5,
    agents: {
      default_mode: "agentic",
      default_prompt_profile: "default",
      models: {
        orchestrator_model: "@cf/openai/gpt-oss-120b",
        copy_model: "@cf/openai/gpt-oss-120b",
      },
      runtime: {
        copy_temperature: 0.2,
        copy_max_tokens: 2200,
      },
      prompts: {
        copy_system_prompt: [
          "You are an elite multi-platform marketing strategist and conversion copywriter.",
          "Produce precise, persuasive, and platform-native content from the provided source context.",
          "Do not invent facts not present in source content.",
          "Output strict JSON only and satisfy all schema requirements.",
        ],
        copy_user_instructions: [
          "Create platform-ready campaign copy from the source content.",
          "Primary goal: convert attention into clear intent (read, save, share, click, follow).",
          "Constraints:",
          "- Keep one coherent campaign angle across platforms, adapted to each platform's tone.",
          "- instagram_caption: emotionally engaging hook + practical value + soft CTA, max 600 characters.",
          "- twitter_caption: concise high-signal insight + payoff + direct CTA, max 280 characters.",
          "- linkedin_caption: problem -> insight -> action narrative for professionals, max 900 characters.",
          "- Captions must be plain text; no markdown headings, no list markers, no leading #.",
          "- Keep language specific and credible; avoid vague hype.",
          "- carousel_slides: exactly 5 slides with narrative flow.",
          "- Carousel flow: slide 1 hook/intro, middle slides distinct support, final slide concrete next step.",
          "- Each carousel slide must introduce new information.",
          "- image_prompt: background-only art direction, no text, no UI, no logos.",
          "- use_feature_image: true only when source feature image fits the campaign.",
          "- stock_search_query: focused keyword phrase (<= 10 words), no metadata.",
          "Output JSON only.",
        ],
        gemini_html_generation_system_prompt: [
          "You are a master of Swiss-style layout design and modern web development.",
          "Your task is to generate ONE COMPLETE, SELF-CONTAINED HTML document for a social media post.",
          "The HTML must be a full standalone document with <!DOCTYPE html>, <html>, <head>, and <body>.",
          "Use Tailwind CSS via CDN.",
          "Configure Tailwind with the provided design tokens.",
          "Rules:",
          "- Use Tailwind utility classes for all styling.",
          "- Use the design tokens as Tailwind theme extensions (colors, fonts).",
          "- The design must be exactly sized for the given width x height viewport.",
          "- Typography must be bold, professional, and highly readable.",
          "- The design must feel PREMIUM, DYNAMIC, and visually striking.",
          "- Never include text in generated images — all text is HTML/CSS.",
          "- No external libraries except Tailwind CDN.",
          "- Output should be the complete HTML document string.",
        ],
        gemini_html_generation_user_instructions: [
          "Generate a social post design for the platform: <platform> (<width>x<height>).",
          "Design tokens: <design_tokens>",
          "Source Content Title: <title>",
          "Source Content Excerpt: <excerpt>",
          "Instructions: Create a high-impact visual design using the source content. Use Tailwind classes with the provided design tokens.",
          "Return a JSON object with: { 'generated_html': '...', 'instagram_caption': '...', 'twitter_caption': '...', 'linkedin_caption': '...', 'image_prompt': '...' }",
        ],
      },
      render_policy: {
        allow_markdown: true,
        allow_math: true,
        allow_diagrams: true,
        allow_text_in_ai_images: false,
      },
      prompt_profiles: {
        default: {
          mastermind: [
            "You are the marketing mastermind for multi-platform campaign generation.",
            "Plan platform-native assets with clear strategic intent, varied angles, and cohesive campaign narrative.",
            "Prioritize readability and conversion outcomes.",
          ],
          roles: {
            strategist: [
              "Plan how many posts to create per platform based on source depth and user goals.",
              "Design clear narrative arcs for carousel intros, middle education slides, and ending CTA slides.",
              "Ensure each post angle is unique and non-repetitive.",
            ],
            copywriter: [
              "Generate platform-native copy that is specific, useful, and non-generic.",
              "Prefer complete thoughts, avoid partial sentence truncation, and keep language concise.",
            ],
            visual_director: [
              "Generate image direction for clean editorial backgrounds with intentional text-safe negative space.",
              "Never include text artifacts in generated image content.",
            ],
            render_guard: [
              "Optimize format content to prevent overflow, clipping, and hidden text.",
              "If markdown, math, or diagram syntax appears, normalize it to render-safe output.",
            ],
          },
        },
      },
    },
    limits: {
      instagram_caption_max_chars: 600,
      twitter_caption_max_chars: 280,
      linkedin_caption_max_chars: 900,
      carousel_heading_max_chars: 72,
      carousel_body_max_chars: 260,
      image_prompt_max_chars: 700,
    },
    fallbacks: {
      carousel_heading: "Key Point",
      carousel_heading_prefix: "Insight",
      stock_search_query: "technology lifestyle",
      untitled_text: "Untitled",
      default_quote_author: "Editorial Team",
    },
    image: {
      default_model: "@cf/black-forest-labs/flux-1-schnell",
      prompt_fallback: "<title>, modern editorial photo, clean composition, natural lighting, no text overlay",
      prompt_prefix: [
        "Create one campaign-quality social background image that can be reused across square, portrait, and landscape crops.",
        "Use one clear focal subject, intentional negative space for headline placement, and brand-safe composition.",
        "No text, no letters, no numbers, no logos, no UI elements, no watermarks.",
        "Avoid heavy black gradients unless dramatic contrast is explicitly requested.",
      ],
      negative_clauses: [
        "Avoid muddy shadows and overly dark vignette overlays.",
        "Avoid cluttered scenes that reduce text readability.",
        "Avoid generic stock-photo look; keep visual identity distinct.",
        "Do not render any typography, captions, labels, symbols, glyphs, or watermarks.",
        "Avoid signage, billboards, screens, packaging text, and posters with words.",
      ],
    },
  },
  runtime: {
    browser_keep_alive_ms: 60000,
    page_set_content_wait_until: "networkidle0",
    asset_cache_control: "public, max-age=31536000, immutable",
    ghost_error_preview_chars: 300,
  },
  features: {
    enable_agentic_orchestration: true,
    enable_ai_image_generation: true,
    prefer_feature_image: false,
    enable_notifications: true,
  },
  storage: {
    default_key_prefix: "social-assets",
    default_mode: "overwrite",
    versioned_include_date: true,
  },
};

export const PIPELINE_CONFIG = DEFAULT_CONFIG;

export function getFormatConfig(name: string): FormatConfig | null {
  return DEFAULT_CONFIG.formats[name] ?? null;
}

export function getAllFormats(): Record<string, FormatConfig> {
  return { ...DEFAULT_CONFIG.formats };
}

export function getFormatNames(): string[] {
  return Object.keys(DEFAULT_CONFIG.formats);
}

export function getDesignTokens() {
  return {
    colors: { primary_bg: "#0b0b0b", primary_text: "#f5f5f5", accent: "#3b82f6", accent_text: "#ffffff", muted_text: "#a3a3a3", border: "#262626", surface: "#171717" },
    fonts: { display: "system-ui, -apple-system, sans-serif", body: "system-ui, -apple-system, sans-serif", mono: "ui-monospace, SFMono-Regular, monospace" },
    spacing: { xs: "4px", sm: "8px", md: "16px", lg: "24px", xl: "32px", "2xl": "48px", "3xl": "64px" },
  };
}

export function generateTailwindConfig(): string {
  return `/* Tailwind config generated from design tokens */`;
}

export function formatDesignTokensForPrompt(): string {
  const tokens = getDesignTokens();
  const parts: string[] = [];
  parts.push("Colors:");
  for (const [key, value] of Object.entries(tokens.colors)) {
    parts.push(`  --${key}: ${value}`);
  }
  parts.push("Fonts:");
  for (const [key, value] of Object.entries(tokens.fonts)) {
    parts.push(`  --font-${key}: ${value}`);
  }
  parts.push("Spacing:");
  for (const [key, value] of Object.entries(tokens.spacing)) {
    parts.push(`  --spacing-${key}: ${value}`);
  }
  return parts.join("\n");
}
