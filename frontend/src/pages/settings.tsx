import { useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { toast } from "sonner"
import { usePlatforms } from "@/hooks/use-platforms"
import {
  createPoolFont,
  createPlatform,
  deletePlatform,
  deletePoolFont,
  exportSystem,
  getRuntimeSettings,
  importSystem,
  listFontPool,
  resetRuntimeSettings,
  updatePoolFont,
  updatePlatform,
  updateRuntimeSettings,
  type PlatformCreate,
  type PoolFontCreate,
  type SystemSnapshot,
} from "@/lib/api"
import { downloadBlob } from "@/lib/api"

const FAMILIES = ["square", "portrait", "story", "landscape"] as const
const FONT_ROLES = ["sans", "serif", "display", "mono"] as const

export default function SettingsPage() {
  const [tab, setTab] = useState<"platforms" | "fonts" | "runtime" | "system">("platforms")

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList>
          <TabsTrigger value="platforms">Platforms</TabsTrigger>
          <TabsTrigger value="fonts">Fonts</TabsTrigger>
          <TabsTrigger value="runtime">Runtime</TabsTrigger>
          <TabsTrigger value="system">Backup</TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "platforms" ? <PlatformsTab /> : null}
      {tab === "fonts" ? <FontsTab /> : null}
      {tab === "runtime" ? <RuntimeTab /> : null}
      {tab === "system" ? <BackupTab /> : null}
    </div>
  )
}

// ─── Platforms ──────────────────────────────────────────────────────────────

