import React from 'react'

interface Props {
  message: string
  progress: number
  total: number
}

export default function ProgressBar({ message, progress, total }: Props) {
  const pct = total > 0 ? Math.round((progress / total) * 100) : 0

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 11, color: 'var(--figma-color-text-secondary)' }}>
        <span>{message}</span>
        <span>{progress}/{total}</span>
      </div>
      <div style={{ height: 4, background: 'var(--figma-color-bg-secondary)', borderRadius: 2, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: 'var(--figma-color-bg-brand)',
            borderRadius: 2,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}
