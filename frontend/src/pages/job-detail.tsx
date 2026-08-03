import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, ExternalLink, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/tasks/status-badge"
import { getAgentJob } from "@/lib/api"
import useSWR from "swr"

export default function JobDetailPage() {
  const { jobId = "" } = useParams()
  const navigate = useNavigate()

  const { data: job, error, isLoading } = useSWR(
    `/agent-jobs/${jobId}`,
    () => getAgentJob(jobId),
    {
      refreshInterval: (j) =>
        j && (j.status === "pending" || j.status === "running") ? 3000 : 0,
    }
  )

  if (isLoading && !job) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-96 rounded-lg" />
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="grid gap-4">
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="icon" aria-label="Back">
            <Link to="/">
              <ArrowLeft aria-hidden="true" className="size-4" />
            </Link>
          </Button>
          <h1 className="text-xl font-semibold">Job not found</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          This agent job no longer exists.{" "}
          <Link to="/" className="underline">
            Back to Tasks
          </Link>
        </p>
      </div>
    )
  }

  const result = job.result ?? {}
  const isTemplate = job.kind === "template"
  const running = job.status === "pending" || job.status === "running"
  const templateId = result.template_id as string | undefined
  const dsId = (result.design_system_id as string | undefined) ?? "default"

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="Back">
            <Link to="/">
              <ArrowLeft aria-hidden="true" className="size-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-xl font-semibold">
              {isTemplate ? "Template creation" : "Brand builder"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {job.title} · started {job.created_at ? new Date(job.created_at).toLocaleString() : "—"}
            </p>
          </div>
        </div>
        <StatusBadge status={job.status} />
      </div>

      <div className="grid gap-3 rounded-lg border p-6">
        {isTemplate ? (
          <div className="grid gap-1">
            <p className="text-sm font-medium">Template build</p>
            <p className="text-xs text-muted-foreground">
              The agent authors, validates, and saves the template in the
              background — this runs even if you close the page.
            </p>
          </div>
        ) : (
          <div className="grid gap-1">
            <p className="text-sm font-medium">Brand builder job</p>
            <p className="text-xs text-muted-foreground">
              The agent generates identity, tokens, campaigns, and starter
              templates in the background.
            </p>
          </div>
        )}

        {running ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            Working…
          </p>
        ) : null}

        {job.status === "completed" ? (
          <div className="flex flex-wrap items-center gap-3">
            {isTemplate && templateId ? (
              <>
                <p className="text-sm text-muted-foreground">
                  Created:{" "}
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {templateId}
                  </code>
                </p>
                <Button
                  size="sm"
                  onClick={() => navigate(`/templates?open=${encodeURIComponent(templateId)}`)}
                >
                  <ExternalLink aria-hidden="true" className="size-3.5" />
                  Open template
                </Button>
              </>
            ) : null}
            {!isTemplate && dsId ? (
              <>
                <p className="text-sm text-muted-foreground">
                  Created: <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{dsId}</code>
                  {" · "}
                  {((result.templates as string[] | undefined) ?? []).length} templates
                </p>
                <Button
                  size="sm"
                  onClick={() => navigate(`/design-systems?ds=${encodeURIComponent(dsId)}`)}
                >
                  Open design system
                </Button>
              </>
            ) : null}
          </div>
        ) : null}

        {job.status === "failed" ? (
          <p className="text-sm text-destructive">
            {job.error || "The job failed. Try again."}
          </p>
        ) : null}
      </div>
    </div>
  )
}