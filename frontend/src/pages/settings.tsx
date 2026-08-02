import { useMemo, useState } from "react"
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
  getRuntimeSettings,
  listFontPool,
  resetRuntimeSettings,
  updatePoolFont,
  updatePlatform,
  updateRuntimeSettings,
  type PlatformCreate,
  type PoolFontCreate,
} from "@/lib/api"

const FAMILIES = ["square", "portrait", "story", "landscape"] as const
const FONT_ROLES = ["sans", "serif", "display", "mono"] as const

export default function SettingsPage() {
  const [tab, setTab] = useState<"platforms" | "fonts" | "runtime">("platforms")

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList>
          <TabsTrigger value="platforms">Platforms</TabsTrigger>
          <TabsTrigger value="fonts">Fonts</TabsTrigger>
          <TabsTrigger value="runtime">Runtime</TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "platforms" ? <PlatformsTab /> : null}
      {tab === "fonts" ? <FontsTab /> : null}
      {tab === "runtime" ? <RuntimeTab /> : null}
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
                <TableRow key={p.id} className="cursor-pointer" onClick={() => openEdit(p)}>
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
        <Label>ID (url-safe, e.g. mastodon-post)</Label>
        <Input value={value.id} disabled={!isNew} onChange={(e) => onChange({ ...value, id: e.target.value.trim() })} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-2">
          <Label>Width (px)</Label>
          <Input type="number" value={value.width} onChange={(e) => onChange({ ...value, width: Number(e.target.value) || 1080 })} />
        </div>
        <div className="grid gap-2">
          <Label>Height (px)</Label>
          <Input type="number" value={value.height} onChange={(e) => onChange({ ...value, height: Number(e.target.value) || 1080 })} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-2">
          <Label>Family</Label>
          <Select value={value.family} onValueChange={(v) => onChange({ ...value, family: v as typeof value.family })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {FAMILIES.map((f) => (
                <SelectItem key={f} value={f}>{f}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label>Sort order</Label>
          <Input type="number" value={value.sort_order} onChange={(e) => onChange({ ...value, sort_order: Number(e.target.value) || 0 })} />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox checked={value.is_active} onCheckedChange={(c) => onChange({ ...value, is_active: c === true })} />
        <Label className="font-normal">Active</Label>
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
                <TableRow key={f.family} className="cursor-pointer" onClick={() => openEdit(f)}>
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
                <Label>Family</Label>
                <Input value={editing.family} disabled={!isNew} onChange={(e) => setEditing({ ...editing, family: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <Label>Role</Label>
                  <Select value={editing.role} onValueChange={(v) => setEditing({ ...editing, role: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FONT_ROLES.map((r) => (
                        <SelectItem key={r} value={r}>{r}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>Weights (comma-separated)</Label>
                  <Input
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
                <Label>Style</Label>
                <Input value={editing.style} onChange={(e) => setEditing({ ...editing, style: e.target.value })} />
              </div>
              <div className="flex items-center gap-2">
                <Checkbox checked={editing.is_active} onCheckedChange={(c) => setEditing({ ...editing, is_active: c === true })} />
                <Label className="font-normal">Active</Label>
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