function PlatformsTab() {
  const { platforms, isLoading, mutate } = usePlatforms()
  const [editing, setEditing] = useState<PlatformCreate | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [open, setOpen] = useState(false)

  function openNew() {
    setEditing({ id: "", name: "", width: 1080, height: 1080, family: "square", is_active: true, sort_order: 0 })
    setIsNew(true)
    setOpen(true)
  }

  function openEdit(row: (typeof platforms)[number]) {
    setEditing({
      id: row.id,
      name: row.name,
      width: row.width,
      height: row.height,
      family: row.family,
      is_active: row.is_active,
      sort_order: row.sort_order,
    })
    setIsNew(false)
    setOpen(true)
  }

  async function save() {
    if (!editing) return
    try {
      if (isNew) {
        await createPlatform(editing)
      } else {
        await updatePlatform(editing.id, {
          name: editing.name,
          width: editing.width,
          height: editing.height,
          family: editing.family,
          is_active: editing.is_active,
          sort_order: editing.sort_order,
        })
      }
      await mutate()
      toast.success("Saved")
      setOpen(false)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    }
  }

  async function remove(id: string) {
    try {
      await deletePlatform(id)
      await mutate()
      setOpen(false)
      toast.success("Deleted")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed")
    }
  }

  if (isLoading && platforms.length === 0) return <Skeleton className="h-64 rounded-md" />

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={openNew}>
          Add platform
        </Button>
      </div>
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Dimensions</TableHead>
                <TableHead>Family</TableHead>
                <TableHead className="text-right">Sort</TableHead>
                <TableHead className="text-right">Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {platforms.map((p) => (
                <TableRow
                  key={p.id}
                  className="cursor-pointer"
                  tabIndex={0}
                  role="button"
                  onClick={() => openEdit(p)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      openEdit(p)
                    }
                  }}
                >
                  <TableCell className="font-mono">{p.id}</TableCell>
                  <TableCell>{p.name || p.id}</TableCell>
                  <TableCell className="font-mono">
                    {p.width}×{p.height}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{p.family}</Badge>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">{p.sort_order}</TableCell>
                  <TableCell className="text-right">
                    {p.is_active ? <span className="text-emerald-500">yes</span> : <span className="text-muted-foreground">no</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{isNew ? "Add platform" : `Edit ${editing?.id}`}</DialogTitle>
          </DialogHeader>
          {editing ? (
            <PlatformForm
              value={editing}
              isNew={isNew}
              onChange={setEditing}
              onSave={() => void save()}
              onDelete={isNew ? undefined : () => void remove(editing.id)}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function PlatformForm({
  value,
  isNew,
  onChange,
  onSave,
  onDelete,
}: {
  value: PlatformCreate
  isNew: boolean
  onChange: (v: PlatformCreate) => void
  onSave: () => void
  onDelete?: () => void
}) {
  return (
    <div className="grid gap-3">
      <div className="grid gap-2">
        <Label htmlFor="plat-id">ID (url-safe, e.g. mastodon-post)</Label>
        <Input id="plat-id" value={value.id} disabled={!isNew} onChange={(e) => onChange({ ...value, id: e.target.value.trim() })} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-2">
          <Label htmlFor="plat-width">Width (px)</Label>
          <Input id="plat-width" type="number" value={value.width} onChange={(e) => onChange({ ...value, width: Number(e.target.value) || 1080 })} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="plat-height">Height (px)</Label>
          <Input id="plat-height" type="number" value={value.height} onChange={(e) => onChange({ ...value, height: Number(e.target.value) || 1080 })} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-2">
          <Label htmlFor="plat-family">Family</Label>
          <Select value={value.family} onValueChange={(v) => onChange({ ...value, family: v as typeof value.family })}>
            <SelectTrigger id="plat-family"><SelectValue /></SelectTrigger>
            <SelectContent>
              {FAMILIES.map((f) => (
                <SelectItem key={f} value={f}>{f}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="plat-sort">Sort order</Label>
          <Input id="plat-sort" type="number" value={value.sort_order} onChange={(e) => onChange({ ...value, sort_order: Number(e.target.value) || 0 })} />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox id="plat-active" checked={value.is_active} onCheckedChange={(c) => onChange({ ...value, is_active: c === true })} />
        <Label htmlFor="plat-active" className="font-normal">Active</Label>
      </div>
      <div className="flex justify-between">
        {onDelete ? (
          <Button variant="destructive" size="sm" onClick={onDelete}>
            Delete
          </Button>
        ) : <span />}
        <Button onClick={onSave}>Save</Button>
      </div>
    </div>
  )
}

// ─── Fonts ──────────────────────────────────────────────────────────────────

function FontsTab() {
  const { data: fonts, isLoading, mutate } = useSWR("/fonts/pool", () => listFontPool())
  const [editing, setEditing] = useState<PoolFontCreate | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [open, setOpen] = useState(false)

  function openNew() {
    setEditing({ family: "", role: "sans", weights: [400], style: "", is_active: true, sort_order: 0 })
    setIsNew(true)
    setOpen(true)
  }
  function openEdit(f: NonNullable<typeof fonts>[number]) {
    setEditing({ family: f.family, role: f.role, weights: f.weights, style: f.style, is_active: f.is_active, sort_order: f.sort_order })
    setIsNew(false)
    setOpen(true)
  }

  async function save() {
    if (!editing) return
    try {
      if (isNew) {
        await createPoolFont(editing)
      } else {
        await updatePoolFont(editing.family, {
          role: editing.role,
          weights: editing.weights,
          style: editing.style,
          is_active: editing.is_active,
          sort_order: editing.sort_order,
        })
      }
      await mutate()
      toast.success("Saved")
      setOpen(false)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    }
  }

  async function remove(family: string) {
    try {
      await deletePoolFont(family)
      await mutate()
      setOpen(false)
      toast.success("Deleted")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed")
    }
  }

  if (isLoading && !fonts) return <Skeleton className="h-64 rounded-md" />

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={openNew}>
          Add font
        </Button>
      </div>
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Family</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Weights</TableHead>
                <TableHead>Style</TableHead>
                <TableHead className="text-right">Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(fonts ?? []).map((f) => (
                <TableRow
                  key={f.family}
                  className="cursor-pointer"
                  tabIndex={0}
                  role="button"
                  onClick={() => openEdit(f)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      openEdit(f)
                    }
                  }}
                >
                  <TableCell className="font-medium">{f.family}</TableCell>
                  <TableCell><Badge variant="outline">{f.role}</Badge></TableCell>
                  <TableCell className="font-mono text-xs">{f.weights.join(", ")}</TableCell>
                  <TableCell className="text-muted-foreground">{f.style || "—"}</TableCell>
                  <TableCell className="text-right">
                    {f.is_active ? <span className="text-emerald-500">yes</span> : <span className="text-muted-foreground">no</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing?.family ? `Edit ${editing.family}` : "Add font"}</DialogTitle>
          </DialogHeader>
          {editing ? (
            <div className="grid gap-3">
              <div className="grid gap-2">
                <Label htmlFor="font-family">Family</Label>
                <Input id="font-family" value={editing.family} disabled={!isNew} onChange={(e) => setEditing({ ...editing, family: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <Label htmlFor="font-role">Role</Label>
                  <Select value={editing.role} onValueChange={(v) => setEditing({ ...editing, role: v })}>
                    <SelectTrigger id="font-role"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FONT_ROLES.map((r) => (
                        <SelectItem key={r} value={r}>{r}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="font-weights">Weights (comma-separated)</Label>
                  <Input
                    id="font-weights"
                    value={editing.weights.join(", ")}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        weights: e.target.value.split(",").map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n)),
                      })
                    }
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="font-style">Style</Label>
                <Input id="font-style" value={editing.style} onChange={(e) => setEditing({ ...editing, style: e.target.value })} />
              </div>
              <div className="flex items-center gap-2">
                <Checkbox id="font-active" checked={editing.is_active} onCheckedChange={(c) => setEditing({ ...editing, is_active: c === true })} />
                <Label htmlFor="font-active" className="font-normal">Active</Label>
              </div>
              <div className="flex justify-between">
                {!isNew ? (
                  <Button variant="destructive" size="sm" onClick={() => void remove(editing.family)}>
                    Delete
                  </Button>
                ) : <span />}
                <Button onClick={() => void save()}>Save</Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ─── Runtime settings ───────────────────────────────────────────────────────

function RuntimeTab() {
  const { data, isLoading, mutate } = useSWR("/settings", () => getRuntimeSettings())
  const [draft, setDraft] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)

  const defaults = useMemo(() => data?.defaults ?? {}, [data])
  const values = useMemo(() => ({ ...(data?.values ?? {}), ...draft }), [data, draft])

  function setValue(key: string, value: unknown) {
    setDraft((d) => ({ ...d, [key]: value }))
  }

  async function save() {
    setSaving(true)
    try {
      const res = await updateRuntimeSettings(draft)
      setDraft({})
      await mutate(res, { revalidate: false })
      toast.success("Settings saved")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function reset() {
    try {
      const res = await resetRuntimeSettings()
      setDraft({})
      await mutate(res, { revalidate: false })
      toast.success("Settings reset")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reset failed")
    }
  }

  if (isLoading && !data) return <Skeleton className="h-64 rounded-md" />

  const keys = Object.keys(defaults)
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Pipeline tuning knobs</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {keys.length === 0 ? (
          <p className="text-sm text-muted-foreground">No runtime settings.</p>
        ) : (
          keys.map((key) => (
            <div key={key} className="grid grid-cols-[minmax(0,1fr)_140px] items-center gap-4">
              <div>
                <p className="text-sm font-medium font-mono">{key}</p>
                <p className="text-xs text-muted-foreground">{defaults[key]?.description}</p>
              </div>
              <Input
                type="number"
                step="any"
                aria-label={key}
                value={String(values[key] ?? "")}
                onChange={(e) => setValue(key, Number(e.target.value))}
              />
            </div>
          ))
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => void reset()}>
            Reset
          </Button>
          <Button onClick={() => void save()} disabled={saving || Object.keys(draft).length === 0}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── System export / import (config backup & restore) ──────────────────────

function BackupTab() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [applied, setApplied] = useState<Record<string, number> | null>(null)

  async function handleExport() {
    setExporting(true)
    try {
      const snap = await exportSystem()
      const stamp = snap.exported_at ? snap.exported_at.replace(/[^0-9]/g, "").slice(0, 14) : new Date().toISOString().slice(0, 10)
      downloadBlob(new Blob([JSON.stringify(snap, null, 2)], { type: "application/json" }), `tasbir-backup-${stamp}.json`)
      toast.success("Exported full configuration")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed")
    } finally {
      setExporting(false)
    }
  }

  async function handleImportFile(file: File) {
    setImporting(true)
    try {
      const parsed = JSON.parse(await file.text()) as SystemSnapshot
      if (parsed.schema_version !== 1) {
        toast.error(`Unsupported schema version ${parsed.schema_version}`)
        return
      }
      const res = await importSystem(parsed)
      setApplied(res.applied)
      toast.success("Imported — configuration restored")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Import failed")
    } finally {
      setImporting(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  const tableLabels: Record<string, string> = {
    design_systems: "Design systems",
    templates: "Templates",
    platforms: "Platforms",
    fonts: "Fonts",
    agents: "Agents",
    app_settings: "Runtime settings",
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Export configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <p className="text-sm text-muted-foreground">
            Downloads every design system, template, platform, curated font, agent config, and
            runtime setting as a single JSON file. Tasks, audit logs, and chats are not included —
            they are per-machine runtime data.
          </p>
          <div>
            <Button onClick={() => void handleExport()} disabled={exporting} size="sm">
              {exporting ? "Exporting…" : "Export to file"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Import configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <p className="text-sm text-muted-foreground">
            Restores a backup file. Rows are upserted by key — existing rows are overwritten, and
            rows missing from the file are left untouched. No data is deleted.
          </p>
          <div className="flex items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void handleImportFile(f)
              }}
            />
            <Button size="sm" variant="outline" disabled={importing} onClick={() => fileRef.current?.click()}>
              {importing ? "Importing…" : "Choose backup file…"}
            </Button>
          </div>
          {applied ? (
            <div className="grid gap-1 rounded-md border p-3 text-sm">
              <p className="font-medium">Imported</p>
              {Object.entries(applied).map(([table, n]) => (
                <div key={table} className="flex justify-between text-muted-foreground">
                  <span>{tableLabels[table] ?? table}</span>
                  <span className="font-mono">{n} rows</span>
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
