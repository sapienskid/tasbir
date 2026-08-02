import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { toast } from "sonner"
import { apiRequest, type SaveTemplateResponse } from "@/lib/api"

interface SaveTemplateDialogProps {
  taskId: string
  format: string
  sourceTemplateId: string | null | undefined
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SaveTemplateDialog({
  taskId,
  format,
  sourceTemplateId,
  open,
  onOpenChange,
}: SaveTemplateDialogProps) {
  const [mode, setMode] = useState<"new" | "update">(sourceTemplateId ? "update" : "new")
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const [savedId, setSavedId] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setMode(sourceTemplateId ? "update" : "new")
      setName("")
      setSavedId(null)
    }
  }, [open, sourceTemplateId])

  async function submit() {
    if (mode === "new" && !name.trim()) {
      toast.error("Give the template a name")
      return
    }
    setSaving(true)
    try {
      const res = await apiRequest<SaveTemplateResponse>(
        `/tasks/${taskId}/formats/${format}/template`,
        { method: "POST", body: JSON.stringify({ name, mode }) }
      )
      setSavedId(res.template_id)
      toast.success(mode === "update" ? "Template updated" : "Template saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const canUpdate = Boolean(sourceTemplateId)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save as Template</DialogTitle>
          <DialogDescription>
            Turns this {format} render into a reusable library template
            (validated for overflow before saving).
          </DialogDescription>
        </DialogHeader>
        {savedId ? (
          <div className="rounded-md border p-4 text-sm">
            <p className="font-medium">Saved: {savedId}</p>
            <p className="text-muted-foreground">
              Future {format} posts can be composed from this template.
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label>Action</Label>
              <Select
                value={mode}
                onValueChange={(v) => setMode(v as "new" | "update")}
                disabled={!canUpdate}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">New template</SelectItem>
                  <SelectItem value="update" disabled={!canUpdate}>
                    Update source ({sourceTemplateId ?? "none"})
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            {mode === "new" ? (
              <div className="grid gap-2">
                <Label htmlFor="tpl-name">Name</Label>
                <Input
                  id="tpl-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. bold-index"
                />
              </div>
            ) : null}
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          {!savedId ? (
            <Button onClick={() => void submit()} disabled={saving}>
              {saving ? "Validating…" : "Save template"}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
