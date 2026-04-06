import { createGoogleGenerativeAI } from "@ai-sdk/google";
import type { LanguageModel } from "ai";

// ─── Configuration ───────────────────────────────────────────────────────────

export interface ProviderConfig {
  googleApiKey: string;
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

// ─── Default Model ───────────────────────────────────────────────────────────

export const DEFAULT_MODEL = "gemma-4-31b-it";

// ─── Model Creation ──────────────────────────────────────────────────────────

function createGoogleModel(apiKey: string, model: string): LanguageModel {
  const google = createGoogleGenerativeAI({ apiKey });
  return google(model);
}

// ─── Model Chain Functions ───────────────────────────────────────────────────

export function createModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGoogleModel(config.googleApiKey, DEFAULT_MODEL)];
}

export function createFastModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGoogleModel(config.googleApiKey, DEFAULT_MODEL)];
}

export function createHtmlLayoutModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGoogleModel(config.googleApiKey, DEFAULT_MODEL)];
}

export function createAdvancedModelChain(config: ProviderConfig): LanguageModel[] {
  return [createGoogleModel(config.googleApiKey, DEFAULT_MODEL)];
}

// ─── Env Resolution ──────────────────────────────────────────────────────────

export function resolveProviderConfig(googleApiKey?: string): ProviderConfig {
  if (!googleApiKey) {
    throw new Error("GOOGLE_API_KEY is required. Set via 'wrangler secret put GOOGLE_API_KEY'");
  }
  return { googleApiKey };
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
