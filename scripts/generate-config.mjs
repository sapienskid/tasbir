import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { parse } from "yaml";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const CONFIG_PATH = resolve(__dirname, "..", "config", "pipeline.config.yaml");
const OUTPUT_PATH = resolve(__dirname, "..", "src", "generated", "config.ts");

const raw = readFileSync(CONFIG_PATH, "utf-8");
const config = parse(raw);

const content = `// Auto-generated from config/pipeline.config.yaml — do not edit manually
export const PIPELINE_CONFIG = ${JSON.stringify(config, null, 2)} as const;

export function getDesignTokens() {
  return (PIPELINE_CONFIG as any).design_tokens ?? DEFAULT_DESIGN_TOKENS;
}

export function getFormatConfig(name: string) {
  const formats = (PIPELINE_CONFIG as any).formats;
  return formats?.[name] ?? null;
}

export function getAllFormats() {
  return (PIPELINE_CONFIG as any).formats ?? {};
}

export function getFormatNames() {
  return Object.keys(getAllFormats());
}

export function formatDesignTokensForPrompt(): string {
  const tokens = getDesignTokens();
  const parts: string[] = [];
  parts.push("Colors:");
  for (const [key, value] of Object.entries(tokens.colors)) {
    parts.push(\`  --\${key}: \${value}\`);
  }
  parts.push("Fonts:");
  for (const [key, value] of Object.entries(tokens.fonts)) {
    parts.push(\`  --font-\${key}: \${value}\`);
  }
  parts.push("Spacing:");
  for (const [key, value] of Object.entries(tokens.spacing)) {
    parts.push(\`  --spacing-\${key}: \${value}\`);
  }
  return parts.join("\\n");
}

export function generateTailwindConfig(): string {
  const tokens = getDesignTokens();
  return \`
tailwind.config = {
  theme: {
    extend: {
      colors: {
        'primary-bg': '\${tokens.colors.primary_bg}',
        'primary-text': '\${tokens.colors.primary_text}',
        'accent': '\${tokens.colors.accent}',
        'accent-text': '\${tokens.colors.accent_text}',
        'muted-text': '\${tokens.colors.muted_text}',
        'surface': '\${tokens.colors.surface}',
        'border-custom': '\${tokens.colors.border}',
      },
      fontFamily: {
        'display': [\${tokens.fonts.display.split(",").map(f => \`'\${f.trim()}'\`).join(", ")}],
        'body': [\${tokens.fonts.body.split(",").map(f => \`'\${f.trim()}'\`).join(", ")}],
        'mono': [\${tokens.fonts.mono.split(",").map(f => \`'\${f.trim()}'\`).join(", ")}],
      },
      spacing: {
        'token-xs': '\${tokens.spacing.xs}',
        'token-sm': '\${tokens.spacing.sm}',
        'token-md': '\${tokens.spacing.md}',
        'token-lg': '\${tokens.spacing.lg}',
        'token-xl': '\${tokens.spacing.xl}',
        'token-2xl': '\${tokens.spacing["2xl"]}',
        'token-3xl': '\${tokens.spacing["3xl"]}',
      },
    }
  }
}
\`.trim();
}

const DEFAULT_DESIGN_TOKENS = {
  colors: {
    primary_bg: "#0b0b0b",
    primary_text: "#f5f5f5",
    accent: "#3b82f6",
    accent_text: "#ffffff",
    muted_text: "#a3a3a3",
    border: "#262626",
    surface: "#171717",
  },
  fonts: {
    display: "system-ui, -apple-system, sans-serif",
    body: "system-ui, -apple-system, sans-serif",
    mono: "ui-monospace, SFMono-Regular, monospace",
  },
  spacing: {
    xs: "4px",
    sm: "8px",
    md: "16px",
    lg: "24px",
    xl: "32px",
    "2xl": "48px",
    "3xl": "64px",
  },
};
`;

writeFileSync(OUTPUT_PATH, content);
console.log(`Generated ${OUTPUT_PATH} from ${CONFIG_PATH}`);
