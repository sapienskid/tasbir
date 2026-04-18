/**
 * Request Context & Structured Logging
 * 
 * Provides request-scoped context with unique request IDs,
 * structured JSON logging, and timing utilities.
 */

export interface RequestContext {
  requestId: string;
  startTime: number;
  method: string;
  path: string;
}

/**
 * Create a new request context with unique request ID.
 */
export function createRequestContext(request: Request): RequestContext {
  const url = new URL(request.url);
  return {
    requestId: generateRequestId(),
    startTime: Date.now(),
    method: request.method,
    path: url.pathname,
  };
}

/**
 * Generate a short, URL-safe request ID.
 */
function generateRequestId(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 12);
}

/**
 * Structured logger that attaches request context to all log entries.
 */
export class RequestLogger {
  constructor(private ctx: RequestContext) {}

  info(step: string, data?: Record<string, unknown>) {
    console.log(JSON.stringify({
      level: "info",
      requestId: this.ctx.requestId,
      step,
      elapsed: Date.now() - this.ctx.startTime,
      ...data,
    }));
  }

  warn(step: string, data?: Record<string, unknown>) {
    console.warn(JSON.stringify({
      level: "warn",
      requestId: this.ctx.requestId,
      step,
      elapsed: Date.now() - this.ctx.startTime,
      ...data,
    }));
  }

  error(step: string, err: unknown, data?: Record<string, unknown>) {
    const message = err instanceof Error ? err.message : String(err);
    const stack = err instanceof Error ? err.stack : undefined;
    console.error(JSON.stringify({
      level: "error",
      requestId: this.ctx.requestId,
      step,
      elapsed: Date.now() - this.ctx.startTime,
      error: message,
      stack: stack?.slice(0, 500),
      ...data,
    }));
  }

  /** Return elapsed time in ms */
  elapsed(): number {
    return Date.now() - this.ctx.startTime;
  }
}

/**
 * Wrap a promise with a timeout. Rejects with a descriptive error if the
 * timeout is exceeded.
 */
export function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  label: string
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`Timeout: ${label} exceeded ${timeoutMs}ms`));
    }, timeoutMs);

    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}

/**
 * Retry a function with exponential backoff.
 * Only retries on errors matching the shouldRetry predicate.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number;
    baseDelayMs?: number;
    maxDelayMs?: number;
    shouldRetry?: (err: unknown) => boolean;
    label?: string;
  } = {}
): Promise<T> {
  const {
    maxRetries = 2,
    baseDelayMs = 500,
    maxDelayMs = 4000,
    shouldRetry = isTransientError,
    label = "operation",
  } = options;

  let lastError: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt >= maxRetries || !shouldRetry(err)) {
        throw err;
      }
      const delay = Math.min(baseDelayMs * Math.pow(2, attempt), maxDelayMs);
      const jitter = Math.random() * delay * 0.3;
      console.warn(`[retry] ${label} attempt ${attempt + 1} failed, retrying in ${Math.round(delay + jitter)}ms`);
      await new Promise((r) => setTimeout(r, delay + jitter));
    }
  }
  throw lastError;
}

/**
 * Check if an error is likely transient and worth retrying.
 */
function isTransientError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return (
    msg.includes("timeout") ||
    msg.includes("connection closed") ||
    msg.includes("network") ||
    msg.includes("502") ||
    msg.includes("503") ||
    msg.includes("504") ||
    msg.includes("econnreset") ||
    msg.includes("econnrefused")
  );
}

/**
 * Build a standard error JSON response with request ID.
 */
export function errorResponse(
  requestId: string,
  status: number,
  message: string,
  extra?: Record<string, unknown>
): Response {
  return new Response(
    JSON.stringify({ error: message, requestId, ...extra }),
    {
      status,
      headers: { "content-type": "application/json; charset=utf-8" },
    }
  );
}
