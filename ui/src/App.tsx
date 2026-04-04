import { useState, useEffect } from 'react'
import {
  Sparkles,
  Palette,
  Terminal,
  History,
  ChevronRight,
  ImageIcon,
  Type,
  Play,
  CheckCircle2,
  Loader2,
  Copy,
  ExternalLink,
  RefreshCw,
  Save
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Label } from '@/components/ui/label'
import { api, setApiKey, getApiKey } from '@/lib/api'

const FORMATS = [
  { id: 'instagram-portrait', label: 'IG Portrait', dims: '1080×1350' },
  { id: 'instagram-square', label: 'IG Square', dims: '1080×1080' },
  { id: 'instagram-story', label: 'IG Story', dims: '1080×1920' },
  { id: 'twitter-card', label: 'Twitter Card', dims: '1200×628' },
  { id: 'linkedin-post', label: 'LinkedIn', dims: '1200×627' },
  { id: 'carousel-post', label: 'Carousel', dims: '1080×1350' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<'studio' | 'design' | 'prompts' | 'history'>('studio')
  const [tokens, setTokens] = useState<Record<string, any>>({})
  const [prompts, setPrompts] = useState<Record<string, any>>({})
  const [_formats, setFormats] = useState<Record<string, any>>({})
  const [_loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<any[]>([])
  const [apiKeyInput, setApiKeyInput] = useState(getApiKey())
  const [showKey, setShowKey] = useState(false)

  useEffect(() => {
    loadConfig()
  }, [])

  function handleApiKeyChange(value: string) {
    setApiKeyInput(value)
    setApiKey(value)
  }

  useEffect(() => {
    loadConfig()
  }, [])

  async function loadConfig() {
    try {
      const [tokensRes, promptsRes, formatsRes] = await Promise.all([
        api.getDesignTokens().catch(() => ({ tokens: {}, tailwindConfig: '' })),
        api.getPrompts().catch(() => ({})),
        api.getFormats().catch(() => ({ formats: {} })),
      ])
      setTokens(tokensRes.tokens || {})
      setPrompts(promptsRes)
      setFormats(formatsRes.formats || {})
    } catch {
      // Config load failed, continue with defaults
    }
  }

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col">
        <div className="p-6 flex items-center gap-3 border-b border-slate-800">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
            T
          </div>
          <h1 className="text-xl font-bold tracking-tight">Tasbir <span className="text-blue-500">AI</span></h1>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <NavItem active={activeTab === 'studio'} onClick={() => setActiveTab('studio')} icon={<Sparkles size={18} />} label="Studio" />
          <NavItem active={activeTab === 'design'} onClick={() => setActiveTab('design')} icon={<Palette size={18} />} label="Design System" />
          <NavItem active={activeTab === 'prompts'} onClick={() => setActiveTab('prompts')} icon={<Terminal size={18} />} label="AI Prompts" />
          <NavItem active={activeTab === 'history'} onClick={() => setActiveTab('history')} icon={<History size={18} />} label="History" />
        </nav>

        <div className="p-4 border-t border-slate-800 space-y-3">
          <div>
            <label className="text-xs text-slate-500 font-medium px-1">API Key</label>
            <div className="flex gap-1 mt-1">
              <Input
                type={showKey ? 'text' : 'password'}
                value={apiKeyInput}
                onChange={(e) => handleApiKeyChange(e.target.value)}
                placeholder="sp_..."
                className="bg-slate-900 border-slate-700 h-7 text-xs font-mono"
              />
              <button
                onClick={() => setShowKey(!showKey)}
                className="px-2 text-xs text-slate-500 hover:text-slate-300 shrink-0"
              >
                {showKey ? '••' : '👁'}
              </button>
            </div>
          </div>
          <div className="px-1 text-xs text-slate-500">
            API: <span className="text-slate-300 font-mono">{import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8787'}</span>
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-slate-400" onClick={loadConfig}>
            <RefreshCw size={14} className="mr-2" /> Refresh Config
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/10 via-slate-950 to-slate-950">
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-8 bg-slate-950/50 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span>App</span>
            <ChevronRight size={14} />
            <span className="text-slate-100 capitalize">{activeTab}</span>
          </div>
          <div className="px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-xs font-semibold text-blue-400">
            Beta v2.0
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-6xl mx-auto space-y-8">
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
                {error}
                <button onClick={() => setError(null)} className="ml-4 text-red-300 hover:text-red-200">Dismiss</button>
              </div>
            )}

            {activeTab === 'studio' && <StudioView setLoading={setLoading} setError={setError} setHistory={setHistory} />}
            {activeTab === 'design' && <DesignView tokens={tokens} />}
            {activeTab === 'prompts' && <PromptsView prompts={prompts} setPrompts={setPrompts} />}
            {activeTab === 'history' && <HistoryView history={history} />}
          </div>
        </div>
      </main>
    </div>
  )
}

