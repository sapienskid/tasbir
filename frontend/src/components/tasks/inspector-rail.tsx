import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { QCReport } from "@/components/editor/qc-report"
import { AgentChat } from "@/components/editor/agent-chat"
import { X } from "lucide-react"

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
}

export function InspectorRail({
  onClose,
  qc,
  taskId,
  format,
  currentHtml,
  onApplyHtml,
}: InspectorRailProps) {
  const [tab, setTab] = useState<"quality" | "agent">("quality")

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-md border">
      <div className="flex shrink-0 items-center justify-between border-b px-2 py-1">
        <Tabs value={tab} onValueChange={(v) => setTab(v as "quality" | "agent")}>
          <TabsList className="h-8">
            <TabsTrigger value="quality" className="px-2 text-xs">
              Quality
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
          <X className="size-4" />
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col p-3">
        {tab === "quality" ? (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <QCReport
              score={qc?.score}
              issues={qc?.issues}
              critique={qc?.critique}
              status={qc?.status}
            />
          </div>
        ) : (
          <AgentChat
            taskId={taskId}
            format={format}
            currentHtml={currentHtml}
            onApplyHtml={onApplyHtml}
          />
        )}
      </div>
    </div>
  )
}
