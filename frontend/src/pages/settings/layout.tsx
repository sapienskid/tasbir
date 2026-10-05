import { NavLink, Outlet } from "react-router-dom"
import { Boxes, HardDriveDownload, SlidersHorizontal, Type } from "lucide-react"
import { cn } from "@/lib/utils"

const SECTIONS = [
  { to: "/settings/platforms", label: "Platforms", icon: Boxes, hint: "Canvas sizes and formats" },
  { to: "/settings/fonts", label: "Fonts", icon: Type, hint: "Curated Google Fonts pool" },
  { to: "/settings/runtime", label: "Runtime", icon: SlidersHorizontal, hint: "Pipeline tuning knobs" },
  { to: "/settings/system", label: "System", icon: HardDriveDownload, hint: "Environment and backup" },
]

/** Settings shell — a persistent left nav so each section is a deep-linkable
 *  route that mounts once (no remount-on-tab-switch, no lost scroll). */
export default function SettingsLayout() {
  return (
    <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <nav aria-label="Settings sections" className="self-start lg:sticky lg:top-20">
        <h1 className="mb-3 text-xl font-semibold">Settings</h1>
        <ul className="grid gap-1">
          {SECTIONS.map(({ to, label, icon: Icon, hint }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    "flex items-start gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                    "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isActive ? "bg-muted font-medium" : "text-muted-foreground"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      aria-hidden="true"
                      className={cn("mt-0.5 size-4 shrink-0", isActive && "text-foreground")}
                    />
                    <span className="min-w-0">
                      <span className="block truncate">{label}</span>
                      <span className="block truncate text-xs font-normal text-muted-foreground">
                        {hint}
                      </span>
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  )
}
