import { SOCIAL_COPYWRITER_PROMPT } from "../prompts.js";
/**
 * Template-Based HTML Generation
 * 
 * Instead of generating full HTML each time, this approach:
 * 1. Uses pre-defined HTML templates with placeholders
 * 2. AI generates only the dynamic content (JSON)
 * 3. Template engine merges content with templates
 * 
 * Benefits:
 * - 50-80% fewer output tokens
 * - Faster generation time
 * - Consistent styling
 * - Better caching potential
 */

import { generateObject, type LanguageModel } from "ai";
import { z } from "zod";

// Schema for structured social post content
export const SocialPostContentSchema = z.object({
  headline: z.string().describe("Main headline (max 80 chars)"),
  subheadline: z.string().optional().describe("Secondary headline or tagline"),
  body: z.string().optional().describe("Body text (max 200 chars)"),
  cta: z.string().optional().describe("Call-to-action text"),
  accent: z.string().optional().describe("Accent color class (e.g., 'blue', 'green', 'orange')"),
  layout: z.enum(["centered", "left", "split", "minimal"]).optional().describe("Layout style"),
  mood: z.enum(["professional", "bold", "minimal", "energetic", "elegant"]).optional(),
});

export type SocialPostContent = z.infer<typeof SocialPostContentSchema>;

// Pre-defined templates for different formats and styles
export const SOCIAL_TEMPLATES: Record<string, string> = {
  // Instagram Square - Centered Bold
  "instagram-square-centered": `<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="w-[1080px] h-[1080px] bg-{{surface}} flex items-center justify-center p-16">
  <div class="text-center max-w-4xl">
    <h1 class="text-7xl font-extrabold text-{{text}} leading-tight mb-8">{{headline}}</h1>
    {{#subheadline}}<p class="text-3xl text-{{textMuted}} mb-8">{{subheadline}}</p>{{/subheadline}}
    {{#body}}<p class="text-2xl text-{{textMuted}} leading-relaxed">{{body}}</p>{{/body}}
    {{#cta}}<div class="mt-12"><span class="inline-block bg-{{accent}} text-white px-8 py-4 rounded-full text-2xl font-semibold">{{cta}}</span></div>{{/cta}}
  </div>
</body>
</html>`,

  // Instagram Square - Bold Split
  "instagram-square-split": `<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="w-[1080px] h-[1080px] bg-gradient-to-br from-{{accent}} to-{{accentDark}} flex flex-col justify-between p-16">
  <div class="flex-1 flex items-center">
    <h1 class="text-6xl font-extrabold text-white leading-tight">{{headline}}</h1>
  </div>
  <div class="border-t border-white/20 pt-8">
    {{#subheadline}}<p class="text-2xl text-white/80">{{subheadline}}</p>{{/subheadline}}
    {{#cta}}<p class="text-xl text-white/60 mt-4">{{cta}}</p>{{/cta}}
  </div>
</body>
</html>`,

  // Twitter/X Card
  "twitter-card-centered": `<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="w-[1200px] h-[675px] bg-{{surface}} flex items-center justify-center p-12">
  <div class="text-center max-w-4xl">
    <h1 class="text-5xl font-bold text-{{text}} leading-tight mb-6">{{headline}}</h1>
    {{#subheadline}}<p class="text-2xl text-{{textMuted}}">{{subheadline}}</p>{{/subheadline}}
    {{#cta}}<div class="mt-8"><span class="inline-block bg-{{accent}} text-white px-6 py-3 rounded-lg text-xl font-medium">{{cta}}</span></div>{{/cta}}
  </div>
</body>
</html>`,

  // LinkedIn Post
  "linkedin-centered": `<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="w-[1200px] h-[627px] bg-{{surface}} flex items-center justify-center p-16">
  <div class="text-center max-w-4xl">
    <h1 class="text-5xl font-semibold text-{{text}} leading-snug mb-6">{{headline}}</h1>
    {{#body}}<p class="text-2xl text-{{textMuted}} leading-relaxed">{{body}}</p>{{/body}}
    {{#cta}}<div class="mt-8 text-xl text-{{accent}} font-medium">{{cta}}</div>{{/cta}}
  </div>
</body>
</html>`,

  // Instagram Story
  "instagram-story-centered": `<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="w-[1080px] h-[1920px] bg-gradient-to-b from-{{accent}} to-{{surface}} flex flex-col items-center justify-center p-16 text-center">
  <h1 class="text-6xl font-extrabold text-white leading-tight mb-8">{{headline}}</h1>
  {{#subheadline}}<p class="text-3xl text-white/80 mb-8">{{subheadline}}</p>{{/subheadline}}
  {{#cta}}<div class="mt-8"><span class="inline-block border-2 border-white text-white px-8 py-4 rounded-full text-2xl font-semibold">{{cta}}</span></div>{{/cta}}
</body>
</html>`,
};

