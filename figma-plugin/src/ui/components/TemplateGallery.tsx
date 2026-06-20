import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function TemplateGallery() {
  const [templates, setTemplates] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getTemplates().then(data => {
      setTemplates(data.templates || [])
    }).catch((e: any) => {
      setError(e.message)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ fontSize: 12, color: 'var(--figma-color-text-secondary)' }}>Loading templates...</div>
  if (error) return <div style={{ fontSize: 12, color: 'var(--figma-color-text-danger)' }}>{error}</div>

  const enabled = templates.filter(t => t.enabled)
  if (enabled.length === 0) {
    return <div style={{ fontSize: 12, color: 'var(--figma-color-text-secondary)', textAlign: 'center', padding: 20 }}>No templates available. Create templates in the API.</div>
  }

  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', color: 'var(--figma-color-text-secondary)' }}>
        {enabled.length} template(s)
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {enabled.map(t => (
          <div
            key={t.id}
            style={{
              padding: '8px 10px',
              border: '1px solid var(--figma-color-border)',
              borderRadius: 6,
              background: 'var(--figma-color-bg)',
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--figma-color-text)' }}>{t.name || t.id}</div>
            {t.description && (
              <div style={{ fontSize: 10, color: 'var(--figma-color-text-secondary)', marginTop: 2 }}>{t.description}</div>
            )}
            <div style={{ fontSize: 10, color: 'var(--figma-color-text-tertiary)', marginTop: 2 }}>
              Slots: {(t.slots || []).join(', ') || 'none'} · Category: {t.category || 'general'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
