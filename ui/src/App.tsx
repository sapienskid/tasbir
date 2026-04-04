import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { generateTokensAI, generateTokensComputational, tokensToCSS, tokensToPrompt, type DesignTokens } from '@/lib/tokens'

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
  maximalist: { primary: '#e11d48', secondary: '#7c3aed', vibe: 'maximalist bold saturated' },
]

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeTab, setActiveTab] = useState<'tokens' | 'studio' | 'config'>('tokens')
  const [tokens, setTokens] = useState<DesignTokens | null>(null)
  const [generating, setGenerating] = useState(false)
  const [genMode, setGenMode] = useState<'ai' | 'compute'>('ai')
  const [vibeInput, setVibeInput] = useState('')
  const [activePreset, setActivePreset] = useState<string | null>(null)
  const [primaryColor, setPrimaryColor] = useState('#3b82f6')
  const [secondaryColor, setSecondaryColor] = useState('#0f172a')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({ color: true })
  const [exportTab, setExportTab] = useState<'css' | 'json' | 'prompt'>('css')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewTab, setPreviewTab] = useState<'components' | 'post'>('components')
  const [serverConfig, setServerConfig] = useState<any>(null)
  const [configLoading, setConfigLoading] = useState(false)
  const [editingConfig, setEditingConfig] = useState<any>(null)
  const [configSaved, setConfigSaved] = useState(false)
  const [studioResult, setStudioResult] = useState<any>(null)
  const [studioGenerating, setStudioGenerating] = useState(false)
  const [studioMode, setStudioMode] = useState<'content' | 'slug'>('content')
  const [studioTitle, setStudioTitle] = useState('')
  const [studioContent, setStudioContent] = useState('')
  const [studioSlug, setStudioSlug] = useState('')
  const [studioFormats, setStudioFormats] = useState(['instagram-portrait', 'twitter-card'])

  useEffect(() => { loadConfig() }, [])

  async function loadConfig() {
    setConfigLoading(true)
    try {
      const cfg = await api.getConfig()
      setServerConfig(cfg)
      setEditingConfig(JSON.parse(JSON.stringify(cfg)))
    } catch { /* ignore */ }
    setConfigLoading(false)
  }

  async function generateTokens() {
    if (!tokens && genMode === 'ai' && !vibeInput.trim() && !activePreset) {
      setError('Enter a vibe or select a preset')
      return
    }
    if (genMode === 'compute' && !primaryColor) {
      setError('Select a primary color')
      return
    }
    setGenerating(true)
    setError(null)
    try {
      let result: DesignTokens
      const vibeLabel = activePreset ? `${PRESETS.find(p => p.id === activePreset)?.l}${vibeInput ? ' + ' + vibeInput : ''}` : vibeInput
      if (genMode === 'ai') {
        result = await generateTokensAI(vibeLabel || 'custom design system', '')
      } else {
        result = generateTokensComputational(primaryColor, secondaryColor, vibeLabel || 'computational')
      }
      setTokens(result)
      setExpandedSections({ color: true })
    } catch (e: any) {
      setError(e.message || 'Token generation failed')
    } finally {
      setGenerating(false)
    }
  }

  function applyPreset(id: string) {
    const p = VIBE_PRESETS[id]
    if (!p) return
    setActivePreset(id === activePreset ? null : id)
    setPrimaryColor(p.primary)
    setSecondaryColor(p.secondary)
    setVibeInput(p.vibe)
  }

  function toggleSection(key: string) {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  function handleCopy() {
    let text = ''
    if (!tokens) return
    if (exportTab === 'css') text = tokensToCSS(tokens)
    else if (exportTab === 'json') text = JSON.stringify(tokens, null, 2)
    else text = tokensToPrompt(tokens)
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function updateConfigValue(path: string[], value: any) {
    setEditingConfig((prev: any) => {
      const next = JSON.parse(JSON.stringify(prev))
      let obj = next
      for (let i = 0; i < path.length - 1; i++) obj = obj[path[i]]
      obj[path[path.length - 1]] = value
      return next
    })
    setConfigSaved(false)
  }

  async function saveConfig() {
    setServerConfig(JSON.parse(JSON.stringify(editingConfig)))
    setConfigSaved(true)
    setTimeout(() => setConfigSaved(false), 2000)
  }

  async function handleStudioGenerate() {
    if (studioMode === 'content' && (!studioTitle.trim() || !studioContent.trim())) { setError('Title and content required'); return }
    if (studioMode === 'slug' && !studioSlug.trim()) { setError('Slug required'); return }
    if (!tokens) { setError('Generate design tokens first'); return }
    setStudioGenerating(true)
    setError(null)
    try {
      const body: any = {
        title: studioMode === 'content' ? studioTitle.trim() : 'Generated Post',
        content: studioMode === 'content' ? studioContent.trim() : '',
        formats: studioFormats,
        image: { mode: 'none' },
      }
      if (studioMode === 'slug') body.slug = studioSlug.trim()
      const res = await api.generateFromContent(body)
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

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ background: '#0b0b0b', color: '#e2e2e2', fontFamily: "'Inter', system-ui, sans-serif", fontSize: 13 }}>
      {!sidebarOpen && (
        <button onClick={() => setSidebarOpen(true)} className="fixed top-3 left-3 z-50 w-8 h-8 flex items-center justify-center rounded border transition-colors hover:bg-[#1c1c1c]" style={{ background: '#141414', borderColor: '#252525' }}>
          <span style={{ color: '#555', fontSize: 14 }}>☰</span>
        </button>
      )}

      <aside
        className="flex flex-col border-r transition-all duration-300 ease-in-out overflow-hidden"
        style={{ width: sidebarOpen ? 300 : 0, minWidth: sidebarOpen ? 300 : 0, maxWidth: sidebarOpen ? 300 : 0, background: '#141414', borderColor: '#252525' }}
      >
        <div className="flex flex-col h-full min-w-[300px]">
          <div className="flex items-center px-4 border-b flex-shrink-0" style={{ height: 44, borderColor: '#252525' }}>
            <span className="font-bold text-sm tracking-tight">Tasbir</span>
            <span className="ml-2 text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 border rounded" style={{ color: '#555', borderColor: '#3d3d3d' }}>Studio</span>
            <button onClick={() => setSidebarOpen(false)} className="ml-auto text-[#555] hover:text-white transition-colors" style={{ fontSize: 14 }}>✕</button>
          </div>

          <div className="flex border-b flex-shrink-0" style={{ borderColor: '#252525' }}>
            {([
              { id: 'tokens' as const, label: 'Tokens' },
              { id: 'studio' as const, label: 'Studio' },
              { id: 'config' as const, label: 'Config' },
            ]).map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`flex-1 text-[10px] font-bold uppercase tracking-wider py-2.5 border-b-2 transition-colors ${activeTab === tab.id ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#999]'}`}>{tab.label}</button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto min-h-0 overflow-x-hidden">
            {activeTab === 'tokens' && (
              <TokensTab
                vibeInput={vibeInput} setVibeInput={setVibeInput}
                genMode={genMode} setGenMode={setGenMode}
                activePreset={activePreset} applyPreset={applyPreset}
                primaryColor={primaryColor} setPrimaryColor={setPrimaryColor}
                secondaryColor={secondaryColor} setSecondaryColor={setSecondaryColor}
                generating={generating} generateTokens={generateTokens}
                tokens={tokens} expandedSections={expandedSections} toggleSection={toggleSection}
              />
            )}
            {activeTab === 'studio' && (
              <StudioTab
                mode={studioMode} setMode={setStudioMode}
                title={studioTitle} setTitle={setStudioTitle}
                content={studioContent} setContent={setStudioContent}
                slug={studioSlug} setSlug={setStudioSlug}
                formats={studioFormats} toggleFormat={toggleStudioFormat}
                generating={studioGenerating} onGenerate={handleStudioGenerate}
                result={studioResult} tokens={tokens}
              />
            )}
            {activeTab === 'config' && (
              <ConfigTab
                config={editingConfig} loading={configLoading}
                onUpdate={updateConfigValue} onSave={saveConfig} saved={configSaved}
              />
            )}
          </div>

          {error && (
            <div className="p-3 border-t flex-shrink-0" style={{ borderColor: '#252525' }}>
              <div className="text-[9px] text-[#f43f5e]">{error}</div>
              <button onClick={() => setError(null)} className="text-[8px] text-[#f43f5e] mt-1 underline">Dismiss</button>
            </div>
          )}
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {activeTab === 'config' ? (
          <ConfigPreview config={editingConfig} />
        ) : (
          <>
            <div className="flex-1 flex flex-col overflow-hidden border-b min-h-0" style={{ borderColor: '#252525' }}>
              <div className="flex items-center border-b flex-shrink-0" style={{ borderColor: '#252525', background: '#141414' }}>
                <button onClick={() => setPreviewTab('components')} className={`text-[10px] font-bold uppercase tracking-wider px-4 py-2.5 border-b-2 transition-colors ${previewTab === 'components' ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#999]'}`}>Components</button>
                <button onClick={() => setPreviewTab('post')} className={`text-[10px] font-bold uppercase tracking-wider px-4 py-2.5 border-b-2 transition-colors ${previewTab === 'post' ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#999]'}`}>Social Post</button>
              </div>
              <div className="flex-1 overflow-auto relative min-h-0" style={{ background: '#1c1c1c' }}>
                {tokens ? (
                  previewTab === 'components' ? <PreviewComponents tokens={tokens} /> : <PreviewSocialPost tokens={tokens} />
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#555' }}>
                    <div className="text-2xl opacity-25">◈</div>
                    <div className="text-[11px] font-bold uppercase tracking-wider">No system generated</div>
                    <div className="text-[10px]">Enter a vibe and generate</div>
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

            <div className="h-48 flex flex-col flex-shrink-0" style={{ background: '#141414' }}>
              <div className="flex items-center border-b flex-shrink-0" style={{ borderColor: '#252525' }}>
                {(['css', 'json', 'prompt'] as const).map(tab => (
                  <button key={tab} onClick={() => setExportTab(tab)} className={`text-[9px] font-bold uppercase tracking-wider px-3 py-2 transition-colors ${exportTab === tab ? 'text-white' : 'text-[#555] hover:text-[#999]'}`}>
                    {tab === 'css' ? 'CSS Vars' : tab === 'json' ? 'W3C JSON' : 'AI Prompt'}
                  </button>
                ))}
                <button onClick={handleCopy} className={`ml-auto mr-3 text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded border transition-all ${copied ? 'border-[#22c55e] text-[#22c55e]' : 'border-[#313131] text-[#555] hover:border-white hover:text-white'}`}>
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre className="flex-1 overflow-auto p-3 text-[9px] font-mono leading-relaxed whitespace-pre-wrap break-all" style={{ color: '#555', background: '#0b0b0b' }}>
                {tokens
                  ? exportTab === 'css' ? tokensToCSS(tokens)
                  : exportTab === 'json' ? JSON.stringify(tokens, null, 2)
                  : tokensToPrompt(tokens)
                  : '/* Generate a design system to see exports */'}
              </pre>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

/* ── Tokens Tab ── */

function TokensTab({ vibeInput, setVibeInput, genMode, setGenMode, activePreset, applyPreset, primaryColor, setPrimaryColor, secondaryColor, setSecondaryColor, generating, generateTokens, tokens, expandedSections, toggleSection }: any) {
  return (
    <>
      <div className="p-3.5 border-b" style={{ borderColor: '#252525' }}>
        <div className="text-[9px] font-bold tracking-widest uppercase mb-1.5" style={{ color: '#555' }}>Vibe</div>
        <textarea value={vibeInput} onChange={(e: any) => setVibeInput(e.target.value)} placeholder="cold brutalist luxury…" rows={3} className="w-full rounded border resize-none outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2', fontFamily: 'inherit', fontSize: 12, padding: '9px 11px', lineHeight: 1.5 }} />
        <div className="flex gap-1.5 mt-2">
          <button onClick={() => setGenMode('ai')} className={`flex-1 text-[9px] font-bold uppercase tracking-wider py-1.5 rounded border transition-all ${genMode === 'ai' ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>AI</button>
          <button onClick={() => setGenMode('compute')} className={`flex-1 text-[9px] font-bold uppercase tracking-wider py-1.5 rounded border transition-all ${genMode === 'compute' ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>Compute</button>
        </div>
        {genMode === 'compute' && (
          <div className="flex gap-2 mt-2">
            <div className="flex-1">
              <div className="text-[8px] font-bold uppercase tracking-wider mb-1" style={{ color: '#555' }}>Primary</div>
              <div className="flex items-center gap-1.5">
                <input type="color" value={primaryColor} onChange={(e: any) => setPrimaryColor(e.target.value)} className="w-6 h-6 rounded border-0 cursor-pointer" />
                <input value={primaryColor} onChange={(e: any) => setPrimaryColor(e.target.value)} className="flex-1 bg-[#0b0b0b] border border-[#313131] rounded px-1.5 py-1 text-[10px] font-mono outline-none" style={{ color: '#e2e2e2' }} />
              </div>
            </div>
            <div className="flex-1">
              <div className="text-[8px] font-bold uppercase tracking-wider mb-1" style={{ color: '#555' }}>Secondary</div>
              <div className="flex items-center gap-1.5">
                <input type="color" value={secondaryColor} onChange={(e: any) => setSecondaryColor(e.target.value)} className="w-6 h-6 rounded border-0 cursor-pointer" />
                <input value={secondaryColor} onChange={(e: any) => setSecondaryColor(e.target.value)} className="flex-1 bg-[#0b0b0b] border border-[#313131] rounded px-1.5 py-1 text-[10px] font-mono outline-none" style={{ color: '#e2e2e2' }} />
              </div>
            </div>
          </div>
        )}
        <button onClick={generateTokens} disabled={generating} className="w-full mt-2 py-2 rounded font-bold text-[11px] tracking-widest uppercase cursor-pointer transition-opacity disabled:opacity-25" style={{ background: '#fff', color: '#0b0b0b' }}>
          {generating ? 'Generating…' : 'Generate System'}
        </button>
      </div>
      <div className="flex flex-wrap gap-1 p-2.5 border-b" style={{ borderColor: '#252525' }}>
        {PRESETS.map((p: any) => (
          <button key={p.id} onClick={() => applyPreset(p.id)} className={`text-[9px] font-bold tracking-wider uppercase px-2 py-1 rounded border transition-all ${activePreset === p.id ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>{p.l}</button>
        ))}
      </div>
      <div className="overflow-y-auto">
        {tokens ? (
          <>
            <TokenSection title="Color" expanded={!!expandedSections.color} onToggle={() => toggleSection('color')}><ColorExplorer colors={tokens.colors} /></TokenSection>
            <TokenSection title="Typography" expanded={!!expandedSections.typography} onToggle={() => toggleSection('typography')}><TypographyExplorer typography={tokens.typography} /></TokenSection>
            <TokenSection title="Spacing" expanded={!!expandedSections.spacing} onToggle={() => toggleSection('spacing')}><SpacingExplorer spacing={tokens.spacing} /></TokenSection>
            <TokenSection title="Shadows" expanded={!!expandedSections.shadow} onToggle={() => toggleSection('shadow')}><ShadowExplorer shadows={tokens.shadow} /></TokenSection>
            <TokenSection title="Border" expanded={!!expandedSections.border} onToggle={() => toggleSection('border')}><BorderExplorer border={tokens.border} /></TokenSection>
            <TokenSection title="Gradients" expanded={!!expandedSections.gradient} onToggle={() => toggleSection('gradient')}><GradientExplorer gradients={tokens.gradient} /></TokenSection>
            <TokenSection title="Components" expanded={!!expandedSections.component} onToggle={() => toggleSection('component')}><ComponentExplorer components={tokens.component} /></TokenSection>
          </>
        ) : (
          <div className="p-6 text-center" style={{ color: '#555', fontSize: 11, lineHeight: 1.7 }}>Generate a design system<br />to explore tokens here</div>
        )}
      </div>
    </>
  )
}

/* ── Studio Tab ── */

function StudioTab({ mode, setMode, title, setTitle, content, setContent, slug, setSlug, formats, toggleFormat, generating, onGenerate, result, tokens }: any) {
  const FORMATS = [
    { id: 'instagram-portrait', label: 'IG Portrait', dims: '1080×1350' },
    { id: 'instagram-square', label: 'IG Square', dims: '1080×1080' },
    { id: 'twitter-card', label: 'Twitter', dims: '1200×628' },
    { id: 'linkedin-post', label: 'LinkedIn', dims: '1200×627' },
  ]

  return (
    <div className="p-3.5 space-y-3">
      <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Content Source</div>
      <div className="flex gap-1">
        <button onClick={() => setMode('content')} className={`flex-1 text-[9px] font-bold uppercase tracking-wider py-1.5 rounded border transition-all ${mode === 'content' ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>Direct</button>
        <button onClick={() => setMode('slug')} className={`flex-1 text-[9px] font-bold uppercase tracking-wider py-1.5 rounded border transition-all ${mode === 'slug' ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>Ghost Slug</button>
      </div>
      {mode === 'content' ? (
        <>
          <input value={title} onChange={(e: any) => setTitle(e.target.value)} placeholder="Post title…" className="w-full rounded border px-2.5 py-2 text-[11px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
          <textarea value={content} onChange={(e: any) => setContent(e.target.value)} placeholder="Paste content…" rows={4} className="w-full rounded border px-2.5 py-2 text-[11px] outline-none resize-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2', lineHeight: 1.5 }} />
        </>
      ) : (
        <input value={slug} onChange={(e: any) => setSlug(e.target.value)} placeholder="my-post-slug" className="w-full rounded border px-2.5 py-2 text-[11px] outline-none" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#e2e2e2' }} />
      )}
      <div className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Formats</div>
      <div className="flex flex-wrap gap-1">
        {FORMATS.map((f: any) => (
          <button key={f.id} onClick={() => toggleFormat(f.id)} className={`text-[9px] font-bold tracking-wider px-2 py-1 rounded border transition-all ${formats.includes(f.id) ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>
            {f.label} <span style={{ color: '#3d3d3d' }}>{f.dims}</span>
          </button>
        ))}
      </div>
      <button onClick={onGenerate} disabled={generating || !tokens} className="w-full py-2 rounded font-bold text-[11px] tracking-widest uppercase cursor-pointer transition-opacity disabled:opacity-25" style={{ background: '#fff', color: '#0b0b0b' }}>
        {generating ? 'Generating…' : 'Generate Posts'}
      </button>
      {result && (
        <div className="p-2.5 rounded text-[10px] font-mono" style={{ background: '#0b0b0b', color: '#999', lineHeight: 1.6 }}>
          <div>Slug: {result.slug}</div>
          <div>Formats: {result.requested_formats?.join(', ')}</div>
          {result.llm_output?.instagram_caption && <div className="mt-1 pt-1 border-t" style={{ borderColor: '#252525' }}>IG: {result.llm_output.instagram_caption}</div>}
          {result.llm_output?.twitter_caption && <div className="mt-1">TW: {result.llm_output.twitter_caption}</div>}
          {result.assets && <div className="mt-1 pt-1 border-t" style={{ borderColor: '#252525' }}>Assets: {Object.keys(result.assets).filter((k: string) => result.assets[k]).length}</div>}
        </div>
      )}
    </div>
  )
}

/* ── Config Tab (User-level only) ── */

function ConfigTab({ config, loading, onUpdate, onSave, saved }: any) {
  const [section, setSection] = useState('formats')

  if (loading || !config) {
    return <div className="flex items-center justify-center h-32" style={{ color: '#555' }}><div className="w-5 h-5 border-2 rounded-full animate-spin" style={{ borderColor: '#313131', borderTopColor: '#fff' }} /></div>
  }

  const sections = [
    { id: 'formats', label: 'Formats' },
    { id: 'prompts', label: 'Prompts' },
    { id: 'image', label: 'Image' },
    { id: 'features', label: 'Features' },
  ]

  const gen = config.generation || {}

  return (
    <>
      <div className="flex flex-wrap gap-1 p-2.5 border-b flex-shrink-0" style={{ borderColor: '#252525' }}>
        {sections.map((s: any) => (
          <button key={s.id} onClick={() => setSection(s.id)} className={`text-[9px] font-bold tracking-wider uppercase px-2 py-1 rounded border transition-all whitespace-nowrap ${section === s.id ? 'text-[#0b0b0b] border-white bg-white' : 'text-[#555] border-[#313131]'}`}>{s.label}</button>
        ))}
      </div>
      <div className="p-3.5 space-y-3 overflow-y-auto overflow-x-hidden">
        {section === 'formats' && (
          <div className="space-y-2">
            {Object.entries(config.formats || {}).map(([id, f]: [string, any]) => (
              <div key={id} className="p-2.5 rounded space-y-1.5" style={{ background: '#0b0b0b' }}>
                <div className="text-[11px] font-medium">{id}</div>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <div className="text-[8px] font-bold uppercase tracking-wider mb-0.5" style={{ color: '#555' }}>Width</div>
                    <input type="number" value={f.width} onChange={(e: any) => onUpdate(['formats', id, 'width'], Number(e.target.value))} className="w-full bg-[#141414] border border-[#313131] rounded px-1.5 py-1 text-[10px] font-mono outline-none" style={{ color: '#e2e2e2' }} />
                  </div>
                  <div className="flex-1">
                    <div className="text-[8px] font-bold uppercase tracking-wider mb-0.5" style={{ color: '#555' }}>Height</div>
                    <input type="number" value={f.height} onChange={(e: any) => onUpdate(['formats', id, 'height'], Number(e.target.value))} className="w-full bg-[#141414] border border-[#313131] rounded px-1.5 py-1 text-[10px] font-mono outline-none" style={{ color: '#e2e2e2' }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {section === 'prompts' && (
          <div className="space-y-3">
            {Object.entries(gen.prompts || {}).map(([key, lines]: [string, any]) => (
              <div key={key}>
                <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#555' }}>{key}</div>
                <textarea
                  value={Array.isArray(lines) ? lines.join('\n') : String(lines)}
                  onChange={(e: any) => onUpdate(['generation', 'prompts', key], e.target.value.split('\n'))}
                  rows={6}
                  className="w-full rounded border px-2.5 py-2 text-[10px] font-mono outline-none resize-y"
                  style={{ background: '#0b0b0b', borderColor: '#313131', color: '#999', lineHeight: 1.6 }}
                />
              </div>
            ))}
          </div>
        )}

        {section === 'image' && (
          <div className="space-y-3">
            <div className="p-2.5 rounded" style={{ background: '#0b0b0b' }}>
              <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#555' }}>Model</div>
              <input value={gen.image?.default_model || ''} onChange={(e: any) => onUpdate(['generation', 'image', 'default_model'], e.target.value)} className="w-full bg-[#141414] border border-[#313131] rounded px-2 py-1.5 text-[10px] font-mono outline-none" style={{ color: '#e2e2e2' }} />
            </div>
            <div>
              <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#555' }}>Prompt Prefix</div>
              <textarea value={(gen.image?.prompt_prefix || []).join('\n')} onChange={(e: any) => onUpdate(['generation', 'image', 'prompt_prefix'], e.target.value.split('\n'))} rows={4} className="w-full rounded border px-2.5 py-2 text-[10px] font-mono outline-none resize-y" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#999', lineHeight: 1.6 }} />
            </div>
            <div>
              <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#555' }}>Negative Clauses</div>
              <textarea value={(gen.image?.negative_clauses || []).join('\n')} onChange={(e: any) => onUpdate(['generation', 'image', 'negative_clauses'], e.target.value.split('\n'))} rows={4} className="w-full rounded border px-2.5 py-2 text-[10px] font-mono outline-none resize-y" style={{ background: '#0b0b0b', borderColor: '#313131', color: '#999', lineHeight: 1.6 }} />
            </div>
          </div>
        )}

        {section === 'features' && (
          <div className="space-y-1">
            {Object.entries(config.features || {}).map(([k, v]: [string, any]) => (
              <div key={k} className="flex items-center justify-between py-1.5 px-2 rounded" style={{ background: '#0b0b0b' }}>
                <span className="text-[10px] font-mono" style={{ color: '#999' }}>{k}</span>
                <button
                  onClick={() => onUpdate(['features', k], !v)}
                  className={`text-[10px] font-mono px-2.5 py-1 rounded border transition-all ${v ? 'border-[#22c55e] text-[#22c55e] bg-[#22c55e10]' : 'border-[#f43f5e] text-[#f43f5e] bg-[#f43f5e10]'}`}
                >{v ? 'ON' : 'OFF'}</button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="p-3 border-t flex-shrink-0" style={{ borderColor: '#252525' }}>
        <button onClick={onSave} className={`w-full py-2 rounded font-bold text-[10px] uppercase tracking-wider border transition-all ${saved ? 'border-[#22c55e] text-[#22c55e] bg-[#22c55e10]' : 'border-white text-white hover:bg-white hover:text-[#0b0b0b]'}`}>
          {saved ? '✓ Saved Locally' : 'Save Changes'}
        </button>
      </div>
    </>
  )
}

/* ── Config Preview ── */

function ConfigPreview({ config }: any) {
  const gen = config?.generation || {}
  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: '#0b0b0b' }}>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Formats</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            {Object.entries(config?.formats || {}).map(([id, f]: [string, any]) => (
              <div key={id} style={{ padding: 16, borderRadius: 8, background: '#141414', border: '1px solid #252525' }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{id}</div>
                <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#555' }}>{f.width} × {f.height}</div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Features</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
            {Object.entries(config?.features || {}).map(([k, v]: [string, any]) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 12, borderRadius: 6, background: '#141414' }}>
                <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#999' }}>{k}</span>
                <span style={{ fontSize: 10, fontFamily: 'monospace', padding: '2px 8px', borderRadius: 4, color: v ? '#22c55e' : '#f43f5e', background: v ? '#22c55e15' : '#f43f5e15' }}>{v ? 'ON' : 'OFF'}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Token Explorer ── */

function TokenSection({ title, expanded, onToggle, children }: { title: string; expanded: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div className="border-b" style={{ borderColor: '#252525' }}>
      <div className="flex items-center justify-between px-3.5 py-2 cursor-pointer select-none hover:bg-[#1c1c1c] transition-colors" onClick={onToggle}>
        <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>{title}</span>
        <span className="text-[9px] transition-transform" style={{ color: '#555', transform: expanded ? 'rotate(180deg)' : undefined }}>▾</span>
      </div>
      {expanded && <div className="p-3" style={{ background: '#0b0b0b' }}>{children}</div>}
    </div>
  )
}

function ColorExplorer({ colors }: { colors: DesignTokens['colors'] }) {
  if (!colors) return null
  const groups = [
    { label: 'Primary', data: colors.primary, keys: ['50','100','200','300','400','500','600','700','800','900'] },
    { label: 'Secondary', data: colors.secondary, keys: ['50','100','500','700','900'] },
    { label: 'Accent', data: colors.accent, keys: ['light','base','dark'] },
    { label: 'Neutral', data: colors.neutral, keys: ['50','100','200','300','400','500','600','700','800','900'] },
  ]
  return (
    <div className="space-y-2.5">
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
  return (
    <div className="space-y-2">
      <div className="text-[8px] font-mono leading-relaxed" style={{ color: '#555' }}>SANS: {typography.fontSans}<br />SERIF: {typography.fontSerif}<br />MONO: {typography.fontMono}</div>
      {Object.entries(typography.scale).map(([k, v]) => (
        <div key={k} className="flex items-baseline gap-2 border-b pb-0.5" style={{ borderColor: '#252525' }}>
          <span className="text-[8px] font-mono min-w-[28px]" style={{ color: '#555' }}>{k}</span>
          <span style={{ fontSize: Math.min(v as number, 28), lineHeight: 1, color: '#999', flex: 1, overflow: 'hidden', whiteSpace: 'nowrap' }}>Aa</span>
          <span className="text-[8px] font-mono ml-1.5" style={{ color: '#555' }}>{v}px</span>
        </div>
      ))}
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
    <div className="space-y-1">
      {Object.entries(shadows).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2 py-1">
          <div className="w-7 h-4 rounded-sm flex-shrink-0" style={{ background: '#1c1c1c', boxShadow: v }} />
          <span className="text-[8px] font-mono min-w-[20px]" style={{ color: '#555' }}>{k}</span>
        </div>
      ))}
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

/* ── Preview ── */

function PreviewComponents({ tokens }: { tokens: DesignTokens }) {
  const css = tokensToCSS(tokens)
  const fi = fontImport(tokens)
  const ty = tokens.typography
  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
${fi}
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
${css}
body{font-family:var(--font-sans);background:var(--surface-base);color:var(--text-primary);padding:32px;line-height:1.5}
.nav{display:flex;align-items:center;gap:24px;padding:16px 0;border-bottom:var(--border-hairline) solid var(--color-neutral-200);margin-bottom:40px}
.nav-logo{font-weight:700;font-size:18px;letter-spacing:-0.02em}
.nav-links{display:flex;gap:16px;margin-left:auto}
.nav-links a{color:var(--text-secondary);text-decoration:none;font-size:13px;font-weight:500}
.nav-cta{padding:8px 16px;background:var(--color-primary-500);color:var(--text-inverse);border:none;border-radius:var(--radius-md);font-weight:600;font-size:13px;cursor:pointer}
.hero{text-align:center;padding:48px 0 56px}
.hero h1{font-size:var(--text-6xl);font-weight:700;letter-spacing:var(--tracking-tight);line-height:var(--leading-tight);margin-bottom:16px}
.hero p{font-size:var(--text-lg);color:var(--text-secondary);max-width:480px;margin:0 auto 32px}
.btns{display:flex;gap:12px;justify-content:center}
.btn-primary{padding:12px 28px;background:var(--color-primary-500);color:var(--text-inverse);border:none;border-radius:var(--radius-md);font-weight:600;font-size:14px;cursor:pointer}
.btn-secondary{padding:12px 28px;background:transparent;color:var(--text-primary);border:var(--border-normal) solid var(--color-neutral-300);border-radius:var(--radius-md);font-weight:600;font-size:14px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin:40px 0}
.card{padding:var(--card-padding);background:var(--surface-elevated);border-radius:var(--card-radius);border:var(--border-hairline) solid var(--color-neutral-200);box-shadow:var(--shadow-sm)}
.card-icon{font-size:28px;margin-bottom:12px}
.card h3{font-size:var(--text-lg);font-weight:600;margin-bottom:8px}
.card p{font-size:var(--text-sm);color:var(--text-secondary);line-height:1.6}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0;justify-content:center}
.badge{padding:4px 10px;border-radius:var(--badge-radius);font-size:11px;font-weight:600}
.badge-success{background:#22c55e20;color:#22c55e;border:1px solid #22c55e40}
.badge-warning{background:#f59e0b20;color:#f59e0b;border:1px solid #f59e0b40}
.badge-error{background:#ef444420;color:#ef4444;border:1px solid #ef444440}
.badge-info{background:#3b82f620;color:#3b82f6;border:1px solid #3b82f640}
.badge-neutral{background:var(--color-neutral-200);color:var(--text-secondary);border:1px solid var(--color-neutral-300)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:40px 0;text-align:center}
.stat-num{font-size:var(--text-4xl);font-weight:700;letter-spacing:var(--tracking-tight)}
.stat-label{font-size:var(--text-xs);color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;margin-top:4px}
.form-section{max-width:480px;margin:48px auto 0}
.form-section h2{font-size:var(--text-2xl);font-weight:700;margin-bottom:24px;text-align:center}
.field{margin-bottom:16px}
.field label{display:block;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.field input,.field select,.field textarea{width:100%;padding:10px 12px;background:var(--surface-base);border:var(--border-normal) solid var(--color-neutral-300);border-radius:var(--radius-md);color:var(--text-primary);font-family:var(--font-sans);font-size:14px;outline:none}
.field textarea{min-height:80px;resize:vertical}
</style></head><body>
<div class="nav"><div class="nav-logo">◈ Brand</div><div class="nav-links"><a href="#">Features</a><a href="#">Pricing</a><a href="#">About</a></div><button class="nav-cta">Get Started</button></div>
<div class="hero"><h1>Design System<br/>Showcase</h1><p>A complete token-driven design system with colors, typography, spacing, shadows, and component tokens.</p><div class="btns"><button class="btn-primary">Primary Action</button><button class="btn-secondary">Secondary</button></div></div>
<div class="badges"><span class="badge badge-success">Success</span><span class="badge badge-warning">Warning</span><span class="badge badge-error">Error</span><span class="badge badge-info">Info</span><span class="badge badge-neutral">Neutral</span></div>
<div class="grid"><div class="card"><div class="card-icon">◆</div><h3>Design Tokens</h3><p>Colors, typography, spacing, and shadows defined as reusable CSS custom properties.</p></div><div class="card"><div class="card-icon">◇</div><h3>Component API</h3><p>Button, card, input, badge, and nav tokens for consistent component styling.</p></div><div class="card"><div class="card-icon">○</div><h3>Gradient System</h3><p>Primary, hero, subtle, and surface gradients derived from the color palette.</p></div></div>
<div class="stats"><div><div class="stat-num">${Object.keys(tokens.colors.primary || {}).length * 4}</div><div class="stat-label">Colors</div></div><div><div class="stat-num">${Object.keys(ty.scale || {}).length}</div><div class="stat-label">Type Scale</div></div><div><div class="stat-num">${(tokens.spacing?.scale || []).length}</div><div class="stat-label">Spacing</div></div><div><div class="stat-num">${Object.keys(tokens.shadow || {}).length}</div><div class="stat-label">Shadows</div></div></div>
<div class="form-section"><h2>Form Elements</h2><div class="field"><label>Text Input</label><input type="text" placeholder="Enter value…" /></div><div class="field"><label>Select</label><select><option>Option One</option><option>Option Two</option></select></div><div class="field"><label>Textarea</label><textarea placeholder="Write something…"></textarea></div><button class="btn-primary" style="width:100%">Submit</button></div>
</body></html>`
  return <PreviewFrame html={html} />
}

function PreviewSocialPost({ tokens }: { tokens: DesignTokens }) {
  const css = tokensToCSS(tokens)
  const fi = fontImport(tokens)
  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
${fi}
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
${css}
body{display:flex;align-items:center;justify-content:center;min-height:100vh;background:#111;font-family:var(--font-sans)}
.post{width:540px;height:540px;background:var(--surface-base);border-radius:var(--radius-xl);overflow:hidden;position:relative;display:flex;flex-direction:column}
.post-gradient{position:absolute;top:0;left:0;right:0;height:55%;background:var(--gradient-hero);opacity:0.9}
.post-content{position:relative;z-index:1;flex:1;display:flex;flex-direction:column;justify-content:flex-end;padding:32px}
.post-tag{display:inline-block;padding:4px 10px;background:rgba(255,255,255,0.15);backdrop-filter:blur(8px);border-radius:var(--badge-radius);font-size:10px;font-weight:600;color:var(--text-inverse);text-transform:uppercase;letter-spacing:0.08em;width:fit-content;margin-bottom:12px}
.post-title{font-size:var(--text-4xl);font-weight:700;line-height:var(--leading-tight);letter-spacing:var(--tracking-tight);color:var(--text-inverse);margin-bottom:8px}
.post-excerpt{font-size:var(--text-sm);color:var(--text-inverse);opacity:0.8;line-height:1.5}
.post-footer{display:flex;align-items:center;justify-content:space-between;padding:16px 32px;border-top:var(--border-hairline) solid rgba(255,255,255,0.1)}
.post-brand{font-size:11px;font-weight:700;color:var(--text-inverse);opacity:0.6}
.post-date{font-size:10px;color:var(--text-inverse);opacity:0.4}
</style></head><body>
<div class="post"><div class="post-gradient"></div><div class="post-content"><div class="post-tag">Design System</div><div class="post-title">${tokens.meta?.vibeName || 'Your Brand'}</div><div class="post-excerpt">Generated with ${tokens.meta?.aesthetic || 'custom'} aesthetic — ${tokens.meta?.palette || 'dark'} mode.</div></div><div class="post-footer"><div class="post-brand">TASBIR</div><div class="post-date">${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</div></div></div>
</body></html>`
  return <PreviewFrame html={html} />
}

function PreviewFrame({ html }: { html: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  useEffect(() => {
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    setBlobUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [html])
  return <iframe src={blobUrl || ''} title="Preview" className="w-full h-full border-0" style={{ background: '#fff' }} />
}

function fontImport(t: DesignTokens) {
  const ty = t.typography || {}
  const fs = [ty.fontSans, ty.fontSerif, ty.fontMono].filter(Boolean)
  if (!fs.length) return ''
  const q = fs.map((f: string) => `family=${encodeURIComponent(f)}:ital,wght@0,300;0,400;0,500;0,600;0,700;0,900;1,400`).join('&')
  return `<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?${q}&display=swap" rel="stylesheet">`
}
