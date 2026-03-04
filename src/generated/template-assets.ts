import assets from "./template-assets.json";

interface GeneratedAssets {
  pipeline_config: Record<string, unknown>;
  template_files: Record<string, string>;
  template_css: string;
}

const generatedAssets = assets as GeneratedAssets;

export const PIPELINE_CONFIG = generatedAssets.pipeline_config as any;
export const TEMPLATE_FILES = generatedAssets.template_files as Record<string, string>;
export const TEMPLATE_CSS = generatedAssets.template_css;

export type PipelineConfig = typeof PIPELINE_CONFIG;
export type TemplateFileId = keyof typeof TEMPLATE_FILES;
