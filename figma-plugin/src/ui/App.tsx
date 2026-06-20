import React, { useState, useEffect } from 'react'
import ContentForm from './components/ContentForm'
import FormatSelector from './components/FormatSelector'
import ProgressBar from './components/ProgressBar'
import SettingsPanel from './components/SettingsPanel'
import TokenExplorer from './components/TokenExplorer'
import TemplateGallery from './components/TemplateGallery'
import { api, setApiConfig } from './api'
import type { FormatConfig, GenerationResult } from './api'

type Tab = 'generate' | 'templates' | 'tokens' | 'settings'

const TAB_LABELS: Record<Tab, string> = {
  generate: 'Generate',
  templates: 'Templates',
  tokens: 'Tokens',
  settings: 'Settings',
}

export default function App() {
  const [tab, setTab] = useState<Tab>('settings')
  const [apiBaseUrl, setApiBaseUrl] = useState('http://localhost:8787')
  const [apiKey, setApiKey] = useState('')
  const [configured, setConfigured] = useState(false)
  const [formats, setFormats] = useState<{ id: string; width: number; height: number; name?: string }[]>([])
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState<{ message: string; progress: number; total: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    parent.postMessage({ pluginMessage: { type: 'GET_SETTINGS' } }, '*')
    const handler = (event: MessageEvent) => {
      const msg = event.data?.pluginMessage
      if (!msg) return
      if (msg.type === 'SETTINGS_LOADED' && msg.settings) {
        const { apiBaseUrl: url, apiKey: key } = msg.settings
        if (url) setApiBaseUrl(url)
        if (key) setApiKey(key)
        setApiConfig(url || 'http://localhost:8787', key || '')
        setConfigured(true)
      }
      if (msg.type === 'FRAME_CREATED') {
        setGenerating(false)
        setProgress(null)
        parent.postMessage({ pluginMessage: { type: 'NOTIFY', message: 'Frames created in Figma!' } }, '*')
      }
      if (msg.type === 'ERROR') {
        setError(msg.message || 'Unknown error')
        setGenerating(false)
        setProgress(null)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [])

  useEffect(() => {
    if (!configured) return
    api.getFormats().then(data => {
      const fmtList = Object.entries(data.formats || {}).map(([id, f]) => ({
        id, width: f.width, height: f.height, name: f.name,
      }))
      setFormats(fmtList)
    }).catch(() => {})
  }, [configured])

  const handleConfigure = () => {
    setApiConfig(apiBaseUrl, apiKey)
    parent.postMessage({
      pluginMessage: {
        type: 'SAVE_SETTINGS',
        payload: { apiBaseUrl, apiKey },
      },
    }, '*')
    setConfigured(true)
  }

  const handleGenerate = async (title: string, content: string, selectedFormats: string[], prompt?: string, imageMode?: string, designTokens?: any) => {
    if (!title || !content || selectedFormats.length === 0) {
      setError('Title, content, and at least one format are required')
      return
    }

    setGenerating(true)
    setProgress({ message: 'Starting...', progress: 0, total: selectedFormats.length })
    setError(null)

    try {
      const result = await api.generateFromContent({
        title,
        content,
        output: { formats: selectedFormats, postCount: 1 },
        prompt: prompt || undefined,
        image: imageMode ? { mode: imageMode } : undefined,
        designTokens: designTokens || undefined,
      })

      const metadata: Record<string, any> = {}
      for (const format of selectedFormats) {
        metadata[format] = {
          width: formats.find(f => f.id === format)?.width || 1080,
          height: formats.find(f => f.id === format)?.height || 1080,
          slug: result.slug,
          html: result.html_by_format?.[format] || '',
          template_html: result.template_html_by_format?.[format] || '',
          slot_values: result.slot_values_by_format?.[format] || {},
        }
      }

      parent.postMessage({
        pluginMessage: {
          type: 'CREATE_FRAMES_FROM_ASSETS',
          payload: {
            assets: result.assets,
            metadata,
            formats: selectedFormats,
          },
        },
      }, '*')
    } catch (e: any) {
      setError(e.message || 'Generation failed')
      setGenerating(false)
      setProgress(null)
    }
  }

  const handleRenderHtml = async (
    html: string, format: string, slug: string,
    width: number, height: number, designTokens?: any, slotValues?: Record<string, string>
  ) => {
    setGenerating(true)
    setError(null)
    try {
      const data = await api.renderHtml({ html, width, height, format, slug, designTokens, slot_values: slotValues })
      parent.postMessage({
        pluginMessage: {
          type: 'UPDATE_FRAME_FILL',
          payload: { frameId: (window as any).__editingFrameId, dataUri: data.asset.url },
        },
      }, '*')
      setGenerating(false)
    } catch (e: any) {
      setError(e.message || 'Re-render failed')
      setGenerating(false)
    }
  }

  const handleSyncTokens = (tokens: any) => {
    parent.postMessage({
      pluginMessage: {
        type: 'CREATE_TOKEN_VARIABLES',
        payload: tokens,
      },
    }, '*')
  }

  // Settings tab shown until configured
  if (!configured) {
    return (
      <SettingsPanel
        apiBaseUrl={apiBaseUrl}
        setApiBaseUrl={setApiBaseUrl}
        apiKey={apiKey}
        setApiKey={setApiKey}
        onSave={handleConfigure}
      />
    )
  }

  return (
    <div style={{ padding: 16, fontFamily: 'Inter, sans-serif', fontSize: 13, color: 'var(--figma-color-text)' }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {(Object.keys(TAB_LABELS) as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              flex: 1,
              padding: '8px 12px',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: 600,
              background: tab === t ? 'var(--figma-color-bg-brand)' : 'var(--figma-color-bg-secondary)',
              color: tab === t ? 'var(--figma-color-text-onbrand)' : 'var(--figma-color-text)',
            }}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: 8, marginBottom: 12, background: 'var(--figma-color-bg-danger)', color: 'var(--figma-color-text-ondanger)', borderRadius: 6, fontSize: 12 }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 8, background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontWeight: 700 }}>x</button>
        </div>
      )}

      {tab === 'generate' && (
        <div>
          <ContentForm
            formats={formats}
            onGenerate={handleGenerate}
            onRenderHtml={handleRenderHtml}
            generating={generating}
          />
          {progress && <ProgressBar message={progress.message} progress={progress.progress} total={progress.total} />}
        </div>
      )}
      {tab === 'templates' && <TemplateGallery />}
      {tab === 'tokens' && <TokenExplorer onSyncTokens={handleSyncTokens} />}
      {tab === 'settings' && (
        <SettingsPanel
          apiBaseUrl={apiBaseUrl}
          setApiBaseUrl={setApiBaseUrl}
          apiKey={apiKey}
          setApiKey={setApiKey}
          onSave={handleConfigure}
        />
      )}
    </div>
  )
}
