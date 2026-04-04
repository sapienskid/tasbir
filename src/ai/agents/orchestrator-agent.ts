import { generateObject, type LanguageModel } from "ai";
import { z } from "zod";

const ORCHESTRATOR_SCHEMA = z.object({
  strategic_brief: z.string(),
  copywriter_notes: z.string(),
  visual_notes: z.string(),
  warnings: z.array(z.string()),
});

export type OrchestratorOutput = z.infer<typeof ORCHESTRATOR_SCHEMA>;

export async function generateOrchestration(
  models: LanguageModel[],
  args: {
    title: string;
    excerpt: string;
    content: string;
    tags: string[];
    formats: string[];
    userPrompt?: string;
    systemPrompt: string;
  },
): Promise<OrchestratorOutput> {
  const errors: Error[] = [];

  for (const model of models) {
    try {
      const result = await generateObject({
        model,
        system: args.systemPrompt,
        prompt: `Build one campaign orchestration decision for social content generation.

Requested output formats: ${args.formats.join(", ") || "(none)"}
Tags: ${args.tags.join(", ") || "(none)"}
User prompt: ${args.userPrompt || "(none)"}

Source content:
<title>${args.title}</title>
<excerpt>${args.excerpt || "(none)"}</excerpt>
<body>${args.content || "(none)"}</body>

Produce concise notes for:
- strategic_brief: campaign intent and angle guidance
- copywriter_notes: platform tone and structure guidance
- visual_notes: image direction and no-text image policy reminders
- warnings: potential quality/compliance risks`,
        schema: ORCHESTRATOR_SCHEMA,
        temperature: 0.2,
        maxOutputTokens: 900,
      });
      return result.object;
    } catch (error) {
      errors.push(error instanceof Error ? error : new Error(String(error)));
      if (!isRetryableError(error)) throw error;
    }
  }

  return {
    strategic_brief: `Create platform-native assets for ${args.formats.join(", ")} with clear hooks, practical middle content, and concrete CTA endings.`,
    copywriter_notes: "Write concise platform-native copy, complete sentences, and non-repetitive angles.",
    visual_notes: "Use clean editorial visuals aligned to the message.",
    warnings: ["orchestrator_fallback_used"],
  };
}

function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return msg.includes("429") || msg.includes("too many requests") || msg.includes("quota exceeded") || msg.includes("rate limit") || msg.includes("500") || msg.includes("503");
  }
  return false;
}
