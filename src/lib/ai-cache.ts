/**
 * AI Response Cache
 * 
 * Provides content-hash based caching for AI-generated HTML.
 * Uses KV storage with TTL for automatic expiration.
 */

// Cache configuration
const CACHE_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days
const CACHE_KEY_PREFIX = "ai-html-cache:";

export interface CacheEntry {
  html: string;
  generatedAt: number;
  contentHash: string;
  format: string;
}

/**
 * Generate a cache key from content inputs.
 * Uses a fast hash of the content that determines the output.
 */
export async function generateCacheKey(inputs: {
  title: string;
  content: string;
  format: string;
  width: number;
  height: number;
  prompt?: string;
  designTokensHash?: string;
}): Promise<string> {
  const keyParts = [
    inputs.title.slice(0, 200),
    inputs.content.slice(0, 2000),
    inputs.format,
    `${inputs.width}x${inputs.height}`,
    inputs.prompt?.slice(0, 500) || "",
    inputs.designTokensHash || "",
  ].join("|");

  const hash = await hashString(keyParts);
  return `${CACHE_KEY_PREFIX}${inputs.format}:${hash}`;
}

/**
 * Generate a hash for design tokens to detect changes.
 */
export async function hashDesignTokens(tokens: Record<string, unknown>): Promise<string> {
  // Only hash the parts that affect visual output
  const relevantParts = {
    colors: tokens.colors,
    typography: tokens.typography,
    spacing: tokens.spacing,
    surfaces: tokens.surfaces,
    gradients: tokens.gradients,
  };
  return hashString(JSON.stringify(relevantParts));
}

/**
 * Get cached AI response if available.
 */
export async function getCachedHtml(
  kv: KVNamespace | undefined,
  cacheKey: string
): Promise<CacheEntry | null> {
  if (!kv) return null;

  try {
    const cached = await kv.get(cacheKey, "json");
    if (!cached) return null;

    const entry = cached as CacheEntry;
    // Validate entry structure
    if (!entry.html || !entry.generatedAt || !entry.format) {
      return null;
    }

    return entry;
  } catch {
    return null;
  }
}

/**
 * Store AI response in cache.
 */
export async function setCachedHtml(
  kv: KVNamespace | undefined,
  cacheKey: string,
  entry: CacheEntry
): Promise<void> {
  if (!kv) return;

  try {
    await kv.put(cacheKey, JSON.stringify(entry), {
      expirationTtl: CACHE_TTL_SECONDS,
    });
  } catch (error) {
    // Log but don't fail on cache write errors
    console.warn("[ai-cache] Failed to write cache:", error);
  }
}

/**
 * Fast string hashing using Web Crypto API.
 */
async function hashString(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = new Uint8Array(hashBuffer);
  
  // Convert to hex string (first 16 chars for shorter keys)
  return Array.from(hashArray.slice(0, 8))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Check if caching should be used for this request.
 * Returns false for requests that should always generate fresh content.
 */
export function shouldUseCache(options: {
  postCount?: number;
  forceRefresh?: boolean;
}): boolean {
  // Don't cache when generating multiple variants (they should differ)
  if (options.postCount && options.postCount > 1) return false;
  
  // Respect explicit refresh requests
  if (options.forceRefresh) return false;
  
  return true;
}
