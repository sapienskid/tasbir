import { getDefaultDesignTokens } from "../shared/tokens";

export interface FormatConfig {
  width: number;
  height: number;
  name?: string;
  aiInstruction?: string;
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
        html_layout_system_prompt: string[];
        html_layout_user_instructions: string[];
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
    "instagram-portrait": { width: 1080, height: 1350, name: "Instagram Portrait", aiInstruction: "Vertical layout optimized for mobile feed. Bold headline at top, supporting text below. High visual impact with strong typography hierarchy." },
    "instagram-square": { width: 1080, height: 1080, name: "Instagram Square", aiInstruction: "Square format for Instagram feed. Centered composition, balanced whitespace. Works well for quotes and key insights." },
    "instagram-story": { width: 1080, height: 1920, name: "Instagram Story", aiInstruction: "Full-screen vertical story format. Top and bottom safe zones for UI. Immersive, attention-grabbing design with strong readability and safe text placement." },
    "carousel-post": { width: 1080, height: 1350, name: "Carousel Post", aiInstruction: "Swipeable carousel slide. Each slide should be self-contained but part of a visual series. Consistent styling across slides. Include subtle 'Swipe →' indicator on non-final slides." },
    "twitter-card": { width: 1200, height: 628, name: "Twitter/X Card", aiInstruction: "Horizontal preview card for Twitter/X. Headline-focused with clear value proposition. Optimized for timeline visibility." },
    "linkedin-post": { width: 1200, height: 627, name: "LinkedIn Post", aiInstruction: "Professional horizontal format. Clean, corporate-friendly design. Emphasize credibility and thought leadership." },
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
        copy_temperature: 0.7,
        copy_max_tokens: 2200,
      },
      prompts: {
        html_layout_system_prompt: [
          "You are an elite social media post art director and layout engineer.",
          "Your task is to generate ONE COMPLETE, SELF-CONTAINED HTML document for screenshot rendering.",
          "The HTML must be a full standalone document with <!DOCTYPE html>, <html>, <head>, and <body>.",
          "Use Tailwind CSS via CDN.",
          "Configure Tailwind with the provided design tokens.",
          "Rules:",
          "- The output must look like a social media post, not a website.",
          "- Do not create webpage patterns (navbar, footer, menu, sidebar, blog/article page, long multi-section layout).",
          "- Treat the design as one locked frame that will be screenshotted.",
          "- Use Tailwind utility classes for all styling.",
          "- Use the design tokens as the single source of truth for all visual styling.",
          "- Use only token-backed Tailwind theme classes for color, typography, spacing, radius, and shadow.",
          "- Use token CSS variables via var(--...) only when utility classes cannot express the exact token mapping.",
          "- Do NOT hardcode color literals (#hex, rgb/rgba, hsl/hsla, oklch, color()).",
          "- Do NOT use arbitrary Tailwind color classes like bg-[#...], text-[rgb(...)], border-[hsl(...)].",
          "- Ensure readable contrast by pairing background tokens with corresponding foreground tokens (for example on-primary/on-surface tokens).",
          "- Prioritize platform-native composition that performs well in social feeds.",
          "- Build strong visual hierarchy with clear focal point, fast scannability, and thumbnail legibility.",
          "- The design must be exactly sized for the given width x height viewport.",
          "- Enforce fixed-canvas rendering: html/body/frame must be full size with overflow hidden.",
          "- Never rely on scrolling; no text or element may be clipped outside the canvas.",
          "- Prefer concise copy and stronger hierarchy over dense content blocks.",
          "- Typography must be bold, professional, and highly readable at first glance.",
          "- The design must feel premium, intentional, and compositionally strong.",
          "- Avoid generic template aesthetics; composition should feel authored and distinct.",
          "- Never include text in generated images — all text is HTML/CSS.",
          "- NO 'swipe', 'swipe left', 'swipe right', 'swipe to learn more', or similar navigation text UNLESS the format is explicitly 'carousel-post' or 'carousel-post-slide-N'.",
          "- PREVENT TEXT OVERLAPPING: Use adequate line-height (leading-relaxed or leading-loose), proper margins (mb-2, mb-4, mb-6), and padding. Never stack text elements without spacing.",
          "- Use flex/grid layouts with gap (gap-4, gap-6) instead of absolute positioning for text elements.",
          "- Ensure text containers have max-width to prevent overly wide lines.",
          "- Use truncate or line-clamp-2/line-clamp-3 for long text that might overflow.",
          "- Minimum font size for body text: 14px (text-base). Headlines: 24px+ (text-2xl+).",
          "- No external libraries except Tailwind CDN.",
          "- Return only raw HTML output.",
          "- Never return JSON or captions.",
        ],
        html_layout_user_instructions: [
          "Generate a social post design for the platform: <platform> (<width>x<height>).",
          "Design tokens and Tailwind token theme: <design_tokens>",
          "Source Content Title: <title>",
          "Source Content Excerpt: <excerpt>",
          "Instructions:",
          "- Create a high-impact social post visual using the source content.",
          "- This is not a webpage. Produce one framed composition only.",
          "- Rewrite and rebalance source copy when needed so all content remains readable and fully within frame.",
          "- All visual values must flow from the provided tokenized Tailwind theme.",
          "- Prefer semantic token classes (bg-surface-*, text-content-*, bg-primary-*, text-content-on-*).",
          "- If a token exists, do not use hardcoded values.",
          "- Maintain strong readability and contrast for every text/background pairing.",
          "- Ensure zero overflow: no clipping, no hidden text, no scroll.",
          "Return exactly one full HTML document string and nothing else.",
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
              "Keep language concise and social-first: strong headline, compact support text, no filler.",
              "Prefer complete thoughts while staying brief enough for fixed-canvas visual layouts.",
            ],
            visual_director: [
              "Generate image direction for social-post compositions with intentional text-safe negative space.",
              "Never include text artifacts in generated image content.",
            ],
            render_guard: [
              "Enforce fixed-canvas output with no webpage structure and no scrolling.",
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
      default_model: "@cf/black-forest-labs/flux-2-klein-9b",
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

// Runtime state for custom formats (merged with defaults)
let runtimeFormats: Record<string, FormatConfig> = { ...DEFAULT_CONFIG.formats };

export const PIPELINE_CONFIG = DEFAULT_CONFIG;

export function getFormatConfig(name: string): FormatConfig | null {
  return runtimeFormats[name] ?? null;
}

export function getAllFormats(): Record<string, FormatConfig> {
  return { ...runtimeFormats };
}

export function getFormatNames(): string[] {
  return Object.keys(runtimeFormats);
}

export function setFormat(id: string, config: FormatConfig): void {
  runtimeFormats[id] = config;
}

export function deleteFormat(id: string): boolean {
  if (runtimeFormats[id]) {
    delete runtimeFormats[id];
    return true;
  }
  return false;
}

export function resetFormats(): void {
  runtimeFormats = { ...DEFAULT_CONFIG.formats };
}

export function loadFormatsFromStorage(formats: Record<string, FormatConfig>): void {
  const entries = Object.entries(formats || {});
  runtimeFormats = entries.length > 0 ? { ...formats } : { ...DEFAULT_CONFIG.formats };
}

export function getDesignTokens() {
  return getDefaultDesignTokens();
}

export function generateTailwindConfig(): string {
  return `/* Tailwind config generated from design tokens */`;
}

export function formatDesignTokensForPrompt(): string {
  const tokens = getDesignTokens();
  const parts: string[] = [];
  
  parts.push("Colors:");
  // Primary scale
  for (const [key, value] of Object.entries(tokens.colors.primary)) {
    parts.push(`  --color-primary-${key}: ${value}`);
  }
  // Surface colors
  for (const [key, value] of Object.entries(tokens.colors.surface)) {
    parts.push(`  --surface-${key}: ${value}`);
  }
  // Text colors
  for (const [key, value] of Object.entries(tokens.colors.text)) {
    parts.push(`  --text-${key}: ${value}`);
  }
  
  parts.push("Fonts:");
  parts.push(`  --font-sans: ${tokens.typography.fontSans}`);
  parts.push(`  --font-serif: ${tokens.typography.fontSerif}`);
  parts.push(`  --font-mono: ${tokens.typography.fontMono}`);
  
  parts.push("Spacing:");
  for (const [i, value] of tokens.spacing.scale.entries()) {
    parts.push(`  --space-${i + 1}: ${value}px`);
  }
  
  return parts.join("\n");
}