function NavItem({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 w-full px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
        active
          ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20 shadow-[0_0_15px_-3px_rgba(59,130,246,0.2)]'
          : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50 border border-transparent'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

function StudioView({ setLoading, setError, setHistory }: { setLoading: (v: boolean) => void; setError: (v: string | null) => void; setHistory: React.Dispatch<React.SetStateAction<any[]>> }) {
  const [mode, setMode] = useState<'content' | 'slug'>('content')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [slug, setSlug] = useState('')
  const [prompt, setPrompt] = useState('')
  const [selectedFormats, setSelectedFormats] = useState<string[]>(['instagram-portrait', 'twitter-card', 'linkedin-post'])
  const [imageMode, setImageMode] = useState('auto')
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<any>(null)

  async function handleGenerate() {
    if (mode === 'content' && (!title.trim() || !content.trim())) {
      setError('Title and content are required')
      return
    }
    if (mode === 'slug' && !slug.trim()) {
      setError('Slug is required')
      return
    }

    setGenerating(true)
    setLoading(true)
    setError(null)

    try {
      const body: any = {
        formats: selectedFormats,
        prompt: prompt || undefined,
        image: { mode: imageMode },
      }

      if (mode === 'content') {
        body.title = title.trim()
        body.content = content.trim()
      } else {
        body.slug = slug.trim()
      }

      const res = await api.generateFromContent(body)
      setResult(res)
      setHistory(prev => [res, ...prev])
    } catch (e: any) {
      setError(e.message || 'Generation failed')
    } finally {
      setGenerating(false)
      setLoading(false)
    }
  }

  function toggleFormat(id: string) {
    setSelectedFormats(prev =>
      prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]
    )
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Input Section */}
      <Card className="bg-slate-900/40 border-slate-800/60 backdrop-blur-md shadow-2xl overflow-hidden relative group">
        <div className="absolute top-0 right-0 -m-8 w-64 h-64 bg-blue-600/10 rounded-full blur-[100px] pointer-events-none group-hover:bg-blue-600/15 transition-colors duration-700"></div>
        <CardHeader>
          <CardTitle className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Sparkles className="text-blue-500" size={24} />
            Tasbir Studio
          </CardTitle>
          <p className="text-slate-400 max-w-2xl">
            Generate AI-powered social media designs from your content. AI creates complete HTML with Tailwind CSS.
          </p>
        </CardHeader>
        <CardContent className="space-y-6 relative">
          {/* Mode Toggle */}
          <Tabs value={mode} onValueChange={(v) => setMode(v as 'content' | 'slug')} className="w-full">
            <TabsList>
              <TabsTrigger value="content">Direct Content</TabsTrigger>
              <TabsTrigger value="slug">Ghost Slug</TabsTrigger>
            </TabsList>
          </Tabs>

          {mode === 'content' ? (
            <div className="space-y-4">
              <div>
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Your post title"
                  className="bg-slate-950 border-slate-800 mt-1"
                />
              </div>
              <div>
                <Label htmlFor="content">Content</Label>
                <Textarea
                  id="content"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Paste your article content here..."
                  className="bg-slate-950 border-slate-800 mt-1 min-h-[120px]"
                />
              </div>
            </div>
          ) : (
            <div>
              <Label htmlFor="slug">Ghost Post Slug</Label>
              <Input
                id="slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="my-post-slug"
                className="bg-slate-950 border-slate-800 mt-1"
              />
            </div>
          )}

          <div>
            <Label htmlFor="prompt">Additional Prompt (optional)</Label>
            <Input
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g., Make it dark themed with bold typography"
              className="bg-slate-950 border-slate-800 mt-1"
            />
          </div>

          {/* Format Selection */}
          <div>
            <Label className="mb-2 block">Output Formats</Label>
            <div className="flex flex-wrap gap-2">
              {FORMATS.map((f) => (
                <button
                  key={f.id}
                  onClick={() => toggleFormat(f.id)}
                  className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
                    selectedFormats.includes(f.id)
                      ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
                      : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  {f.label}
                  <span className="ml-1 text-slate-500">{f.dims}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Image Mode */}
          <div>
            <Label>Image Mode</Label>
            <div className="flex gap-2 mt-2">
              {['auto', 'none', 'feature', 'ai'].map((m) => (
                <button
                  key={m}
                  onClick={() => setImageMode(m)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    imageMode === m
                      ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
                      : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <Button
            onClick={handleGenerate}
            disabled={generating}
            size="lg"
            className="w-full bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20"
          >
            {generating ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
            {generating ? 'Generating...' : 'Generate Assets'}
          </Button>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
              <ImageIcon size={20} className="text-slate-400" />
              Generated Assets
            </h3>
            <Badge variant="default" className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
              <CheckCircle2 size={12} className="mr-1" />
              {Object.keys(result.assets || {}).filter(k => result.assets[k]).length} assets
            </Badge>
          </div>

          {/* HTML Preview */}
          {result.llm_output?.generated_html && (
            <Card className="bg-slate-900/40 border-slate-800/60">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-mono text-slate-400">Generated HTML</CardTitle>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(result.llm_output.generated_html)}>
                      <Copy size={14} className="mr-1" /> Copy
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="bg-slate-950 rounded-lg p-4 text-xs text-slate-300 overflow-auto max-h-64 font-mono">
                  {result.llm_output.generated_html.slice(0, 2000)}
                  {result.llm_output.generated_html.length > 2000 ? '...' : ''}
                </pre>
              </CardContent>
            </Card>
          )}

          {/* Asset Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(result.assets || {}).map(([key, asset]: [string, any]) =>
              asset ? (
                <Card key={key} className="bg-slate-900 border-slate-800 overflow-hidden hover:border-slate-600 transition-all shadow-xl hover:-translate-y-1 duration-300">
                  <div className="aspect-[4/3] bg-slate-950 relative overflow-hidden flex items-center justify-center">
                    <div className="text-center p-4">
                      <Badge className="mb-2">{key}</Badge>
                      <p className="text-xs text-slate-500 font-mono">{asset.key}</p>
                    </div>
                  </div>
                  <div className="p-4 flex items-center justify-between">
                    <div className="text-sm font-medium text-slate-300">{asset.format}</div>
                    {asset.url && (
                      <a href={asset.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:text-blue-400 font-semibold flex items-center gap-1">
                        View <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </Card>
              ) : null
            )}
          </div>

          {/* Captions */}
          {result.llm_output && (
            <Card className="bg-slate-900/40 border-slate-800/60">
              <CardHeader>
                <CardTitle className="text-sm text-slate-400">Generated Captions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {result.llm_output.instagram_caption && (
                  <div>
                    <Label className="text-xs text-slate-500">Instagram</Label>
                    <p className="text-sm text-slate-300 mt-1">{result.llm_output.instagram_caption}</p>
                  </div>
                )}
                {result.llm_output.twitter_caption && (
                  <div>
                    <Label className="text-xs text-slate-500">Twitter</Label>
                    <p className="text-sm text-slate-300 mt-1">{result.llm_output.twitter_caption}</p>
                  </div>
                )}
                {result.llm_output.linkedin_caption && (
                  <div>
                    <Label className="text-xs text-slate-500">LinkedIn</Label>
                    <p className="text-sm text-slate-300 mt-1">{result.llm_output.linkedin_caption}</p>
                  </div>
                )}
                {result.llm_output.hashtags?.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {result.llm_output.hashtags.map((tag: string, i: number) => (
                      <Badge key={i} variant="secondary" className="text-xs">{tag}</Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {!result && !generating && (
        <div className="h-64 border-2 border-dashed border-slate-800/50 rounded-3xl flex flex-col items-center justify-center text-slate-500 gap-3 group hover:border-slate-700 transition-colors">
          <ImageIcon size={32} className="group-hover:text-slate-400 transition-colors" />
          <p className="text-sm">Configure your content and click Generate to create AI-powered designs.</p>
        </div>
      )}
    </div>
  )
}

function DesignView({ tokens }: { tokens: any }) {
  const [editing, setEditing] = useState<Record<string, string>>({})

  useEffect(() => {
    if (tokens.colors || tokens.fonts || tokens.spacing) {
      const all: Record<string, string> = {}
      if (tokens.colors) Object.entries(tokens.colors).forEach(([k, v]) => { all[`colors.${k}`] = v as string })
      if (tokens.fonts) Object.entries(tokens.fonts).forEach(([k, v]) => { all[`fonts.${k}`] = v as string })
      if (tokens.spacing) Object.entries(tokens.spacing).forEach(([k, v]) => { all[`spacing.${k}`] = v as string })
      setEditing(all)
    }
  }, [tokens])

  function handleSave() {
    // In production, POST to /config/design-tokens
    console.log('Saving tokens:', editing)
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Palette className="text-blue-500" size={24} />
            Design Tokens
          </h2>
          <p className="text-slate-400 mt-1">Manage the design system used by AI when generating HTML with Tailwind CSS.</p>
        </div>
        <Button onClick={handleSave} className="bg-blue-600 hover:bg-blue-500">
          <Save size={16} className="mr-2" /> Save Tokens
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {Object.entries(editing).map(([key, value]) => {
          const isColor = key.startsWith('colors.')
          return (
            <Card key={key} className="bg-slate-900/40 border-slate-800 hover:bg-slate-900/60 transition-colors">
              <CardContent className="flex items-center gap-4 p-5">
                {isColor ? (
                  <div className="w-10 h-10 rounded-lg border border-slate-700 shrink-0" style={{ backgroundColor: value }} />
                ) : (
                  <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                    <Type size={18} className="text-slate-400" />
                  </div>
                )}
                <div className="flex-1 space-y-1">
                  <Label className="text-xs font-bold text-slate-500 uppercase tracking-wider">{key}</Label>
                  <Input
                    value={value}
                    onChange={(e) => setEditing({ ...editing, [key]: e.target.value })}
                    className="bg-transparent border-none p-0 h-auto text-slate-100 font-medium focus-visible:ring-0"
                  />
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {tokens.tailwindConfig && (
        <Card className="bg-slate-900/40 border-slate-800/60">
          <CardHeader>
            <CardTitle className="text-sm text-slate-400">Tailwind Config Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-slate-950 rounded-lg p-4 text-xs text-slate-300 overflow-auto max-h-64 font-mono">
              {tokens.tailwindConfig}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function PromptsView({ prompts, setPrompts }: { prompts: any; setPrompts: (v: any) => void }) {
  const [activePrompt, setActivePrompt] = useState('gemini_html_generation_system_prompt')

  const promptKeys = [
    { key: 'gemini_html_generation_system_prompt', label: 'HTML Generation (System)' },
    { key: 'gemini_html_generation_user_instructions', label: 'HTML Generation (User)' },
    { key: 'copy_system_prompt', label: 'Copy System' },
    { key: 'copy_user_instructions', label: 'Copy User' },
  ]

  const currentPrompt = prompts[activePrompt] || []
  const promptText = Array.isArray(currentPrompt) ? currentPrompt.join('\n') : ''

  function handleSave() {
    // In production, POST to update prompts
    console.log('Saving prompt:', activePrompt, promptText)
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 h-full flex flex-col">
      <div className="space-y-1 shrink-0">
        <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <Terminal className="text-blue-500" size={24} />
          AI System Prompts
        </h2>
        <p className="text-slate-400">Configure how the AI interprets and generates HTML structures.</p>
      </div>

      <div className="flex gap-2 shrink-0">
        {promptKeys.map((pk) => (
          <button
            key={pk.key}
            onClick={() => setActivePrompt(pk.key)}
            className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
              activePrompt === pk.key
                ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
                : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600'
            }`}
          >
            {pk.label}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-[400px] bg-slate-950 border border-slate-800 rounded-3xl overflow-hidden flex flex-col shadow-2xl">
        <div className="bg-slate-900/50 px-6 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/40"></div>
              <div className="w-3 h-3 rounded-full bg-amber-500/20 border border-amber-500/40"></div>
              <div className="w-3 h-3 rounded-full bg-emerald-500/20 border border-emerald-500/40"></div>
            </div>
            <span className="text-xs font-mono text-slate-500">{activePrompt}.md</span>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(promptText)}>
              <Copy size={14} className="mr-1" /> Copy
            </Button>
            <Button variant="ghost" size="sm" onClick={handleSave} className="text-blue-500">
              <Save size={14} className="mr-1" /> Save
            </Button>
          </div>
        </div>
        <Textarea
          value={promptText}
          onChange={(e) => {
            const lines = e.target.value.split('\n')
            setPrompts({ ...prompts, [activePrompt]: lines })
          }}
          placeholder="# System Instructions..."
          className="flex-1 w-full bg-transparent p-8 font-mono text-sm text-slate-300 resize-none outline-none focus:ring-0 leading-relaxed border-none"
        />
      </div>
    </div>
  )
}

function HistoryView({ history }: { history: any[] }) {
  if (history.length === 0) {
    return (
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <History className="text-blue-500" size={24} />
          Generation History
        </h2>
        <div className="h-64 border-2 border-dashed border-slate-800/50 rounded-3xl flex flex-col items-center justify-center text-slate-500 gap-3">
          <History size={32} />
          <p className="text-sm">No generations yet. Create your first design in Studio.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
        <History className="text-blue-500" size={24} />
        Generation History
      </h2>
      <div className="space-y-4">
        {history.map((item, i) => (
          <Card key={i} className="bg-slate-900/40 border-slate-800/60">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-200">{item.slug}</p>
                  <p className="text-xs text-slate-500 mt-1">{item.requested_formats?.join(', ')}</p>
                </div>
                <Badge variant="secondary">{Object.keys(item.assets || {}).filter(k => item.assets[k]).length} assets</Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
