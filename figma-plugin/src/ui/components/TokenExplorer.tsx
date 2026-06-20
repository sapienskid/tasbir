import React, { useState, useEffect } from 'react'
import { api } from '../api'

interface Props {
  onSyncTokens: (tokens: any) => void
}

const VIBE_PRESETS = [
  'Luxury', 'Brutalist', 'Organic', 'Dark Tech', 'Editorial',
  'Playful', 'Gothic', 'Retro', 'Minimal', 'Maximalist',
]

export default function TokenExplorer({ onSyncTokens }: Props) {
  const [tokens, setTokens] = useState<any>(null)
  const [vibe, setVibe] = useState('')
  const [primaryHint, setPrimaryHint] = useState('')
  const [secondaryHint, setSecondaryHint] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getTokens().then(data => setTokens(data)).catch(() => {})
  }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const data = await api.generateTokens({
        vibe: vibe || undefined,
        primaryHint: primaryHint || undefined,
        secondaryHint: secondaryHint || undefined,
      })
      setTokens(data)
      await api.saveTokens(data)
    } catch (e: any) {
      setError(e.message)
    }
    setGenerating(false)
  }

  const handleSync = () => {
    if (tokens) onSyncTokens(tokens)
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 11, fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', color: 'var(--figma-color-text-secondary)' }}>
          Vibe
        </label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {VIBE_PRESETS.map(v => (
            <button
              key={v}
              onClick={() => setVibe(v)}
              style={{
                padding: '4px 10px',
                border: `1px solid ${vibe === v ? 'var(--figma-color-border-brand)' : 'var(--figma-color-border)'}`,
                borderRadius: 14,
                cursor: 'pointer',
                fontSize: 11,
                background: vibe === v ? 'var(--figma-color-bg-brand)' : 'var(--figma-color-bg)',
                color: vibe === v ? 'var(--figma-color-text-onbrand)' : 'var(--figma-color-text)',
              }}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <input
            placeholder="Primary color (#hex)"
            value={primaryHint}
            onChange={e => setPrimaryHint(e.target.value)}
            style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--figma-color-border)', borderRadius: 4, fontSize: 11, background: 'var(--figma-color-bg)', color: 'var(--figma-color-text)', boxSizing: 'border-box' }}
          />
        </div>
        <div style={{ flex: 1 }}>
          <input
            placeholder="Secondary color (#hex)"
            value={secondaryHint}
            onChange={e => setSecondaryHint(e.target.value)}
            style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--figma-color-border)', borderRadius: 4, fontSize: 11, background: 'var(--figma-color-bg)', color: 'var(--figma-color-text)', boxSizing: 'border-box' }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          onClick={handleGenerate}
          disabled={generating}
          style={{
            flex: 1, padding: '8px 12px', border: 'none', borderRadius: 6, cursor: generating ? 'not-allowed' : 'pointer',
            fontSize: 12, fontWeight: 600, background: 'var(--figma-color-bg-brand)', color: 'var(--figma-color-text-onbrand)',
            opacity: generating ? 0.6 : 1,
          }}
        >
          {generating ? 'Generating...' : 'Generate Tokens'}
        </button>
        {tokens && (
          <button
            onClick={handleSync}
            style={{
              flex: 1, padding: '8px 12px', border: '1px solid var(--figma-color-border)', borderRadius: 6, cursor: 'pointer',
              fontSize: 12, fontWeight: 600, background: 'var(--figma-color-bg)', color: 'var(--figma-color-text)',
            }}
          >
            Sync to Figma Variables
          </button>
        )}
      </div>

      {error && <div style={{ color: 'var(--figma-color-text-danger)', fontSize: 11, marginBottom: 8 }}>{error}</div>}

      {tokens?.colors && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, color: 'var(--figma-color-text-secondary)', textTransform: 'uppercase' }}>
            Colors
          </div>
          {Object.entries(tokens.colors as Record<string, any>).map(([group, shades]) => (
            <div key={group} style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, fontWeight: 600, marginBottom: 3, color: 'var(--figma-color-text)' }}>{group}</div>
              <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                {typeof shades === 'object' && Object.entries(shades as Record<string, string>).map(([name, hex]) => (
                  <div
                    key={name}
                    title={`${group}/${name}: ${hex}`}
                    style={{
                      width: 22, height: 22, borderRadius: 4,
                      background: hex as string,
                      border: '1px solid var(--figma-color-border)',
                    }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
