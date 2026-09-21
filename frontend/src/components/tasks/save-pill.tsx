import { AlertCircle, Check, Loader2 } from "lucide-react"
import type { SaveSnapshot } from "@/lib/save-queue"

function clock(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

/** Save status: Saved 10:42 / Saving… / Unsaved / Failed — Retry. */
export function SavePill({ save, onRetry }: { save: SaveSnapshot; onRetry: () => void }) {
  const base = "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
  if (save.phase === "saving") {
    return (
      <span role="status" data-save="saving" className={`${base} text-muted-foreground`}>
        <Loader2 aria-hidden="true" className="size-3 animate-spin" /> Saving…
      </span>
    )
  }
  if (save.phase === "error") {
    const retrying = save.error?.retryable && save.retryInMs
    return (
      <span
        role="status"
        data-save="error"
        title={save.error?.message}
        className={`${base} border-destructive/50 text-destructive`}
      >
        <AlertCircle aria-hidden="true" className="size-3" />
        {retrying ? `Offline — retrying in ${Math.ceil((save.retryInMs ?? 0) / 1000)}s` : "Failed"}
        <button type="button" onClick={onRetry} className="font-medium underline underline-offset-2">
          Retry
        </button>
      </span>
    )
  }
  if (save.phase === "dirty") {
    return (
      <span role="status" data-save="dirty" className={`${base} text-muted-foreground`}>
        <span aria-hidden="true" className="size-1.5 rounded-full bg-amber-500" /> Unsaved
      </span>
    )
  }
  return (
    <span role="status" data-save="saved" className={`${base} text-muted-foreground`}>
      <Check aria-hidden="true" className="size-3" />
      {save.lastSavedAt ? `Saved ${clock(save.lastSavedAt)}` : "Saved"}
    </span>
  )
}
