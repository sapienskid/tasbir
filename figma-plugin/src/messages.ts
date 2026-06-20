export interface PluginMessage {
  type: 'GENERATE' | 'FETCH_SETTINGS' | 'SAVE_SETTINGS' | 'FETCH_TEMPLATES' | 'FETCH_TOKENS' | 'CLOSE'
  payload?: any
}

export interface UiMessage {
  type: 'PROGRESS' | 'GENERATION_COMPLETE' | 'ERROR' | 'SETTINGS_LOADED' | 'TEMPLATES_LOADED' | 'TOKENS_LOADED' | 'FRAME_CREATED'
  step?: string
  message?: string
  format?: string
  progress?: number
  total?: number
  result?: any
  settings?: any
  templates?: any[]
  tokens?: any
  frameId?: string
}

export interface GenerationRequest {
  title: string
  content: string
  excerpt?: string
  tags?: string[]
  formats: string[]
  postCount?: number
  prompt?: string
  imageMode?: string
  designTokens?: any
}

export interface RenderRequest {
  html: string
  width: number
  height: number
  format: string
  slug: string
  designTokens?: any
  slot_values?: Record<string, string>
}
