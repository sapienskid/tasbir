interface HealthEnv {
  OUTPUT_BUCKET: R2Bucket;
  SETTINGS_KV?: KVNamespace;
  TEMPLATES_KV?: KVNamespace;
}

export interface HealthStatus {
  ok: boolean;
  version: string;
  uptime: number;
  dependencies: Record<string, { status: "ok" | "degraded" | "down"; message?: string }>;
}

const startTime = Date.now();

export async function checkHealth(env: HealthEnv): Promise<HealthStatus> {
  const dependencies: HealthStatus["dependencies"] = {};

  dependencies.r2 = await checkR2(env);
  dependencies.kv_settings = await checkKV(env.SETTINGS_KV, "settings");
  dependencies.kv_templates = await checkKV(env.TEMPLATES_KV, "templates");

  const allOk = Object.values(dependencies).every((d) => d.status === "ok");

  return {
    ok: allOk,
    version: "0.3.0",
    uptime: Date.now() - startTime,
    dependencies,
  };
}

async function checkR2(env: HealthEnv): Promise<{ status: "ok" | "degraded" | "down"; message?: string }> {
  try {
    await env.OUTPUT_BUCKET.list({ limit: 1 });
    return { status: "ok" };
  } catch (error) {
    return { status: "down", message: error instanceof Error ? error.message : "Unknown error" };
  }
}

async function checkKV(kv: KVNamespace | undefined, label: string): Promise<{ status: "ok" | "degraded" | "down"; message?: string }> {
  if (!kv) return { status: "degraded", message: `${label} KV namespace not configured` };
  try {
    await kv.get("health:check");
    return { status: "ok" };
  } catch (error) {
    return { status: "down", message: error instanceof Error ? error.message : "Unknown error" };
  }
}
