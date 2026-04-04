export {
  PIPELINE_CONFIG,
  getDesignTokens,
  getFormatConfig,
  getAllFormats,
  getFormatNames,
  formatDesignTokensForPrompt,
  generateTailwindConfig
} from "./generated/config";

export interface DesignTokens {
  colors: Record<string, string>;
  fonts: Record<string, string>;
  spacing: Record<string, string>;
}

export interface FormatConfig {
  width: number;
  height: number;
  caption_source: string;
  hashtag_count: number;
}
