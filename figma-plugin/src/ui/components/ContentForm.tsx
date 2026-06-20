import React, { useState } from 'react'
import FormatSelector from './FormatSelector'

interface Props {
  formats: { id: string; width: number; height: number; name?: string }[]
  onGenerate: (title: string, content: string, selectedFormats: string[], prompt?: string, imageMode?: string, designTokens?: any) => void
  onRenderHtml: (html: string, format: string, slug: string, width: number, height: number, designTokens?: any, slotValues?: Record<string, string>) => void
  generating: boolean
}

export default function ContentForm({ formats, onGenerate, generating }: Props) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [selectedFormats, setSelectedFormats] = useState<string[]>([])
  const [prompt, setPrompt] = useState('')
  const [imageMode, setImageMode] = useState('auto')

  const handleSubmit = () => {
    onGenerate(title, content, selectedFormats, prompt || undefined, imageMode || undefined, undefined)
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
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    marginBottom: 4,
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--figma-color-text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  }

  const sectionStyle: React.CSSProperties = { marginBottom: 14 }

  return (
    <div>
      <div style={sectionStyle}>
        <label style={labelStyle}>Title</label>
        <input style={inputStyle} value={title} onChange={e => setTitle(e.target.value)} placeholder="Post title..." />
      </div>

      <div style={sectionStyle}>
        <label style={labelStyle}>Content</label>
        <textarea
          style={{ ...inputStyle, minHeight: 100, resize: 'vertical' }}
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="Paste your article or post content here..."
        />
      </div>

      <div style={sectionStyle}>
        <label style={labelStyle}>Output Formats</label>
        <FormatSelector formats={formats} selected={selectedFormats} onChange={setSelectedFormats} />
      </div>

      <div style={sectionStyle}>
        <label style={labelStyle}>Style Prompt (optional)</label>
        <input style={inputStyle} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="e.g. Make it bold and minimal..." />
      </div>

      <div style={sectionStyle}>
        <label style={labelStyle}>Image Mode</label>
        <select style={inputStyle} value={imageMode} onChange={e => setImageMode(e.target.value)}>
          <option value="auto">Auto (AI decides)</option>
          <option value="ai">Always generate AI image</option>
          <option value="none">No images</option>
        </select>
      </div>

      <button
        onClick={handleSubmit}
        disabled={generating || !title || !content || selectedFormats.length === 0}
        style={{
          width: '100%',
          padding: '10px 16px',
          border: 'none',
          borderRadius: 6,
          cursor: generating ? 'not-allowed' : 'pointer',
          fontSize: 13,
          fontWeight: 600,
          background: generating ? 'var(--figma-color-bg-disabled)' : 'var(--figma-color-bg-brand)',
          color: generating ? 'var(--figma-color-text-disabled)' : 'var(--figma-color-text-onbrand)',
          opacity: generating ? 0.6 : 1,
        }}
      >
        {generating ? 'Generating...' : 'Generate Social Posts'}
      </button>
    </div>
  )
}
