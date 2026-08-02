import { lazy, Suspense } from "react"
import { memo } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { useTheme } from "@/lib/theme"

// Monaco is ~5MB — only loaded when the editor pane actually mounts.
const MonacoEditor = lazy(() =>
  import("@monaco-editor/react").then((m) => ({ default: m.default }))
)

interface HtmlEditorProps {
  value: string
  onChange: (value: string) => void
}

export const HtmlEditor = memo(function HtmlEditor({ value, onChange }: HtmlEditorProps) {
  const { resolved } = useTheme()
  return (
    <Suspense fallback={<Skeleton className="h-full w-full" />}>
      <MonacoEditor
        language="html"
        theme={resolved === "dark" ? "vs-dark" : "light"}
        value={value}
        onChange={(v) => onChange(v ?? "")}
        loading={<Skeleton className="h-full w-full" />}
        options={{
          minimap: { enabled: false },
          fontSize: 13,
          scrollBeyondLastLine: false,
          wordWrap: "on",
          tabSize: 2,
        }}
      />
    </Suspense>
  )
})
