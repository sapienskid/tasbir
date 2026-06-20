import { useState, useEffect, useRef } from 'react'
import JSZip from 'jszip'
import { api, getApiKey, setApiKey } from '@/lib/api'
import { tokensToCSS, type DesignTokens } from '@/lib/tokens'
import { generateComponentsSkeleton } from '@/components/skeletons'
import { GOOGLE_FONTS, FONT_CATEGORIES } from '@/lib/google-fonts'

const PRESETS = [
  { id: 'luxury', l: 'Luxury' },
  { id: 'brutalist', l: 'Brutalist' },
  { id: 'organic', l: 'Organic' },
  { id: 'tech', l: 'Dark Tech' },
  { id: 'editorial', l: 'Editorial' },
  { id: 'playful', l: 'Playful' },
  { id: 'gothic', l: 'Gothic' },
  { id: 'retro', l: 'Retro' },
  { id: 'minimal', l: 'Minimal' },
  { id: 'maximalist', l: 'Maximalist' },
]

const VIBE_PRESETS: Record<string, { primary: string; secondary: string; vibe: string }> = {
  luxury: { primary: '#c9a96e', secondary: '#1a1a2e', vibe: 'cold luxury minimal' },
  brutalist: { primary: '#ff3b3b', secondary: '#0a0a0a', vibe: 'raw brutalist bold' },
  organic: { primary: '#4a7c59', secondary: '#f5f0e8', vibe: 'warm organic wellness' },
  tech: { primary: '#3b82f6', secondary: '#0f172a', vibe: 'dark tech futuristic' },
  editorial: { primary: '#1a1a1a', secondary: '#faf9f6', vibe: 'clean editorial serif' },
  playful: { primary: '#f472b6', secondary: '#fef3c7', vibe: 'playful colorful fun' },
  gothic: { primary: '#7c3aed', secondary: '#0c0a09', vibe: 'dark gothic dramatic' },
  retro: { primary: '#f97316', secondary: '#1e1b4b', vibe: 'retro futurist neon' },
  minimal: { primary: '#171717', secondary: '#fafafa', vibe: 'minimal clean whitespace' },
  maximalist: { primary: '#e11d48', secondary: '#7c3aed', vibe: 'maximalist bold saturated' }
}

const TOKENS_LOCAL_KEY = 'tasbir:tokens'

function hexToHSL(hex: string): { h: number; s: number; l: number } {
  const normalized = hex.replace('#', '')
  if (normalized.length !== 6) return { h: 0, s: 0, l: 50 }
  const r = parseInt(normalized.slice(0, 2), 16) / 255
  const g = parseInt(normalized.slice(2, 4), 16) / 255
  const b = parseInt(normalized.slice(4, 6), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  let h = 0
  let s = 0
  const l = (max + min) / 2

  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r:
        h = ((g - b) / d + (g < b ? 6 : 0)) / 6
        break
      case g:
        h = ((b - r) / d + 2) / 6
        break
      default:
        h = ((r - g) / d + 4) / 6
        break
    }
  }

  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) }
}

function hslToHex(h: number, s: number, l: number): string {
  const sat = s / 100
  const light = l / 100
  const a = sat * Math.min(light, 1 - light)
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    const color = light - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * color).toString(16).padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

function generateColorScale(baseHex: string): Record<string, string> {
  const steps = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900']
  const lightnessMap = [95, 88, 78, 68, 58, 50, 42, 34, 24, 14]
  const { h, s } = hexToHSL(baseHex)
  const scale: Record<string, string> = {}
  steps.forEach((step, i) => {
    const satAdjust = step === '50' || step === '100' ? -12 : step === '800' || step === '900' ? 8 : 0
    scale[step] = hslToHex(h, Math.max(8, Math.min(96, s + satAdjust)), lightnessMap[i])
  })
  scale['500'] = baseHex
  return scale
}

