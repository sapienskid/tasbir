import { createOpenAI } from "@ai-sdk/openai";
import type { LanguageModel } from "ai";

export interface ProviderConfig {
  cloudflareApiToken?: string;
  cloudflareAccountId?: string;
  cloudflareModel?: string;
  cloudflareFastModel?: string;
}

export function createModelChain(config: ProviderConfig): LanguageModel[] {
  const models: LanguageModel[] = [];

  if (config.cloudflareApiToken && config.cloudflareAccountId) {
    const cloudflare = createOpenAI({
      apiKey: config.cloudflareApiToken,
      baseURL: `https://api.cloudflare.com/client/v4/accounts/${config.cloudflareAccountId}/ai/v1`,
    });
    models.push(cloudflare(config.cloudflareModel || "@cf/openai/gpt-oss-120b"));
  }

  if (models.length === 0) {
    throw new Error("No AI provider configured. Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID.");
  }

  return models;
}

export function createFastModelChain(config: ProviderConfig): LanguageModel[] {
  const models: LanguageModel[] = [];

  if (config.cloudflareApiToken && config.cloudflareAccountId) {
    const cloudflare = createOpenAI({
      apiKey: config.cloudflareApiToken,
      baseURL: `https://api.cloudflare.com/client/v4/accounts/${config.cloudflareAccountId}/ai/v1`,
    });
    models.push(cloudflare(config.cloudflareFastModel || "@cf/meta/llama-3.1-8b-instruct-fp8-fast"));
  }

  if (models.length === 0) {
    throw new Error("No AI provider configured. Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID.");
  }

  return models;
}

export function resolveProviderConfig(env: Record<string, string | undefined>): ProviderConfig {
  return {
    cloudflareApiToken: env.CLOUDFLARE_API_TOKEN || env.CF_API_TOKEN,
    cloudflareAccountId: env.CLOUDFLARE_ACCOUNT_ID || env.CF_ACCOUNT_ID,
    cloudflareModel: env.CLOUDFLARE_MODEL || env.LLM_MODEL,
    cloudflareFastModel: env.CLOUDFLARE_FAST_MODEL || env.LLM_FAST_MODEL,
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
