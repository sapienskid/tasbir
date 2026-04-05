import { createOpenAI } from "@ai-sdk/openai";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import type { LanguageModel } from "ai";

export interface ProviderConfig {
  googleApiKey?: string;
  googleModel?: string;
  googleFastModel?: string;
  cfApiToken?: string;
  cfAccountId?: string;
  cfModel?: string;
  cfFastModel?: string;
}

export function createModelChain(config: ProviderConfig): LanguageModel[] {
  const models: LanguageModel[] = [];

  if (config.googleApiKey) {
    const google = createGoogleGenerativeAI({ apiKey: config.googleApiKey });
    models.push(google(config.googleModel || "gemini-2.5-flash"));
  }

  if (config.cfApiToken && config.cfAccountId) {
    const cf = createOpenAI({
      apiKey: config.cfApiToken,
      baseURL: `https://api.cloudflare.com/client/v4/accounts/${config.cfAccountId}/ai/v1`,
    });
    models.push(cf(config.cfModel || "@cf/openai/gpt-oss-120b"));
  }

  if (models.length === 0) {
    throw new Error("No AI provider configured. Set GOOGLE_API_KEY or CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID.");
  }

  return models;
}

export function createFastModelChain(config: ProviderConfig): LanguageModel[] {
  const models: LanguageModel[] = [];

  if (config.googleApiKey) {
    const google = createGoogleGenerativeAI({ apiKey: config.googleApiKey });
    models.push(google(config.googleFastModel || config.googleModel || "gemini-2.5-flash"));
  }

  if (config.cfApiToken && config.cfAccountId) {
    const cf = createOpenAI({
      apiKey: config.cfApiToken,
      baseURL: `https://api.cloudflare.com/client/v4/accounts/${config.cfAccountId}/ai/v1`,
    });
    models.push(cf(config.cfFastModel || config.cfModel || "@cf/openai/gpt-oss-120b"));
  }

  if (models.length === 0) {
    throw new Error("No AI provider configured. Set GOOGLE_API_KEY or CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID.");
  }

  return models;
}

export function resolveProviderConfig(env: Record<string, string | undefined>): ProviderConfig {
  return {
    googleApiKey: env.GOOGLE_API_KEY,
    googleModel: env.GOOGLE_MODEL,
    googleFastModel: env.GOOGLE_FAST_MODEL,
    cfApiToken: env.CLOUDFLARE_API_TOKEN,
    cfAccountId: env.CLOUDFLARE_ACCOUNT_ID,
    cfModel: env.LLM_MODEL,
    cfFastModel: env.LLM_FAST_MODEL,
  };
}

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
