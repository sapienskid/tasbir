import { Agent } from "agents";
import { generateObject } from "ai";
import { z } from "zod";
import { createModelChain, resolveProviderConfig } from "../ai/providers";

interface Env {
  AI: Ai;
  GOOGLE_API_KEY?: string;
  GOOGLE_MODEL?: string;
  CLOUDFLARE_API_TOKEN?: string;
  CLOUDFLARE_ACCOUNT_ID?: string;
  LLM_MODEL?: string;
}

interface PromptProfilePayload {
  mastermind: string[];
  strategist: string[];
  copywriter: string[];
  visualDirector: string[];
  renderGuard: string[];
}

interface RenderPolicyPayload {
  allowMarkdown: boolean;
  allowMath: boolean;
  allowDiagrams: boolean;
  allowTextInAiImages: boolean;
}

interface OrchestratorRequestPayload {
  post: {
    title: string;
    excerpt?: string;
    plaintext?: string;
    tags?: string[];
  };
  requestedFormats: string[];
  userPrompt?: string;
  promptProfile: PromptProfilePayload;
  renderPolicy: RenderPolicyPayload;
}

interface OrchestratorResponsePayload {
  strategic_brief: string;
  copywriter_notes: string;
  visual_notes: string;
  warnings: string[];
}

const ORCHESTRATOR_SCHEMA = z.object({
  strategic_brief: z.string(),
  copywriter_notes: z.string(),
  visual_notes: z.string(),
  warnings: z.array(z.string())
});

export class MarketingOrchestratorAgent extends Agent<Env> {
  async onRequest(request: Request): Promise<Response> {
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/orchestrate") {
      return json({ error: "Not found" }, 404);
    }

    const payload = await parseRequestPayload(request);
    if (!payload) {
      return json({ error: "Invalid JSON payload" }, 400);
    }

    const result = await this.plan(payload);
    return json(result);
  }

  private async plan(input: OrchestratorRequestPayload): Promise<OrchestratorResponsePayload> {
    const sourceBody = (input.post.plaintext ?? "").trim();
    const sourceExcerpt = (input.post.excerpt ?? "").trim();
    const sourceText = sourceBody || sourceExcerpt;
    const truncatedSource = sourceText.length > 14000 ? `${sourceText.slice(0, 14000)}...` : sourceText;

    const tags = (input.post.tags ?? []).slice(0, 8).join(", ");
    const requestedFormats = input.requestedFormats.join(", ");
    const userPrompt = input.userPrompt?.trim() || "(none)";

    const policyNotes = [
      `allow_markdown=${input.renderPolicy.allowMarkdown}`,
      `allow_math=${input.renderPolicy.allowMath}`,
      `allow_diagrams=${input.renderPolicy.allowDiagrams}`,
      `allow_text_in_ai_images=${input.renderPolicy.allowTextInAiImages}`
    ].join(", ");

    const systemPrompt = [
      ...input.promptProfile.mastermind,
      ...input.promptProfile.strategist,
      ...input.promptProfile.copywriter,
      ...input.promptProfile.visualDirector,
      ...input.promptProfile.renderGuard,
      "Return strict JSON matching the required response schema."
    ].filter(Boolean).join("\n");

    const prompt = [
      "Build one creative campaign orchestration decision for social content generation.",
      "",
      `Requested output formats: ${requestedFormats || "(none)"}`,
      `Render policy: ${policyNotes}`,
      `User prompt: ${userPrompt}`,
      "",
      "Source content:",
      `<title>${input.post.title.trim()}</title>`,
      `<excerpt>${sourceExcerpt || "(none)"}</excerpt>`,
      `<tags>${tags || "(none)"}</tags>`,
      "<body>",
      truncatedSource || "(none)",
      "</body>",
      "",
      "Produce concise notes for:",
      "- strategic_brief: campaign intent, creative angle, and hook strategy",
      "- copywriter_notes: platform tone, structure, and copy direction",
      "- visual_notes: image direction and composition guidance",
      "- warnings: potential quality/compliance risks"
    ].join("\n");

    try {
      const providerConfig = resolveProviderConfig(
        {
          GOOGLE_API_KEY: this.env.GOOGLE_API_KEY,
          GOOGLE_MODEL: this.env.GOOGLE_MODEL,
          CLOUDFLARE_API_TOKEN: this.env.CLOUDFLARE_API_TOKEN,
          CLOUDFLARE_ACCOUNT_ID: this.env.CLOUDFLARE_ACCOUNT_ID,
          LLM_MODEL: this.env.LLM_MODEL,
        },
        this.env.AI,
      );
      const models = createModelChain(providerConfig);

      const result = await generateObject({
        model: models[0],
        system: systemPrompt,
        prompt,
        schema: ORCHESTRATOR_SCHEMA,
        temperature: 0.7,
        maxOutputTokens: 900,
      });
      return normalizeResponse(result.object, input.renderPolicy);
    } catch {
      return fallbackResponse(input);
    }
  }
}

function fallbackResponse(input: OrchestratorRequestPayload): OrchestratorResponsePayload {
  const formatSummary = input.requestedFormats.join(", ") || "requested formats";
  return {
    strategic_brief: `Create platform-native assets for ${formatSummary} with clear hooks, practical middle content, and concrete CTA endings.`,
    copywriter_notes: "Write concise platform-native copy, complete sentences, and non-repetitive angles. Keep captions informative and conversion-oriented.",
    visual_notes: input.renderPolicy.allowTextInAiImages
      ? "Use clean editorial visuals aligned to the message."
      : "Use clean editorial visuals with intentional negative space. Never include text artifacts in generated images.",
    warnings: ["orchestrator_fallback_used"]
  };
}

function normalizeResponse(
  raw: Record<string, unknown>,
  policy: RenderPolicyPayload
): OrchestratorResponsePayload {
  const warnings = toStringArray(raw.warnings);
  if (!policy.allowTextInAiImages) {
    warnings.push("no_text_in_ai_images_enforced");
  }

  return {
    strategic_brief: toSingleLine(raw.strategic_brief, "Focus on platform-native strategy."),
    copywriter_notes: toSingleLine(raw.copywriter_notes, "Write concise and complete platform-native copy."),
    visual_notes: toSingleLine(raw.visual_notes, "Use clean text-safe editorial backgrounds with no generated text artifacts."),
    warnings: [...new Set(warnings.map((item) => item.trim()).filter(Boolean))].slice(0, 8)
  };
}

async function parseRequestPayload(request: Request): Promise<OrchestratorRequestPayload | null> {
  try {
    const data = await request.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      return null;
    }
    return data as OrchestratorRequestPayload;
  } catch {
    return null;
  }
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => (typeof item === "string" ? item.trim() : "")).filter(Boolean);
}

function toSingleLine(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  const compact = value.replace(/\s+/g, " ").trim();
  return compact || fallback;
}

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" }
  });
}
