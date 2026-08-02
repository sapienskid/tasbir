import { memo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"

const EMPTY_ISSUES: string[] = []

interface QCReportProps {
  score?: number
  issues?: string[]
  critique?: string
  status?: string
}

export const QCReport = memo(function QCReport({
  score,
  issues = EMPTY_ISSUES,
  critique,
  status,
}: QCReportProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm">Quality Check</CardTitle>
        {status ? <Badge variant={status === "verified" ? "default" : "outline"}>{status}</Badge> : null}
      </CardHeader>
      <CardContent className="grid gap-4">
        {typeof score === "number" ? (
          <div className="grid gap-1">
            <div className="flex items-center justify-between text-sm">
              <span>Score</span>
              <span className="font-medium tabular-nums">{score}/100</span>
            </div>
            <Progress value={score} />
          </div>
        ) : null}
        {issues.length > 0 ? (
          <ul className="grid gap-1.5 text-sm text-muted-foreground">
            {issues.map((issue, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-destructive">•</span>
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No issues reported.</p>
        )}
        {critique ? (
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{critique}</p>
        ) : null}
      </CardContent>
    </Card>
  )
})
