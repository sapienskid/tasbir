import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { apiRequest } from "@/lib/api"

interface Example {
  id: string
  headline: string
  rationale: string
  design_system_id: string
  category: string
}

export function GenerationFeedback({ taskId, format }: { taskId: string; format: string }) {
  const [note, setNote] = useState("")
  const [curate, setCurate] = useState(false)
  const [busy, setBusy] = useState(false)
  const { data: examples, mutate } = useSWR<Example[]>("/generation-examples")
  const inputId = `reference-${format}`

  async function submit(verdict: "approve" | "reject") {
    setBusy(true)
    try {
      await apiRequest(`/tasks/${taskId}/feedback`, {
        method: "POST",
        body: JSON.stringify({ format, verdict, note, curate: verdict === "approve" && curate }),
      })
      toast.success(verdict === "approve" && curate ? "Saved as an approved reference" : "Feedback recorded")
      await mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save feedback")
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: string) {
    setBusy(true)
    try {
      await apiRequest(`/generation-examples/${encodeURIComponent(id)}`, { method: "DELETE" })
      await mutate()
      toast.success("Reference removed")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not remove reference")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="grid gap-3 rounded-md border p-3" aria-label="Generation feedback">
      <p className="text-sm font-medium">Your review</p>
      <Label htmlFor={`${inputId}-note`}>What works, or what should change?</Label>
      <Textarea id={`${inputId}-note`} value={note} maxLength={1000}
        onChange={(event) => setNote(event.target.value)}
        placeholder="For example: a specific hook, one clear point, and a useful example."
      />
      <div className="flex items-start gap-2">
        <input id={inputId} type="checkbox" checked={curate}
          onChange={(event) => setCurate(event.target.checked)} className="mt-1" />
        <Label htmlFor={inputId} className="text-xs leading-relaxed">
          Use this approved post as a reference for future posts from this brand and category.
          Explain why it works above.
        </Label>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => submit("approve")}
          disabled={busy || !format || (curate && !note.trim())}>Approve</Button>
        <Button size="sm" variant="outline" onClick={() => submit("reject")}
          disabled={busy || !format}>Needs improvement</Button>
      </div>
      <details className="text-xs">
        <summary className="cursor-pointer">Approved references ({examples?.length ?? 0})</summary>
        <div className="mt-2 grid gap-2">
          {examples?.map((example) => (
            <div key={example.id} className="grid gap-1 border-t pt-2">
              <p className="font-medium">{example.headline || "Approved post"}</p>
              <p className="text-muted-foreground">{example.design_system_id} · {example.category}</p>
              <p>{example.rationale}</p>
              <Button size="sm" variant="ghost" className="justify-self-start"
                disabled={busy} onClick={() => remove(example.id)}>Remove reference</Button>
            </div>
          ))}
        </div>
      </details>
    </section>
  )
}
