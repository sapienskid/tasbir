import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { generateTokensComputational, tokensToCSS, tokensToPrompt, type DesignTokens } from '@/lib/tokens'

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
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({ color: true, typography: true, spacing: true, shadow: true, border: true, gradient: true, motion: true, component: true })
  const [exportTab, setExportTab] = useState<'css' | 'json' | 'prompt'>('css')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewTab, setPreviewTab] = useState<'components' | 'landing' | 'poster'>('components')
  const [_serverConfig, setServerConfig] = useState<any>(null)
  const [demoHtml, setDemoHtml] = useState<Record<string, string>>({})
  const [demoGenerating, setDemoGenerating] = useState(false)
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
        result = await api.generateTokens({ vibe: vibeLabel || 'custom design system', mode: 'ai' })
      } else {
        result = generateTokensComputational(primaryColor, secondaryColor, vibeLabel || 'computational')
      }
      setTokens(result)
      setDemoHtml({})
      setExpandedSections({ color: true, typography: true, spacing: true, shadow: true, border: true, gradient: true, motion: true, component: true })
    } catch (e: any) {
      setError(e.message || 'Token generation failed')
    } finally {
      setGenerating(false)
    }
  }

  async function generateDemo(type: 'components' | 'landing' | 'poster') {
    if (!tokens) return
    if (demoHtml[type]) return
    setDemoGenerating(true)
    setError(null)
    try {
      const res = await api.generateDemo({ tokens, demoType: type })
      setDemoHtml(prev => ({ ...prev, [type]: res.html }))
    } catch (e: any) {
      setError(e.message || 'Demo generation failed')
    } finally {
      setDemoGenerating(false)
    }
  }

  async function handlePreviewTabChange(tab: 'components' | 'landing' | 'poster') {
    setPreviewTab(tab)
    if (tokens && !demoHtml[tab]) {
      await generateDemo(tab)
    }
  }

  async function handleRegenDemo() {
    if (!tokens) return
    setDemoHtml(prev => {
      const next = { ...prev }
      delete next[previewTab]
      return next
    })
    await generateDemo(previewTab)
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
                expandedSections={expandedSections} toggleSection={toggleSection}
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
                <button onClick={() => handlePreviewTabChange('components')} className={`text-[10px] font-bold uppercase tracking-wider px-4 py-2.5 border-b-2 transition-colors ${previewTab === 'components' ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#999]'}`}>Components</button>
                <button onClick={() => handlePreviewTabChange('landing')} className={`text-[10px] font-bold uppercase tracking-wider px-4 py-2.5 border-b-2 transition-colors ${previewTab === 'landing' ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#999]'}`}>Landing Page</button>
                <button onClick={() => handlePreviewTabChange('poster')} className={`text-[10px] font-bold uppercase tracking-wider px-4 py-2.5 border-b-2 transition-colors ${previewTab === 'poster' ? 'text-white border-white' : 'text-[#555] border-transparent hover:text-[#999]'}`}>Poster</button>
                {demoHtml[previewTab] && (
                  <button onClick={handleRegenDemo} className="ml-auto mr-3 text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded border transition-all border-[#313131] text-[#555] hover:border-[#3d3d3d] hover:text-[#999]">↺ Regen</button>
                )}
              </div>
              <div className="flex-1 overflow-auto relative min-h-0" style={{ background: '#1c1c1c' }}>
                {tokens ? (
                  demoHtml[previewTab] ? (
                    <PreviewFrame html={demoHtml[previewTab]} />
                  ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#555' }}>
                      <div className="text-2xl opacity-25">◈</div>
                      <div className="text-[11px] font-bold uppercase tracking-wider">Generating {previewTab}…</div>
                    </div>
                  )
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" style={{ color: '#555' }}>
                    <div className="text-2xl opacity-25">◈</div>
                    <div className="text-[11px] font-bold uppercase tracking-wider">No system generated</div>
                    <div className="text-[10px]">Enter a vibe and generate</div>
                  </div>
                )}
                {(generating || demoGenerating) && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 z-10" style={{ background: '#0b0b0b' }}>
                    <div className="w-7 h-7 border-2 rounded-full animate-spin" style={{ borderColor: '#313131', borderTopColor: '#fff' }} />
                    <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#555' }}>{generating ? 'Building token system…' : `Generating ${previewTab}…`}</div>
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

/* ── Studio Tab ── */

function StudioTab({ mode, setMode, title, setTitle, content, setContent, slug, setSlug, formats, toggleFormat, generating, onGenerate, result, tokens, expandedSections, toggleSection }: any) {
  const FORMATS = [
    { id: 'instagram-portrait', label: 'IG Portrait', dims: '1080×1350' },
    { id: 'instagram-square', label: 'IG Square', dims: '1080×1080' },
    { id: 'twitter-card', label: 'Twitter', dims: '1200×628' },
    { id: 'linkedin-post', label: 'LinkedIn', dims: '1200×627' },
  ]

  return (
    <>
      {/* Generation Controls */}
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

      {/* Design Tokens View - Shared with TokensTab */}
      <div className="overflow-y-auto">
        {tokens ? (
          <>
            <div className="px-3.5 py-2 border-b" style={{ borderColor: '#252525' }}>
              <div className="flex items-center gap-2">
                <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: '#555' }}>Active System</span>
                <span className="text-[10px] font-bold tracking-wide" style={{ color: '#999' }}>{tokens.meta?.vibeName || 'CUSTOM'}</span>
              </div>
              {tokens.meta?.description && (
                <div className="text-[9px] mt-0.5" style={{ color: '#555' }}>{tokens.meta.description}</div>
              )}
            </div>
            <TokenSection title="Color" expanded={!!expandedSections.color} onToggle={() => toggleSection('color')}><ColorExplorer colors={tokens.colors} /></TokenSection>
            <TokenSection title="Typography" expanded={!!expandedSections.typography} onToggle={() => toggleSection('typography')}><TypographyExplorer typography={tokens.typography} /></TokenSection>
            <TokenSection title="Spacing" expanded={!!expandedSections.spacing} onToggle={() => toggleSection('spacing')}><SpacingExplorer spacing={tokens.spacing} /></TokenSection>
            <TokenSection title="Shadows" expanded={!!expandedSections.shadow} onToggle={() => toggleSection('shadow')}><ShadowExplorer shadows={tokens.shadow} /></TokenSection>
            <TokenSection title="Border" expanded={!!expandedSections.border} onToggle={() => toggleSection('border')}><BorderExplorer border={tokens.border} /></TokenSection>
            <TokenSection title="Gradients" expanded={!!expandedSections.gradient} onToggle={() => toggleSection('gradient')}><GradientExplorer gradients={tokens.gradient} /></TokenSection>
            <TokenSection title="Motion" expanded={!!expandedSections.motion} onToggle={() => toggleSection('motion')}><MotionExplorer motion={tokens.motion} /></TokenSection>
            <TokenSection title="Components" expanded={!!expandedSections.component} onToggle={() => toggleSection('component')}><ComponentExplorer components={tokens.component} /></TokenSection>
          </>
        ) : (
          <div className="p-6 text-center" style={{ color: '#555', fontSize: 11, lineHeight: 1.7 }}>
            Generate a design system in the<br /><strong style={{ color: '#999' }}>Tokens</strong> tab to see tokens here
          </div>
        )}
      </div>
    </>
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

function MotionExplorer({ motion }: { motion: DesignTokens['motion'] }) {
  if (!motion) return null
  return (
    <div className="space-y-3">
      <div>
        <div className="text-[8px] font-bold uppercase tracking-widest mb-1" style={{ color: '#555' }}>Duration</div>
        <div className="space-y-1">
          {Object.entries(motion.duration || {}).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 py-0.5">
              <div 
                className="h-2 rounded-sm flex-shrink-0 transition-all" 
                style={{ 
                  width: parseInt(v) / 5, 
                  background: 'linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%)',
                  opacity: 0.7
                }} 
              />
              <span className="text-[8px] font-mono min-w-[40px]" style={{ color: '#555' }}>{k}</span>
              <span className="text-[8px] font-mono ml-auto" style={{ color: '#999' }}>{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[8px] font-bold uppercase tracking-widest mb-1" style={{ color: '#555' }}>Easing</div>
        <div className="space-y-1">
          {Object.entries(motion.easing || {}).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 py-0.5">
              <span className="text-[8px] font-mono min-w-[40px]" style={{ color: '#555' }}>{k}</span>
              <span className="text-[8px] font-mono truncate" style={{ color: '#999', maxWidth: 150 }} title={v}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── Preview ── */

function PreviewFrame({ html }: { html: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  useEffect(() => {
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    setBlobUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [html])
  if (!blobUrl) return null
  return <iframe src={blobUrl} title="Preview" className="w-full h-full border-0" style={{ background: '#fff' }} />
}
