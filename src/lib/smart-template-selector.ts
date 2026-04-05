/**
 * Smart Template Selection System
 * 
 * AI decides whether to:
 * 1. Use an existing saved HTML template (fast - skip AI generation)
 * 2. Generate new HTML from scratch (slower but creative)
 * 
 * Decision factors:
 * - Content type (quote, metric, story, etc.)
 * - Available templates that match the content
 * - User preferences (always generate, prefer templates, etc.)
 * - Content complexity
 * 
 * Generated HTML can be saved as templates for future reuse.
 */

import { generateObject } from "ai";
import { z } from "zod";
import { createFastModelChain, resolveProviderConfig, type ProviderConfig } from "../ai/providers";
import { createPromptConfig } from "./prompt-utils.js";
import type { WorkspaceSettings } from "./settings.js";

export interface SavedHtmlTemplate {
  id: string;
  name: string;
  description: string;
  html: string;
  contentTypes: string[];  // What content types this template is good for
  format: string;          // instagram-square, twitter-card, etc.
  tags: string[];
  createdAt: number;
  usageCount: number;
  lastUsedAt?: number;
  quality?: number;        // User rating 1-5
}

export interface TemplateDecision {
  action: "use_template" | "generate_new";
  templateId?: string;
  reasoning: string;
  confidence: number;
  suggestedSaveAsTemplate?: boolean;  // If generating, should we save result?
}

const TemplateDecisionSchema = z.object({
  action: z.enum(["use_template", "generate_new"]),
  templateId: z.string().nullable().describe("Template ID to use if action is use_template"),
  reasoning: z.string().describe("Brief explanation of the decision"),
  confidence: z.number().min(0).max(1).describe("Confidence in this decision 0-1"),
  suggestSaveAsTemplate: z.boolean().describe("If generating new, should we save this as a template?"),
});

/**
 * AI-powered decision: use existing template or generate new HTML?
 */
export async function decideTemplateOrGenerate(
  providerConfig: ProviderConfig,
  content: {
    title: string;
    excerpt: string;
    body: string;
    contentType?: string;
  },
  format: string,
  availableTemplates: SavedHtmlTemplate[],
  preferences?: {
    preferTemplates?: boolean;      // Bias towards using templates
    alwaysGenerate?: boolean;       // Force generation
    qualityThreshold?: number;      // Min template quality to consider
  },
  settings?: WorkspaceSettings | null
): Promise<TemplateDecision> {
  // Fast path: if user wants to always generate, skip AI decision
  if (preferences?.alwaysGenerate) {
    return {
      action: "generate_new",
      reasoning: "User preference: always generate fresh HTML",
      confidence: 1.0,
      suggestedSaveAsTemplate: true,
    };
  }

  // Fast path: if no templates available, must generate
  const formatTemplates = availableTemplates.filter(t => t.format === format);
  if (formatTemplates.length === 0) {
    return {
      action: "generate_new",
      reasoning: "No saved templates available for this format",
      confidence: 1.0,
      suggestedSaveAsTemplate: true,
    };
  }

  // Filter by quality threshold
  const qualityThreshold = preferences?.qualityThreshold ?? 3;
  const qualifiedTemplates = formatTemplates.filter(t => (t.quality ?? 3) >= qualityThreshold);

  if (qualifiedTemplates.length === 0) {
    return {
      action: "generate_new",
      reasoning: "No templates meet quality threshold",
      confidence: 0.9,
      suggestedSaveAsTemplate: true,
    };
  }

  // Use AI to decide
  const models = createFastModelChain(providerConfig);
  const model = models[0];

  try {
    const templateSummaries = qualifiedTemplates.map(t => ({
      id: t.id,
      name: t.name,
      description: t.description,
      contentTypes: t.contentTypes,
      tags: t.tags,
      usageCount: t.usageCount,
      quality: t.quality,
    }));

    // Create enhanced prompt configuration
    const promptConfig = createPromptConfig(
      `You are a smart template selector for social media content generation.
Your job is to decide whether to use an existing HTML template or generate new HTML.

Decision criteria:
- Use templates when content closely matches a template's purpose and style
- Generate new when content is unique, complex, or needs custom layout
- Consider template quality ratings and usage counts
- Prefer templates for common content types (quotes, metrics, simple insights)
- Generate new for stories, tutorials, complex narratives, or unique requests`,
      settings,
      'templateSelection'
    );

    const result = await generateObject({
      model,
      schema: TemplateDecisionSchema,
      system: promptConfig.system,

      prompt: `Decide: use existing template or generate new HTML?

CONTENT TO RENDER:
Title: ${content.title}
Type: ${content.contentType || "unknown"}
Excerpt: ${content.excerpt}
Body: ${content.body.slice(0, 500)}...

FORMAT: ${format}

AVAILABLE TEMPLATES:
${JSON.stringify(templateSummaries, null, 2)}

USER PREFERENCE: ${preferences?.preferTemplates ? "Prefers templates when possible" : "No strong preference"}

Decide the best approach. If using a template, specify which one.`,
      temperature: 0.2,
    });

    return {
      action: result.object.action,
      templateId: result.object.templateId ?? undefined,
      reasoning: result.object.reasoning,
      confidence: result.object.confidence,
      suggestedSaveAsTemplate: result.object.suggestSaveAsTemplate,
    };
  } catch (error) {
    console.warn("[smart-selector] AI decision failed, defaulting to generate:", error);
    return {
      action: "generate_new",
      reasoning: "AI decision failed, falling back to generation",
      confidence: 0.5,
      suggestedSaveAsTemplate: true,
    };
  }
}

