// Auto-generated from config/pipeline.config.yaml — do not edit manually
export const PIPELINE_CONFIG = {
  "schema_version": 4,
  "brand": {
    "default_name": "Tasbir Blog"
  },
  "formats": {
    "instagram-portrait": {
      "width": 1080,
      "height": 1350,
      "caption_source": "instagram_caption",
      "hashtag_count": 3
    },
    "instagram-square": {
      "width": 1080,
      "height": 1080,
      "caption_source": "instagram_caption",
      "hashtag_count": 3
    },
    "instagram-story": {
      "width": 1080,
      "height": 1920,
      "caption_source": "instagram_caption",
      "hashtag_count": 2
    },
    "carousel-post": {
      "width": 1080,
      "height": 1350,
      "caption_source": "carousel_slides",
      "hashtag_count": 0
    },
    "twitter-card": {
      "width": 1200,
      "height": 628,
      "caption_source": "twitter_caption",
      "hashtag_count": 0
    },
    "linkedin-post": {
      "width": 1200,
      "height": 627,
      "caption_source": "linkedin_caption",
      "hashtag_count": 0
    }
  },
  "generation": {
    "carousel_required_slides": 5,
    "agents": {
      "default_mode": "agentic",
      "default_prompt_profile": "default",
      "models": {
        "orchestrator_model": "@cf/openai/gpt-oss-120b",
        "copy_model": "@cf/openai/gpt-oss-120b"
      },
      "runtime": {
        "copy_temperature": 0.2,
        "copy_max_tokens": 2200
      },
      "prompts": {
        "copy_system_prompt": [
          "You are an elite multi-platform marketing strategist and conversion copywriter.",
          "Produce precise, persuasive, and platform-native content from the provided source context.",
          "Do not invent facts not present in source content.",
          "Output strict JSON only and satisfy all schema requirements."
        ],
        "copy_user_instructions": [
          "Create platform-ready campaign copy from the source content.",
          "Primary goal: convert attention into clear intent (read, save, share, click, follow).",
          "Constraints:",
          "- Keep one coherent campaign angle across platforms, adapted to each platform's tone.",
          "- instagram_caption: emotionally engaging hook + practical value + soft CTA, max <instagram_caption_max_chars> characters.",
          "- twitter_caption: concise high-signal insight + payoff + direct CTA, max <twitter_caption_max_chars> characters.",
          "- linkedin_caption: problem -> insight -> action narrative for professionals, max <linkedin_caption_max_chars> characters.",
          "- Captions must be plain text; no markdown headings, no list markers, no leading #.",
          "- Keep language specific and credible; avoid vague hype.",
          "- carousel_slides: exactly <required_carousel_slides> slides with narrative flow.",
          "- Carousel flow: slide 1 hook/intro, middle slides distinct support, final slide concrete next step.",
          "- Each carousel slide must introduce new information.",
          "- hashtags: <hashtag_min_count>-<hashtag_max_count> relevant tags, #prefix, no spaces.",
          "- image_prompt: background-only art direction, no text, no UI, no logos.",
          "- use_feature_image: true only when source feature image fits the campaign.",
          "- stock_search_query: focused keyword phrase (<= 10 words), no metadata.",
          "- Apply composition directives exactly:",
          "<composition_directives>",
          "Output JSON only."
        ],
        "gemini_html_generation_system_prompt": [
          "You are a master of Swiss-style layout design and modern web development.",
          "Your task is to generate ONE COMPLETE, SELF-CONTAINED HTML document for a social media post.",
          "The HTML must be a full standalone document with <!DOCTYPE html>, <html>, <head>, and <body>.",
          "Use Tailwind CSS via CDN: <script src=\"https://cdn.tailwindcss.com\"></script>",
          "Configure Tailwind with the provided design tokens in a <script> tag before the closing </body>.",
          "Rules:",
          "- Use Tailwind utility classes for all styling.",
          "- Use the design tokens as Tailwind theme extensions (colors, fonts).",
          "- The design must be exactly sized for the given width x height viewport.",
          "- Use a wrapper <div> with the exact width/height as the canvas.",
          "- Typography must be bold, professional, and highly readable.",
          "- The design must feel PREMIUM, DYNAMIC, and visually striking.",
          "- Never include text in generated images — all text is HTML/CSS.",
          "- No external libraries except Tailwind CDN.",
          "- Use system fonts or the provided font tokens.",
          "- Output should be the complete HTML document string."
        ],
        "gemini_html_generation_user_instructions": [
          "Generate a social post design for the platform: <platform> (<width>x<height>).",
          "Design tokens: <design_tokens>",
          "Source Content Title: <title>",
          "Source Content Excerpt: <excerpt>",
          "Instructions: Create a high-impact visual design using the source content. Use Tailwind classes with the provided design tokens. Use a clear hierarchy, impactful typography, and the brand vibes provided.",
          "Return a JSON object with: { 'generated_html': '...', 'instagram_caption': '...', 'twitter_caption': '...', 'linkedin_caption': '...', 'hashtags': [...], 'image_prompt': '...' }"
        ]
      },
      "render_policy": {
        "allow_markdown": true,
        "allow_math": true,
        "allow_diagrams": true,
        "allow_text_in_ai_images": false,
        "strip_hashtags_in_visual_slots": true
      },
      "prompt_profiles": {
        "default": {
          "mastermind": [
            "You are the marketing mastermind for multi-platform campaign generation.",
            "Plan platform-native assets with clear strategic intent, varied angles, and cohesive campaign narrative.",
            "Prioritize readability and conversion outcomes."
          ],
          "roles": {
            "strategist": [
              "Plan how many posts to create per platform based on source depth and user goals.",
              "Design clear narrative arcs for carousel intros, middle education slides, and ending CTA slides.",
              "Ensure each post angle is unique and non-repetitive."
            ],
            "copywriter": [
              "Generate platform-native copy that is specific, useful, and non-generic.",
              "Prefer complete thoughts, avoid partial sentence truncation, and keep language concise."
            ],
            "visual_director": [
              "Generate image direction for clean editorial backgrounds with intentional text-safe negative space.",
              "Never include text artifacts in generated image content."
            ],
            "render_guard": [
              "Optimize format content to prevent overflow, clipping, and hidden text.",
              "If markdown, math, or diagram syntax appears, normalize it to render-safe output."
            ]
          }
        }
      }
    },
    "limits": {
      "post_text_max_chars": 14000,
      "direct_content_max_chars": 120000,
      "direct_excerpt_default_max_chars": 360,
      "input_tags_max_count": 8,
      "stock_query_term_max_count": 6,
      "storage_run_id_max_chars": 64,
      "instagram_caption_max_chars": 600,
      "twitter_caption_max_chars": 280,
      "linkedin_caption_max_chars": 900,
      "carousel_heading_max_chars": 72,
      "carousel_body_max_chars": 260,
      "image_prompt_max_chars": 700,
      "hashtag_min_count": 5,
      "hashtag_max_count": 8,
      "hashtag_min_token_chars": 3,
      "title_keyword_min_chars": 3,
      "fallback_keyword_min_chars": 4,
      "caption_with_hashtags_max_chars": 980,
      "single_sentence_max_chars": 240
    },
    "fallbacks": {
      "carousel_heading": "Key Point",
      "carousel_heading_prefix": "Insight",
      "stock_search_query": "technology lifestyle",
      "untitled_text": "Untitled",
      "default_quote_author": "Editorial Team"
    },
    "image": {
      "default_model": "@cf/black-forest-labs/flux-1-schnell",
      "prompt_fallback": "<title>, modern editorial photo, clean composition, natural lighting, no text overlay",
      "prompt_composition": [
        "<prompt_prefix>",
        "Campaign title: <title>",
        "Tags: <tags>",
        "Scene description: <scene>",
        "<negative_clauses>"
      ],
      "prompt_prefix": [
        "Create one campaign-quality social background image that can be reused across square, portrait, and landscape crops.",
        "Use one clear focal subject, intentional negative space for headline placement, and brand-safe composition.",
        "No text, no letters, no numbers, no logos, no UI elements, no watermarks.",
        "Avoid heavy black gradients unless dramatic contrast is explicitly requested."
      ],
      "negative_clauses": [
        "Avoid muddy shadows and overly dark vignette overlays.",
        "Avoid cluttered scenes that reduce text readability.",
        "Avoid generic stock-photo look; keep visual identity distinct.",
        "Do not render any typography, captions, labels, symbols, glyphs, or watermarks.",
        "Avoid signage, billboards, screens, packaging text, and posters with words."
      ]
    }
  },
  "runtime": {
    "browser_keep_alive_ms": 60000,
    "page_set_content_wait_until": "networkidle0",
    "asset_cache_control": "public, max-age=31536000, immutable",
    "ghost_error_preview_chars": 300
  },
  "features": {
    "enable_agentic_orchestration": true,
    "enable_ai_image_generation": true,
    "prefer_feature_image": false,
    "enable_notifications": true
  },
  "security": {
    "api_auth": {
      "enabled": true,
      "header_name": "x-api-key",
      "require_for_generate": true,
      "require_for_direct_content": true,
      "require_for_webhook": false
    },
    "cors": {
      "enabled": true,
      "allowed_origins": [
        "*"
      ],
      "allowed_headers": [
        "content-type",
        "authorization",
        "x-api-key",
        "x-webhook-token"
      ],
      "allowed_methods": [
        "GET",
        "POST",
        "OPTIONS"
      ],
      "allow_credentials": false,
      "max_age_seconds": 86400
    },
    "request_limits": {
      "max_json_body_bytes": 256000
    },
    "rate_limit": {
      "enabled": true,
      "window_seconds": 60,
      "max_requests_per_window": 30
    },
    "outbound": {
      "allow_private_network_targets": false,
      "allowed_notify_hosts": [],
      "allowed_image_hosts": []
    }
  },
  "storage": {
    "default_key_prefix": "social-assets",
    "default_mode": "overwrite",
    "versioned_include_date": true
  }
} as const;

