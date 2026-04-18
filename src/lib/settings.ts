export interface WorkspaceSettings {
  brand: {
    name: string;
    tone: string;
    audience: string;
  };
  campaign: {
    goal: "awareness" | "engagement" | "conversion" | "education";
    framework: "AIDA" | "PAS" | "FAB" | "none";
    hashtags: {
      style: "niche" | "broad" | "branded";
      count: number;
    };
    cta: string;
  };
  formats: {
    enabled: string[];
    postCount: number;
  };
  templates: {
    autoSelect: boolean;
    disabled: string[];
  };
  image: {
    mode: "auto" | "none" | "feature" | "ai";
    style: string;
  };
  prompts: {
    htmlGeneration: string;
    contentCreation: string;
    contentClassification: string;
    imageGeneration: string;
    templateSelection: string;
    designTokens: string;
    customInstructions: string;
  };
  integrations?: {
    ghost?: {
      url: string;
      token: string;
      enabled: boolean;
    };
    webhook?: {
      url: string;
      secret: string;
      enabled: boolean;
    };
  };
  designTokens: Record<string, unknown> | null;
  updatedAt: string;
}

const DEFAULT_SETTINGS: WorkspaceSettings = {
  brand: {
    name: "Tasbir",
    tone: "confident, practical",
    audience: "developers and founders"
  },
  campaign: {
    goal: "awareness",
    framework: "none",
    hashtags: { style: "niche", count: 5 },
    cta: ""
  },
  formats: {
    enabled: ["instagram-square", "twitter-card", "linkedin-post"],
    postCount: 1
  },
  templates: {
    autoSelect: true,
    disabled: []
  },
  image: {
    mode: "auto",
    style: "editorial"
  },
  prompts: {
    htmlGeneration: "",
    contentCreation: "",
    contentClassification: "",
    imageGeneration: "",
    templateSelection: "", 
    designTokens: "",
    customInstructions: ""
  },
  integrations: {
    ghost: { url: "", token: "", enabled: false },
    webhook: { url: "", secret: "", enabled: false }
  },
  designTokens: null,
  updatedAt: new Date().toISOString()
};

const SETTINGS_KEY = "workspace";

export async function loadSettings(kv: KVNamespace): Promise<WorkspaceSettings> {
  try {
    const raw = await kv.get(SETTINGS_KEY, "text");
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw) as Partial<WorkspaceSettings>;
    return mergeWithDefaults(parsed);
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export async function saveSettings(kv: KVNamespace, settings: WorkspaceSettings): Promise<void> {
  await kv.put(SETTINGS_KEY, JSON.stringify({
    ...settings,
    updatedAt: new Date().toISOString()
  }));
}

export async function patchSettings(kv: KVNamespace, patch: Partial<WorkspaceSettings>): Promise<WorkspaceSettings> {
  const current = await loadSettings(kv);
  const merged = deepMerge(current as unknown as Record<string, unknown>, patch as unknown as Record<string, unknown>) as unknown as WorkspaceSettings;
  merged.updatedAt = new Date().toISOString();
  await saveSettings(kv, merged);
  return merged;
}

function mergeWithDefaults(partial: Partial<WorkspaceSettings>): WorkspaceSettings {
  return deepMerge(DEFAULT_SETTINGS as unknown as Record<string, unknown>, partial as unknown as Record<string, unknown>) as unknown as WorkspaceSettings;
}

function deepMerge(target: Record<string, unknown>, source: Record<string, unknown>): Record<string, unknown> {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    const sourceVal = source[key];
    const targetVal = target[key];
    if (sourceVal && typeof sourceVal === "object" && !Array.isArray(sourceVal) &&
        targetVal && typeof targetVal === "object" && !Array.isArray(targetVal)) {
      result[key] = deepMerge(targetVal as Record<string, unknown>, sourceVal as Record<string, unknown>);
    } else if (sourceVal !== undefined) {
      result[key] = sourceVal;
    }
  }
  return result;
}

export function getDefaultSettings(): WorkspaceSettings {
  return { ...DEFAULT_SETTINGS };
}