/**
 * Get a saved template by ID.
 */
export async function getSavedTemplate(
  kv: KVNamespace,
  templateId: string
): Promise<SavedHtmlTemplate | null> {
  try {
    const key = `html-template:${templateId}`;
    const data = await kv.get(key, "json");
    return data as SavedHtmlTemplate | null;
  } catch {
    return null;
  }
}

/**
 * Save generated HTML as a reusable template.
 */
export async function saveHtmlAsTemplate(
  kv: KVNamespace,
  template: Omit<SavedHtmlTemplate, "id" | "createdAt" | "usageCount">
): Promise<SavedHtmlTemplate> {
  const id = `tpl_${Date.now()}_${crypto.randomUUID().slice(0, 8)}`;
  const fullTemplate: SavedHtmlTemplate = {
    ...template,
    id,
    createdAt: Date.now(),
    usageCount: 0,
  };

  const key = `html-template:${id}`;
  await kv.put(key, JSON.stringify(fullTemplate));

  // Update template index
  await updateTemplateIndex(kv, fullTemplate);

  return fullTemplate;
}

/**
 * Record template usage (for popularity tracking).
 */
export async function recordTemplateUsage(
  kv: KVNamespace,
  templateId: string
): Promise<void> {
  try {
    const template = await getSavedTemplate(kv, templateId);
    if (template) {
      template.usageCount += 1;
      template.lastUsedAt = Date.now();
      const key = `html-template:${templateId}`;
      await kv.put(key, JSON.stringify(template));
    }
  } catch {
    // Ignore usage tracking errors
  }
}

/**
 * List all saved templates, optionally filtered by format.
 */
export async function listSavedTemplates(
  kv: KVNamespace,
  format?: string
): Promise<SavedHtmlTemplate[]> {
  try {
    const indexKey = "html-template-index";
    const index = await kv.get(indexKey, "json") as SavedHtmlTemplate[] | null;
    
    if (!index) return [];
    
    if (format) {
      return index.filter(t => t.format === format);
    }
    
    return index;
  } catch {
    return [];
  }
}

/**
 * Update the template index (for fast listing).
 */
async function updateTemplateIndex(
  kv: KVNamespace,
  template: SavedHtmlTemplate
): Promise<void> {
  try {
    const indexKey = "html-template-index";
    const index = (await kv.get(indexKey, "json") as SavedHtmlTemplate[] | null) || [];
    
    // Remove existing entry if updating
    const filtered = index.filter(t => t.id !== template.id);
    
    // Add new entry (without full HTML to keep index small)
    const indexEntry: SavedHtmlTemplate = {
      ...template,
      html: "", // Don't store full HTML in index
    };
    filtered.push(indexEntry);
    
    // Sort by usage count (most used first)
    filtered.sort((a, b) => b.usageCount - a.usageCount);
    
    await kv.put(indexKey, JSON.stringify(filtered));
  } catch {
    // Ignore index update errors
  }
}

/**
 * Delete a saved template.
 */
export async function deleteSavedTemplate(
  kv: KVNamespace,
  templateId: string
): Promise<boolean> {
  try {
    const key = `html-template:${templateId}`;
    await kv.delete(key);
    
    // Update index
    const indexKey = "html-template-index";
    const index = (await kv.get(indexKey, "json") as SavedHtmlTemplate[] | null) || [];
    const filtered = index.filter(t => t.id !== templateId);
    await kv.put(indexKey, JSON.stringify(filtered));
    
    return true;
  } catch {
    return false;
  }
}

/**
 * Rate a template (affects future selection).
 */
export async function rateTemplate(
  kv: KVNamespace,
  templateId: string,
  quality: number
): Promise<void> {
  const template = await getSavedTemplate(kv, templateId);
  if (template) {
    template.quality = Math.max(1, Math.min(5, quality));
    const key = `html-template:${templateId}`;
    await kv.put(key, JSON.stringify(template));
    await updateTemplateIndex(kv, template);
  }
}
