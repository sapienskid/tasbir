import { useMemo, useState } from "react"
import { Search } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
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
import { FontForm } from "@/components/settings/font-form"
import { useFontPool } from "@/hooks/use-font-pool"
import { useSettingsMeta } from "@/hooks/use-settings-meta"
import { createPoolFont, deletePoolFont, updatePoolFont, type PoolFontCreate } from "@/lib/api"

const BLANK: PoolFontCreate = {
  family: "",
  role: "sans",
  weights: [400],
  style: "",
  is_active: true,
  sort_order: 0,
}

export default function FontsPanel() {
  const [showInactive, setShowInactive] = useState(false)
  const [query, setQuery] = useState("")
  const { fonts, isLoading, mutate } = useFontPool(showInactive)
  const { meta } = useSettingsMeta()

  const [draft, setDraft] = useState<PoolFontCreate | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return fonts
    return fonts.filter((f) => `${f.family} ${f.role} ${f.style}`.toLowerCase().includes(q))
  }, [fonts, query])

  const openNew = () => {
    setDraft({ ...BLANK })
    setIsNew(true)
    setOpen(true)
  }

  const openEdit = (row: PoolFontCreate) => {
    setDraft({ ...row })
    setIsNew(false)
    setOpen(true)
  }

  const save = async () => {
    if (!draft) return
    const family = draft.family.trim()
    if (!family) {
      toast.error("A family is required")
      return
    }
    setSaving(true)
    try {
      if (isNew) await createPoolFont({ ...draft, family })
      else await updatePoolFont(family, draft)
      await mutate()
      toast.success(isNew ? "Font added" : "Saved")
      setOpen(false)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const remove = async (family: string) => {
    try {
      await deletePoolFont(family)
      await mutate()
      toast.success("Font removed")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed")
      throw e
    }
  }

  if (isLoading && fonts.length === 0) {
    return <Skeleton className="h-72 rounded-md" />
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Curated fonts</h2>
          <p className="text-sm text-muted-foreground">
            The pool the brand builder picks from. Only active families are offered to agents and
            the font picker.
          </p>
        </div>
        <Button size="sm" onClick={openNew}>
          Add font
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
            placeholder="Search family, role or style"
            aria-label="Search fonts"
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="show-inactive-fonts"
            checked={showInactive}
            onCheckedChange={(v) => setShowInactive(v === true)}
          />
          <Label htmlFor="show-inactive-fonts" className="text-sm font-normal">
            Show inactive
          </Label>
        </div>
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
                <TableHead className="text-right">Sort</TableHead>
                <TableHead>Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                    No fonts match.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((f) => (
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
                    <TableCell>
                      <Badge variant="outline">{f.role}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{f.weights.join(", ")}</TableCell>
                    <TableCell className="text-sm">
                      {f.style || <span className="text-muted-foreground">—</span>}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{f.sort_order}</TableCell>
                    <TableCell>
                      {f.is_active ? (
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
            <DialogTitle>{isNew ? "Add font" : `Edit ${draft?.family}`}</DialogTitle>
            <DialogDescription>
              The family name must match Google Fonts exactly — it is used to build the font link
              injected into every render.
            </DialogDescription>
          </DialogHeader>
          {draft ? (
            <FontForm
              value={draft}
              isNew={isNew}
              roles={meta.font_roles}
              saving={saving}
              onChange={setDraft}
              onSave={save}
              onDelete={
                isNew
                  ? undefined
                  : async () => {
                      const family = draft.family
                      await remove(family)
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
