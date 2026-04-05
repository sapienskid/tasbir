import { createOpenAI } from "@ai-sdk/openai";
import type { LanguageModel } from "ai";

// ─── Configuration ───────────────────────────────────────────────────────────

export interface ProviderConfig {
  aiBinding: Ai;
  gatewayToken?: string;
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
// Default values hardcoded - no environment variables needed in deployment.
// The gateway token is the only secret needed (via wrangler secret put).

const DEFAULT_AI_GATEWAY_ACCOUNT_ID = "a19f853d1b3f6af9c7f2a8fa1e63bb27";
const DEFAULT_AI_GATEWAY_ID = "tasbir";

// Mixed model configuration via AI Gateway:
// - Workers AI models via AI binding (not gateway HTTP) 
// - External providers via AI Gateway with BYOK
// All using BYOK - only AI_GATEWAY_TOKEN needed
export const DYNAMIC_ROUTES = {
  DESIGN_TOKENS: "google-ai-studio/gemini-2.5-flash",
  HTML_LAYOUT: "google-ai-studio/gemini-2.5-flash",
  GENERIC: "google-ai-studio/gemini-2.5-flash",
} as const;

// Workers AI models used directly via AI binding
export const WORKERS_AI_MODELS = {
  TEXT: "@cf/google/gemma-4-26b-a4b-it",
  IMAGE: "@cf/black-forest-labs/flux-2-klein-9b",
} as const;

function buildGatewayBaseUrl(): string {
  return `https://gateway.ai.cloudflare.com/v1/${DEFAULT_AI_GATEWAY_ACCOUNT_ID}/${DEFAULT_AI_GATEWAY_ID}`;
}

// ─── Model Creation ──────────────────────────────────────────────────────────

/**
 * Creates a language model using AI Gateway with dynamic routing.
 * 
 * Uses the /compat (OpenAI-compatible) endpoint with dynamic routes.
 * The AI Gateway is configured with:
 * - BYOK (Bring Your Own Keys) for provider API keys (stored in dashboard)
 * - Dynamic routes for model selection and fallbacks
 * - Gateway authentication via cf-aig-authorization header
 * 
 * No environment variables needed in the code - only:
 * - AI_GATEWAY_TOKEN as a wrangler secret (for gateway auth)
 * - Provider API keys stored in AI Gateway dashboard (BYOK)
 */
function createGatewayModel(gatewayToken: string | undefined, googleApiKey: string | undefined, route: string): LanguageModel {
  if (!gatewayToken && !googleApiKey) {
    throw new Error(
      "Either AI_GATEWAY_TOKEN (for BYOK) or GOOGLE_API_KEY is required"
    );
  }

  // Use /compat endpoint (OpenAI-compatible) with google-ai-studio/{model} format
  const baseURL = `${buildGatewayBaseUrl()}/compat`;
  console.log(`[ai-gateway] Creating model with baseURL: ${baseURL}, route: ${route}`);
  console.log(`[ai-gateway] Using direct API key: ${googleApiKey ? 'yes' : 'no'}, Using gateway token: ${gatewayToken ? 'yes' : 'no'}`);

  // Use direct API key OR BYOK (gateway token only)
  const apiKey = googleApiKey || "not-used-with-byok";
  
  const openai = createOpenAI({
    apiKey,
    baseURL,
    headers: gatewayToken ? {
      "cf-aig-authorization": `Bearer ${gatewayToken}`,
    } : {},
    // Add fetch wrapper for better error logging
    fetch: async (url, init) => {
      console.log(`[ai-gateway] Request to: ${url}`);
      console.log(`[ai-gateway] Request method: ${init?.method || 'GET'}`);
      
      try {
        const response = await fetch(url, init);
        console.log(`[ai-gateway] Response status: ${response.status} ${response.statusText}`);
        
        if (!response.ok) {
          // Clone response to read body without consuming it
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

  // Use .chat() for google-ai-studio endpoint with Gemini/Gemma API
  return openai.chat(route);
}

/**
 * Creates a model chain for design token generation.
 * Uses the "dynamic/design-tokens" route configured in AI Gateway.
 */
export function createModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGatewayModel(config.gatewayToken, config.googleApiKey, DYNAMIC_ROUTES.DESIGN_TOKENS)];
}

export function createFastModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGatewayModel(config.gatewayToken, config.googleApiKey, DYNAMIC_ROUTES.GENERIC)];
}

export function createHtmlLayoutModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGatewayModel(config.gatewayToken, config.googleApiKey, DYNAMIC_ROUTES.HTML_LAYOUT)];
}

// ─── Env Resolution ──────────────────────────────────────────────────────────

/**
 * Resolves provider configuration from the environment.
 */
export function resolveProviderConfig(aiBinding: Ai, gatewayToken?: string, googleApiKey?: string): ProviderConfig {
  if (!aiBinding) {
    throw new Error(
      "AI binding is required. Ensure 'ai' is configured in wrangler.jsonc."
    );
  }
  
  return {
    aiBinding,
    gatewayToken,
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
