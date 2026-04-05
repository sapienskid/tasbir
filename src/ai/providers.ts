import { createOpenAI } from "@ai-sdk/openai";
import type { LanguageModel } from "ai";

// ─── Configuration ───────────────────────────────────────────────────────────

export interface ProviderConfig {
  aiBinding: Ai;
  googleApiKey?: string;
}

export interface ModelSettings {
  temperature: number;
  maxTokens?: number;
}

export const MODEL_SETTINGS = {
  designTokens: { temperature: 0.9 },
  htmlLayout: { temperature: 0.7 },
  orchestrator: { temperature: 0.7, maxTokens: 900 },
  classification: { temperature: 0.2 },
  generic: { temperature: 0.7 },
} as const;

// ─── AI Gateway Configuration ────────────────────────────────────────────────

const DEFAULT_AI_GATEWAY_ACCOUNT_ID = "a19f853d1b3f6af9c7f2a8fa1e63bb27";
const DEFAULT_AI_GATEWAY_ID = "tasbir";

// Configuration:
// - gemini-2.5-flash via AI Gateway (works with BYOK)
// - gemma-4 via direct Google API (separate, requires GOOGLE_API_KEY)
// - Workers AI for images (via AI binding)
export const DYNAMIC_ROUTES = {
  DESIGN_TOKENS: "google-ai-studio/gemini-2.5-flash",
  HTML_LAYOUT: "google-ai-studio/gemini-2.5-flash",
  GENERIC: "google-ai-studio/gemini-2.5-flash",
  ADVANCED: "gemma-4-31b-it", // via direct API
} as const;

// Workers AI models (used via AI binding)
export const WORKERS_AI_MODELS = {
  TEXT: "@cf/google/gemma-4-26b-a4b-it",
  IMAGE: "@cf/black-forest-labs/flux-2-klein-9b",
} as const;

function buildGatewayBaseUrl(): string {
  return `https://gateway.ai.cloudflare.com/v1/${DEFAULT_AI_GATEWAY_ACCOUNT_ID}/${DEFAULT_AI_GATEWAY_ID}`;
}

// ─── Model Creation: AI Gateway (gemini-2.5-flash with BYOK) ────────────────

function createGatewayModel(googleApiKey: string | undefined, route: string): LanguageModel {
  if (!googleApiKey) {
    throw new Error("GOOGLE_API_KEY is required for text generation");
  }

  const baseURL = `${buildGatewayBaseUrl()}/compat`;
  console.log(`[ai-gateway] Creating model with baseURL: ${baseURL}, route: ${route}`);

  const apiKey = googleApiKey;
  
  const openai = createOpenAI({
    apiKey,
    baseURL,
    fetch: async (url, init) => {
      console.log(`[ai-gateway] Request to: ${url}`);
      console.log(`[ai-gateway] Request method: ${init?.method || 'GET'}`);
      
      try {
        const response = await fetch(url, init);
        console.log(`[ai-gateway] Response status: ${response.status} ${response.statusText}`);
        
        if (!response.ok) {
          const clonedResponse = response.clone();
          try {
            const errorBody = await clonedResponse.text();
            console.error(`[ai-gateway] Error response body: ${errorBody.slice(0, 500)}`);
          } catch (e) {
            console.error(`[ai-gateway] Could not read error body`);
          }
        }
        
        return response;
      } catch (error) {
        console.error(`[ai-gateway] Fetch error:`, error);
        throw error;
      }
    },
  });

  return openai.chat(route);
}

// ─── Model Creation: Direct Google API (gemma-4) ───────────────────────────

function createDirectGoogleModel(googleApiKey: string | undefined, model: string = "gemma-4-31b-it"): LanguageModel {
  if (!googleApiKey) {
    throw new Error(
      "GOOGLE_API_KEY is required for direct Google API. Set via 'wrangler secret put GOOGLE_API_KEY'"
    );
  }

  console.log(`[google-direct] Creating model: ${model} with direct API`);

  const baseURL = "https://generativelanguage.googleapis.com/v1";
  
  const openai = createOpenAI({
    apiKey: googleApiKey,
    baseURL,
    fetch: async (url, init) => {
      const urlStr = url.toString();
      const modifiedUrl = urlStr.replace("/chat/completions", "");
      console.log(`[google-direct] Request to: ${modifiedUrl}`);
      
      try {
        const response = await fetch(modifiedUrl, init);
        console.log(`[google-direct] Response status: ${response.status} ${response.statusText}`);
        return response;
      } catch (error) {
        console.error(`[google-direct] Fetch error:`, error);
        throw error;
      }
    },
  });

  return openai.chat(model);
}

// ─── Model Chain Functions ───────────────────────────────────────────────────

export function createModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGatewayModel(config.googleApiKey, DYNAMIC_ROUTES.DESIGN_TOKENS)];
}

export function createFastModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGatewayModel(config.googleApiKey, DYNAMIC_ROUTES.GENERIC)];
}

export function createHtmlLayoutModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGatewayModel(config.googleApiKey, DYNAMIC_ROUTES.HTML_LAYOUT)];
}

export function createAdvancedModelChain(config: ProviderConfig): LanguageModel[] {
  return [createDirectGoogleModel(config.googleApiKey, DYNAMIC_ROUTES.ADVANCED)];
}

// ─── Workers AI Helpers ───────────────────────────────────────────────────────

export function getWorkersAiImageModel(aiBinding: Ai): Ai {
  return aiBinding;
}

// ─── Env Resolution ──────────────────────────────────────────────────────────

export function resolveProviderConfig(aiBinding: Ai, googleApiKey?: string): ProviderConfig {
  if (!aiBinding) {
    throw new Error(
      "AI binding is required. Ensure 'ai' is configured in wrangler.jsonc."
    );
  }
  
  return {
    aiBinding,
    googleApiKey,
  };
}

// ─── Error Handling ──────────────────────────────────────────────────────────

export function isRateLimitError(error: unknown): boolean {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return (
      msg.includes("429") ||
      msg.includes("too many requests") ||
      msg.includes("quota exceeded") ||
      msg.includes("rate limit") ||
      msg.includes("insufficient_quota")
    );
  }
  return false;
}

export function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return (
      isRateLimitError(error) ||
      msg.includes("500") ||
      msg.includes("502") ||
      msg.includes("503") ||
      msg.includes("504") ||
      msg.includes("timeout") ||
      msg.includes("network")
    );
  }
  return false;
}

export async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