export function getDesignTokens() {
  return (PIPELINE_CONFIG as any).design_tokens ?? DEFAULT_DESIGN_TOKENS;
}

export function getFormatConfig(name: string) {
  const formats = (PIPELINE_CONFIG as any).formats;
  return formats?.[name] ?? null;
}

export function getAllFormats() {
  return (PIPELINE_CONFIG as any).formats ?? {};
}

export function getFormatNames() {
  return Object.keys(getAllFormats());
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

export function generateTailwindConfig(): string {
  const tokens = getDesignTokens();
  return `
tailwind.config = {
  theme: {
    extend: {
      colors: {
        'primary-bg': '${tokens.colors.primary_bg}',
        'primary-text': '${tokens.colors.primary_text}',
        'accent': '${tokens.colors.accent}',
        'accent-text': '${tokens.colors.accent_text}',
        'muted-text': '${tokens.colors.muted_text}',
        'surface': '${tokens.colors.surface}',
        'border-custom': '${tokens.colors.border}',
      },
      fontFamily: {
        'display': [${tokens.fonts.display.split(",").map((f: string) => `'${f.trim()}'`).join(", ")}],
        'body': [${tokens.fonts.body.split(",").map((f: string) => `'${f.trim()}'`).join(", ")}],
        'mono': [${tokens.fonts.mono.split(",").map((f: string) => `'${f.trim()}'`).join(", ")}],
      },
      spacing: {
        'token-xs': '${tokens.spacing.xs}',
        'token-sm': '${tokens.spacing.sm}',
        'token-md': '${tokens.spacing.md}',
        'token-lg': '${tokens.spacing.lg}',
        'token-xl': '${tokens.spacing.xl}',
        'token-2xl': '${tokens.spacing["2xl"]}',
        'token-3xl': '${tokens.spacing["3xl"]}',
      },
    }
  }
}
`.trim();
}

const DEFAULT_DESIGN_TOKENS = {
  colors: {
    primary_bg: "#0b0b0b",
    primary_text: "#f5f5f5",
    accent: "#3b82f6",
    accent_text: "#ffffff",
    muted_text: "#a3a3a3",
    border: "#262626",
    surface: "#171717",
  },
  fonts: {
    display: "system-ui, -apple-system, sans-serif",
    body: "system-ui, -apple-system, sans-serif",
    mono: "ui-monospace, SFMono-Regular, monospace",
  },
  spacing: {
    xs: "4px",
    sm: "8px",
    md: "16px",
    lg: "24px",
    xl: "32px",
    "2xl": "48px",
    "3xl": "64px",
  },
};