function resolveShadowPreviewValue(input: unknown, key: string): string {
  const fallback: Record<string, string> = {
    xs: '0 1px 2px rgba(2, 6, 23, 0.18)',
    sm: '0 2px 6px rgba(2, 6, 23, 0.2)',
    md: '0 8px 16px rgba(2, 6, 23, 0.22)',
    lg: '0 14px 28px rgba(2, 6, 23, 0.24)',
    xl: '0 24px 44px rgba(2, 6, 23, 0.28)',
    inner: 'inset 0 2px 6px rgba(2, 6, 23, 0.2)'
  }

  const fail = fallback[key] || fallback.md
  if (typeof input !== 'string') return fail
  const value = input.trim()
  if (!value) return fail
  if (value === 'none') return 'none'
  if (fallback[value.toLowerCase()]) return fallback[value.toLowerCase()]

  const hasLength = /\d+px/.test(value)
  const hasColor = /(rgba?\(|hsla?\(|#[0-9a-f]{3,8})/i.test(value)
  return hasLength && hasColor ? value : fail
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeTab, setActiveTab] = useState<'studio' | 'templates' | 'settings' | 'tokens' | 'editor'>('studio')
  const [tokens, setTokens] = useState<DesignTokens | null>(null)
  const [generating, setGenerating] = useState(false)
  const [vibeInput, setVibeInput] = useState('')
  const [activePreset, setActivePreset] = useState<string | null>(null)
  const [primaryColorHint, setPrimaryColorHint] = useState('')
  const [secondaryColorHint, setSecondaryColorHint] = useState('')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({ color: true, typography: true, instructions: false, spacing: true, shadow: true, border: true, gradient: true, motion: true, component: true })
  const [error, setError] = useState<string | null>(null)
  const [, setServerConfig] = useState<any>(null)
  const [, setConfigLoading] = useState(false)
  const [editingConfig, setEditingConfig] = useState<any>(null)
  const [studioResult, setStudioResult] = useState<any>(() => {
    try {
      const saved = localStorage.getItem('tasbir:studioResult')
      return saved ? JSON.parse(saved) : null
    } catch { return null }
  })
  const [studioGenerating, setStudioGenerating] = useState(false)
  const [studioMode, setStudioMode] = useState<'content' | 'slug'>('content')
  const [studioTitle, setStudioTitle] = useState(() => {
    return localStorage.getItem('tasbir:studioTitle') || ''
  })
  const [studioContent, setStudioContent] = useState(() => {
    return localStorage.getItem('tasbir:studioContent') || ''
  })
  const [studioSlug, setStudioSlug] = useState('')
  const [selectedAsset, setSelectedAsset] = useState<{ format: string; asset: any; resolvedSrc: string } | null>(null)

  useEffect(() => {
    localStorage.setItem('tasbir:studioContent', studioContent)
  }, [studioContent])

  useEffect(() => {
    localStorage.setItem('tasbir:studioTitle', studioTitle)
  }, [studioTitle])

  useEffect(() => {
    if (studioResult) {
      localStorage.setItem('tasbir:studioResult', JSON.stringify(studioResult))
    } else {
      localStorage.removeItem('tasbir:studioResult')
    }
  }, [studioResult])
  const [settings, setSettings] = useState<any>(null)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [templates, setTemplates] = useState<any[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<{ id: string; html: string; name: string; description: string; category: string; slots: string[] } | null>(null)
  const [templateHtml, setTemplateHtml] = useState('')
  const [templatePreviewHtml, setTemplatePreviewHtml] = useState('')
  const [designInstructions, setDesignInstructions] = useState('')
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [templateSaveDialog, setTemplateSaveDialog] = useState(false)
  const [templateSaveName, setTemplateSaveName] = useState('')
  const [fontSearches, setFontSearches] = useState<Record<string, string>>({ fontSans: '', fontSerif: '', fontMono: '' })
  const [fontCategories, setFontCategories] = useState<Record<string, string>>({ fontSans: 'all', fontSerif: 'all', fontMono: 'all' })
  // Format management state
  const [editingFormat, setEditingFormat] = useState<{ id: string; width: number; height: number; name: string; aiInstruction: string; isNew: boolean } | null>(null)
  const [formatSaving, setFormatSaving] = useState(false)

  useEffect(() => {
    loadConfig()
    loadSavedTokens()
    loadSettings()
    loadTemplates()
  }, [])

  useEffect(() => {
    if (!tokens) return
    try {
      localStorage.setItem(TOKENS_LOCAL_KEY, JSON.stringify(tokens))
    } catch {
      // ignore
    }
  }, [tokens])

  async function loadSavedTokens() {
    try {
      const localRaw = localStorage.getItem(TOKENS_LOCAL_KEY)
      if (localRaw) {
        const parsed = JSON.parse(localRaw)
        setTokens(parsed)
        if (parsed?.meta?.instructions) {
          setDesignInstructions(parsed.meta.instructions)
        }
      }
    } catch {
      // ignore malformed local tokens
    }

    try {
      const saved = await api.getSavedTokens()
      if (saved) {
        setTokens(saved)
        localStorage.setItem(TOKENS_LOCAL_KEY, JSON.stringify(saved))
        if (saved?.meta?.instructions) {
          setDesignInstructions(saved.meta.instructions)
        }
      }
    } catch {
      // ignore backend token load failures
    }
  }

  async function loadConfig() {
    setConfigLoading(true)
    try {
      const cfg = await api.getConfig()
      setServerConfig(cfg)
      setEditingConfig(JSON.parse(JSON.stringify(cfg)))
    } catch { /* ignore */ }
    setConfigLoading(false)
  }

  async function loadSettings() {
    setSettingsLoading(true)
    try {
      const s = await api.getSettings()
      setSettings(s)
    } catch {
      // ignore
    }
    setSettingsLoading(false)
  }

  async function loadTemplates() {
    setTemplatesLoading(true)
    try {
      const res = await api.getTemplates()
      setTemplates(res.templates || [])
    } catch {
      // ignore
    }
    setTemplatesLoading(false)
  }

  async function saveSettings(patch: any) {
    try {
      const res = await api.patchSettings(patch)
      setSettings(res.settings)
    } catch (e: any) {
      setError(e.message || 'Failed to save settings')
    }
  }

  async function generateTokens() {
    if (!vibeInput.trim() && !activePreset) {
      setError('Enter a vibe or select a preset')
      return
    }
    setGenerating(true)
    setError(null)
    try {
      const vibeLabel = activePreset ? `${PRESETS.find(p => p.id === activePreset)?.l}${vibeInput ? ' + ' + vibeInput : ''}` : vibeInput
      const result = await api.generateTokens({ 
        vibe: vibeLabel || 'custom design system',
        primaryHint: primaryColorHint || undefined,
        secondaryHint: secondaryColorHint || undefined
      })
      await persistTokens(result)
      setExpandedSections({ color: true, typography: true, spacing: true, shadow: true, border: true, gradient: true, motion: true, component: true })
    } catch (e: any) {
      setError(e.message || 'Token generation failed')
    } finally {
      setGenerating(false)
    }
  }

  async function handleRegenDemo() {
    if (tokens) {
      await persistTokens({ ...tokens })
    }
  }

  async function persistTokens(nextTokens: DesignTokens) {
    setTokens(nextTokens)
    try {
      localStorage.setItem(TOKENS_LOCAL_KEY, JSON.stringify(nextTokens))
    } catch {
      // ignore local storage failures
    }
    try {
      await api.saveTokens(nextTokens)
    } catch {
      // ignore backend save failures
    }
  }

  async function updateTokenColor(group: 'primary' | 'secondary', hex: string) {
    if (!tokens) return
    if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return
    const next: DesignTokens = {
      ...tokens,
      colors: {
        ...tokens.colors,
        [group]: generateColorScale(hex),
      },
    }
    await persistTokens(next)
  }

  async function updateAccentColor(key: 'light' | 'base' | 'dark', hex: string) {
    if (!tokens) return
    if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return
    const next: DesignTokens = {
      ...tokens,
      colors: {
        ...tokens.colors,
        accent: {
          ...tokens.colors.accent,
          [key]: hex,
        },
      },
    }
    await persistTokens(next)
  }

  function applyPreset(id: string) {
    const p = VIBE_PRESETS[id]
    if (!p) return
    setActivePreset(id === activePreset ? null : id)
    setPrimaryColorHint(p.primary)
    setSecondaryColorHint(p.secondary)
    setVibeInput(p.vibe)
  }

  function toggleSection(key: string) {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  async function handleStudioGenerate() {
    if (studioMode === 'content' && (!studioTitle.trim() || !studioContent.trim())) { setError('Title and content required'); return }
    if (studioMode === 'slug' && !studioSlug.trim()) { setError('Slug required'); return }
    setStudioGenerating(true)
    setError(null)
    try {
      // Use settings from Settings tab
      const enabledFormats = settings?.formats?.enabled || []
      const postCount = settings?.formats?.postCount || 1
      const imageMode = settings?.image?.mode || 'auto'
      
      const shared: any = {
        output: { formats: enabledFormats, postCount },
        image: { mode: imageMode },
        designTokens: tokens || undefined,
      }

      const res = studioMode === 'slug'
        ? await api.generate({
            slug: studioSlug.trim(),
            ...shared,
          })
        : await api.generateFromContent({
            title: studioTitle.trim(),
            content: studioContent.trim(),
            ...shared,
          })

      // Store HTML for each format for editing
      const htmlByFormat: Record<string, string> = {}
      if (res.llm_output?.generated_html) {
        // Primary format (first requested format)
        const primaryFormat = res.requested_formats[0]
        if (primaryFormat) htmlByFormat[primaryFormat] = res.llm_output.generated_html
      }
      if (res.variants) {
        res.variants.forEach((variant, idx) => {
          if (variant.llm_output?.generated_html) {
            const format = res.requested_formats[idx] || `variant-${idx + 1}`
            htmlByFormat[format] = variant.llm_output.generated_html
          }
        })
      }
      
      setStudioResult({ ...res, htmlByFormat })
    } catch (e: any) {
      setError(e.message || 'Generation failed')
    } finally {
      setStudioGenerating(false)
    }
  }

  const availableFormats = Object.entries(editingConfig?.formats || {}).map(([id, f]: [string, any]) => ({
    id,
    label: f?.name || id,
    dims: `${f?.width || 0}×${f?.height || 0}`,
    width: f?.width || 0,
    height: f?.height || 0,
    aiInstruction: f?.aiInstruction || '',
  }))

  // Format management functions
  function openFormatEditor(format?: any) {
    if (format) {
      setEditingFormat({
        id: format.id,
        width: format.width,
        height: format.height,
        name: format.label || format.id,
        aiInstruction: format.aiInstruction || '',
        isNew: false,
      })
    } else {
      setEditingFormat({
        id: '',
        width: 1080,
        height: 1080,
        name: '',
        aiInstruction: '',
        isNew: true,
      })
    }
  }

  async function handleSaveFormat() {
    if (!editingFormat) return
    const id = editingFormat.id.trim() || editingFormat.name.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-')
    if (!id) { setError('Format ID is required'); return }
    if (editingFormat.width < 100 || editingFormat.height < 100) { setError('Minimum size is 100x100'); return }
    
    setFormatSaving(true)
    try {
      await api.saveFormat(id, {
        width: editingFormat.width,
        height: editingFormat.height,
        name: editingFormat.name || id,
        aiInstruction: editingFormat.aiInstruction,
      })
      // Reload config to get updated formats
      await loadConfig()
      setEditingFormat(null)
      setError(null)
    } catch (e: any) {
      setError(e.message || 'Failed to save format')
    } finally {
      setFormatSaving(false)
    }
  }

  async function handleDeleteFormat(id: string) {
    if (!confirm(`Delete format "${id}"? This cannot be undone.`)) return
    try {
      await api.deleteFormat(id)
      await loadConfig()
    } catch (e: any) {
      setError(e.message || 'Failed to delete format')
    }
  }

  function openTemplateEditor(template?: any) {
    if (template) {
      api.getTemplate(template.id).then(res => {
        setEditingTemplate({
          id: template.id,
          html: res.html,
          name: template.name || template.id,
          description: template.description || '',
          category: template.category || 'custom',
          slots: template.slots || [],
        })
        setTemplateHtml(res.html)
        updateTemplatePreview(res.html)
      }).catch(() => {
        setEditingTemplate({
          id: template.id,
          html: '',
          name: template.name || template.id,
          description: template.description || '',
          category: template.category || 'custom',
          slots: template.slots || [],
        })
        setTemplateHtml('')
        setTemplatePreviewHtml('')
      })
    } else {
      setEditingTemplate({ id: '', html: '', name: '', description: '', category: 'custom', slots: [] })
      setTemplateHtml('')
      setTemplatePreviewHtml('')
    }
  }

  function updateTemplatePreview(html: string) {
    const slots = extractSlotsFromHtml(html)
    const filled = fillSlotsForPreview(html, slots)
    setTemplatePreviewHtml(filled)
  }

  function extractSlotsFromHtml(html: string): string[] {
    const matches = html.match(/\{\{(\w+)\}\}/g) || []
    return [...new Set(matches.map(m => m.replace(/[{}]/g, '')))]
  }

  function fillSlotsForPreview(html: string, slots: string[]): string {
    let result = html
    const sampleValues: Record<string, string> = {
      headline: 'Your Headline Here',
      title: 'Your Headline Here',
      subtitle: 'Supporting text goes here',
      body: 'This is sample content that demonstrates how the template will look when filled with real content.',
      quote: '"The best code is no code."',
      author: 'Jane Doe',
      role: 'Founder & CEO',
      metric: '9.8K',
      metric_label: 'Engagement',
      brand: 'Your Brand',
      cta: 'Learn More →',
      image_url: '',
    }
    for (const slot of slots) {
      const value = sampleValues[slot] || `{{${slot}}}`
      result = result.replace(new RegExp(`\\{\\{${slot}\\}\\}`, 'g'), value)
    }
    return result
  }

  async function handleSaveTemplate() {
    if (!editingTemplate) return
    const id = editingTemplate.id.trim() || editingTemplate.name.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-')
    if (!id) { setError('Template ID is required'); return }
    if (!templateHtml.trim()) { setError('Template HTML is required'); return }
    try {
      await api.saveTemplate(id, templateHtml, {
        name: editingTemplate.name || id,
        description: editingTemplate.description,
        category: editingTemplate.category,
      })
      setEditingTemplate(prev => prev ? { ...prev, id } : null)
      await loadTemplates()
      setError(null)
    } catch (e: any) {
      setError(e.message || 'Failed to save template')
    }
  }

  async function handleDeleteTemplate(id: string) {
    if (!confirm('Delete this template?')) return
    try {
      await api.deleteTemplate(id)
      await loadTemplates()
      if (editingTemplate?.id === id) {
        setEditingTemplate(null)
      }
    } catch (e: any) {
      setError(e.message || 'Failed to delete template')
    }
  }

  async function handleToggleTemplate(id: string, enabled: boolean) {
    try {
      await api.toggleTemplate(id, enabled)
      await loadTemplates()
    } catch (e: any) {
      setError(e.message || 'Failed to toggle template')
    }
  }

  async function handleSaveAsTemplate(type: 'generated' | 'design') {
    if (!tokens) return
    setTemplateSaveDialog(true)
    setTemplateSaveName(type === 'generated' ? 'generated-design' : tokens.meta?.vibeName?.toLowerCase().replace(/[^a-z0-9-]/g, '-') || 'design-tokens')
  }

  async function confirmSaveTemplate() {
    if (!tokens || !templateSaveName.trim()) return
    setSavingTemplate(true)
    try {
      const id = templateSaveName.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-')
      const instructions = designInstructions || tokens.meta?.instructions || ''
      const tokensWithInstructions = {
        ...tokens,
        meta: {
          ...tokens.meta,
          instructions
        }
      }

      let html: string
      let description: string

      if (studioResult?.llm_output?.generated_html) {
        html = studioResult.llm_output.generated_html
        description = `AI-generated HTML template from ${tokens.meta?.vibeName || 'design system'}. Design tokens: ${JSON.stringify(tokensWithInstructions).substring(0, 200)}...`
      } else {
        const skeletonHtml = generateComponentsSkeleton()
        const cssVars = tokensToCSS(tokensWithInstructions)
        const fonts = [
          tokensWithInstructions.typography?.fontSans,
          tokensWithInstructions.typography?.fontSerif,
          tokensWithInstructions.typography?.fontMono
        ].filter(Boolean).map((f: string) => f?.replace(/\s+/g, '+'))
        const fontImport = fonts.length > 0
          ? `<link href="https://fonts.googleapis.com/css2?${fonts.map((f: string) => `family=${f}:wght@300;400;500;600;700;900`).join('&')}&display=swap" rel="stylesheet">`
          : ''
        html = skeletonHtml.replace('</head>', `${fontImport}\n</head>`)
        html = html.replace('<style id="token-styles"></style>', `<style id="token-styles">${cssVars}</style>`)
        description = `Design template from ${tokens.meta?.vibeName || 'design system'} with tokens and instructions`
      }

      await api.saveTemplate(id, html, {
        name: templateSaveName.trim(),
        description,
        category: 'custom',
      })
      await loadTemplates()
      setTemplateSaveDialog(false)
      setTemplateSaveName('')
      setError(null)
    } catch (e: any) {
      setError(e.message || 'Failed to save as template')
    } finally {
      setSavingTemplate(false)
    }
  }

  function handleUpdateDesignInstructions(instructions: string) {
    setDesignInstructions(instructions)
    if (tokens) {
      const next = {
        ...tokens,
        meta: {
          ...tokens.meta,
          instructions
        }
      }
      persistTokens(next)
    }
  }

  function handleUpdateFont(type: 'fontSans' | 'fontSerif' | 'fontMono', family: string) {
    if (!tokens) return
    const next = {
      ...tokens,
      typography: {
        ...tokens.typography,
        [type]: family
      }
    }
    persistTokens(next)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ background: '#0b0b0b', color: '#e2e2e2', fontFamily: "'Inter', system-ui, sans-serif", fontSize: 13 }}>
      {selectedAsset && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" 
             onClick={() => setSelectedAsset(null)}
             style={{ background: 'rgba(0, 0, 0, 0.95)' }}>
          <div className="relative max-w-full max-h-full w-auto h-auto" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setSelectedAsset(null)}
              className="absolute -top-12 right-0 z-10 p-2 rounded transition-colors"
              style={{ background: '#1c1c1c', color: '#888', borderColor: '#313131' }}
              aria-label="Close preview"
            >
              ✕
            </button>
            <img 
              src={selectedAsset.resolvedSrc} 
              alt={`${selectedAsset.format} screenshot`}
              className="max-w-full max-h-[90vh] w-auto h-auto"
              style={{ boxShadow: '0 24px 48px rgba(0,0,0,0.5)' }}
            />
            <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 text-[10px] font-medium" style={{ color: '#888' }}>
              {selectedAsset.format}
            </div>
          </div>
        </div>
      )}
      {!sidebarOpen && (
        <button onClick={() => setSidebarOpen(true)} className="fixed top-3 left-3 z-50 w-8 h-8 flex items-center justify-center rounded border transition-colors hover:bg-[#1c1c1c]" style={{ background: '#141414', borderColor: '#252525' }}>
          <span style={{ color: '#555', fontSize: 14 }}>☰</span>
        </button>
      )}

      <aside
        className="flex flex-col border-r overflow-hidden"
        style={{ width: sidebarOpen ? 300 : 0, background: '#141414', borderColor: '#252525', boxShadow: sidebarOpen ? '4px 0 24px rgba(0,0,0,0.4)' : 'none', transition: 'width 300ms cubic-bezier(0.4, 0, 0.2, 1), box-shadow 300ms cubic-bezier(0.4, 0, 0.2, 1)' }}
      >
        <div className="flex flex-col h-full min-w-[300px]">
          <div className="flex items-center px-4 border-b flex-shrink-0" style={{ height: 52, borderColor: '#252525' }}>
            <span className="font-semibold tracking-tight" style={{ fontSize: 15 }}>Tasbir</span>
            <span className="ml-2 text-[10px] font-medium tracking-wide uppercase px-1.5 py-0.5 border rounded" style={{ color: '#777', borderColor: '#3d3d3d' }}>Studio</span>
            <button onClick={() => setSidebarOpen(false)} className="ml-auto text-[#666] hover:text-white transition-colors" style={{ fontSize: 16 }}>✕</button>
          </div>

          <div className="flex border-b flex-shrink-0" style={{ borderColor: '#252525' }}>
            {([
              { id: 'studio' as const, label: 'Studio' },
              { id: 'templates' as const, label: 'Templates & Formats' },
              { id: 'settings' as const, label: 'Settings' },
              { id: 'tokens' as const, label: 'Tokens' },
            ]).map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`flex-1 py-3 border-b-2 transition-all ${activeTab === tab.id ? 'text-white border-white font-semibold' : 'text-[#555] border-transparent hover:text-[#888] font-medium'}`} style={{ fontSize: 11, letterSpacing: '0.05em' }}>{tab.label}</button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto min-h-0 overflow-x-hidden">
            {activeTab === 'studio' && (
              <StudioTab
                mode={studioMode} setMode={setStudioMode}
                title={studioTitle} setTitle={setStudioTitle}
                content={studioContent} setContent={setStudioContent}
                slug={studioSlug} setSlug={setStudioSlug}
                generating={studioGenerating} onGenerate={handleStudioGenerate}
                result={studioResult}
              />
            )}
            {activeTab === 'templates' && (
              <FormatsTemplatesTab
                templates={templates}
                loading={templatesLoading}
                editingTemplate={editingTemplate}
                setEditingTemplate={setEditingTemplate}
                templateHtml={templateHtml}
                setTemplateHtml={setTemplateHtml}
                openTemplateEditor={openTemplateEditor}
                onSaveTemplate={handleSaveTemplate}
                onDeleteTemplate={handleDeleteTemplate}
                onToggleTemplate={handleToggleTemplate}
                onUpdatePreview={updateTemplatePreview}
                formats={availableFormats}
                editingFormat={editingFormat}
                setEditingFormat={setEditingFormat}
                formatSaving={formatSaving}
                onOpenFormatEditor={openFormatEditor}
                onSaveFormat={handleSaveFormat}
                onDeleteFormat={handleDeleteFormat}
              />
            )}
            {activeTab === 'settings' && (
              <SettingsTab
                settings={settings}
                loading={settingsLoading}
                onSave={saveSettings}
                formats={availableFormats}
              />
            )}
            {activeTab === 'tokens' && (
              <TokensTab
                vibeInput={vibeInput} setVibeInput={setVibeInput}
                activePreset={activePreset} applyPreset={applyPreset}
                primaryColorHint={primaryColorHint} setPrimaryColorHint={setPrimaryColorHint}
                secondaryColorHint={secondaryColorHint} setSecondaryColorHint={setSecondaryColorHint}
                generating={generating} generateTokens={generateTokens}
                tokens={tokens} expandedSections={expandedSections} toggleSection={toggleSection}
                onUpdateTokenColor={updateTokenColor}
                onUpdateAccentColor={updateAccentColor}
                fontSearches={fontSearches} setFontSearches={setFontSearches}
                fontCategories={fontCategories} setFontCategories={setFontCategories}
                designInstructions={designInstructions} setDesignInstructions={handleUpdateDesignInstructions}
                onUpdateFont={handleUpdateFont}
                onSaveAsTemplate={handleSaveAsTemplate}
                studioResult={studioResult}
              />
            )}
          </div>

          {error && (
            <div className="p-3.5 border-t flex-shrink-0" style={{ borderColor: '#252525' }}>
              <div className="text-[10px] text-[#f43f5e]">{error}</div>
              <button onClick={() => setError(null)} className="text-[9px] text-[#f43f5e] mt-1 underline">Dismiss</button>
            </div>
          )}

          {templateSaveDialog && (
            <div className="p-3.5 border-t flex-shrink-0" style={{ borderColor: '#252525', background: '#0f0f0f' }}>
              <div className="text-[9px] font-bold uppercase tracking-widest mb-2" style={{ color: '#888' }}>Save as Template</div>
              <input
                value={templateSaveName}
                onChange={(e: any) => setTemplateSaveName(e.target.value)}
                placeholder="Template name…"
                className="w-full rounded border px-2 py-1.5 text-[10px] outline-none mb-2"
                style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}
                autoFocus
                onKeyDown={(e: any) => e.key === 'Enter' && confirmSaveTemplate()}
              />
              <div className="flex gap-2">
                <button
                  onClick={confirmSaveTemplate}
                  disabled={savingTemplate || !templateSaveName.trim()}
                  className="flex-1 py-1.5 rounded font-bold text-[10px] uppercase tracking-wider border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all disabled:opacity-25"
                >
                  {savingTemplate ? 'Saving…' : 'Save'}
                </button>
                <button
                  onClick={() => { setTemplateSaveDialog(false); setTemplateSaveName('') }}
                  className="py-1.5 px-3 rounded font-bold text-[10px] uppercase tracking-wider border border-[#313131] text-[#555] hover:border-[#444] hover:text-[#888] transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {activeTab === 'settings' ? (
          <SettingsPreview settings={settings} />
        ) : (
          <>
            <div className="flex-1 flex flex-col overflow-hidden min-h-0">
              <div className="flex items-center border-b flex-shrink-0" style={{ borderColor: '#252525', background: '#141414' }}>
                <div className="text-[10px] font-bold uppercase tracking-wider px-4 py-2.5 border-b-2 text-white border-white">
                  {activeTab === 'studio' ? 'Screenshots' : activeTab === 'templates' ? 'Preview' : 'Components'}
                </div>
                {tokens && activeTab !== 'templates' && (
                  <button onClick={handleRegenDemo} className="ml-auto mr-3 text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded border transition-all border-[#313131] text-[#555] hover:border-[#3d3d3d] hover:text-[#999]">↺ Refresh</button>
                )}
              </div>
              <div className="flex-1 overflow-auto relative min-h-0" style={{ background: '#1c1c1c' }}>
                {activeTab === 'studio' ? (
                  <StudioScreenshotPanel result={studioResult} generating={studioGenerating} tokens={tokens} availableFormats={availableFormats} setStudioResult={setStudioResult} />
                ) : activeTab === 'templates' ? (
                  <TemplatePreview html={templatePreviewHtml} />
                ) : tokens ? (
                  <PreviewFrame tokens={tokens} />
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#666' }}>
                    <div className="text-3xl opacity-25">◈</div>
                    <div className="text-[12px] font-semibold tracking-wide">No system generated</div>
                    <div className="text-[11px]" style={{ color: '#777' }}>Enter a vibe and generate</div>
                  </div>
                )}
                {generating && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 z-10" style={{ background: '#0b0b0b' }}>
                    <div className="w-7 h-7 border-2 rounded-full animate-spin" style={{ borderColor: '#313131', borderTopColor: '#fff' }} />
                    <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#555' }}>Building token system…</div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

/* ── Studio Tab ── */

function StudioTab({ mode, setMode, title, setTitle, content, setContent, slug, setSlug, generating, onGenerate, result }: any) {
  return (
    <>
      <div className="p-3.5 space-y-3 border-b" style={{ borderColor: '#252525' }}>
        <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Content Source</div>
        <div className="flex gap-1">
          <button onClick={() => setMode('content')} className={`flex-1 text-[9px] font-bold uppercase tracking-wider py-1.5 rounded border transition-all ${mode === 'content' ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>Direct</button>
          <button onClick={() => setMode('slug')} className={`flex-1 text-[9px] font-bold uppercase tracking-wider py-1.5 rounded border transition-all ${mode === 'slug' ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>Ghost Slug</button>
        </div>
        {mode === 'content' ? (
          <>
            <input value={title} onChange={(e: any) => setTitle(e.target.value)} placeholder="Post title…" className="w-full rounded border px-2.5 py-2 text-[11px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            <textarea value={content} onChange={(e: any) => setContent(e.target.value)} placeholder="Paste content or article text…" rows={4} className="w-full rounded border px-2.5 py-2 text-[11px] outline-none resize-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2', lineHeight: 1.5 }} />
          </>
        ) : (
          <input value={slug} onChange={(e: any) => setSlug(e.target.value)} placeholder="my-post-slug" className="w-full rounded border px-2.5 py-2 text-[11px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
        )}
        <div className="text-[8px]" style={{ color: '#444' }}>
          Settings from the Settings tab will be used (formats, post count, image mode)
        </div>
        <button onClick={onGenerate} disabled={generating} className="w-full py-3 rounded font-bold text-[11px] tracking-widest uppercase cursor-pointer transition-opacity disabled:opacity-25" style={{ background: '#fff', color: '#0b0b0b' }}>
          {generating ? 'Generating…' : 'Generate'}
        </button>
        {result && (
          <div className="p-2.5 rounded text-[10px] font-mono" style={{ background: '#0b0b0b', color: '#999', lineHeight: 1.6 }}>
            <div>Slug: {result.slug}</div>
            <div>Formats: {result.requested_formats?.join(', ')}</div>
            {result.classification && (
              <div className="mt-1 pt-1 border-t" style={{ borderColor: '#252525' }}>
                <div>Type: {result.classification.type}</div>
                <div>Template: {result.classification.templateUsed || 'AI generated'}</div>
              </div>
            )}
            {result.assets && <div className="mt-1 pt-1 border-t" style={{ borderColor: '#252525' }}>Assets: {Object.keys(result.assets).filter((k: string) => result.assets[k]).length}</div>}
          </div>
        )}
      </div>
    </>
  )
}

/* ── Templates Tab ── */

function FormatsTemplatesTab({ 
  templates, loading, editingTemplate, setEditingTemplate, templateHtml, setTemplateHtml, 
  openTemplateEditor, onSaveTemplate, onDeleteTemplate, onToggleTemplate, onUpdatePreview,
  formats, editingFormat, setEditingFormat, formatSaving, onOpenFormatEditor, onSaveFormat, onDeleteFormat 
}: any) {
  const [subTab, setSubTab] = useState<'formats' | 'templates'>('formats')

  return (
    <>
      {/* Sub-tab navigation */}
      <div className="flex border-b flex-shrink-0" style={{ borderColor: '#252525' }}>
        <button 
          onClick={() => setSubTab('formats')} 
          className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-wider border-b transition-all ${subTab === 'formats' ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#888]'}`}
        >
          Sizes
        </button>
        <button 
          onClick={() => setSubTab('templates')} 
          className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-wider border-b transition-all ${subTab === 'templates' ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#888]'}`}
        >
          Templates
        </button>
      </div>

      {/* Sizes Section */}
      {subTab === 'formats' && (
        <>
          <div className="p-3.5 space-y-2 border-b" style={{ borderColor: '#252525' }}>
            <div className="flex items-center justify-between">
              <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Output Sizes</div>
              <button onClick={() => onOpenFormatEditor()} className="text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all">+ New</button>
            </div>

            {editingFormat && (
              <div className="space-y-2 p-2.5 rounded border" style={{ background: '#0a0a0a', borderColor: '#313131' }}>
                <div className="text-[8px] font-bold uppercase tracking-widest" style={{ color: '#666' }}>
                  {editingFormat.isNew ? 'New Format' : 'Edit Format'}
                </div>
                <input
                  value={editingFormat.name}
                  onChange={(e: any) => setEditingFormat({ ...editingFormat, name: e.target.value })}
                  placeholder="Format name (e.g. Instagram Story)"
                  className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                  style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
                />
                {editingFormat.isNew && (
                  <input
                    value={editingFormat.id}
                    onChange={(e: any) => setEditingFormat({ ...editingFormat, id: e.target.value })}
                    placeholder="ID (e.g. ig-story, auto-generated if empty)"
                    className="w-full rounded border px-2 py-1.5 text-[10px] outline-none font-mono"
                    style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
                  />
                )}
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="text-[8px] font-bold uppercase tracking-wider block mb-1" style={{ color: '#555' }}>Width</label>
                    <input
                      type="number"
                      value={editingFormat.width}
                      onChange={(e: any) => setEditingFormat({ ...editingFormat, width: Number(e.target.value) })}
                      className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                      style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
                    />
                  </div>
                  <div className="flex-1">
                    <label className="text-[8px] font-bold uppercase tracking-wider block mb-1" style={{ color: '#555' }}>Height</label>
                    <input
                      type="number"
                      value={editingFormat.height}
                      onChange={(e: any) => setEditingFormat({ ...editingFormat, height: Number(e.target.value) })}
                      className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                      style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[8px] font-bold uppercase tracking-wider block mb-1" style={{ color: '#555' }}>AI Instructions</label>
                  <textarea
                    value={editingFormat.aiInstruction}
                    onChange={(e: any) => setEditingFormat({ ...editingFormat, aiInstruction: e.target.value })}
                    placeholder="Optional instructions for AI when generating for this format..."
                    rows={2}
                    className="w-full rounded border px-2 py-1.5 text-[10px] outline-none resize-none"
                    style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={onSaveFormat}
                    disabled={formatSaving}
                    className="flex-1 py-1.5 rounded font-bold text-[9px] uppercase tracking-wider border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all disabled:opacity-25"
                  >
                    {formatSaving ? 'Saving…' : 'Save Format'}
                  </button>
                  <button
                    onClick={() => setEditingFormat(null)}
                    className="py-1.5 px-3 rounded font-bold text-[9px] uppercase tracking-wider border border-[#313131] text-[#555] hover:border-[#444] hover:text-[#888] transition-all"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="p-3.5">
            {formats.length === 0 ? (
              <div className="p-4 text-center" style={{ color: '#555', fontSize: 11 }}>No formats configured. Add one to get started.</div>
            ) : (
              <div className="space-y-1">
                {formats.map((f: any) => (
                  <div key={f.id} className="flex items-center gap-2 p-2 rounded" style={{ background: '#0b0b0b' }}>
                    <button onClick={() => onOpenFormatEditor(f)} className="flex-1 text-left">
                      <div className="text-[10px] font-medium" style={{ color: '#e2e2e2' }}>{f.label}</div>
                      <div className="text-[8px]" style={{ color: '#555' }}>
                        {f.dims}
                        {f.aiInstruction && <span className="ml-1.5 px-1 py-0.5 rounded" style={{ background: '#1c1c1c' }}>AI hints</span>}
                      </div>
                    </button>
                    <button
                      onClick={() => onDeleteFormat(f.id)}
                      className="text-[8px] px-1.5 py-0.5 rounded border border-[#f43f5e] text-[#f43f5e] hover:bg-[#f43f5e15] transition-all"
                    >
                      Del
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Templates Section */}
      {subTab === 'templates' && (
        <>
          <div className="p-3.5 space-y-2 border-b" style={{ borderColor: '#252525' }}>
            <div className="flex items-center justify-between">
              <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>HTML Templates</div>
              <button onClick={() => openTemplateEditor()} className="text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all">+ New</button>
            </div>

            {editingTemplate && (
              <div className="space-y-2">
                <input
                  value={editingTemplate.name}
                  onChange={(e: any) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                  placeholder="Template name"
                  className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                  style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}
                />
                <input
                  value={editingTemplate.description}
                  onChange={(e: any) => setEditingTemplate({ ...editingTemplate, description: e.target.value })}
                  placeholder="Description"
                  className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                  style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}
                />
                <div className="flex gap-2">
                  <input
                    value={editingTemplate.id}
                    onChange={(e: any) => setEditingTemplate({ ...editingTemplate, id: e.target.value })}
                    placeholder="ID (e.g. quote-card)"
                    className="flex-1 rounded border px-2 py-1.5 text-[10px] font-mono outline-none"
                    style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}
                  />
                  <select
                    value={editingTemplate.category}
                    onChange={(e: any) => setEditingTemplate({ ...editingTemplate, category: e.target.value })}
                    className="rounded border px-2 py-1.5 text-[10px] outline-none"
                    style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}
                  >
                    <option value="quote">Quote</option>
                    <option value="metric">Metric</option>
                    <option value="list">List</option>
                    <option value="carousel">Carousel</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>
                <textarea
                  value={templateHtml}
                  onChange={(e: any) => { setTemplateHtml(e.target.value); onUpdatePreview(e.target.value) }}
                  placeholder="HTML template with slots {{headline}}, {{body}}, etc."
                  rows={8}
                  className="w-full rounded border px-2 py-1.5 text-[10px] font-mono outline-none resize-none"
                  style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2', lineHeight: 1.4 }}
                />
                <div className="flex gap-2">
                  <button
                    onClick={onSaveTemplate}
                    className="flex-1 py-1.5 rounded font-bold text-[9px] uppercase tracking-wider border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all"
                  >
                    Save Template
                  </button>
                  <button
                    onClick={() => { setEditingTemplate(null); setTemplateHtml('') }}
                    className="py-1.5 px-3 rounded font-bold text-[9px] uppercase tracking-wider border border-[#313131] text-[#555] hover:border-[#444] hover:text-[#888] transition-all"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="p-3.5">
            {loading ? (
              <div className="flex items-center justify-center py-4"><div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: '#313131', borderTopColor: '#fff' }} /></div>
            ) : templates.length === 0 ? (
              <div className="p-4 text-center" style={{ color: '#555', fontSize: 11 }}>No templates yet. Create one to get started.</div>
            ) : (
              <div className="space-y-1">
                {templates.map((t: any) => (
                  <div key={t.id} className="flex items-center gap-2 p-2 rounded" style={{ background: '#0b0b0b', opacity: t.enabled ? 1 : 0.5 }}>
                    <button
                      onClick={() => onToggleTemplate(t.id, !t.enabled)}
                      className={`text-[8px] font-mono px-1.5 py-0.5 rounded ${t.enabled ? 'text-[#22c55e]' : 'text-[#555]'}`}
                    >
                      {t.enabled ? 'ON' : 'OFF'}
                    </button>
                    <button onClick={() => openTemplateEditor(t)} className="flex-1 text-left">
                      <div className="text-[10px] font-medium">{t.name || t.id}</div>
                      <div className="text-[8px]" style={{ color: '#555' }}>{t.category} · {t.slots?.length || 0} slots</div>
                    </button>
                    <button onClick={() => onDeleteTemplate(t.id)} className="text-[8px] px-1.5 py-0.5 rounded border border-[#f43f5e] text-[#f43f5e] hover:bg-[#f43f5e15]">Del</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </>
  )
}

/* ── Formats Tab ── */



/* ── Settings Tab ── */

function SettingsTab({ settings, loading, onSave, formats }: any) {
  const [local, setLocal] = useState<any>(null)
  const [apiKey, setApiKeyState] = useState(getApiKey())
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({
    strategy: false,  // brand + campaign combined
    output: false,   // formats + image + templates
    prompts: true,     // AI prompts
    advanced: true,   // api + connections
  })

  useEffect(() => {
    if (settings) setLocal(JSON.parse(JSON.stringify(settings)))
  }, [settings])

  const handleApiKeyChange = (value: string) => {
    setApiKeyState(value)
    setApiKey(value)
  }

  const toggleSection = (section: string) => {
    setCollapsedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  if (loading || !local) {
    return <div className="flex items-center justify-center h-32" style={{ color: '#555' }}><div className="w-5 h-5 border-2 rounded-full animate-spin" style={{ borderColor: '#313131', borderTopColor: '#fff' }} /></div>
  }

  function set(path: string[], value: any) {
    setLocal((prev: any) => {
      const next = JSON.parse(JSON.stringify(prev))
      let obj = next
      for (let i = 0; i < path.length - 1; i++) obj = obj[path[i]]
      obj[path[path.length - 1]] = value
      return next
    })
  }

  function handleSave() {
    onSave(local)
  }

  function Section({ id, label, children, defaultCollapsed = false }: { id: string; label: string; children: React.ReactNode; defaultCollapsed?: boolean }) {
    const isCollapsed = collapsedSections[id] ?? defaultCollapsed
    return (
      <div className="border-b" style={{ borderColor: '#252525' }}>
        <button
          onClick={() => toggleSection(id)}
          className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-white/5 transition-colors"
        >
          <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#888' }}>{label}</span>
          <span className="text-[10px]" style={{ color: '#555' }}>{isCollapsed ? '▼' : '▲'}</span>
        </button>
        {!isCollapsed && <div className="px-3 pb-3 space-y-2">{children}</div>}
      </div>
    )
  }

  return (
    <>
      <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 140px)' }}>
        {/* Combined Strategy Section */}
        <Section id="strategy" label="Strategy" defaultCollapsed={false}>
          <input value={local.brand?.name || ''} onChange={(e: any) => set(['brand', 'name'], e.target.value)} placeholder="Brand name" className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
          <div className="flex gap-2 items-center">
            <input value={local.brand?.logo_url || ''} onChange={(e: any) => set(['brand', 'logo_url'], e.target.value)} placeholder="Brand Logo URL or base64" className="flex-1 rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            <input type="file" id="logoUpload" className="hidden" accept="image/*" onChange={async (e) => {
              const file = e.target.files?.[0]
              if (!file) return
              const reader = new FileReader()
              reader.onload = (re) => set(['brand', 'logo_url'], re.target?.result as string)
              reader.readAsDataURL(file)
            }} />
            <button onClick={() => document.getElementById('logoUpload')?.click()} className="whitespace-nowrap px-3 py-1.5 rounded transition-all text-[10px] font-bold" style={{ background: '#252525', color: '#fff' }}>Upload</button>
            {local.brand?.logo_url && <img src={local.brand.logo_url} alt="Logo" className="w-6 h-6 object-contain rounded" style={{ background: '#fff' }} />}
          </div>
          <input value={local.brand?.tone || ''} onChange={(e: any) => set(['brand', 'tone'], e.target.value)} placeholder="Tone (e.g. confident, practical)" className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
          <select value={local.campaign?.goal || 'awareness'} onChange={(e: any) => set(['campaign', 'goal'], e.target.value)} className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}>
            <option value="awareness">Goal: Awareness</option>
            <option value="engagement">Goal: Engagement</option>
            <option value="conversion">Goal: Conversion</option>
            <option value="education">Goal: Education</option>
          </select>
          <input value={local.campaign?.cta || ''} onChange={(e: any) => set(['campaign', 'cta'], e.target.value)} placeholder="Default CTA (e.g. Read more →)" className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
        </Section>

        {/* Combined Output Section */}
        <Section id="output" label="Output" defaultCollapsed={false}>
          <div className="flex flex-wrap gap-1">
            {formats.map((f: any) => (
              <button
                key={f.id}
                onClick={() => {
                  const enabled = local.formats?.enabled || []
                  const next = enabled.includes(f.id) ? enabled.filter((id: string) => id !== f.id) : [...enabled, f.id]
                  set(['formats', 'enabled'], next)
                }}
                className={`text-[9px] font-bold tracking-wider px-2 py-1 rounded border transition-all ${(local.formats?.enabled || []).includes(f.id) ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-[9px]" style={{ color: '#777' }}>Posts:</span>
            <input type="number" value={local.formats?.postCount || 1} onChange={(e: any) => set(['formats', 'postCount'], Number(e.target.value))} min={1} max={10} className="w-14 rounded border px-2 py-1 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            <span className="text-[9px]" style={{ color: '#777' }}>Images:</span>
            <select value={local.image?.mode || 'auto'} onChange={(e: any) => set(['image', 'mode'], e.target.value)} className="flex-1 rounded border px-2 py-1 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}>
              <option value="auto">Auto</option>
              <option value="none">None</option>
              <option value="ai">AI</option>
              <option value="feature">Feature</option>
            </select>
          </div>
          <div className="flex items-center justify-between py-1 px-2 rounded mt-2" style={{ background: '#0b0b0b' }}>
            <span className="text-[10px]" style={{ color: '#999' }}>Auto templates</span>
            <button onClick={() => set(['templates', 'autoSelect'], !local.templates?.autoSelect)} className={`text-[10px] font-mono px-2 py-0.5 rounded border ${local.templates?.autoSelect ? 'border-[#22c55e] text-[#22c55e]' : 'border-[#555] text-[#555]'}`}>
              {local.templates?.autoSelect ? 'ON' : 'OFF'}
            </button>
          </div>
        </Section>

        {/* Prompts Section (collapsed by default) */}
        <Section id="prompts" label="AI Personalities & Prompts" defaultCollapsed={true}>
          <div className="space-y-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Content Classifier</div>
              <textarea value={local.prompts?.contentClassification || ''} onChange={(e: any) => set(['prompts', 'contentClassification'], e.target.value)} placeholder="Guidelines for extracting content metadata and tags..." className="w-full h-16 rounded border px-2 py-1.5 text-[10px] outline-none resize-none font-mono" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Orchestrator Rules</div>
              <textarea value={local.prompts?.contentCreation || ''} onChange={(e: any) => set(['prompts', 'contentCreation'], e.target.value)} placeholder="Marketing strategy and campaign generation guidelines..." className="w-full h-16 rounded border px-2 py-1.5 text-[10px] outline-none resize-none font-mono" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Image Generation Guidelines</div>
              <textarea value={local.prompts?.imageGeneration || ''} onChange={(e: any) => set(['prompts', 'imageGeneration'], e.target.value)} placeholder="Guidelines for deciding on AI background images..." className="w-full h-16 rounded border px-2 py-1.5 text-[10px] outline-none resize-none font-mono" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Template Selection Rules</div>
              <textarea value={local.prompts?.templateSelection || ''} onChange={(e: any) => set(['prompts', 'templateSelection'], e.target.value)} placeholder="Criteria to choose HTML template vs generate new layout..." className="w-full h-16 rounded border px-2 py-1.5 text-[10px] outline-none resize-none font-mono" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Layout Engineer (HTML)</div>
              <textarea value={local.prompts?.htmlGeneration || ''} onChange={(e: any) => set(['prompts', 'htmlGeneration'], e.target.value)} placeholder="Instructions for Tailwind layout generation..." className="w-full h-16 rounded border px-2 py-1.5 text-[10px] outline-none resize-none font-mono" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Design Token Architect</div>
              <textarea value={local.prompts?.designTokens || ''} onChange={(e: any) => set(['prompts', 'designTokens'], e.target.value)} placeholder="Rules for typography, shadow, and color scale generation..." className="w-full h-16 rounded border px-2 py-1.5 text-[10px] outline-none resize-none font-mono" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Global Rules (Applied Everywhere)</div>
              <textarea value={local.prompts?.customInstructions || ''} onChange={(e: any) => set(['prompts', 'customInstructions'], e.target.value)} placeholder="e.g. Always write out full numbers instead of using digits..." className="w-full h-16 rounded border px-2 py-1.5 text-[10px] outline-none resize-none font-mono" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
            </div>
          </div>
        </Section>

        {/* Advanced Section (collapsed by default) */}
        <Section id="advanced" label="Webhook & API Connections" defaultCollapsed={true}>
          <div className="space-y-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Authentication</div>
              <input
                type="password"
                value={apiKey}
                onChange={(e: any) => handleApiKeyChange(e.target.value)}
                placeholder="API Key..."
                className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
              />
              <div className="text-[8px] mt-1" style={{ color: '#666' }}>
                {apiKey ? <span style={{ color: '#22c55e' }}>✓ Configured</span> : <span style={{ color: '#f43f5e' }}>✗ Missing</span>}
              </div>
            </div>

            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Ghost CMS Webhook</div>
              <div className="space-y-2">
                <input
                  type="text"
                  value={local.integrations?.ghost?.url || ''}
                  onChange={(e: any) => set(['integrations', 'ghost', 'url'], e.target.value)}
                  placeholder="https://your-ghost-url.com"
                  className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                  style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
                />
                <input
                  type="password"
                  value={local.integrations?.ghost?.token || ''}
                  onChange={(e: any) => set(['integrations', 'ghost', 'token'], e.target.value)}
                  placeholder="Ghost Admin API Key..."
                  className="w-full rounded border px-2 py-1.5 text-[10px] outline-none"
                  style={{ background: '#0b0b0b', borderColor: '#252525', color: '#e2e2e2' }}
                />
                <label className="flex items-center gap-2 cursor-pointer mt-2 text-[10px]">
                  <input
                    type="checkbox"
                    checked={local.integrations?.ghost?.enabled || false}
                    onChange={(e: any) => set(['integrations', 'ghost', 'enabled'], e.target.checked)}
                    className="accent-blue-500"
                  />
                  <span style={{ color: '#888' }}>Enable Ghost Webhook</span>
                </label>
              </div>
            </div>
            
          </div>
        </Section>
      </div>
      <div className="p-3 border-t flex-shrink-0" style={{ borderColor: '#252525' }}>
        <button onClick={handleSave} className="w-full py-2 rounded font-bold text-[10px] uppercase tracking-wider border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all">
          Save
        </button>
      </div>
    </>
  )
}

function SettingsPreview({ settings }: any) {
  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: '#0b0b0b' }}>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Current Settings</h2>
          {settings ? (
            <div className="space-y-4">
              <div style={{ padding: 16, borderRadius: 8, background: '#141414', border: '1px solid #252525' }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Brand</div>
                <div style={{ fontSize: 11, color: '#999' }}>Name: {settings.brand?.name}</div>
                <div style={{ fontSize: 11, color: '#999' }}>Tone: {settings.brand?.tone}</div>
                <div style={{ fontSize: 11, color: '#999' }}>Audience: {settings.brand?.audience}</div>
              </div>
              <div style={{ padding: 16, borderRadius: 8, background: '#141414', border: '1px solid #252525' }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Campaign</div>
                <div style={{ fontSize: 11, color: '#999' }}>Goal: {settings.campaign?.goal}</div>
                <div style={{ fontSize: 11, color: '#999' }}>Framework: {settings.campaign?.framework}</div>
                <div style={{ fontSize: 11, color: '#999' }}>CTA: {settings.campaign?.cta || 'None'}</div>
              </div>
              <div style={{ padding: 16, borderRadius: 8, background: '#141414', border: '1px solid #252525' }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Formats</div>
                <div style={{ fontSize: 11, color: '#999' }}>Enabled: {(settings.formats?.enabled || []).join(', ')}</div>
                <div style={{ fontSize: 11, color: '#999' }}>Post count: {settings.formats?.postCount}</div>
              </div>
              <div style={{ padding: 16, borderRadius: 8, background: '#141414', border: '1px solid #252525' }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Templates</div>
                <div style={{ fontSize: 11, color: '#999' }}>Auto-select: {settings.templates?.autoSelect ? 'Yes' : 'No'}</div>
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 11, color: '#555' }}>Loading settings…</div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Studio Screenshot Panel ── */

function StudioScreenshotPanel({ result, generating, tokens, availableFormats, setStudioResult }: { result: any; generating: boolean; tokens: DesignTokens | null; availableFormats: any[]; setStudioResult: (result: any) => void }) {
  const entries = Object.entries(result?.assets || {}).filter(([, asset]: [string, any]) => Boolean(asset?.key || asset?.url)) as Array<[string, any]>
  const [editingFormat, setEditingFormat] = useState<string | null>(null)
  const [slotValues, setSlotValues] = useState<Record<string, string>>({})
  const [templateHtml, setTemplateHtml] = useState<string>('')
  const [previewHtml, setPreviewHtml] = useState<string>('')
  const [editorGenerating, setEditorGenerating] = useState(false)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [previewZoom, setPreviewZoom] = useState(1)
  const [previewOffset, setPreviewOffset] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const [previewWidth, setPreviewWidth] = useState(1080)
  const [previewHeight, setPreviewHeight] = useState(1350)

  // Extract slots from HTML
  function extractSlots(html: string): string[] {
    const slots = new Set<string>()
    const pattern = /\{\{(\w+)\}\}/g
    let match
    while ((match = pattern.exec(html)) !== null) {
      slots.add(match[1])
    }
    return Array.from(slots)
  }

  // Fill template with slot values
  function fillTemplate(html: string, values: Record<string, string>): string {
    let result = html
    for (const [key, value] of Object.entries(values)) {
      result = result.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value)
    }
    return result
  }

  // Auto-render preview when slot values change
  const previewTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  useEffect(() => {
    if (!templateHtml || !tokens || !editingFormat) return
    if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current)
    previewTimeoutRef.current = setTimeout(() => {
      const filledHtml = fillTemplate(templateHtml, slotValues)
      const fonts = [
        tokens.typography?.fontSans,
        tokens.typography?.fontSerif,
        tokens.typography?.fontMono
      ].filter(Boolean).map(f => f?.replace(/\s+/g, '+'))
      
      const fontImport = fonts.length > 0 
        ? `<link href="https://fonts.googleapis.com/css2?${fonts.map(f => `family=${f}:wght@300;400;500;600;700;900`).join('&')}&display=swap" rel="stylesheet">`
        : ''
      
      const cssVars = tokensToCSS(tokens)
      
      let finalHtml = filledHtml
      finalHtml = finalHtml.replace('</head>', `${fontImport}\n</head>`)
      finalHtml = finalHtml.replace('<style id="token-styles"></style>', `<style id="token-styles">${cssVars}</style>`)
      if (!finalHtml.includes('id="token-styles"')) {
        finalHtml = finalHtml.replace('</head>', `<style id="token-styles">${cssVars}</style>\n</head>`)
      }
      if (!finalHtml.includes('cdn.tailwindcss.com')) {
        finalHtml = finalHtml.replace('</head>', `<script src="https://cdn.tailwindcss.com"></script>\n</head>`)
      }

      setPreviewHtml(finalHtml)
    }, 300)
    return () => { if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current) }
  }, [slotValues, templateHtml, tokens, editingFormat])

  const handleDownloadAll = async () => {
    const zip = new JSZip();
    for (const [format, asset] of entries) {
      if (asset.url && asset.url.startsWith('data:image/png;base64,')) {
        const base64Data = asset.url.replace(/^data:image\/png;base64,/, '');
        zip.file(`${format}.png`, base64Data, { base64: true });
      } else if (asset.url) {
        try {
          const res = await fetch(asset.url);
          const blob = await res.blob();
          zip.file(`${format}.png`, blob);
        } catch (e) {
          console.error('Failed to fetch', format, e);
        }
      }
    }
    const content = await zip.generateAsync({ type: 'blob' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(content);
    link.download = 'tasbir-assets.zip';
    link.click();
  };

  const handleEdit = (format: string, _asset: any, _resolvedSrc: string) => {
    setEditingFormat(format)
    // Set preview dimensions from format config
    const fmt = availableFormats.find((f: any) => f.id === format)
    if (fmt) {
      setPreviewWidth(fmt.width || 1080)
      setPreviewHeight(fmt.height || 1350)
    }
    // Use template HTML (with placeholders) for editing, not the filled HTML
    const templateHtml = result?.template_html_by_format?.[format] || result?.templateHtmlByFormat?.[format]
    const slotValues = result?.slot_values_by_format?.[format] || result?.slotValuesByFormat?.[format]
    
    if (templateHtml) {
      // Use template HTML which has {{slot}} placeholders
      setTemplateHtml(templateHtml)
      const slots = extractSlots(templateHtml)
      const initialValues: Record<string, string> = {}
      
      // Use slot values directly from the response if available
      if (slotValues && Object.keys(slotValues).length > 0) {
        for (const slot of slots) {
          initialValues[slot] = slotValues[slot] || ''
        }
      } else {
        // Fallback: leave empty for user to fill
        slots.forEach(slot => initialValues[slot] = '')
      }
      setSlotValues(initialValues)
    } else {
      setTemplateHtml(`// HTML for ${format}\n// Edit the content below and preview updates automatically`)
      setSlotValues({})
    }
    setPreviewHtml('')
    setEditorError(null)
  }

  const handleSave = async () => {
    if (!templateHtml || !editingFormat || !result || !tokens) return
    if (Object.values(slotValues).every(v => !v.trim())) return
    setEditorGenerating(true)
    try {
      const apiKey = (import.meta.env.VITE_API_KEY || "").trim() || window.localStorage.getItem("tasbir:api-key")?.trim() || ""
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (apiKey) headers["x-api-key"] = apiKey
      
      // Find the format config for width/height
      const formatConfig = availableFormats.find((f: any) => f.id === editingFormat)
      if (!formatConfig) throw new Error('Format not found')
      
      // Fill template with slot values
      let filledHtml = templateHtml
      for (const [key, value] of Object.entries(slotValues)) {
        filledHtml = filledHtml.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value)
      }
      
      // Use the new render-html endpoint to re-render the edited HTML
      const response = await fetch(`/render-html`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          html: filledHtml,
          width: formatConfig.width,
          height: formatConfig.height,
          format: editingFormat,
          slug: result.slug,
          designTokens: tokens,
          slot_values: slotValues,
        })
      })
      
      if (!response.ok) {
        const err = await response.json().catch(() => ({ error: 'Render failed' }))
        throw new Error(err.error || 'Failed to re-render')
      }
      
      const data = await response.json()
      
      // Update the asset in the result to show the new render
      // Also update the html_by_format and template_html_by_format with the new HTML
      setStudioResult((prev: any) => {
        if (!prev) return prev
        return {
          ...prev,
          assets: {
            ...prev.assets,
            [editingFormat]: data.asset
          },
          html_by_format: {
            ...prev.html_by_format,
            [editingFormat]: filledHtml
          },
          template_html_by_format: {
            ...prev.template_html_by_format,
            [editingFormat]: templateHtml
          }
        }
      })
      
      setEditingFormat(null)
      setSlotValues({})
      setTemplateHtml('')
      setPreviewHtml('')
      alert('Saved and re-rendered!')
    } catch (e: any) {
      setEditorError(e.message || 'Save failed')
    } finally {
      setEditorGenerating(false)
    }
  }

  const handleCloseEditor = () => {
    setEditingFormat(null)
    setSlotValues({})
    setTemplateHtml('')
    setPreviewHtml('')
    setEditorError(null)
  }

  if (generating) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#666' }}>
        <div className="w-6 h-6 border-2 rounded-full animate-spin" style={{ borderColor: '#313131', borderTopColor: '#fff' }} />
        <div className="text-[11px]" style={{ color: '#888' }}>Rendering screenshots…</div>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#666' }}>
        <div className="text-3xl opacity-25">▣</div>
        <div className="text-[12px] font-semibold tracking-wide">No Screenshots Yet</div>
        <div className="text-[11px]" style={{ color: '#777' }}>Generate from Studio to view results here</div>
      </div>
    )
  }

  if (entries.length === 0) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#666' }}>
        <div className="text-3xl opacity-25">◻</div>
        <div className="text-[12px] font-semibold tracking-wide">No Rendered Assets</div>
        <div className="text-[11px]" style={{ color: '#777' }}>Try Generate</div>
      </div>
    )
  }

  return (
    <>
      <div className="flex justify-end px-4 pt-4 pb-0">
        <button onClick={handleDownloadAll} className="px-4 py-2 rounded text-[11px] font-bold uppercase tracking-wider bg-white text-black transition-opacity hover:opacity-90">
          Download ZIP
        </button>
      </div>
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        {entries.map(([format, asset]) => (
          <AssetPreviewCard 
            key={format} 
            format={format} 
            asset={asset} 
            isEditing={editingFormat === format}
            onEdit={handleEdit}
          />
        ))}
      </div>

      {/* Inline Editor Overlay */}
      {editingFormat && (
        <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'rgba(0, 0, 0, 0.95)' }}>
          <div className="flex items-center justify-between p-3 border-b" style={{ borderColor: '#252525', background: '#141414' }}>
            <div className="flex items-center gap-3">
              <button onClick={handleCloseEditor} className="p-1 rounded hover:bg-[#252525]" style={{ color: '#888' }}>✕</button>
              <span className="font-medium text-white">{editingFormat}</span>
              <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: '#3b82f6', color: 'white' }}>EDITING</span>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={handleSave} 
                disabled={editorGenerating || Object.values(slotValues).every(v => !v.trim())}
                className="px-3 py-1.5 rounded font-bold text-[10px] uppercase tracking-wider border border-[#3b82f6] text-[#3b82f6] hover:bg-[#3b82f615] disabled:opacity-25"
              >
                Save & Re-render
              </button>
            </div>
          </div>

          <div className="flex-1 flex overflow-hidden">
            {/* Content Editor - Slot-based */}
            <div className="w-1/2 flex flex-col border-r" style={{ borderColor: '#252525', background: '#0b0b0b', minWidth: 300 }}>
              <div className="px-2 py-1 border-b" style={{ borderColor: '#252525' }}>
                <span className="text-[9px] font-medium" style={{ color: '#888' }}>Content</span>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-3">
                {Object.keys(slotValues).length === 0 ? (
                  <div className="text-[11px] text-center text-[#888] py-8">No editable content slots found</div>
                ) : (
                  Object.entries(slotValues).map(([slot, value]) => (
                    <div key={slot} className="space-y-1">
                      <label className="text-[9px] font-medium uppercase tracking-wider" style={{ color: '#888' }}>{slot}</label>
                      <textarea
                        value={value}
                        onChange={(e) => setSlotValues(prev => ({ ...prev, [slot]: e.target.value }))}
                        className="w-full resize-none p-2 text-[11px] font-mono outline-none"
                        style={{ background: '#0a0a0a', borderColor: '#313131', color: '#e2e2e2', lineHeight: 1.5, fontFamily: 'monospace' }}
                        placeholder={`Enter ${slot}...`}
                        spellCheck={false}
                        rows={slot.includes('body') || slot.includes('content') ? 4 : 2}
                      />
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Live Preview */}
            <div className="flex-1 flex flex-col overflow-hidden" style={{ background: '#1a1a1a', minWidth: 300 }}>
              <div className="flex items-center justify-between px-2 py-1 border-b" style={{ borderColor: '#252525' }}>
                <span className="text-[9px] font-medium" style={{ color: '#888' }}>Live Preview</span>
                <div className="flex items-center gap-1">
                  <button onClick={() => setPreviewZoom(Math.max(0.1, previewZoom - 0.1))} className="p-1 rounded hover:bg-[#333]" style={{ color: '#aaa', fontSize: 14, lineHeight: 1 }} title="Zoom out">−</button>
                  <span className="text-[9px] font-mono min-w-[36px] text-center" style={{ color: '#aaa' }}>{Math.round(previewZoom * 100)}%</span>
                  <button onClick={() => setPreviewZoom(Math.min(3, previewZoom + 0.1))} className="p-1 rounded hover:bg-[#333]" style={{ color: '#aaa', fontSize: 14, lineHeight: 1 }} title="Zoom in">+</button>
                  <button onClick={() => { setPreviewZoom(1); setPreviewOffset({ x: 0, y: 0 }); }} className="px-1.5 py-1 rounded hover:bg-[#333]" style={{ color: '#aaa', fontSize: 10 }} title="Reset zoom">Fit</button>
                </div>
              </div>
              <div 
                className="flex-1 overflow-auto"
                style={{ background: '#1a1a1a', cursor: isPanning ? 'grabbing' : 'grab' }}
                onMouseDown={(e) => {
                  if (e.button === 0) {
                    setIsPanning(true)
                    setPanStart({ x: e.clientX - previewOffset.x, y: e.clientY - previewOffset.y })
                    e.preventDefault()
                  }
                }}
                onMouseMove={(e) => {
                  if (isPanning) {
                    setPreviewOffset({ x: e.clientX - panStart.x, y: e.clientY - panStart.y })
                  }
                }}
                onMouseUp={() => setIsPanning(false)}
                onMouseLeave={() => setIsPanning(false)}
                onWheel={(e) => {
                  if (e.ctrlKey || e.metaKey) {
                    e.preventDefault()
                    const delta = e.deltaY > 0 ? -0.1 : 0.1
                    setPreviewZoom(prev => Math.max(0.1, Math.min(3, prev + delta)))
                  }
                }}
              >
                <div className="flex items-start justify-start p-6" style={{ minWidth: 'max-content', minHeight: 'max-content' }}>
                {previewHtml ? (
                  <div 
                    style={{ 
                      transformOrigin: 'top left',
                      transform: `translate(${previewOffset.x}px, ${previewOffset.y}px) scale(${previewZoom})`,
                      background: '#fff',
                      flexShrink: 0,
                      boxShadow: '0 0 40px rgba(0,0,0,0.5)',
                    }}
                  >
                    <iframe
                      srcDoc={previewHtml}
                      className="border-0 block"
                      style={{ 
                        background: '#fff',
                        width: previewWidth,
                        height: previewHeight,
                        border: 'none',
                        pointerEvents: 'none',
                      }}
                      sandbox="allow-scripts allow-same-origin"
                    />
                  </div>
                ) : (
                  <div className="flex items-center justify-center text-[11px]" style={{ color: '#888', minHeight: 200, minWidth: 300 }}>
                    Live preview updates as you type...
                  </div>
                )}
                </div>
              </div>
              {editorError && (
                <div className="absolute bottom-4 left-4 right-4 p-2 rounded text-[10px]" style={{ background: '#f43f5e', color: 'white' }}>
                  {editorError}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function TemplatePreview({ html }: { html: string }) {
  if (!html) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#666' }}>
        <div className="text-3xl opacity-25">◈</div>
        <div className="text-[12px] font-semibold tracking-wide">No Template Preview</div>
        <div className="text-[11px]" style={{ color: '#777' }}>Select or create a template to preview</div>
      </div>
    )
  }

  return (
    <div className="absolute inset-0">
      <iframe
        srcDoc={html}
        title="Template Preview"
        className="w-full h-full border-0"
        style={{ background: '#fff' }}
      />
    </div>
  )
}

function AssetPreviewCard({ format, asset, isEditing, onEdit }: { format: string; asset: any; isEditing: boolean; onEdit?: (format: string, asset: any, resolvedSrc: string) => void }) {
  const [resolvedSrc, setResolvedSrc] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [savingR2, setSavingR2] = useState(false)
  const [savedR2, setSavedR2] = useState(false)

  useEffect(() => {
    let active = true
    let localBlobUrl: string | null = null

    async function load() {
      if (asset?.url && (asset.url.startsWith('data:') || asset.url.startsWith('http'))) {
        setResolvedSrc(asset.url)
        setLoading(false)
        return
      }

      if (!asset?.key) {
        setResolvedSrc(asset?.url || '')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        const blobUrl = await api.fetchAssetBlobUrl(asset.key)
        if (!active) {
          URL.revokeObjectURL(blobUrl)
          return
        }
        localBlobUrl = blobUrl
        setResolvedSrc(blobUrl)
      } catch {
        if (active) {
          setResolvedSrc(asset?.url || '')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    load()

    return () => {
      active = false
      if (localBlobUrl) URL.revokeObjectURL(localBlobUrl)
    }
  }, [asset?.key, asset?.url])

  const handleSaveToR2 = async () => {
    if (!asset?.key || !resolvedSrc.startsWith('data:image')) return;
    try {
      setSavingR2(true);
      await api.saveToR2(asset.key, resolvedSrc);
      setSavedR2(true);
      setTimeout(() => setSavedR2(false), 2000);
    } catch (e) {
      console.error(e);
      alert('Failed to save to R2');
    } finally {
      setSavingR2(false);
    }
  }

  if (isEditing) {
    return (
      <div className="rounded overflow-hidden self-start relative ring-2" style={{ background: '#111', borderColor: '#3b82f6' }}>
        <div className="absolute top-2 left-2 bg-[#3b82f6] text-white px-2 py-0.5 rounded text-[8px] font-bold tracking-wider">
          EDITING
        </div>
        <img
          src={resolvedSrc}
          alt={`${format} screenshot`}
          className="w-full h-auto block opacity-50"
          loading="lazy"
        />
      </div>
    )
  }

  return (
    <div
      className="rounded overflow-hidden self-start relative group"
      style={{ background: '#111' }}
      aria-label={`${format} screenshot card`}
    >
      {resolvedSrc ? (
        <>
          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity z-10 flex gap-2">
            {resolvedSrc.startsWith('data:image') && (
              <button 
                onClick={handleSaveToR2} 
                disabled={savingR2 || savedR2}
                className="bg-black/80 text-white px-3 py-1.5 rounded text-[10px] font-bold tracking-wider uppercase border border-white/20 hover:bg-black"
              >
                {savingR2 ? 'Saving...' : savedR2 ? 'Saved!' : 'Save to R2'}
              </button>
            )}
          </div>
          <img
            src={resolvedSrc}
            alt={`${format} screenshot`}
            className="w-full h-auto block cursor-zoom-in"
            loading="lazy"
            onClick={() => onEdit?.(format, asset, resolvedSrc)}
          />
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEdit?.(format, asset, resolvedSrc);
            }}
            className="absolute bottom-2 left-2 bg-black/80 text-white px-2 py-1 rounded text-[9px] font-medium tracking-wider uppercase border border-white/20 hover:bg-black"
          >
            Edit HTML
          </button>
        </>
      ) : (
        <div className="w-full flex items-center justify-center text-[9px]" style={{ minHeight: 120, color: '#666' }}>
          {loading ? 'Loading preview…' : 'Preview unavailable'}
        </div>
      )}
    </div>
  )
}

/* ── Tokens Tab ── */

function TokensTab({ vibeInput, setVibeInput, activePreset, applyPreset, primaryColorHint, setPrimaryColorHint, secondaryColorHint, setSecondaryColorHint, generating, generateTokens, tokens, expandedSections, toggleSection, onUpdateTokenColor, onUpdateAccentColor, fontSearches, setFontSearches, fontCategories, setFontCategories, designInstructions, setDesignInstructions, onUpdateFont, onSaveAsTemplate, studioResult }: any) {
  return (
    <>
      <div className="p-4 border-b" style={{ borderColor: '#252525' }}>
        <div className="text-[10px] font-semibold tracking-wide uppercase mb-2" style={{ color: '#888' }}>Vibe</div>
        <textarea value={vibeInput} onChange={(e: any) => setVibeInput(e.target.value)} placeholder="cold brutalist luxury…" rows={3} className="w-full rounded border resize-none outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2', fontFamily: 'inherit', fontSize: 13, padding: '10px 12px', lineHeight: 1.6 }} />
        
        <div className="mt-3">
          <div className="text-[9px] font-semibold tracking-wide uppercase mb-2" style={{ color: '#888' }}>Color Hints (optional)</div>
          <div className="flex gap-2">
            <div className="flex-1">
              <div className="text-[9px] font-semibold tracking-wide uppercase mb-1" style={{ color: '#888' }}>Primary</div>
              <div className="flex items-center gap-2">
                <input type="color" value={primaryColorHint || '#3b82f6'} onChange={(e: any) => setPrimaryColorHint(e.target.value)} className="w-7 h-7 rounded border-0 cursor-pointer" />
                <input value={primaryColorHint} onChange={(e: any) => setPrimaryColorHint(e.target.value)} placeholder="#hex" className="flex-1 bg-[#0b0b0b] border border-[#313131] rounded px-2 py-1.5 text-[11px] font-mono outline-none" style={{ color: '#e2e2e2' }} />
              </div>
            </div>
            <div className="flex-1">
              <div className="text-[9px] font-semibold tracking-wide uppercase mb-1" style={{ color: '#888' }}>Secondary</div>
              <div className="flex items-center gap-2">
                <input type="color" value={secondaryColorHint || '#0f172a'} onChange={(e: any) => setSecondaryColorHint(e.target.value)} className="w-7 h-7 rounded border-0 cursor-pointer" />
                <input value={secondaryColorHint} onChange={(e: any) => setSecondaryColorHint(e.target.value)} placeholder="#hex" className="flex-1 bg-[#0b0b0b] border border-[#313131] rounded px-2 py-1.5 text-[11px] font-mono outline-none" style={{ color: '#e2e2e2' }} />
              </div>
            </div>
          </div>
        </div>
        
        <button onClick={generateTokens} disabled={generating} className="w-full mt-4 py-2.5 rounded font-semibold text-[12px] tracking-wide cursor-pointer transition-all disabled:opacity-25 hover:opacity-90" style={{ background: '#fff', color: '#0b0b0b' }}>
          {generating ? 'Generating…' : 'Generate System'}
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5 p-3 border-b" style={{ borderColor: '#252525' }}>
        {PRESETS.map((p: any) => (
          <button key={p.id} onClick={() => applyPreset(p.id)} className={`text-[10px] font-medium tracking-wide px-2.5 py-1.5 rounded border transition-all ${activePreset === p.id ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#666] border-[#313131] hover:text-[#999] hover:border-[#444]'}`}>{p.l}</button>
        ))}
      </div>
      <div className="overflow-y-auto">
        {tokens ? (
          <>
            {tokens.meta?.instructions !== undefined && (
              <TokenSection title="Design Instructions" expanded={!!expandedSections.instructions} onToggle={() => toggleSection('instructions')}>
                <DesignInstructionsEditor
                  value={designInstructions || tokens.meta?.instructions || ''}
                  onChange={setDesignInstructions}
                />
              </TokenSection>
            )}
            <TokenSection title="Typography" expanded={!!expandedSections.typography} onToggle={() => toggleSection('typography')}>
              <TypographyExplorer
                typography={tokens.typography}
                fontSearches={fontSearches}
                setFontSearches={setFontSearches}
                fontCategories={fontCategories}
                setFontCategories={setFontCategories}
                onUpdateFont={onUpdateFont}
              />
            </TokenSection>
            <TokenSection title="Color" expanded={!!expandedSections.color} onToggle={() => toggleSection('color')}><ColorExplorer colors={tokens.colors} onUpdateTokenColor={onUpdateTokenColor} onUpdateAccentColor={onUpdateAccentColor} /></TokenSection>
            <TokenSection title="Spacing" expanded={!!expandedSections.spacing} onToggle={() => toggleSection('spacing')}><SpacingExplorer spacing={tokens.spacing} /></TokenSection>
            <TokenSection title="Shadows" expanded={!!expandedSections.shadow} onToggle={() => toggleSection('shadow')}><ShadowExplorer shadows={tokens.shadow} /></TokenSection>
            <TokenSection title="Border" expanded={!!expandedSections.border} onToggle={() => toggleSection('border')}><BorderExplorer border={tokens.border} /></TokenSection>
            <TokenSection title="Gradients" expanded={!!expandedSections.gradient} onToggle={() => toggleSection('gradient')}><GradientExplorer gradients={tokens.gradient} /></TokenSection>
            <TokenSection title="Motion" expanded={!!expandedSections.motion} onToggle={() => toggleSection('motion')}><MotionExplorer motion={tokens.motion} /></TokenSection>
            <TokenSection title="Components" expanded={!!expandedSections.component} onToggle={() => toggleSection('component')}><ComponentExplorer components={tokens.component} /></TokenSection>
            {studioResult?.llm_output?.generated_html && (
              <div className="p-3 border-t" style={{ borderColor: '#252525' }}>
                <button
                  onClick={() => onSaveAsTemplate('generated')}
                  className="w-full py-2 rounded font-bold text-[10px] uppercase tracking-wider border border-[#22c55e] text-[#22c55e] hover:bg-[#22c55e15] transition-all"
                >
                  Save Generated HTML as Template
                </button>
              </div>
            )}
            <div className="p-3 border-t" style={{ borderColor: '#252525' }}>
              <button
                onClick={() => onSaveAsTemplate('design')}
                className="w-full py-2 rounded font-bold text-[10px] uppercase tracking-wider border border-[#3b82f6] text-[#3b82f6] hover:bg-[#3b82f615] transition-all"
              >
                Save Design Tokens as Template
              </button>
            </div>
          </>
        ) : (
          <div className="p-6 text-center" style={{ color: '#555', fontSize: 11, lineHeight: 1.7 }}>Generate a design system<br />to explore tokens here</div>
        )}
      </div>
    </>
  )
}

/* ── Token Explorer ── */

function TokenSection({ title, expanded, onToggle, children }: { title: string; expanded: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div className="border-b" style={{ borderColor: '#252525' }}>
      <div className="flex items-center justify-between px-4 py-2.5 cursor-pointer select-none hover:bg-[#1c1c1c] transition-colors" onClick={onToggle}>
        <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: '#888' }}>{title}</span>
        <span className="text-[11px] transition-transform" style={{ color: '#888', transform: expanded ? 'rotate(180deg)' : undefined }}>▾</span>
      </div>
      {expanded && <div className="p-3.5" style={{ background: '#0b0b0b' }}>{children}</div>}
    </div>
  )
}

function DesignInstructionsEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-2">
      <div className="text-[9px]" style={{ color: '#666', lineHeight: 1.6 }}>
        Write specific design guidance for HTML generation. These instructions tell the AI how to compose layouts, what visual patterns to use, and any creative direction for social media posts.
      </div>
      <textarea
        value={value}
        onChange={(e: any) => onChange(e.target.value)}
        placeholder="e.g. Use large bold headlines with generous whitespace. Prefer card-based layouts with subtle borders. Use gradients sparingly — only for hero elements…"
        rows={6}
        className="w-full rounded border resize-y outline-none"
        style={{ background: '#121212', borderColor: '#313131', color: '#e2e2e2', fontFamily: 'inherit', fontSize: 12, padding: '10px 12px', lineHeight: 1.6 }}
      />
      {value && (
        <div className="text-[8px]" style={{ color: '#555' }}>
          {value.length} characters · Instructions will be passed to the HTML generator
        </div>
      )}
    </div>
  )
}

function ColorExplorer({ colors, onUpdateTokenColor, onUpdateAccentColor }: {
  colors: DesignTokens['colors']
  onUpdateTokenColor?: (group: 'primary' | 'secondary', hex: string) => void | Promise<void>
  onUpdateAccentColor?: (key: 'light' | 'base' | 'dark', hex: string) => void | Promise<void>
}) {
  if (!colors) return null
  const groups = [
    { label: 'Primary', data: colors.primary, keys: ['50','100','200','300','400','500','600','700','800','900'] },
    { label: 'Secondary', data: colors.secondary, keys: ['50','100','500','700','900'] },
    { label: 'Accent', data: colors.accent, keys: ['light','base','dark'] },
    { label: 'Neutral', data: colors.neutral, keys: ['50','100','200','300','400','500','600','700','800','900'] },
  ]
  return (
    <div className="space-y-2.5">
      <div className="space-y-2 p-2 rounded border" style={{ borderColor: '#252525', background: '#121212' }}>
        <div className="text-[9px] font-semibold uppercase tracking-wide" style={{ color: '#888' }}>Quick Edit Colors</div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="text-[8px] mb-1" style={{ color: '#666' }}>Primary 500</div>
            <input
              type="color"
              value={colors.primary?.['500'] || '#3b82f6'}
              onChange={(e: any) => onUpdateTokenColor?.('primary', e.target.value)}
              className="w-full h-7 rounded cursor-pointer"
            />
          </div>
          <div>
            <div className="text-[8px] mb-1" style={{ color: '#666' }}>Secondary 500</div>
            <input
              type="color"
              value={colors.secondary?.['500'] || '#0f172a'}
              onChange={(e: any) => onUpdateTokenColor?.('secondary', e.target.value)}
              className="w-full h-7 rounded cursor-pointer"
            />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {(['light', 'base', 'dark'] as const).map((k) => (
            <div key={k}>
              <div className="text-[8px] mb-1 capitalize" style={{ color: '#666' }}>{k}</div>
              <input
                type="color"
                value={colors.accent?.[k] || '#8b5cf6'}
                onChange={(e: any) => onUpdateAccentColor?.(k, e.target.value)}
                className="w-full h-7 rounded cursor-pointer"
              />
            </div>
          ))}
        </div>
      </div>
      {groups.map(g => {
        if (!g.data) return null
        return (
          <div key={g.label}>
            <div className="text-[8px] font-bold uppercase tracking-widest mb-1" style={{ color: '#555' }}>{g.label}</div>
            <div className="flex rounded overflow-hidden">
              {g.keys.map(k => {
                const v = (g.data as any)[k]
                if (!v) return null
                return (
                  <div key={k} className="flex-1 h-5 relative cursor-default hover:flex-[2.5] transition-all group/swatch">
                    <div className="absolute inset-0" style={{ background: v }} />
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-0.5 px-1 py-0.5 rounded text-[8px] font-mono whitespace-nowrap opacity-0 group-hover/swatch:opacity-100 pointer-events-none z-20" style={{ background: '#1c1c1c', border: '1px solid #313131', color: '#999' }}>{k}: {v}</div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
      {[...Object.entries(colors.semantic || {}), ...Object.entries(colors.text || {}), ...Object.entries(colors.surface || {})].map(([k, v]) => (
        <div key={k} className="flex items-center gap-1.5 py-0.5">
          <div className="w-3.5 h-3.5 rounded-sm flex-shrink-0" style={{ background: v, border: '1px solid rgba(255,255,255,0.08)' }} />
          <span className="text-[10px] font-medium" style={{ color: '#999' }}>{k}</span>
          <span className="ml-auto text-[8px] font-mono" style={{ color: '#555' }}>{v}</span>
        </div>
      ))}
    </div>
  )
}

function TypographyExplorer({ typography, fontSearches, setFontSearches, fontCategories, setFontCategories, onUpdateFont }: {
  typography: DesignTokens['typography']
  fontSearches: Record<string, string>
  setFontSearches: (v: Record<string, string>) => void
  fontCategories: Record<string, string>
  setFontCategories: (v: Record<string, string>) => void
  onUpdateFont?: (type: 'fontSans' | 'fontSerif' | 'fontMono', family: string) => void
}) {
  if (!typography) return null
  const entries = Object.entries(typography.scale)
  const fontTypes: { key: 'fontSans' | 'fontSerif' | 'fontMono'; label: string; category: string }[] = [
    { key: 'fontSans', label: 'Sans', category: 'sans-serif' },
    { key: 'fontSerif', label: 'Serif', category: 'serif' },
    { key: 'fontMono', label: 'Mono', category: 'monospace' },
  ]

  function getFilteredFonts(typeKey: string, typeCategory: string) {
    const search = fontSearches[typeKey] || ''
    const cat = fontCategories[typeKey] || 'all'
    let fonts = GOOGLE_FONTS
    if (cat !== 'all') {
      if (typeCategory === 'sans-serif' && cat === 'sans-serif') fonts = fonts.filter(f => f.category === 'sans-serif' || f.category === 'display')
      else if (typeCategory === cat) fonts = fonts.filter(f => f.category === cat)
      else fonts = fonts.filter(f => f.category === cat)
    }
    if (search) {
      fonts = fonts.filter(f => f.family.toLowerCase().includes(search.toLowerCase()))
    }
    return fonts
  }

  return (
    <div className="space-y-3">
      {fontTypes.map(({ key, label, category }) => {
        const filtered = getFilteredFonts(key, category)
        return (
          <div key={key} className="space-y-1">
            <div className="text-[9px] font-semibold uppercase tracking-wide" style={{ color: '#888' }}>{label}</div>
            <div className="flex items-center gap-2">
              <input
                value={fontSearches[key] || ''}
                onChange={(e: any) => setFontSearches({ ...fontSearches, [key]: e.target.value })}
                placeholder={`Search ${label.toLowerCase()} fonts…`}
                className="flex-1 rounded border px-2 py-1 text-[10px] outline-none"
                style={{ background: '#121212', borderColor: '#313131', color: '#e2e2e2' }}
              />
              <select
                value={fontCategories[key] || 'all'}
                onChange={(e: any) => setFontCategories({ ...fontCategories, [key]: e.target.value })}
                className="rounded border px-2 py-1 text-[10px] outline-none"
                style={{ background: '#121212', borderColor: '#313131', color: '#e2e2e2' }}
              >
                {FONT_CATEGORIES.map(cat => (
                  <option key={cat} value={cat}>{cat === 'all' ? 'All' : cat}</option>
                ))}
              </select>
            </div>
            <div className="text-[11px] font-medium px-2 py-1.5 rounded border" style={{ background: '#121212', borderColor: '#252525', color: '#e2e2e2' }}>
              {typography[key]}
            </div>
            <div className="max-h-32 overflow-y-auto rounded border" style={{ background: '#121212', borderColor: '#252525' }}>
              {filtered.map((font: any) => (
                <button
                  key={font.family}
                  onClick={() => onUpdateFont?.(key, font.family)}
                  className={`w-full text-left px-2 py-1 text-[10px] transition-colors hover:bg-[#1c1c1c] ${typography[key] === font.family ? 'text-white bg-[#1c1c1c]' : 'text-[#999]'}`}
                  style={{ fontFamily: `'${font.family}', sans-serif` }}
                >
                  {font.family}
                  <span className="ml-1 text-[8px]" style={{ color: '#555' }}>{font.category}</span>
                </button>
              ))}
            </div>
          </div>
        )
      })}
      <div className="space-y-3 pt-2 border-t" style={{ borderColor: '#252525' }}>
        {entries.map(([k, v]) => {
          const size = v as number
          const weight = size >= 36 ? 700 : size >= 24 ? 600 : size >= 18 ? 500 : 400
          const previewHeight = Math.max(24, Math.min(88, size * 1.08))
          return (
            <div key={k} className="flex items-baseline gap-3" style={{ padding: '6px 0', borderBottom: '1px solid #252525' }}>
              <span className="text-[9px] font-mono min-w-[32px]" style={{ color: '#777' }}>{k}</span>
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  height: previewHeight,
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'flex-end'
                }}
              >
                <span
                  style={{
                    fontSize: size,
                    lineHeight: 1,
                    color: '#e2e2e2',
                    fontWeight: weight,
                    whiteSpace: 'nowrap',
                    letterSpacing: size >= 32 ? '-0.02em' : 'normal'
                  }}
                >
                  Aa
                </span>
              </span>
              <span className="text-[9px] font-mono" style={{ color: '#777' }}>{size}px</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SpacingExplorer({ spacing }: { spacing: DesignTokens['spacing'] }) {
  if (!spacing) return null
  return (
    <div className="space-y-0.5">
      {(spacing.scale as number[]).map((v: number) => (
        <div key={v} className="flex items-center gap-1.5 py-0.5">
          <div className="rounded-sm flex-shrink-0" style={{ width: Math.min(v * 1.4, 220), height: 3, background: '#e2e2e2', opacity: 0.5 }} />
          <span className="text-[8px] font-mono" style={{ color: '#555' }}>{v}px</span>
        </div>
      ))}
    </div>
  )
}

function ShadowExplorer({ shadows }: { shadows: Record<string, string> }) {
  if (!shadows) return null

  return (
    <div className="space-y-3">
      {Object.entries(shadows).map(([k, raw]) => {
        const v = resolveShadowPreviewValue(raw, k)
        return (
        <div key={k} className="flex items-center gap-3">
          <div
            className="flex items-center justify-center flex-shrink-0 rounded"
            style={{
              width: 116,
              height: 64,
              background: '#ffffff',
              border: '1px solid #252525'
            }}
          >
            <div
              className="rounded"
              style={{
                width: 46,
                height: 32,
                background: '#334155',
                boxShadow: v,
                borderRadius: 6
              }}
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-medium mb-0.5" style={{ color: '#ccc' }}>{k}</div>
            <div className="text-[8px] font-mono truncate" style={{ color: '#666' }} title={raw}>{String(raw)}</div>
          </div>
        </div>
      )})}
    </div>
  )
}

function BorderExplorer({ border }: { border: DesignTokens['border'] }) {
  if (!border?.radius) return null
  return (
    <div className="space-y-1">
      <div className="text-[8px] font-bold uppercase tracking-widest mb-1" style={{ color: '#555' }}>Radius</div>
      {Object.entries(border.radius).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2 py-0.5">
          <div className="w-5 h-3.5 flex-shrink-0" style={{ borderRadius: v, background: '#999', opacity: 0.2 }} />
          <span className="text-[8px] font-mono min-w-[24px]" style={{ color: '#555' }}>{k}</span>
          <span className="text-[8px] font-mono" style={{ color: '#555' }}>{v}</span>
        </div>
      ))}
    </div>
  )
}

function GradientExplorer({ gradients }: { gradients: Record<string, string> }) {
  if (!gradients) return null
  return (
    <div className="space-y-1">
      {Object.entries(gradients).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2 py-0.5">
          <div className="w-14 h-3.5 rounded-sm flex-shrink-0" style={{ background: v }} />
          <span className="text-[8px] font-mono" style={{ color: '#555' }}>{k}</span>
        </div>
      ))}
    </div>
  )
}

function ComponentExplorer({ components }: { components: DesignTokens['component'] }) {
  if (!components) return null
  return (
    <div className="space-y-2">
      {Object.entries(components).map(([name, vals]) => (
        <div key={name}>
          <div className="text-[8px] font-bold uppercase tracking-widest mb-0.5" style={{ color: '#555' }}>{name}</div>
          {Object.entries(vals).map(([k, v]) => (
            <div key={k} className="flex justify-between items-center py-0.5 text-[10px]">
              <span style={{ color: '#555' }}>{k}</span>
              <span className="text-[8px] font-mono" style={{ color: '#999' }}>{String(v)}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

function MotionExplorer({ motion }: { motion: DesignTokens['motion'] }) {
  if (!motion) return null
  const easingEntries = Object.entries(motion.easing || {})
  return (
    <div className="space-y-4">
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-wide mb-2" style={{ color: '#888' }}>Duration</div>
        <div className="space-y-2.5">
          {Object.entries(motion.duration || {}).map(([k, v]) => {
            const ms = parseInt(v) || 200
            return (
              <div key={k} className="flex items-center gap-3">
                <div className="h-2 rounded-full flex-shrink-0 overflow-hidden" style={{ width: 120, background: '#1c1c1c' }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: '60%',
                      background: 'linear-gradient(90deg, #22d3ee 0%, #3b82f6 55%, #a78bfa 100%)',
                      animationName: 'motion-duration-pulse',
                      animationDuration: `${Math.max(ms, 120)}ms`,
                      animationTimingFunction: 'ease-in-out',
                      animationIterationCount: 'infinite',
                      animationDirection: 'alternate'
                    }}
                  />
                </div>
                <span className="text-[9px] font-mono min-w-[40px]" style={{ color: '#777' }}>{k}</span>
                <span className="text-[9px] font-mono ml-auto" style={{ color: '#aaa' }}>{v}</span>
              </div>
            )
          })}
        </div>
      </div>
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-wide mb-2" style={{ color: '#888' }}>Easing</div>
        <div className="space-y-2.5">
          {easingEntries.map(([k, v], idx) => (
            <div key={k} className="flex items-center gap-3">
              <div className="flex items-center justify-center flex-shrink-0" style={{ width: 36, height: 36, background: '#1c1c1c', borderRadius: 6 }}>
                <div
                  className="rounded-full"
                  style={{
                    width: 9,
                    height: 9,
                    background: '#60a5fa',
                    animationName: 'motion-easing-orbit',
                    animationDuration: '1600ms',
                    animationTimingFunction: v || 'ease-in-out',
                    animationDelay: `${idx * 120}ms`,
                    animationIterationCount: 'infinite',
                    animationDirection: 'alternate'
                  }}
                />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[9px] font-mono" style={{ color: '#aaa' }}>{k}</div>
                <div className="text-[8px] font-mono truncate" style={{ color: '#666', maxWidth: 140 }} title={v}>{v}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes motion-duration-pulse {
          from { width: 22%; filter: saturate(0.9); }
          to { width: 100%; filter: saturate(1.25); }
        }

        @keyframes motion-easing-orbit {
          from { transform: translateX(-11px) scale(0.85); opacity: 0.65; }
          to { transform: translateX(11px) scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  )
}

/* ── Preview ── */

function PreviewFrame({ tokens }: { tokens: DesignTokens }) {
  const skeletonHtml = generateComponentsSkeleton()
  
  const cssVars = tokensToCSS(tokens)
  
  const fonts = [
    tokens.typography?.fontSans,
    tokens.typography?.fontSerif,
    tokens.typography?.fontMono
  ].filter(Boolean).map(f => f?.replace(/\s+/g, '+'))
  
  const fontImport = fonts.length > 0 
    ? `<link href="https://fonts.googleapis.com/css2?${fonts.map(f => `family=${f}:wght@300;400;500;600;700;900`).join('&')}&display=swap" rel="stylesheet">`
    : ''
  
  let finalHtml = skeletonHtml.replace('</head>', `${fontImport}\n</head>`)
  finalHtml = finalHtml.replace('<style id="token-styles"></style>', `<style id="token-styles">${cssVars}</style>`)
  
  return (
    <div className="absolute inset-0">
      <iframe
        srcDoc={finalHtml}
        title="Preview"
        className="w-full h-full border-0"
        style={{ background: '#fff' }}
      />
    </div>
  )
}
