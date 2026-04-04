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
    "instagram-story": { width: 1080, height: 1920, name: "Instagram Story", aiInstruction: "Full-screen vertical story format. Top and bottom safe zones for UI. Immersive, attention-grabbing design with minimal text." },
    "carousel-post": { width: 1080, height: 1350, name: "Carousel Post", aiInstruction: "Swipeable carousel slide. Each slide should be self-contained but part of a visual series. Consistent styling across slides." },
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
        copy_temperature: 0.2,
        copy_max_tokens: 2200,
      },
      prompts: {
        html_layout_system_prompt: [
          "You are a master of Swiss-style layout design and modern web development.",
          "Your task is to generate ONE COMPLETE, SELF-CONTAINED HTML document for screenshot rendering.",
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
          "- Return only raw HTML output.",
          "- Never return JSON or captions.",
        ],
        html_layout_user_instructions: [
          "Generate a social post design for the platform: <platform> (<width>x<height>).",
          "Design tokens: <design_tokens>",
          "Source Content Title: <title>",
          "Source Content Excerpt: <excerpt>",
          "Instructions: Create a high-impact visual design using the source content. Use Tailwind classes with the provided design tokens.",
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
  return {
    colors: {
      primary: {
        "50": "#eff6ff",
        "100": "#dbeafe",
        "200": "#bfdbfe",
        "300": "#93c5fd",
        "400": "#60a5fa",
        "500": "#3b82f6",
        "600": "#2563eb",
        "700": "#1d4ed8",
        "800": "#1e40af",
        "900": "#1e3a8a",
      },
      secondary: {
        "50": "#f5f3ff",
        "100": "#ede9fe",
        "200": "#ddd6fe",
        "300": "#c4b5fd",
        "400": "#a78bfa",
        "500": "#8b5cf6",
        "600": "#7c3aed",
        "700": "#6d28d9",
        "800": "#5b21b6",
        "900": "#4c1d95",
      },
      accent: { light: "#60a5fa", base: "#3b82f6", dark: "#1d4ed8" },
      neutral: {
        "50": "#fafafa",
        "100": "#f5f5f5",
        "200": "#e5e5e5",
        "300": "#d4d4d4",
        "400": "#a3a3a3",
        "500": "#737373",
        "600": "#525252",
        "700": "#404040",
        "800": "#262626",
        "900": "#171717",
      },
      semantic: { success: "#22c55e", warning: "#f59e0b", error: "#ef4444", info: "#3b82f6" },
      surface: { base: "#0b0b0b", subtle: "#171717", elevated: "#1f1f1f", overlay: "rgba(0, 0, 0, 0.8)" },
      text: { primary: "#f5f5f5", secondary: "#a3a3a3", muted: "#737373", inverse: "#0b0b0b", accent: "#60a5fa" },
    },
    typography: {
      fontSans: "Inter",
      fontSerif: "Georgia",
      fontMono: "JetBrains Mono",
      scale: { xs: 12, sm: 14, base: 16, lg: 18, xl: 20, "2xl": 24, "3xl": 30, "4xl": 36, "5xl": 48, "6xl": 60, "7xl": 72 },
      weights: { light: 300, regular: 400, medium: 500, semibold: 600, bold: 700, black: 900 },
      tracking: { tight: "-0.025em", normal: "0em", wide: "0.025em", wider: "0.05em", widest: "0.1em" },
      leading: { tight: 1.25, snug: 1.375, normal: 1.5, relaxed: 1.625, loose: 2 },
    },
    spacing: { base: 4, scale: [4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128] },
    border: {
      width: { hairline: "0.5px", thin: "1px", normal: "2px", medium: "3px", thick: "4px" },
      radius: { none: "0", xs: "2px", sm: "4px", md: "6px", lg: "8px", xl: "12px", "2xl": "16px", "3xl": "24px", full: "9999px" },
    },
    shadow: {
      xs: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
      sm: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
      md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
      lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
      xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
      inner: "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
    },
    gradient: {
      primary: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
      hero: "linear-gradient(180deg, rgba(59, 130, 246, 0.15) 0%, transparent 50%)",
      subtle: "linear-gradient(180deg, rgba(255, 255, 255, 0.05) 0%, transparent 100%)",
      surface: "linear-gradient(180deg, #171717 0%, #0b0b0b 100%)",
    },
    motion: {
      duration: { instant: "50ms", fast: "150ms", normal: "300ms", slow: "500ms", slower: "700ms" },
      easing: { default: "cubic-bezier(0.4, 0, 0.2, 1)", in: "cubic-bezier(0.4, 0, 1, 1)", out: "cubic-bezier(0, 0, 0.2, 1)", bounce: "cubic-bezier(0.68, -0.55, 0.265, 1.55)" },
    },
    component: {
      button: { height: "40px", heightSm: "32px", heightLg: "48px", paddingX: "16px", radius: "6px", fontWeight: 500, fontSize: "14px" },
      card: { padding: "24px", paddingLg: "32px", radius: "12px", shadow: "md", border: "1px" },
      input: { height: "40px", paddingX: "12px", paddingY: "8px", radius: "6px", borderWidth: "1px" },
      badge: { height: "24px", paddingX: "8px", radius: "4px", fontSize: "12px", fontWeight: 500 },
      nav: { height: "64px", paddingX: "24px" },
    },
    meta: {
      vibeName: "Default Dark",
      description: "A clean, modern dark theme with blue accents",
      aesthetic: "minimal",
      palette: "dark",
    },
  };
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