// Color mappings for design tokens
const COLOR_MAPPINGS: Record<string, Record<string, string>> = {
  dark: {
    surface: "gray-900",
    text: "white",
    textMuted: "gray-400",
    accent: "blue-500",
    accentDark: "blue-700",
  },
  light: {
    surface: "white",
    text: "gray-900",
    textMuted: "gray-600",
    accent: "blue-600",
    accentDark: "blue-800",
  },
};

const ACCENT_COLORS: Record<string, { light: string; dark: string }> = {
  blue: { light: "blue-600", dark: "blue-800" },
  green: { light: "emerald-600", dark: "emerald-800" },
  orange: { light: "orange-500", dark: "orange-700" },
  purple: { light: "purple-600", dark: "purple-800" },
  red: { light: "red-600", dark: "red-800" },
  cyan: { light: "cyan-500", dark: "cyan-700" },
};

/**
 * Generate structured content using AI, then merge with template.
 * Much faster than generating full HTML.
 */
export async function generateWithTemplate(
  model: LanguageModel,
  args: {
    title: string;
    excerpt: string;
    content: string;
    format: string;
    templateId?: string;
    userPrompt?: string;
    designTokens?: Record<string, unknown>;
  }
): Promise<{ html: string; content: SocialPostContent }> {
  // Generate structured content
  const result = await generateObject({
    model,
    schema: SocialPostContentSchema,
    system: SOCIAL_COPYWRITER_PROMPT,
    prompt: `Create social media content based on this source:

Title: ${args.title}
Excerpt: ${args.excerpt}
Content: ${args.content.slice(0, 1500)}
${args.userPrompt ? `User instructions: ${args.userPrompt}` : ""}

Generate content optimized for ${args.format}. Make it engaging and shareable.`,
    temperature: 0.7,
  });

  const content = result.object;
  
  // Select template
  const templateId = args.templateId || selectTemplate(args.format, content.layout);
  const template = SOCIAL_TEMPLATES[templateId] || SOCIAL_TEMPLATES["instagram-square-centered"];
  
  // Determine color scheme from design tokens
  const colorScheme = determineColorScheme(args.designTokens);
  const accentColor = content.accent || "blue";
  
  // Merge content with template
  const html = renderTemplate(template, {
    ...content,
    ...colorScheme,
    accent: ACCENT_COLORS[accentColor]?.light || ACCENT_COLORS.blue.light,
    accentDark: ACCENT_COLORS[accentColor]?.dark || ACCENT_COLORS.blue.dark,
  });
  
  return { html, content };
}

/**
 * Select appropriate template based on format and layout preference.
 */
function selectTemplate(format: string, layout?: string): string {
  const formatMap: Record<string, string> = {
    "instagram-square": `instagram-square-${layout || "centered"}`,
    "instagram-portrait": `instagram-square-${layout || "centered"}`,
    "instagram-story": `instagram-story-${layout || "centered"}`,
    "twitter-card": `twitter-card-${layout || "centered"}`,
    "linkedin": `linkedin-${layout || "centered"}`,
  };
  
  return formatMap[format] || "instagram-square-centered";
}

/**
 * Determine color scheme from design tokens.
 */
function determineColorScheme(tokens?: Record<string, unknown>): Record<string, string> {
  // Default to dark theme
  let scheme = "dark";
  
  if (tokens?.surfaces) {
    const surfaces = tokens.surfaces as Record<string, string>;
    const baseSurface = surfaces.base || "";
    // Check if surface is light (simple heuristic)
    if (baseSurface.includes("#f") || baseSurface.includes("#e") || baseSurface.includes("#d")) {
      scheme = "light";
    }
  }
  
  return COLOR_MAPPINGS[scheme];
}

/**
 * Simple mustache-like template renderer.
 * Supports: {{var}}, {{#var}}...{{/var}} conditionals
 */
function renderTemplate(template: string, data: Record<string, unknown>): string {
  let result = template;
  
  // Handle conditionals first: {{#var}}content{{/var}}
  result = result.replace(/\{\{#(\w+)\}\}([\s\S]*?)\{\{\/\1\}\}/g, (_match: string, key: string, content: string) => {
    const value = data[key];
    if (value && value !== "") {
      // Render the content if value exists
      return content.replace(/\{\{(\w+)\}\}/g, (_innerMatch: string, innerKey: string) => {
        return String(data[innerKey] || "");
      });
    }
    return "";
  });
  
  // Handle simple variables: {{var}}
  result = result.replace(/\{\{(\w+)\}\}/g, (_match: string, key: string) => {
    return String(data[key] || "");
  });
  
  return result;
}

/**
 * Get all available template IDs.
 */
export function getAvailableTemplates(): string[] {
  return Object.keys(SOCIAL_TEMPLATES);
}
