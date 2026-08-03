import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import {
  Bot,
  CheckCircle2,
  FileCode2,
  Loader2,
  Send,
  Sparkles,
  User,
  X,
} from "lucide-react"
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

// Persist handled proposals per (task, format) so the action bar doesn't
// reappear every time the tab is reopened.
function readHandled(taskId: string, format: string): string[] {
  try {
    return JSON.parse(
      localStorage.getItem(`tasbir:chat:handled:${taskId}:${format}`) ?? "[]"
    ) as string[]
  } catch {
    return []
  }
}

function writeHandled(taskId: string, format: string, ids: string[]): void {
  try {
    localStorage.setItem(`tasbir:chat:handled:${taskId}:${format}`, JSON.stringify(ids))
  } catch {
    /* storage unavailable */
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch {
    return ""
  }
}

function Avatar({ who }: { who: "agent" | "user" }) {
  return (
    <div
      className={
        "flex size-7 shrink-0 items-center justify-center rounded-full " +
        (who === "agent"
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground")
      }
      aria-hidden
    >
      {who === "agent" ? <Bot className="size-4" /> : <User className="size-4" />}
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

const MessageRow = memo(function MessageRow({ m }: { m: ChatMessage }) {
  const isUser = m.role === "user"
  return (
    <div className="flex flex-col gap-1">
      <div className={"flex items-end gap-2 " + (isUser ? "justify-end" : "justify-start")}>
        {!isUser ? <Avatar who="agent" /> : null}
        <div
          className={
            "max-w-[80%] rounded-2xl px-3 py-2 text-sm " +
            (isUser
              ? "rounded-br-sm bg-primary text-primary-foreground"
              : "rounded-bl-sm border bg-muted/40")
          }
        >
          {m.content}
        </div>
        {isUser ? <Avatar who="user" /> : null}
      </div>
      <span
        className={
          "text-[10px] text-muted-foreground/60 " +
          (isUser ? "self-end pr-1" : "self-start pl-9")
        }
      >
        {formatTime(m.created_at)}
      </span>
    </div>
  )
})

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
  const [pendingUser, setPendingUser] = useState<ChatMessage | null>(null)
  const [handled, setHandled] = useState<string[]>(() => readHandled(taskId, format))
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setInput("")
    setPendingUser(null)
    setSending(false)
    setHandled(readHandled(taskId, format))
  }, [key, taskId, format])

  // Optimistic list: DB history + the in-flight user message.
  const messages = useMemo(() => {
    const base = data?.messages ?? []
    return pendingUser ? [...base, pendingUser] : base
  }, [data, pendingUser])

  const lastMessage = messages[messages.length - 1]
  const pendingProposal =
    !sending && !pendingUser && lastMessage?.role === "assistant" && !!lastMessage.html
      ? (handled.includes(lastMessage.id) ? null : lastMessage)
      : null

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length, sending])

  const markHandled = useCallback(
    (id: string) => {
      setHandled((prev) => {
        const next = [...prev, id]
        writeHandled(taskId, format, next)
        return next
      })
    },
    [taskId, format]
  )

  async function send() {
    const text = input.trim()
    if (!text || sending) return
    // Optimistic: put the message in the chat immediately, clear the box.
    setInput("")
    setPendingUser({ id: "pending", role: "user", content: text, html: null, created_at: null })
    setSending(true)
    try {
      await sendChat(taskId, format, text, currentHtml || undefined)
      // Refresh authoritative history, then drop the optimistic placeholder.
      await mutate()
    } catch (err) {
      setInput(text)
      toast.error(err instanceof Error ? err.message : "Chat failed")
    } finally {
      setPendingUser(null)
      setSending(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header */}
      <div className="flex shrink-0 items-center gap-3 border-b px-3 py-2.5">
        <div className="relative">
          <Avatar who="agent" />
          <span className="absolute -bottom-0.5 -right-0.5 size-2 rounded-full border-2 border-background bg-emerald-500" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium leading-tight">Marcus Chen</p>
          <p className="truncate text-[11px] leading-tight text-muted-foreground">
            Design assistant · {format}
          </p>
        </div>
        {sending ? (
          <span className="flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground">
            <Loader2 className="size-3 animate-spin" />
            thinking…
          </span>
        ) : null}
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
            <MessageRow key={m.id} m={m} />
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

      {/* Proposed-change action bar (only for the latest unhandled proposal) */}
      {pendingProposal ? (
        <div className="mx-3 mb-2 shrink-0 rounded-xl border border-primary/30 bg-primary/5">
          <div className="flex items-center justify-between gap-2 px-3 pt-2.5">
            <p className="flex items-center gap-1.5 text-xs font-medium text-primary">
              <Sparkles className="size-3.5" />
              Proposed changes
            </p>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Dismiss proposal"
              className="h-6 w-6"
              onClick={() => markHandled(pendingProposal.id)}
            >
              <X className="size-3.5" />
            </Button>
          </div>
          <p className="line-clamp-2 px-3 pt-1 text-[11px] text-muted-foreground">
            {pendingProposal.content}
          </p>
          <div className="grid grid-cols-2 gap-1.5 p-3 pt-2">
            <Button
              size="sm"
              className="h-8 text-xs"
              onClick={() => {
                onApplyAndRender(pendingProposal.html!)
                markHandled(pendingProposal.id)
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
                markHandled(pendingProposal.id)
              }}
            >
              <FileCode2 className="size-3.5" />
              Apply to editor
            </Button>
          </div>
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
          className="size-10 shrink-0"
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
