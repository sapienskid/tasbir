import { createAnthropic } from "@ai-sdk/anthropic";
import { createOpenAI } from "@ai-sdk/openai";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
import type { LanguageModel } from "ai";

export interface ProviderConfig {
  anthropicApiKey?: string;
  openaiApiKey?: string;
  googleApiKey?: string;
  preferredProvider?: "anthropic" | "openai" | "google";
}

export function createModelChain(config: ProviderConfig): LanguageModel[] {
  const models: LanguageModel[] = [];
  const order = config.preferredProvider
    ? [config.preferredProvider, "anthropic", "openai", "google"].filter((v, i, a) => a.indexOf(v) === i)
    : ["anthropic", "openai", "google"];

  for (const provider of order) {
    switch (provider) {
      case "anthropic":
        if (config.anthropicApiKey) {
          const anthropic = createAnthropic({ apiKey: config.anthropicApiKey });
          models.push(anthropic("claude-sonnet-4-20250514"));
        }
        break;
      case "openai":
        if (config.openaiApiKey) {
          const openai = createOpenAI({ apiKey: config.openaiApiKey });
          models.push(openai("gpt-4o"));
        }
        break;
      case "google":
        if (config.googleApiKey) {
          const google = createGoogleGenerativeAI({ apiKey: config.googleApiKey });
          models.push(google("gemini-2.5-flash"));
        }
        break;
    }
  }

  if (models.length === 0) {
    throw new Error("No AI provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY.");
  }

  return models;
}

export function createFastModelChain(config: ProviderConfig): LanguageModel[] {
  const models: LanguageModel[] = [];
  const order = config.preferredProvider
    ? [config.preferredProvider, "anthropic", "openai", "google"].filter((v, i, a) => a.indexOf(v) === i)
    : ["anthropic", "openai", "google"];

  for (const provider of order) {
    switch (provider) {
      case "anthropic":
        if (config.anthropicApiKey) {
          const anthropic = createAnthropic({ apiKey: config.anthropicApiKey });
          models.push(anthropic("claude-haiku-4-20250414"));
        }
        break;
      case "openai":
        if (config.openaiApiKey) {
          const openai = createOpenAI({ apiKey: config.openaiApiKey });
          models.push(openai("gpt-4o-mini"));
        }
        break;
      case "google":
        if (config.googleApiKey) {
          const google = createGoogleGenerativeAI({ apiKey: config.googleApiKey });
          models.push(google("gemini-2.5-flash"));
        }
        break;
    }
  }

  if (models.length === 0) {
    throw new Error("No AI provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY.");
  }

  return models;
}

export function resolveProviderConfig(env: Record<string, string | undefined>): ProviderConfig {
  return {
    anthropicApiKey: env.ANTHROPIC_API_KEY,
    openaiApiKey: env.OPENAI_API_KEY,
    googleApiKey: env.GOOGLE_API_KEY || env.GEMINI_API_KEY,
    preferredProvider: (env.AI_PREFERRED_PROVIDER as "anthropic" | "openai" | "google") || undefined,
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
