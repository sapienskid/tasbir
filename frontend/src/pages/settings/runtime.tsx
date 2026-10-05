import { useMemo, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ConfirmAction } from "@/components/settings/confirm-action"
import { RuntimeKnob } from "@/components/settings/runtime-knob"
import { useRuntimeSettings } from "@/hooks/use-runtime-settings"
import { buildPayload, dirtyKeys, groupKnobs } from "@/lib/settings-knobs"
import { resetRuntimeSettings, updateRuntimeSettings } from "@/lib/api"

export default function RuntimePanel() {
  const { data, isLoading, mutate } = useRuntimeSettings()
  const [draft, setDraft] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)

  const defaults = useMemo(() => data?.defaults ?? {}, [data])
  const values = useMemo(() => data?.values ?? {}, [data])
  const groups = useMemo(() => groupKnobs(defaults), [defaults])
  const changed = useMemo(() => dirtyKeys(draft, values), [draft, values])

  const setDraftValue = (key: string, value: unknown) =>
    setDraft((d) => ({ ...d, [key]: value }))

  const save = async () => {
    const payload = buildPayload(draft, values)
    if (!payload) {
      setDraft({})
      toast.error("Nothing to save — every change was cleared")
      return
    }
    setSaving(true)
    try {
      const res = await updateRuntimeSettings(payload)
      setDraft({})
      // Adopt the server response instead of refetching.
      await mutate(res, { revalidate: false })
      toast.success("Runtime settings saved")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    try {
      const res = await resetRuntimeSettings()
      setDraft({})
      await mutate(res, { revalidate: false })
      toast.success("Reset to defaults")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reset failed")
    }
  }

  if (isLoading && !data) {
    return <Skeleton className="h-72 rounded-md" />
  }

  return (
    <div className="grid gap-4">
      <div>
        <h2 className="text-lg font-semibold">Runtime tuning</h2>
        <p className="text-sm text-muted-foreground">
          Behavioral knobs for the pipeline. Values are validated by the server on save and take
          effect on the next generation task — no restart needed. Infrastructure and secrets stay
          in environment variables.
        </p>
      </div>

      {groups.map(([group, keys]) => (
        <Card key={group}>
          <CardContent className="px-4 py-2">
            <h3 className="border-b py-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {group}
            </h3>
            {keys.map((key) => (
              <RuntimeKnob
                key={key}
                name={key}
                spec={defaults[key]}
                serverValue={values[key]}
                draftValue={draft[key]}
                dirty={changed.includes(key)}
                onDraft={(v) => setDraftValue(key, v)}
                onRevert={() =>
                  setDraft((d) => {
                    const next = { ...d }
                    delete next[key]
                    return next
                  })
                }
              />
            ))}
          </CardContent>
        </Card>
      ))}

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          {changed.length === 0
            ? "No unsaved changes."
            : `${changed.length} unsaved change${changed.length === 1 ? "" : "s"}.`}
        </p>
        <div className="flex items-center gap-2">
          <ConfirmAction
            trigger={
              <Button variant="outline" size="sm" disabled={saving}>
                Reset to defaults
              </Button>
            }
            title="Reset every knob to its default?"
            description="All runtime settings go back to their shipped defaults. This cannot be undone."
            confirmLabel="Reset"
            onConfirm={reset}
          />
          <Button size="sm" onClick={save} disabled={saving || changed.length === 0}>
            {saving
              ? "Saving…"
              : changed.length === 0
                ? "Save"
                : `Save ${changed.length} change${changed.length === 1 ? "" : "s"}`}
          </Button>
        </div>
      </div>
    </div>
  )
}
