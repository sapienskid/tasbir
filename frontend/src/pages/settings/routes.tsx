import { lazy } from "react"
import { Navigate, Route } from "react-router-dom"
import { page } from "@/lib/route-page"

/** One lazily-loaded chunk per settings section. */
const Layout = lazy(() => import("@/pages/settings/layout"))
const Platforms = lazy(() => import("@/pages/settings/platforms"))
const Fonts = lazy(() => import("@/pages/settings/fonts"))
const Runtime = lazy(() => import("@/pages/settings/runtime"))
const System = lazy(() => import("@/pages/settings/system"))

/**
 * The settings route tree.
 *
 * Invariant worth preserving: the PARENT route's element must render an
 * `<Outlet/>` (the Layout does). A parent whose element is `<Navigate>` renders
 * no outlet, so its children never mount — that produced a redirect to
 * /settings/platforms followed by a blank page. The /settings redirect
 * therefore belongs on the `index` route, never on the parent.
 *
 * Exported so tests can assert the topology rather than trust it.
 */
export const settingsRoutes = (
  <Route path="settings" element={page(<Layout />)}>
    <Route index element={<Navigate to="/settings/platforms" replace />} />
    <Route path="platforms" element={page(<Platforms />)} />
    <Route path="fonts" element={page(<Fonts />)} />
    <Route path="runtime" element={page(<Runtime />)} />
    <Route path="system" element={page(<System />)} />
  </Route>
)
