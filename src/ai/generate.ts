import { generateText, type LanguageModel } from "ai";
import { isRetryableError, sleep } from "./providers";

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 2000;

export async function generateWithFallback(
  models: LanguageModel[],
  options: {
    system?: string;
    prompt: string;
    temperature?: number;
    maxTokens?: number;
  },
): Promise<string> {
  const errors: Error[] = [];

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    for (const model of models) {
      try {
        const result = await generateText({
          model,
          system: options.system,
          prompt: options.prompt,
          temperature: options.temperature ?? 0.2,
          maxOutputTokens: options.maxTokens,
        });
        return result.text;
      } catch (error) {
        errors.push(error instanceof Error ? error : new Error(String(error)));
        if (!isRetryableError(error)) {
          throw error;
        }
      }
    }

    if (attempt < MAX_RETRIES - 1) {
      await sleep(BASE_DELAY_MS * Math.pow(2, attempt));
    }
  }

  throw new AggregateError(errors, `All providers failed after ${MAX_RETRIES} retries`);
}

export async function generateJsonWithFallback<T>(
  models: LanguageModel[],
  options: {
    system?: string;
    prompt: string;
    temperature?: number;
    maxTokens?: number;
  },
): Promise<T> {
  const text = await generateWithFallback(models, options);
  const cleaned = text.replace(/```json\s*/g, "").replace(/```\s*/g, "").trim();
  return JSON.parse(cleaned) as T;
}
