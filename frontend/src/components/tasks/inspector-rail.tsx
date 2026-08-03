import { useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { QCReport } from "@/components/editor/qc-report"
import { AgentChat } from "@/components/editor/agent-chat"
import { getTaskAudit } from "@/lib/api"
import { Activity, Eye, X } from "lucide-react"
import { cn } from "@/lib/utils"

export interface QcState {
  score?: number
  issues: string[]
  critique: string
  status?: string
}

interface InspectorRailProps {
  onClose: () => void
  qc: QcState | null
  taskId: string
  format: string
  currentHtml: string
  onApplyHtml: (html: string) => void
  onApplyAndRender: (html: string) => void
  /** Runs the vision audit on the current format. */
  onAudit: () => void
  auditing: boolean
  /** When true, the Trace tab polls live while the pipeline is running. */
  running?: boolean
}

export function InspectorRail({
  onClose,
  qc,
  taskId,
  format,
  currentHtml,
  onApplyHtml,
  onApplyAndRender,
  onAudit,
  auditing,
  running = false,
}: InspectorRailProps) {
  const [tab, setTab] = useState<"quality" | "agent" | "trace">("quality")
  const { data: audit } = useSWR(
    tab === "trace" ? `/tasks/${taskId}/audit` : null,
    () => getTaskAudit(taskId),
    { refreshInterval: tab === "trace" && running ? 2500 : 0 }
  )

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-md border">
      <div className="flex shrink-0 items-center justify-between border-b px-2 py-1">
        <Tabs value={tab} onValueChange={(v) => setTab(v as "quality" | "agent" | "trace")}>
          <TabsList className="h-8">
            <TabsTrigger value="quality" className="px-2 text-xs">
              Quality
            </TabsTrigger>
            <TabsTrigger value="trace" className="px-2 text-xs">
              Trace
            </TabsTrigger>
            <TabsTrigger value="agent" className="px-2 text-xs">
              Agent
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close inspector"
          onClick={onClose}
          className="h-7 w-7"
        >
          <X aria-hidden="true" className="size-4" />
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col p-3">
        {tab === "quality" ? (
          <div className="grid min-h-0 flex-1 content-start gap-3 overflow-y-auto">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-muted-foreground">Quality</p>
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={onAudit}
                disabled={auditing}
              >
                <Eye aria-hidden="true" className="size-3.5" />
                {auditing ? "Auditing…" : "Run audit"}
              </Button>
            </div>
            <QCReport
              score={qc?.score}
              issues={qc?.issues}
              critique={qc?.critique}
              status={qc?.status}
            />
          </div>
        ) : tab === "trace" ? (
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
            <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Activity aria-hidden="true" className="size-3.5" />
              Agent steps
            </p>
            {!audit || audit.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No trace yet — steps are recorded when the task runs.
              </p>
            ) : (
              audit.map((entry) => {
                const decision = entry.decision ?? {}
                const status = String(decision.status ?? decision.category ?? "")
                return (
                  <div key={entry.id} className="rounded-md border px-2 py-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold">{entry.agent_name}</span>
                      <span className="flex items-center gap-1.5">
                        {typeof decision.pass === "boolean" ? (
                          <BadgeStatus ok={Boolean(decision.pass)} />
                        ) : null}
                        {decision.score != null ? (
                          <span className="text-[10px] text-muted-foreground">
                            {String(decision.score)}
                          </span>
                        ) : null}
                        {status ? (
                          <span className="text-[10px] text-muted-foreground">{status}</span>
                        ) : null}
                      </span>
                    </div>
                    {entry.critique ? (
                      <p className="mt-0.5 line-clamp-3 text-xs text-muted-foreground">
                        {entry.critique}
                      </p>
                    ) : null}
                  </div>
                )
              })
            )}
          </div>
        ) : (
          <AgentChat
            taskId={taskId}
            format={format}
            currentHtml={currentHtml}
            onApplyHtml={onApplyHtml}
            onApplyAndRender={onApplyAndRender}
          />
        )}
      </div>
    </div>
  )
}

function BadgeStatus({ ok }: { ok: boolean }) {
  return (
    <span
      role="img"
      aria-label={ok ? "passed" : "failed"}
      className={cn(
        "inline-flex h-2 w-2 rounded-full",
        ok ? "bg-emerald-500" : "bg-destructive"
      )}
      title={ok ? "passed" : "failed"}
    />
  )
}
