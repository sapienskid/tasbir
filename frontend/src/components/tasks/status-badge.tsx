import { memo } from "react"
import { Badge } from "@/components/ui/badge"

const VARIANTS: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  running: "secondary",
  completed: "default",
  failed: "destructive",
  needs_review: "outline",
  verified: "default",
}

export const StatusBadge = memo(function StatusBadge({ status }: { status: string }) {
  const variant = VARIANTS[status] ?? "secondary"
  return <Badge variant={variant}>{status}</Badge>
})
