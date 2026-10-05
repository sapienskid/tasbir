import { useMemo, useState } from "react"
import { Search } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PlatformForm } from "@/components/settings/platform-form"
import { usePlatforms } from "@/hooks/use-platforms"
import { useSettingsMeta } from "@/hooks/use-settings-meta"
import { loadPlatforms } from "@/lib/platforms"
import { createPlatform, deletePlatform, updatePlatform, type PlatformCreate } from "@/lib/api"

const BLANK: PlatformCreate = {
  id: "",
  name: "",
  width: 1080,
  height: 1080,
  family: "square",
  is_active: true,
  sort_order: 0,
}

export default function PlatformsPanel() {
  const [showInactive, setShowInactive] = useState(false)
  const [query, setQuery] = useState("")
  const { platforms, isLoading, mutate } = usePlatforms(showInactive)
  const { meta } = useSettingsMeta()

  const [draft, setDraft] = useState<PlatformCreate | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return platforms
    return platforms.filter((p) => `${p.id} ${p.name} ${p.family}`.toLowerCase().includes(q))
  }, [platforms, query])

  const openNew = () => {
    setDraft({ ...BLANK })
    setIsNew(true)
    setOpen(true)
  }

  const openEdit = (row: PlatformCreate) => {
    setDraft({ ...row })
    setIsNew(false)
    setOpen(true)
  }

  /** Refetch the active list too — the module dimension caches power every
   *  template preview and render size in the app. */
  const refreshAll = async () => {
    await mutate()
    await loadPlatforms().catch(() => {})
  }

  const save = async () => {
    if (!draft) return
    const id = draft.id.trim()
    if (!id) {
      toast.error("An id is required")
      return
    }
    setSaving(true)
    try {
      const body = { ...draft, id }
      if (isNew) await createPlatform(body)
      else await updatePlatform(body.id, body)
      await refreshAll()
      toast.success(isNew ? "Platform created" : "Saved")
      setOpen(false)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    try {
      await deletePlatform(id)
      await refreshAll()
      toast.success("Platform deleted")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed")
      throw e
    }
  }

  if (isLoading && platforms.length === 0) {
    return <Skeleton className="h-72 rounded-md" />
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Platforms</h2>
          <p className="text-sm text-muted-foreground">
            Canvas sizes for every format. A family&apos;s first active platform sets the canvas
            used for its template previews and validation.
          </p>
        </div>
        <Button size="sm" onClick={openNew}>
          Add platform
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="relative min-w-56 flex-1">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search id, name or family"
            aria-label="Search platforms"
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="show-inactive-platforms"
            checked={showInactive}
            onCheckedChange={(v) => setShowInactive(v === true)}
          />
          <Label htmlFor="show-inactive-platforms" className="text-sm font-normal">
            Show inactive
          </Label>
        </div>
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
                <TableHead>Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                    No platforms match.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((p) => (
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
                    <TableCell className="font-mono text-xs">{p.id}</TableCell>
                    <TableCell>{p.name || <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {p.width} × {p.height}
                    </TableCell>
                    <TableCell>{p.family}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{p.sort_order}</TableCell>
                    <TableCell>
                      {p.is_active ? (
                        <span className="text-emerald-500">yes</span>
                      ) : (
                        <span className="text-muted-foreground">no</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{isNew ? "Add platform" : `Edit ${draft?.id}`}</DialogTitle>
            <DialogDescription>
              {isNew
                ? "Creates a new format id usable by templates and jobs."
                : "Changes apply within about five seconds — no worker restart."}
            </DialogDescription>
          </DialogHeader>
          {draft ? (
            <PlatformForm
              value={draft}
              isNew={isNew}
              families={meta.families}
              saving={saving}
              onChange={setDraft}
              onSave={save}
              onDelete={
                isNew
                  ? undefined
                  : async () => {
                      const id = draft.id
                      await remove(id)
                      setOpen(false)
                    }
              }
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
