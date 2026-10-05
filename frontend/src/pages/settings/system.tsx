import { useRef, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ConfirmAction } from "@/components/settings/confirm-action"
import { useSystemInfo } from "@/hooks/use-system-info"
import {
  downloadBlob,
  exportSystem,
  importSystem,
  type SystemSnapshot,
} from "@/lib/api"

const TABLES: { key: keyof SystemSnapshot; label: string }[] = [
  { key: "design_systems", label: "Design systems" },
  { key: "templates", label: "Templates" },
  { key: "design_languages", label: "Design languages" },
  { key: "platforms", label: "Platforms" },
  { key: "fonts", label: "Fonts" },
  { key: "agents", label: "Agents" },
  { key: "app_settings", label: "Runtime settings" },
]

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[180px_minmax(0,1fr)] gap-4 border-b py-2 last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="min-w-0 text-sm break-words">{children}</span>
    </div>
  )
}

function YesNo({ value }: { value: boolean }) {
  return value ? (
    <Badge variant="outline" className="text-emerald-500">
      configured
    </Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      not set
    </Badge>
  )
}

export default function SystemPanel() {
  const { info, isLoading } = useSystemInfo()
  const fileRef = useRef<HTMLInputElement>(null)
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [pending, setPending] = useState<SystemSnapshot | null>(null)
  const [applied, setApplied] = useState<Record<string, number> | null>(null)

  const handleExport = async () => {
    setExporting(true)
    try {
      const snap = await exportSystem()
      const stamp = snap.exported_at
        ? snap.exported_at.replace(/[^0-9]/g, "").slice(0, 14)
        : new Date().toISOString().slice(0, 10).replace(/-/g, "")
      downloadBlob(
        new Blob([JSON.stringify(snap, null, 2)], { type: "application/json" }),
        `tasbir-backup-${stamp}.json`,
      )
      toast.success("Configuration exported")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed")
    } finally {
      setExporting(false)
    }
  }

  /** Parse + validate client-side, then ask before touching the database. */
  const handleFile = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text()) as SystemSnapshot
      if (parsed.schema_version !== 1 && parsed.schema_version !== 2) {
        toast.error(`Unsupported backup version ${String(parsed.schema_version)}`)
        return
      }
      setPending(parsed)
    } catch {
      toast.error("That file is not valid JSON")
    }
  }

  const confirmImport = async () => {
    if (!pending) return
    setImporting(true)
    try {
      const res = await importSystem(pending)
      setApplied(res.applied)
      setPending(null)
      toast.success("Configuration imported")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Import failed")
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div>
        <h2 className="text-lg font-semibold">System</h2>
        <p className="text-sm text-muted-foreground">
          The environment actually in force, and the configuration backup.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Environment</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && !info ? (
            <Skeleton className="h-56 w-full" />
          ) : !info ? (
            <p className="text-sm text-destructive">Could not load system info.</p>
          ) : (
            <>
              <Row label="Version">{info.version}</Row>
              <Row label="AI Gateway">
                <span className="flex flex-wrap items-center gap-2">
                  <YesNo value={info.llm_configured} />
                  <span className="font-mono text-xs">{info.gateway_id}</span>
                </span>
              </Row>
              <Row label="Decision models">
                <span className="font-mono text-xs">{info.decision_provider_order}</span>
              </Row>
              <Row label="Redis">
                <YesNo value={info.redis_configured} />
              </Row>
              <Row label="Render service">
                <span className="font-mono text-xs">{info.renderer_url}</span>
              </Row>
              <Row label="Stock photo keys">
                <YesNo value={info.photo_keys_configured} />
              </Row>
              <Row label="Artifact retention">
                {info.output_ttl_hours} hours
                {info.delete_on_download ? " (deleted on download)" : ""}
              </Row>
              <Row label="Rate limits">
                <span className="font-mono text-xs">
                  {info.rate_limit_per_min}/min generation ·{" "}
                  {info.rate_limit_interactive_per_min}/min interactive
                </span>
              </Row>
              <Row label="Max image bytes">{info.image_max_bytes.toLocaleString()}</Row>
              <Row label="Copy QA enforced">
                {info.copy_qa_enforce ? "blocking" : "advisory"}
              </Row>
              <Row label="Skip verification">
                {info.skip_verify ? (
                  <Badge variant="destructive">dev bypass active</Badge>
                ) : (
                  "off"
                )}
              </Row>
              <Row label="Backup format">schema v{info.schema_version}</Row>
              <Row label="Stored rows">
                <span className="flex flex-wrap gap-1.5">
                  {Object.entries(info.counts).map(([k, n]) => (
                    <Badge key={k} variant="secondary" className="font-mono text-[11px]">
                      {k} {n}
                    </Badge>
                  ))}
                </span>
              </Row>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <p className="text-sm text-muted-foreground">
            Downloads every configuration table as one JSON document — design systems, templates,
            design languages, platforms, fonts, agent prompts, and runtime settings. Tasks, audit
            logs and chats are runtime data and are not included.
          </p>
          <div>
            <Button size="sm" onClick={handleExport} disabled={exporting}>
              {exporting ? "Exporting…" : "Download backup"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Import configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <p className="text-sm text-muted-foreground">
            Restores a backup by merging it in: rows are matched by primary key and overwritten,
            and anything not in the file is left untouched. Nothing is ever deleted.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void handleFile(file)
                // Allow re-picking the same file after a cancel.
                e.target.value = ""
              }}
            />
            <Button size="sm" variant="outline" onClick={() => fileRef.current?.click()}>
              Choose backup file
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPending(null)} disabled={!pending}>
              Clear
            </Button>
          </div>

          {pending ? (
            <div className="grid gap-2 rounded-md border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Ready to import
                </p>
                <Badge variant="outline">schema v{pending.schema_version}</Badge>
              </div>
              <ul className="grid gap-0.5 sm:grid-cols-2">
                {TABLES.map((t) => {
                  const rows = (pending[t.key] as unknown[] | undefined) ?? []
                  if (rows.length === 0) return null
                  return (
                    <li key={t.key} className="flex justify-between text-sm">
                      <span>{t.label}</span>
                      <span className="font-mono text-xs">{rows.length} rows</span>
                    </li>
                  )
                })}
              </ul>
              <div className="flex justify-end">
                <ConfirmAction
                  trigger={
                    <Button size="sm" disabled={importing}>
                      {importing ? "Importing…" : "Import this backup"}
                    </Button>
                  }
                  title="Import this backup?"
                  description="Rows matching by primary key will be overwritten with the file's values. Rows not in the file, and built-in design languages, are left untouched."
                  confirmLabel="Import"
                  onConfirm={confirmImport}
                />
              </div>
            </div>
          ) : null}

          {applied ? (
            <div className="grid gap-1 rounded-md border p-3">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Last import applied
              </p>
              <ul className="grid gap-0.5 sm:grid-cols-2">
                {Object.entries(applied).map(([table, n]) => (
                  <li key={table} className="flex justify-between text-sm">
                    <span>{TABLES.find((t) => t.key === table)?.label ?? table}</span>
                    <span className="font-mono text-xs">{n} rows</span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs text-muted-foreground">
                Built-in design languages resolve live from code and are reported as 0 applied.
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
