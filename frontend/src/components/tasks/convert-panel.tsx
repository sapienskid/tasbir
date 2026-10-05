import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { TemplatePicker } from "@/components/compose/template-picker"
import { listTemplates, refillFormat, type Template } from "@/lib/api"

/**
 * What a post with no template offers instead of the structured editor.
 *
 * A designer-LLM post has no template, so it has no slots and the structured
 * editor cannot mount. The backend could always convert one (send a
 * `template_id`; the original HTML is kept as `{fmt}.designer.html`), but there
 * was no UI for it — conversion only happened as a side effect of switching
 * design system, which is itself only offered when a second system exists. With
 * one design system there was no way to convert at all.
 */
export function ConvertPanel({
  taskId,
  format,
  reason,
  convertible,
  designSystemId,
  family,
  ground,
  busy,
  onConverted,
  onOpenCode,
}: {
  taskId: string
  format: string
  reason: string | null
  convertible: boolean
  designSystemId: string
  family?: string
  ground: "white" | "black"
  busy?: boolean
  onConverted: () => Promise<void>
  onOpenCode: () => void
}) {
  const [open, setOpen] = useState(false)

  if (reason === "manual") {
    return (
      <Note
        title="Manually composed post"
        body="Composed posts are edited from their composition, not from here."
        onOpenCode={onOpenCode}
      />
    )
  }
  if (reason === "running") {
    return (
      <p className="text-xs text-muted-foreground">
        This post is still generating — the editor opens when it finishes.
      </p>
    )
  }
  if (reason === "expired") {
    return (
      <p className="text-xs text-muted-foreground">
        This post&apos;s artifacts have passed their retention window, so there is nothing to
        edit. Re-run the task to regenerate it.
      </p>
    )
  }

  const canConvert = convertible && !!family

  return (
    <div className="grid gap-2 text-sm">
      <p className="font-medium">Freeform AI design</p>
      <p className="text-xs text-muted-foreground">
        {reason === "template_missing"
          ? "This post's template was deleted, so it has no structured fields."
          : "This post was designed freeform rather than filled from a template, so it has no structured fields. Convert it to a template to edit copy, media and layout here — or edit the HTML directly."}
      </p>
      <div className="flex flex-wrap gap-2">
        {canConvert ? (
          <Button size="sm" onClick={() => setOpen(true)} disabled={busy}>
            Convert to a template
          </Button>
        ) : null}
        <Button size="sm" variant="outline" onClick={onOpenCode}>
          Open Code
        </Button>
      </div>

      {canConvert ? (
        <ConvertDialog
          open={open}
          onOpenChange={setOpen}
          taskId={taskId}
          format={format}
          designSystemId={designSystemId}
          family={family!}
          ground={ground}
          onConverted={onConverted}
        />
      ) : null}
    </div>
  )
}

function Note({
  title,
  body,
  onOpenCode,
}: {
  title: string
  body: string
  onOpenCode: () => void
}) {
  return (
    <div className="grid gap-2 text-sm">
      <p className="font-medium">{title}</p>
      <p className="text-xs text-muted-foreground">{body}</p>
      <Button size="sm" variant="outline" onClick={onOpenCode}>
        Open Code
      </Button>
    </div>
  )
}

function ConvertDialog({
  open,
  onOpenChange,
  taskId,
  format,
  designSystemId,
  family,
  ground,
  onConverted,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  taskId: string
  format: string
  designSystemId: string
  family: string
  ground: "white" | "black"
  onConverted: () => Promise<void>
}) {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(false)
  const [picked, setPicked] = useState<string>("")
  const [working, setWorking] = useState(false)

  useEffect(() => {
    if (!open || templates.length > 0) return
    let alive = true
    setLoading(true)
    listTemplates(designSystemId, family)
      .then((rows) => {
        if (alive) setTemplates(rows)
      })
      .catch((e: unknown) => {
        if (alive) toast.error(e instanceof Error ? e.message : "Couldn't load templates")
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [open, templates.length, designSystemId, family])

  async function convert() {
    if (!picked) return
    setWorking(true)
    try {
      const res = await refillFormat(taskId, format, { template_id: picked, render: true })
      if (res.converted) {
        toast.success("Converted — the original design is kept as a .designer.html backup")
      } else {
        toast.success("Template applied")
      }
      onOpenChange(false)
      setPicked("")
      await onConverted()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't convert the post")
    } finally {
      setWorking(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Convert to a template</DialogTitle>
          <DialogDescription>
            The post&apos;s copy moves onto the template you pick. The original freeform design is
            kept alongside it, so nothing is lost — but the template&apos;s layout replaces it.
          </DialogDescription>
        </DialogHeader>
        <TemplatePicker
          family={family as Template["family"]}
          templates={templates}
          loading={loading}
          selected={templates.find((t) => t.id === picked)}
          ground={ground}
          hidden={null}
          mediaPosition="auto"
          multiSlide={false}
          showApplyAll={false}
          onPick={(id) => setPicked(id)}
          onHidden={() => {}}
          onMediaPosition={() => {}}
          onApplyAll={() => {}}
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={working}>
            Cancel
          </Button>
          <Button onClick={convert} disabled={!picked || working}>
            {working ? "Converting…" : "Convert"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
