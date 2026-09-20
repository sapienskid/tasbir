import { Link } from "react-router-dom"
import { Bot, PenLine } from "lucide-react"

/**
 * "AI agent" (New Task pipeline) vs "Manual" (Compose) switch shown at the
 * top of both creation pages. Plain links so each mode keeps its own URL.
 */
export function ModeSwitch({ active }: { active: "ai" | "manual" }) {
  const items = [
    { id: "ai" as const, to: "/new", label: "AI agent", Icon: Bot },
    { id: "manual" as const, to: "/compose", label: "Manual", Icon: PenLine },
  ]
  return (
    <nav aria-label="Creation mode" className="flex w-fit overflow-hidden rounded-md border">
      {items.map(({ id, to, label, Icon }) => (
        <Link
          key={id}
          to={to}
          aria-current={active === id ? "page" : undefined}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
            active === id
              ? "bg-primary text-primary-foreground"
              : "bg-background text-muted-foreground hover:bg-muted"
          }`}
        >
          <Icon aria-hidden="true" className="size-3.5" />
          {label}
        </Link>
      ))}
    </nav>
  )
}
