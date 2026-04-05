import { WorkspaceSettings } from './settings.js';

export interface PromptConfig {
  system: string;
  userCustom?: string;
  systemCustom?: string;
}

/**
 * Merges custom prompts with system prompts for AI operations
 */
export function mergePrompts(
  systemPrompt: string | string[], 
  customPrompt?: string, 
  position: 'append' | 'prepend' = 'append'
): string {
  const basePrompt = Array.isArray(systemPrompt) ? systemPrompt.join('\n') : systemPrompt;
  
  if (!customPrompt || customPrompt.trim() === '') {
    return basePrompt;
  }
  
  const customInstructions = `\n\nADDITIONAL INSTRUCTIONS:\n${customPrompt.trim()}`;
  
  return position === 'prepend' 
    ? customInstructions + '\n\n' + basePrompt
    : basePrompt + customInstructions;
}

/**
 * Gets custom prompts from workspace settings with fallbacks
 */
export function getCustomPrompts(settings?: WorkspaceSettings | null): {
  htmlGeneration: string;
  contentCreation: string;
  imageGeneration: string;
  templateSelection: string;
  designTokens: string;
  customInstructions: string;
} {
  return {
    htmlGeneration: settings?.prompts?.htmlGeneration || '',
    contentCreation: settings?.prompts?.contentCreation || '',
    imageGeneration: settings?.prompts?.imageGeneration || '',
    templateSelection: settings?.prompts?.templateSelection || '',
    designTokens: settings?.prompts?.designTokens || '',
    customInstructions: settings?.prompts?.customInstructions || ''
  };
}

/**
 * Builds enhanced system prompt with custom instructions and global context
 */
export function buildEnhancedPrompt(
  systemPrompt: string | string[],
  customPrompt: string = '',
  globalInstructions: string = '',
  context?: Record<string, unknown>
): string {
  let basePrompt = Array.isArray(systemPrompt) ? systemPrompt.join('\n') : systemPrompt;
  
  // Add context if provided
  if (context && Object.keys(context).length > 0) {
    const contextSection = '\n\nCONTEXT:\n' + 
      Object.entries(context)
        .filter(([_, value]) => value !== undefined && value !== null && value !== '')
        .map(([key, value]) => `- ${key}: ${value}`)
        .join('\n');
    basePrompt += contextSection;
  }
  
  // Add global custom instructions first (if any)
  if (globalInstructions && globalInstructions.trim() !== '') {
    basePrompt += `\n\nGLOBAL INSTRUCTIONS:\n${globalInstructions.trim()}`;
  }
  
  // Add specific custom prompt last (highest priority)
  if (customPrompt && customPrompt.trim() !== '') {
    basePrompt += `\n\nCUSTOM INSTRUCTIONS:\n${customPrompt.trim()}`;
  }
  
  return basePrompt;
}

/**
 * Creates a prompt configuration object for AI agents
 */
export function createPromptConfig(
  systemPrompt: string | string[],
  settings?: WorkspaceSettings | null,
  promptType?: keyof ReturnType<typeof getCustomPrompts>
): PromptConfig {
  const customPrompts = getCustomPrompts(settings);
  const specificCustom = promptType ? customPrompts[promptType] : '';
  
  return {
    system: buildEnhancedPrompt(
      systemPrompt,
      specificCustom,
      customPrompts.customInstructions
    ),
    userCustom: specificCustom,
    systemCustom: customPrompts.customInstructions
  };
}