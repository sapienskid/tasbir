import { useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, Loader2, Send, Sparkles } from "lucide-react"
import { toast } from "sonner"
import { getChat, sendChat, type ChatMessage, type ChatThread } from "@/lib/api"

interface AgentChatProps {
  taskId: string
  format: string
  /** Current editor HTML — sent so the agent edits the live state. */
  currentHtml: string
  /** Apply a proposed document to the editor (review-then-render). */
  onApplyHtml: (html: string) => void
  /** Apply a proposed document AND re-render it immediately (persists). */
  onApplyAndRender: (html: string) => void
}

function formatTime(iso: string | null): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch {
    return ""
  }
}

function Avatar({ who, className }: { who: "agent" | "user"; className?: string }) {
  return (
    <div
      className={
        "flex size-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold uppercase " +
        (who === "agent"
          ? "bg-primary text-primary-foreground"
          : "bg-muted-foreground/20 text-muted-foreground") +
        (className ?? "")
      }
      aria-hidden
    >
      {who === "agent" ? "MC" : "You"}
    </div>
  )
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-2" aria-label="Agent is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
          style={{ animationDelay: `${i * 120}ms` }}
        />
      ))}
    </div>
  )
}

function MessageRow({ m }: { m: ChatMessage }) {
  if (m.role === "user") {
    return (
      <div className="flex items-end justify-end gap-2">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
          {m.content}
        </div>
        <Avatar who="user" />
      </div>
    )
  }
  return (
    <div className="flex items-end justify-start gap-2">
      <Avatar who="agent" />
      <div className="max-w-[85%]">
        <div className="whitespace-pre-wrap rounded-2xl rounded-bl-sm border bg-muted/40 px-3 py-2 text-sm">
          {m.content}
        </div>
        {m.html ? (
          <div className="mt-1 flex items-center gap-1.5 pl-1">
            <Sparkles className="size-3 text-primary" />
            <span className="text-[11px] font-medium text-primary">
              Suggested a change
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function AgentChat({
  taskId,
  format,
  currentHtml,
  onApplyHtml,
  onApplyAndRender,
}: AgentChatProps) {
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
    let found: ChatMessage | null = null
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
    <div className="flex h-full min-h-0 flex-col">
      {/* Conversation header */}
      <div className="flex shrink-0 items-center gap-3 border-b px-3 py-2.5">
        <div className="relative">
          <Avatar who="agent" />
          <span className="absolute -bottom-0.5 -right-0.5 size-2 rounded-full border-2 border-background bg-emerald-500" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium leading-tight">Marcus Chen</p>
          <p className="truncate text-[11px] leading-tight text-muted-foreground">
            Design assistant · {format}
          </p>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-3 px-3 py-3">
          {messages.length === 0 ? (
            <div className="grid gap-1 rounded-xl border bg-muted/20 p-4 text-center text-xs text-muted-foreground">
              <p>Ask the design assistant to adjust this format.</p>
              <p className="text-muted-foreground/70">
                "tighter headline", "move the subhead up", "switch to black ground"
              </p>
            </div>
          ) : null}
          {messages.map((m) => (
            <div key={m.id} className="grid gap-1">
              <MessageRow m={m} />
              <span className="px-1 text-[10px] text-muted-foreground/60">
                {formatTime(m.created_at)}
              </span>
            </div>
          ))}
          {sending ? (
            <div className="flex items-start gap-2">
              <Avatar who="agent" />
              <div className="rounded-2xl rounded-bl-sm border bg-muted/40">
                <TypingDots />
              </div>
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Proposed-change action bar */}
      {pendingProposal ? (
        <div className="mx-3 mb-2 shrink-0 rounded-xl border border-primary/40 bg-primary/5 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-xs font-medium">
              <Sparkles className="size-3.5 text-primary" />
              Agent proposed changes
            </p>
            <Badge variant="outline" className="text-[10px]">
              {pendingProposal.html!.length.toLocaleString()} chars
            </Badge>
          </div>
          <div className="grid gap-1.5 sm:grid-cols-2">
            <Button
              size="sm"
              className="h-8 text-xs"
              onClick={() => {
                onApplyAndRender(pendingProposal.html!)
                setAppliedId(pendingProposal.id)
              }}
            >
              <CheckCircle2 className="size-3.5" />
              Apply &amp; Save
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-8 text-xs"
              onClick={() => {
                onApplyHtml(pendingProposal.html!)
                setAppliedId(pendingProposal.id)
              }}
            >
              Apply to editor
            </Button>
          </div>
          <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
            Apply &amp; Save re-renders and persists the change; Apply to editor loads it into the
            canvas for review first.
          </p>
        </div>
      ) : null}

      {/* Composer */}
      <div className="flex shrink-0 items-end gap-2 border-t p-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
          placeholder={`Message ${format}…`}
          className="min-h-14 resize-none text-sm"
          rows={2}
        />
        <Button
          size="icon"
          className="h-14 w-10 shrink-0"
          onClick={() => void send()}
          disabled={sending || !input.trim()}
          aria-label="Send"
        >
          {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
        </Button>
      </div>
    </div>
  )
}
