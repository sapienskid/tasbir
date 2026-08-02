import { useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Send, Sparkles } from "lucide-react"
import { toast } from "sonner"
import { getChat, sendChat, type ChatThread } from "@/lib/api"

interface AgentChatProps {
  taskId: string
  format: string
  /** Current editor HTML — sent so the agent edits the live state. */
  currentHtml: string
  onApplyHtml: (html: string) => void
}

export function AgentChat({ taskId, format, currentHtml, onApplyHtml }: AgentChatProps) {
  const key = `/tasks/${taskId}/chat?format=${encodeURIComponent(format)}`
  const { data, mutate } = useSWR<ChatThread>(key, () => getChat(taskId, format))
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [appliedId, setAppliedId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setInput("")
    setAppliedId(null)
  }, [key])

  const messages = useMemo(() => data?.messages ?? [], [data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length, sending])

  const pendingProposal = useMemo(() => {
    let found: (typeof messages)[number] | null = null
    for (const m of messages) {
      if (m.role === "assistant" && m.html && m.id !== appliedId) found = m
    }
    return found
  }, [messages, appliedId])

  async function send() {
    const text = input.trim()
    if (!text || sending) return
    setSending(true)
    try {
      await sendChat(taskId, format, text, currentHtml || undefined)
      setInput("")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Chat failed")
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {pendingProposal ? (
        <Alert className="border-primary/40">
          <Sparkles className="size-4" />
          <AlertDescription className="flex w-full flex-col gap-2">
            <p className="text-xs">
              Agent proposed changes to this format. Apply them to the editor, then hit Re-render
              to validate.
            </p>
            <div className="flex gap-2">
              <Button size="sm" className="h-7 text-xs" onClick={() => { onApplyHtml(pendingProposal.html!); setAppliedId(pendingProposal.id) }}>
                Apply to editor
              </Button>
              <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setAppliedId(pendingProposal.id)}>
                Dismiss
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      <ScrollArea className="min-h-0 flex-1 rounded-md border bg-muted/10">
        <div className="flex flex-col gap-2 p-3">
          {messages.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              Ask the design assistant to adjust this format — e.g. "tighter headline", "move the
              subhead up", "switch to black ground".
            </p>
          ) : null}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="max-w-[85%] self-end rounded-lg bg-primary px-3 py-2 text-xs text-primary-foreground">
                {m.content}
              </div>
            ) : (
              <div key={m.id} className="max-w-[95%] self-start whitespace-pre-wrap rounded-lg border bg-background px-3 py-2 text-xs">
                {m.content}
              </div>
            )
          )}
          {sending ? (
            <div className="flex items-center gap-2 self-start rounded-lg border bg-background px-3 py-2 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              Agent is reviewing the design…
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <div className="flex shrink-0 items-end gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
          placeholder={`Ask the agent about ${format}…`}
          className="min-h-16 resize-none text-sm"
          rows={2}
        />
        <Button size="icon" onClick={() => void send()} disabled={sending || !input.trim()} aria-label="Send">
          <Send className="size-4" />
        </Button>
      </div>
    </div>
  )
}
