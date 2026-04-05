import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { tokensToCSS, type DesignTokens } from '@/lib/tokens'
import { generateComponentsSkeleton } from '@/components/skeletons'

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
  const [activeTab, setActiveTab] = useState<'studio' | 'templates' | 'settings' | 'tokens'>('studio')
  const [tokens, setTokens] = useState<DesignTokens | null>(null)
  const [generating, setGenerating] = useState(false)
  const [vibeInput, setVibeInput] = useState('')
  const [activePreset, setActivePreset] = useState<string | null>(null)
  const [primaryColorHint, setPrimaryColorHint] = useState('')
  const [secondaryColorHint, setSecondaryColorHint] = useState('')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({ color: true, typography: true, spacing: true, shadow: true, border: true, gradient: true, motion: true, component: true })
  const [error, setError] = useState<string | null>(null)
  const [_serverConfig, setServerConfig] = useState<any>(null)
  const [_configLoading, setConfigLoading] = useState(false)
  const [editingConfig, setEditingConfig] = useState<any>(null)
  const [_configSaved, setConfigSaved] = useState(false)
  const [studioResult, setStudioResult] = useState<any>(null)
  const [studioGenerating, setStudioGenerating] = useState(false)
  const [studioMode, setStudioMode] = useState<'content' | 'slug'>('content')
  const [studioTitle, setStudioTitle] = useState('')
  const [studioContent, setStudioContent] = useState('')
  const [studioSlug, setStudioSlug] = useState('')
  const [studioFormats, setStudioFormats] = useState<string[]>([])
  const [settings, setSettings] = useState<any>(null)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [templates, setTemplates] = useState<any[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<{ id: string; html: string; name: string; description: string; category: string; slots: string[] } | null>(null)
  const [templateHtml, setTemplateHtml] = useState('')
  const [templatePreviewHtml, setTemplatePreviewHtml] = useState('')

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
      }
    } catch {
      // ignore malformed local tokens
    }

    try {
      const saved = await api.getSavedTokens()
      if (saved) {
        setTokens(saved)
        localStorage.setItem(TOKENS_LOCAL_KEY, JSON.stringify(saved))
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
      const formatIds = Object.keys(cfg?.formats || {})
      if (formatIds.length > 0) {
        setStudioFormats(formatIds)
      }
    } catch { /* ignore */ }
    setConfigLoading(false)
  }

  async function loadSettings() {
    setSettingsLoading(true)
    try {
      const s = await api.getSettings()
      setSettings(s)
      if (s?.formats?.enabled && s.formats.enabled.length > 0) {
        setStudioFormats(s.formats.enabled)
      }
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

  function _updateConfigValue(path: string[], value: any) {
    setEditingConfig((prev: any) => {
      if (path.length === 0) {
        return typeof value === 'function' ? value(prev) : value
      }
      const next = JSON.parse(JSON.stringify(prev))
      let obj = next
      for (let i = 0; i < path.length - 1; i++) obj = obj[path[i]]
      obj[path[path.length - 1]] = value
      return next
    })
    setConfigSaved(false)
  }

  async function _saveConfig() {
    setServerConfig(JSON.parse(JSON.stringify(editingConfig)))
    try {
      const formats = editingConfig?.formats || {}
      const formatEntries = Object.entries(formats)
      for (const [id, format] of formatEntries as [string, any][]) {
        await api.saveFormat(id, {
          width: Number(format.width),
          height: Number(format.height),
          name: format.name || id,
          aiInstruction: format.aiInstruction || '',
        })
      }
    } catch {
      // ignore backend save failures
    }
    setConfigSaved(true)
    setTimeout(() => setConfigSaved(false), 2000)
  }

  async function handleStudioGenerate() {
    if (studioMode === 'content' && (!studioTitle.trim() || !studioContent.trim())) { setError('Title and content required'); return }
    if (studioMode === 'slug' && !studioSlug.trim()) { setError('Slug required'); return }
    setStudioGenerating(true)
    setError(null)
    try {
      const shared: any = {
        output: { formats: studioFormats, postCount: 1 },
        image: { mode: 'none' },
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

      setStudioResult(res)
    } catch (e: any) {
      setError(e.message || 'Generation failed')
    } finally {
      setStudioGenerating(false)
    }
  }

  function toggleStudioFormat(id: string) {
    setStudioFormats(prev => prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id])
  }

  const availableFormats = Object.entries(editingConfig?.formats || {}).map(([id, f]: [string, any]) => ({
    id,
    label: f?.name || id,
    dims: `${f?.width || 0}×${f?.height || 0}`,
  }))

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

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ background: '#0b0b0b', color: '#e2e2e2', fontFamily: "'Inter', system-ui, sans-serif", fontSize: 13 }}>
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
              { id: 'templates' as const, label: 'Templates' },
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
                formats={studioFormats} toggleFormat={toggleStudioFormat}
                availableFormats={availableFormats}
                generating={studioGenerating} onGenerate={handleStudioGenerate}
                result={studioResult}
              />
            )}
            {activeTab === 'templates' && (
              <TemplatesTab
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
              />
            )}
          </div>

          {error && (
            <div className="p-3.5 border-t flex-shrink-0" style={{ borderColor: '#252525' }}>
              <div className="text-[10px] text-[#f43f5e]">{error}</div>
              <button onClick={() => setError(null)} className="text-[9px] text-[#f43f5e] mt-1 underline">Dismiss</button>
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
                  <StudioScreenshotPanel result={studioResult} generating={studioGenerating} />
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

function StudioTab({ mode, setMode, title, setTitle, content, setContent, slug, setSlug, formats, toggleFormat, availableFormats, generating, onGenerate, result }: any) {
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
            <textarea value={content} onChange={(e: any) => setContent(e.target.value)} placeholder="Paste content…" rows={3} className="w-full rounded border px-2.5 py-2 text-[11px] outline-none resize-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2', lineHeight: 1.5 }} />
          </>
        ) : (
          <input value={slug} onChange={(e: any) => setSlug(e.target.value)} placeholder="my-post-slug" className="w-full rounded border px-2.5 py-2 text-[11px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
        )}
        <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Formats</div>
        <div className="flex flex-wrap gap-1">
          {availableFormats.map((f: any) => (
            <button key={f.id} onClick={() => toggleFormat(f.id)} className={`text-[9px] font-bold tracking-wider px-2 py-1 rounded border transition-all ${formats.includes(f.id) ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>
              {f.label} <span style={{ color: '#3d3d3d' }}>{f.dims}</span>
            </button>
          ))}
        </div>
        <button onClick={onGenerate} disabled={generating} className="w-full py-2 rounded font-bold text-[11px] tracking-widest uppercase cursor-pointer transition-opacity disabled:opacity-25" style={{ background: '#fff', color: '#0b0b0b' }}>
          {generating ? 'Generating…' : 'Generate Posts'}
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

function TemplatesTab({ templates, loading, editingTemplate, setEditingTemplate, templateHtml, setTemplateHtml, openTemplateEditor, onSaveTemplate, onDeleteTemplate, onToggleTemplate, onUpdatePreview }: any) {
  return (
    <>
      <div className="p-3.5 space-y-2 border-b" style={{ borderColor: '#252525' }}>
        <div className="flex items-center justify-between">
          <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Templates</div>
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
              placeholder="<!DOCTYPE html>..."
              rows={8}
              className="w-full rounded border px-2 py-2 text-[10px] font-mono outline-none resize-y"
              style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2', lineHeight: 1.5 }}
            />
            {editingTemplate.slots && editingTemplate.slots.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {editingTemplate.slots.map((slot: string) => (
                  <span key={slot} className="text-[8px] font-mono px-1.5 py-0.5 rounded" style={{ background: '#1c1c1c', color: '#60a5fa', border: '1px solid #1e3a5f' }}>{`{{${slot}}}`}</span>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <button onClick={onSaveTemplate} className="flex-1 py-1.5 rounded font-bold text-[10px] uppercase tracking-wider border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all">Save</button>
              <button onClick={() => setEditingTemplate(null)} className="py-1.5 px-3 rounded font-bold text-[10px] uppercase tracking-wider border border-[#313131] text-[#555] hover:border-[#444] hover:text-[#888] transition-all">Close</button>
            </div>
          </div>
        )}

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
  )
}

/* ── Settings Tab ── */

function SettingsTab({ settings, loading, onSave, formats }: any) {
  const [local, setLocal] = useState<any>(null)

  useEffect(() => {
    if (settings) setLocal(JSON.parse(JSON.stringify(settings)))
  }, [settings])

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

  return (
    <>
      <div className="p-3.5 space-y-3 overflow-y-auto">
        <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Brand</div>
        <input value={local.brand?.name || ''} onChange={(e: any) => set(['brand', 'name'], e.target.value)} placeholder="Brand name" className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
        <input value={local.brand?.tone || ''} onChange={(e: any) => set(['brand', 'tone'], e.target.value)} placeholder="Tone (e.g. confident, practical)" className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
        <input value={local.brand?.audience || ''} onChange={(e: any) => set(['brand', 'audience'], e.target.value)} placeholder="Target audience" className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />

        <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Campaign</div>
        <select value={local.campaign?.goal || 'awareness'} onChange={(e: any) => set(['campaign', 'goal'], e.target.value)} className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}>
          <option value="awareness">Awareness</option>
          <option value="engagement">Engagement</option>
          <option value="conversion">Conversion</option>
          <option value="education">Education</option>
        </select>
        <select value={local.campaign?.framework || 'none'} onChange={(e: any) => set(['campaign', 'framework'], e.target.value)} className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}>
          <option value="none">No framework</option>
          <option value="AIDA">AIDA</option>
          <option value="PAS">PAS</option>
          <option value="FAB">FAB</option>
        </select>
        <div className="flex gap-2">
          <select value={local.campaign?.hashtags?.style || 'niche'} onChange={(e: any) => set(['campaign', 'hashtags', 'style'], e.target.value)} className="flex-1 rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}>
            <option value="niche">Niche hashtags</option>
            <option value="broad">Broad hashtags</option>
            <option value="branded">Branded hashtags</option>
          </select>
          <input type="number" value={local.campaign?.hashtags?.count || 5} onChange={(e: any) => set(['campaign', 'hashtags', 'count'], Number(e.target.value))} className="w-16 rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
        </div>
        <input value={local.campaign?.cta || ''} onChange={(e: any) => set(['campaign', 'cta'], e.target.value)} placeholder="CTA (e.g. Read more →)" className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />

        <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Formats</div>
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
        <div className="flex items-center gap-2">
          <span className="text-[9px]" style={{ color: '#777' }}>Post count:</span>
          <input type="number" value={local.formats?.postCount || 1} onChange={(e: any) => set(['formats', 'postCount'], Number(e.target.value))} min={1} max={10} className="w-16 rounded border px-2 py-1 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
        </div>

        <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Templates</div>
        <div className="flex items-center justify-between py-1 px-2 rounded" style={{ background: '#0b0b0b' }}>
          <span className="text-[10px]" style={{ color: '#999' }}>Auto-select templates</span>
          <button onClick={() => set(['templates', 'autoSelect'], !local.templates?.autoSelect)} className={`text-[10px] font-mono px-2.5 py-1 rounded border transition-all ${local.templates?.autoSelect ? 'border-[#22c55e] text-[#22c55e] bg-[#22c55e10]' : 'border-[#f43f5e] text-[#f43f5e] bg-[#f43f5e10]'}`}>
            {local.templates?.autoSelect ? 'ON' : 'OFF'}
          </button>
        </div>

        <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Image</div>
        <select value={local.image?.mode || 'auto'} onChange={(e: any) => set(['image', 'mode'], e.target.value)} className="w-full rounded border px-2 py-1.5 text-[10px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }}>
          <option value="auto">Auto</option>
          <option value="none">None</option>
          <option value="feature">Feature image</option>
          <option value="ai">AI generated</option>
        </select>
      </div>
      <div className="p-3 border-t flex-shrink-0" style={{ borderColor: '#252525' }}>
        <button onClick={handleSave} className="w-full py-2 rounded font-bold text-[10px] uppercase tracking-wider border border-white text-white hover:bg-white hover:text-[#0b0b0b] transition-all">
          Save Settings
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

function StudioScreenshotPanel({ result, generating }: { result: any; generating: boolean }) {
  const entries = Object.entries(result?.assets || {}).filter(([, asset]: [string, any]) => Boolean(asset?.key || asset?.url)) as Array<[string, any]>

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
    <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
      {entries.map(([format, asset]) => (
        <AssetPreviewCard key={format} format={format} asset={asset} />
      ))}
    </div>
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

function AssetPreviewCard({ format, asset }: { format: string; asset: any }) {
  const [resolvedSrc, setResolvedSrc] = useState<string>(asset?.url || '')
  const [loading, setLoading] = useState(Boolean(asset?.key))

  useEffect(() => {
    let active = true
    let localBlobUrl: string | null = null

    async function load() {
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

  return (
    <div
      className="rounded overflow-hidden self-start"
      style={{ background: '#111' }}
      aria-label={`${format} screenshot card`}
    >
      {resolvedSrc ? (
        <img
          src={resolvedSrc}
          alt={`${format} screenshot`}
          className="w-full h-auto block"
          loading="lazy"
        />
      ) : (
        <div className="w-full flex items-center justify-center text-[9px]" style={{ minHeight: 120, color: '#666' }}>
          {loading ? 'Loading preview…' : 'Preview unavailable'}
        </div>
      )}
    </div>
  )
}

/* ── Tokens Tab ── */

function TokensTab({ vibeInput, setVibeInput, activePreset, applyPreset, primaryColorHint, setPrimaryColorHint, secondaryColorHint, setSecondaryColorHint, generating, generateTokens, tokens, expandedSections, toggleSection, onUpdateTokenColor, onUpdateAccentColor }: any) {
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
            <TokenSection title="Color" expanded={!!expandedSections.color} onToggle={() => toggleSection('color')}><ColorExplorer colors={tokens.colors} onUpdateTokenColor={onUpdateTokenColor} onUpdateAccentColor={onUpdateAccentColor} /></TokenSection>
            <TokenSection title="Typography" expanded={!!expandedSections.typography} onToggle={() => toggleSection('typography')}><TypographyExplorer typography={tokens.typography} /></TokenSection>
            <TokenSection title="Spacing" expanded={!!expandedSections.spacing} onToggle={() => toggleSection('spacing')}><SpacingExplorer spacing={tokens.spacing} /></TokenSection>
            <TokenSection title="Shadows" expanded={!!expandedSections.shadow} onToggle={() => toggleSection('shadow')}><ShadowExplorer shadows={tokens.shadow} /></TokenSection>
            <TokenSection title="Border" expanded={!!expandedSections.border} onToggle={() => toggleSection('border')}><BorderExplorer border={tokens.border} /></TokenSection>
            <TokenSection title="Gradients" expanded={!!expandedSections.gradient} onToggle={() => toggleSection('gradient')}><GradientExplorer gradients={tokens.gradient} /></TokenSection>
            <TokenSection title="Motion" expanded={!!expandedSections.motion} onToggle={() => toggleSection('motion')}><MotionExplorer motion={tokens.motion} /></TokenSection>
            <TokenSection title="Components" expanded={!!expandedSections.component} onToggle={() => toggleSection('component')}><ComponentExplorer components={tokens.component} /></TokenSection>
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

function TypographyExplorer({ typography }: { typography: DesignTokens['typography'] }) {
  if (!typography) return null
  const entries = Object.entries(typography.scale)
  return (
    <div className="space-y-3">
      <div className="text-[10px] font-mono leading-relaxed" style={{ color: '#777' }}>SANS: {typography.fontSans}<br />SERIF: {typography.fontSerif}<br />MONO: {typography.fontMono}</div>
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
