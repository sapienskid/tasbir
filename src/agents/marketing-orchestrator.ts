import { Agent } from "agents";
import { PIPELINE_CONFIG } from "../generated/template-assets";
import type { TemplateKind } from "../templates";

interface Env {
  AI: Ai;
  LLM_MODEL?: string;
}

interface PromptProfilePayload {
  mastermind: string[];
  strategist: string[];
  templatePlanner: string[];
  copywriter: string[];
  visualDirector: string[];
  renderGuard: string[];
}

interface RenderPolicyPayload {
  allowMarkdown: boolean;
  allowMath: boolean;
  allowDiagrams: boolean;
  allowTextInAiImages: boolean;
  stripHashtagsInVisualSlots: boolean;
}

interface PlatformGoalPayload {
  posts?: number;
  feed?: number;
  carousel?: number;
  story?: number;
}

interface PlatformGoalsPayload {
  instagram?: PlatformGoalPayload;
  facebook?: PlatformGoalPayload;
  linkedin?: PlatformGoalPayload;
  twitter?: PlatformGoalPayload;
}

interface OrchestratorRequestPayload {
  post: {
    title: string;
    excerpt?: string;
    plaintext?: string;
    tags?: string[];
  };
  requestedFormats: TemplateKind[];
  userPrompt?: string;
  promptProfile: PromptProfilePayload;
  renderPolicy: RenderPolicyPayload;
  platformGoals?: PlatformGoalsPayload;
  variantContext?: {
    platform?: TemplateKind;
    variantIndex?: number;
  };
}

interface OrchestratorResponsePayload {
  strategic_brief: string;
  template_planner_notes: string;
  copywriter_notes: string;
  visual_notes: string;
  warnings: string[];
}

const ORCHESTRATOR_RESPONSE_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    strategic_brief: { type: "string" },
    template_planner_notes: { type: "string" },
    copywriter_notes: { type: "string" },
    visual_notes: { type: "string" },
    warnings: {
      type: "array",
      items: { type: "string" }
    }
  },
  required: [
    "strategic_brief",
    "template_planner_notes",
    "copywriter_notes",
    "visual_notes",
    "warnings"
  ]
};

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
    const truncatedSource =
      sourceText.length > PIPELINE_CONFIG.generation.limits.post_text_max_chars
        ? `${sourceText.slice(0, PIPELINE_CONFIG.generation.limits.post_text_max_chars)}...`
        : sourceText;

    const tags = (input.post.tags ?? []).slice(0, 8).join(", ");
    const requestedFormats = input.requestedFormats.join(", ");
    const userPrompt = input.userPrompt?.trim() || "(none)";
    const platformGoals = serializePlatformGoals(input.platformGoals);
    const variantLabel = input.variantContext?.platform
      ? `${input.variantContext.platform}${input.variantContext.variantIndex ? ` #${input.variantContext.variantIndex}` : ""}`
      : "none";

    const policyNotes = [
      `allow_markdown=${input.renderPolicy.allowMarkdown}`,
      `allow_math=${input.renderPolicy.allowMath}`,
      `allow_diagrams=${input.renderPolicy.allowDiagrams}`,
      `allow_text_in_ai_images=${input.renderPolicy.allowTextInAiImages}`,
      `strip_hashtags_in_visual_slots=${input.renderPolicy.stripHashtagsInVisualSlots}`
    ].join(", ");

    const systemPrompt = [
      ...input.promptProfile.mastermind,
      ...input.promptProfile.strategist,
      ...input.promptProfile.templatePlanner,
      ...input.promptProfile.copywriter,
      ...input.promptProfile.visualDirector,
      ...input.promptProfile.renderGuard,
      "Return strict JSON matching the required response schema."
    ]
      .filter(Boolean)
      .join("\n");

    const prompt = [
      "Build one campaign orchestration decision for social content generation.",
      "",
      `Requested output formats: ${requestedFormats || "(none)"}`,
      `Variant context: ${variantLabel}`,
      `Render policy: ${policyNotes}`,
      `Platform goals: ${platformGoals}`,
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
      "- strategic_brief: campaign intent and angle guidance",
      "- template_planner_notes: template-fit and slot-density guidance",
      "- copywriter_notes: platform tone and structure guidance",
      "- visual_notes: image direction and no-text image policy reminders",
      "- warnings: potential quality/compliance risks"
    ].join("\n");

    try {
      const orchestratorModel =
        ((PIPELINE_CONFIG.generation?.agents?.models as Record<string, unknown> | undefined)?.orchestrator_model as
          | string
          | undefined) || "@cf/openai/gpt-oss-120b";
      const model = (this.env.LLM_MODEL || orchestratorModel) as keyof AiModels;
      const raw = await this.env.AI.run(model, {
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: prompt }
        ],
        response_format: {
          type: "json_schema",
          json_schema: ORCHESTRATOR_RESPONSE_SCHEMA
        },
        temperature: 0.2,
        max_tokens: 900
      });
      const parsed = parseModelJson(raw) as Record<string, unknown>;
      return normalizeResponse(parsed, input.renderPolicy);
    } catch {
      return fallbackResponse(input);
    }
  }
}

function fallbackResponse(input: OrchestratorRequestPayload): OrchestratorResponsePayload {
  const formatSummary = input.requestedFormats.join(", ") || "requested formats";
  return {
    strategic_brief: `Create platform-native assets for ${formatSummary} with clear hooks, practical middle content, and concrete CTA endings.`,
    template_planner_notes:
      "Choose templates with slot density proportional to message complexity. Avoid text-heavy layouts for dense source content.",
    copywriter_notes:
      "Use concise platform-native language, complete sentences, and non-repetitive angles. Keep captions informative and conversion-oriented.",
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
    template_planner_notes: toSingleLine(
      raw.template_planner_notes,
      "Choose templates that match slot semantics and readability."
    ),
    copywriter_notes: toSingleLine(raw.copywriter_notes, "Write concise and complete platform-native copy."),
    visual_notes: toSingleLine(raw.visual_notes, "Use clean text-safe editorial backgrounds with no generated text artifacts."),
    warnings: [...new Set(warnings.map((item) => item.trim()).filter(Boolean))].slice(0, 8)
  };
}

function parseModelJson(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object") {
    throw new Error("Model response was not an object");
  }
  const response = (raw as Record<string, unknown>).response;
  if (typeof response !== "string") {
    throw new Error("Model response payload missing string response field");
  }
  const parsed = JSON.parse(response);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Model response JSON was not an object");
  }
  return parsed as Record<string, unknown>;
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
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function toSingleLine(value: unknown, fallback: string): string {
  if (typeof value !== "string") {
    return fallback;
  }
  const compact = value.replace(/\s+/g, " ").trim();
  return compact || fallback;
}

function serializePlatformGoals(goals: PlatformGoalsPayload | undefined): string {
  if (!goals) {
    return "(none)";
  }
  const lines: string[] = [];
  for (const [platform, goal] of Object.entries(goals)) {
    if (!goal || typeof goal !== "object") {
      continue;
    }
    const goalParts = [
      goal.posts !== undefined ? `posts=${goal.posts}` : "",
      goal.feed !== undefined ? `feed=${goal.feed}` : "",
      goal.carousel !== undefined ? `carousel=${goal.carousel}` : "",
      goal.story !== undefined ? `story=${goal.story}` : ""
    ].filter(Boolean);
    if (goalParts.length > 0) {
      lines.push(`${platform}[${goalParts.join(", ")}]`);
    }
  }
  return lines.length > 0 ? lines.join("; ") : "(none)";
}

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8"
    }
  });
}
