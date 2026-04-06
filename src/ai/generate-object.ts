import { generateObject, type LanguageModel, type Schema } from "ai";

export async function generateObjectWithRetry<T>(
  model: LanguageModel,
  options: {
    system?: string;
    prompt: string;
    schema: Schema<T>;
    temperature?: number;
    maxOutputTokens?: number;
  },
  fallback: () => T,
  label: string = "generateObject",
): Promise<T> {
  try {
    const result = await generateObject({
      model,
      system: options.system,
      prompt: options.prompt,
      schema: options.schema,
      temperature: options.temperature ?? 0.7,
      maxOutputTokens: options.maxOutputTokens,
    });
    return result.object as T;
  } catch (error) {
    console.warn(`[${label}] generateObject failed, using fallback:`, error);
    return fallback();
  }
}
