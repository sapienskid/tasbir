import { memo } from "react"
import { Skeleton } from "@/components/ui/skeleton"

interface PreviewPaneProps {
  src?: string
  width: number
  height: number
  loading?: boolean
}

export const PreviewPane = memo(function PreviewPane({
  src,
  width,
  height,
  loading,
}: PreviewPaneProps) {
  if (loading) {
    return <Skeleton className="h-full w-full" />
  }
  return (
    <div className="flex h-full min-h-80 items-center justify-center rounded-md border bg-muted/20 p-6">
      {src ? (
        <img
          src={src}
          alt="Rendered design preview"
          className="max-h-full max-w-full border object-contain shadow-sm"
          style={{ aspectRatio: `${width} / ${height}` }}
        />
      ) : (
        <p className="text-sm text-muted-foreground">
          No preview yet — render this format to generate a PNG.
        </p>
      )}
    </div>
  )
})
