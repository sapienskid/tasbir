import { generateText } from "ai";
import { createModelChain, resolveProviderConfig } from "../ai/providers";
import type { TemplateMetadata } from "./templates";

export interface ContentClassification {
  type: "quote" | "insight" | "metric" | "list" | "story" | "tutorial" | "announcement" | "other";
  templateMatch: string | null;
  reasoning: string;
  slotValues: Record<string, string>;
}

const CLASSIFICATION_PROMPT = (content: string, title: string, availableTemplates: TemplateMetadata[]) => {
  const templateList = availableTemplates.length > 0
    ? availableTemplates.map((t) => `- ${t.id}: ${t.description || "custom template"} (slots: ${t.slots.join(", ")})`).join("\n")
    : "No templates available";

  return `Analyze this content and determine the best rendering approach.

Title: ${title}
Content: ${content.slice(0, 2000)}

Available templates:
${templateList}

Determine:
1. Content type: quote | insight | metric | list | story | tutorial | announcement | other
2. Best template match (template ID or null if none match well)
3. Brief reasoning for the choice
4. Extract or generate values for template slots if a template is matched

Rules:
- Use templates only when content strongly matches the template's purpose
- For stories, tutorials, or complex narratives, prefer free-form (null template)
- For quotes, metrics, or simple insights, prefer templates when available
- If multiple templates could work, choose the most specific match
- Slot values should be creative and engaging, not just raw content extraction

Return JSON:
{
  "type": "<content-type>",
  "templateMatch": "<template-id-or-null>",
  "reasoning": "<brief explanation>",
  "slotValues": { "slotName": "value" }
}`;
};

export async function classifyContent(
  env: Record<string, string | undefined>,
  title: string,
  content: string,
  availableTemplates: TemplateMetadata[],
  aiBinding?: Ai,
): Promise<ContentClassification> {
  const providerConfig = resolveProviderConfig(env, aiBinding);
  const models = createModelChain(providerConfig);
  const model = models[0];

  try {
    const response = await generateText({
      model,
      prompt: CLASSIFICATION_PROMPT(content, title, availableTemplates),
      temperature: 0.2,
    });
    const text = response.text.trim();
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return fallbackClassification(title, content, availableTemplates);
    }

    const parsed = JSON.parse(jsonMatch[0]) as Partial<ContentClassification>;
    return {
      type: isValidContentType(parsed.type) ? parsed.type : "other",
      templateMatch: typeof parsed.templateMatch === "string" && parsed.templateMatch !== "null" ? parsed.templateMatch : null,
      reasoning: typeof parsed.reasoning === "string" ? parsed.reasoning : "No reasoning provided",
      slotValues: parsed.slotValues && typeof parsed.slotValues === "object" && !Array.isArray(parsed.slotValues) ? parsed.slotValues as Record<string, string> : {},
    };
  } catch {
    return fallbackClassification(title, content, availableTemplates);
  }
}

function fallbackClassification(title: string, _content: string, availableTemplates: TemplateMetadata[]): ContentClassification {
  const lowerTitle = title.toLowerCase();
  if (lowerTitle.includes("how to") || lowerTitle.includes("guide") || lowerTitle.includes("tutorial")) {
    return { type: "tutorial", templateMatch: null, reasoning: "Title suggests tutorial content", slotValues: {} };
  }
  if (lowerTitle.includes("list") || lowerTitle.includes("ways") || lowerTitle.includes("tips")) {
    return { type: "list", templateMatch: null, reasoning: "Title suggests list content", slotValues: {} };
  }
  if (title.length < 80 && _content.length < 200) {
    const quoteTemplate = availableTemplates.find((t) => t.category === "quote" && t.enabled);
    return {
      type: "quote",
      templateMatch: quoteTemplate?.id || null,
      reasoning: "Short content suggests quote or insight",
      slotValues: { quote: title, author: "" },
    };
  }
  return { type: "other", templateMatch: null, reasoning: "Fallback: no clear pattern detected", slotValues: {} };
}

function isValidContentType(type: unknown): type is ContentClassification["type"] {
  return typeof type === "string" && ["quote", "insight", "metric", "list", "story", "tutorial", "announcement", "other"].includes(type);
}
