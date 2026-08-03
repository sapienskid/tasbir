import { useCallback, useState } from "react"
import { UploadCloud } from "lucide-react"

interface DropzoneProps {
  accept?: string
  onFile: (file: File) => void
  busy?: boolean
  hint?: string
}

/**
 * Hand-rolled drag-and-drop file input (no dependency needed for a single file).
 * The whole box is a <label> wrapping a visually-hidden but focusable file
 * input, so mouse, keyboard (Tab → Enter/Space), and drag-and-drop all work.
 */
export function Dropzone({ accept = "image/png,image/jpeg,image/webp,image/gif", onFile, busy, hint }: DropzoneProps) {
  const [over, setOver] = useState(false)

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setOver(false)
      const file = e.dataTransfer.files?.[0]
      if (file) onFile(file)
    },
    [onFile]
  )

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
      className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground transition-colors ${
        over ? "border-primary bg-muted/50" : "hover:bg-muted/30"
      }`}
    >
      <UploadCloud aria-hidden="true" className={`size-6 ${over ? "text-primary" : ""}`} />
      {busy ? (
        <span>Uploading…</span>
      ) : (
        <>
          <span>Drop an image here, or click to browse</span>
          {hint ? <span className="text-xs">{hint}</span> : null}
        </>
      )}
      <input
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
          e.target.value = ""
        }}
      />
    </label>
  )
}
