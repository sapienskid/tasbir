import React from 'react'

interface Props {
  formats: { id: string; width: number; height: number; name?: string }[]
  selected: string[]
  onChange: (selected: string[]) => void
}

export default function FormatSelector({ formats, selected, onChange }: Props) {
  const toggle = (id: string) => {
    if (selected.includes(id)) {
      onChange(selected.filter(s => s !== id))
    } else {
      onChange([...selected, id])
    }
  }

  const chipStyle = (isSelected: boolean): React.CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '5px 10px',
    margin: '0 6px 6px 0',
    border: `1px solid ${isSelected ? 'var(--figma-color-border-brand)' : 'var(--figma-color-border)'}`,
    borderRadius: 20,
    cursor: 'pointer',
    fontSize: 11,
    fontWeight: 500,
    background: isSelected ? 'var(--figma-color-bg-brand)' : 'var(--figma-color-bg)',
    color: isSelected ? 'var(--figma-color-text-onbrand)' : 'var(--figma-color-text)',
  })

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap' }}>
      {formats.map(f => (
        <div key={f.id} style={chipStyle(selected.includes(f.id))} onClick={() => toggle(f.id)}>
          <span>{f.name || f.id}</span>
          <span style={{ opacity: 0.6, fontSize: 10 }}>{f.width}x{f.height}</span>
        </div>
      ))}
    </div>
  )
}
