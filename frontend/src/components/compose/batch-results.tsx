import { Link } from "react-router-dom"
import { ExternalLink, Loader2, Pencil } from "lucide-react"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/tasks/status-badge"
import { isSettledStatus, useComposeBatch } from "@/hooks/use-compose"
import type { PlatformInfo } from "@/lib/api"
import { platformLabel } from "./model"

/**
 * Batch results: every task of the batch with its live status (polled every
 * 2s until all settle) and a link to its task page.
 */
export function BatchResults({
  batchId,
  platforms,
  onEdit,
}: {
  batchId: string
  platforms: PlatformInfo[]
  onEdit: () => void
}) {
  const { data, error, isLoading } = useComposeBatch(batchId)
  const tasks = data?.tasks ?? []
  const settled = tasks.filter((t) => isSettledStatus(t.status)).length
  const failed = tasks.filter((t) => t.status === "failed").length

  return (
    <section aria-labelledby="batch-results-heading" className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="batch-results-heading" className="text-base font-semibold">
            Batch results
          </h2>
          <p className="text-xs text-muted-foreground" role="status" aria-live="polite">
            {tasks.length === 0
              ? isLoading
                ? "Loading…"
                : "No tasks in this batch."
              : settled < tasks.length
                ? `Rendering ${settled}/${tasks.length}…`
                : `All ${tasks.length} done${failed ? ` · ${failed} failed` : ""}.`}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onEdit} disabled={tasks.length === 0}>
          <Pencil aria-hidden="true" className="size-4" />
          Edit composition
        </Button>
      </div>
      {error ? (
        <p className="rounded-md border border-destructive/50 p-3 text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load batch"}
        </p>
      ) : null}
      <ol className="grid gap-2">
        {tasks.map((t, i) => {
          const first = t.composition?.post.slides[0]
          const text = first?.copy.headline || first?.copy.body || first?.template_id || ""
          return (
            <li key={t.task_id} className="flex flex-wrap items-center gap-3 rounded-md border p-3">
              <span className="w-6 text-xs text-muted-foreground tabular-nums">{i + 1}.</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {platformLabel(platforms.find((p) => p.id === t.platform) ?? { id: t.platform })}
                  {t.composition && t.composition.post.slides.length > 1
                    ? ` · ${t.composition.post.slides.length} slides`
                    : ""}
                </p>
                <p className="truncate text-xs text-muted-foreground">{text}</p>
              </div>
              {!isSettledStatus(t.status) ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin text-muted-foreground" />
              ) : null}
              <StatusBadge status={t.status} />
              <Button asChild variant="ghost" size="sm">
                <Link to={`/tasks/${t.task_id}`}>
                  Open <ExternalLink aria-hidden="true" className="size-3.5" />
                </Link>
              </Button>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
