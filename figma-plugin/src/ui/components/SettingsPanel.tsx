import React from 'react'

interface Props {
  apiBaseUrl: string
  setApiBaseUrl: (url: string) => void
  apiKey: string
  setApiKey: (key: string) => void
  onSave: () => void
}

export default function SettingsPanel({ apiBaseUrl, setApiBaseUrl, apiKey, setApiKey, onSave }: Props) {
  const labelStyle: React.CSSProperties = {
    display: 'block',
    marginBottom: 4,
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--figma-color-text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 10px',
    border: '1px solid var(--figma-color-border)',
    borderRadius: 6,
    fontSize: 12,
    background: 'var(--figma-color-bg)',
    color: 'var(--figma-color-text)',
    boxSizing: 'border-box',
    marginBottom: 12,
  }

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 4px 0', color: 'var(--figma-color-text)' }}>
          Tasbir API Connection
        </h3>
        <p style={{ fontSize: 11, color: 'var(--figma-color-text-secondary)', margin: 0 }}>
          Connect to your Tasbir API instance to generate social posts directly in Figma.
        </p>
      </div>

      <div>
        <label style={labelStyle}>API Base URL</label>
        <input
          style={inputStyle}
          value={apiBaseUrl}
          onChange={e => setApiBaseUrl(e.target.value)}
          placeholder="https://tasbir.example.com"
        />
      </div>

      <div>
        <label style={labelStyle}>API Key</label>
        <input
          style={inputStyle}
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder="sk-..."
        />
      </div>

      <button
        onClick={onSave}
        style={{
          width: '100%',
          padding: '10px 16px',
          border: 'none',
          borderRadius: 6,
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: 600,
          background: 'var(--figma-color-bg-brand)',
          color: 'var(--figma-color-text-onbrand)',
        }}
      >
        Save & Connect
      </button>
    </div>
  )
}
