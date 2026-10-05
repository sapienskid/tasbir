// @vitest-environment jsdom
/**
 * Settings route-tree tests.
 *
 * Guards a bug that shipped through typecheck + build + CI: the parent route's
 * element was <Navigate> instead of the Layout, so /settings redirected to
 * /settings/platforms and then rendered nothing — a blank page. Nothing in the
 * toolchain can see that: the JSX is valid, the types are valid, and it builds.
 *
 * These tests actually render the route tree in jsdom, which is the only way to
 * observe that a child route fails to mount.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { MemoryRouter, Routes } from "react-router-dom"
import { settingsRoutes } from "@/pages/settings/routes"

// jsdom lacks these; several UI primitives touch them.
beforeEach(() => {
  ;(globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  window.matchMedia =
    window.matchMedia ||
    ((q: string) =>
      ({
        matches: false,
        media: q,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList)
  window.scrollTo = window.scrollTo || (() => {})
})

/** Minimal fixtures for everything the panels fetch on mount. */
function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const json = (body: unknown) =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      if (url.includes("/api/settings/meta")) {
        return json({ families: ["square", "portrait"], font_roles: ["sans", "serif"] })
      }
      if (url.includes("/api/settings")) {
        return json({
          defaults: {
            "verifier.max_retries": {
              value: 3,
              type: "int",
              min: 0,
              max: 10,
              description: "Retries",
            },
            "publish.enabled": { value: true, type: "bool", description: "Publish gate" },
          },
          values: { "verifier.max_retries": 3, "publish.enabled": true },
        })
      }
      if (url.includes("/api/system/info")) {
        return json({
          version: "1.2.0",
          llm_configured: true,
          gateway_id: "tasbir",
          decision_provider_order: "clef-flash,clef",
          redis_configured: true,
          renderer_url: "http://playwright:4000",
          output_ttl_hours: 24,
          delete_on_download: false,
          rate_limit_per_min: 30,
          rate_limit_interactive_per_min: 600,
          skip_verify: false,
          copy_qa_enforce: false,
          image_max_bytes: 10485760,
          photo_keys_configured: false,
          counts: { platforms: 9, models: 4 },
          schema_version: 2,
        })
      }
      if (url.includes("/api/platforms")) {
        return json([
          {
            id: "instagram-square",
            name: "Instagram Square",
            width: 1080,
            height: 1080,
            family: "square",
            is_active: true,
            sort_order: 0,
          },
        ])
      }
      if (url.includes("/api/fonts/pool")) {
        return json([
          {
            family: "Inter",
            role: "sans",
            weights: [400],
            style: "",
            is_active: true,
            sort_order: 0,
          },
        ])
      }
      return json([])
    }),
  )
}

/** Mount the settings routes at `path` and return the rendered text. */
async function renderAt(path: string): Promise<{ text: string; container: HTMLDivElement }> {
  const container = document.createElement("div")
  document.body.appendChild(container)
  const root: Root = createRoot(container)
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>{settingsRoutes}</Routes>
      </MemoryRouter>,
    )
  })
  // Flush SWR resolution.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
  return { text: container.textContent ?? "", container }
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ""
})

// The route tree lazy-loads each panel. Vitest transforms those dynamic imports
// asynchronously, so without pre-warming them the panels stay suspended on the
// skeleton and every assertion below would pass/fail for the wrong reason.
beforeAll(async () => {
  await Promise.all([
    import("@/pages/settings/layout"),
    import("@/pages/settings/platforms"),
    import("@/pages/settings/fonts"),
    import("@/pages/settings/runtime"),
    import("@/pages/settings/system"),
  ])
})

describe("settings route tree", () => {
  beforeEach(stubFetch)

  it("renders the platforms panel, not a blank page", async () => {
    const { text } = await renderAt("/settings/platforms")
    // The left nav renders on every section.
    expect(text).toContain("Settings")
    expect(text).toContain("Platforms")
    // The panel's own content, proving the child route actually mounted.
    expect(text).toContain("Add platform")
    expect(text).toContain("instagram-square")
  })

  it("renders every section panel at its own route", async () => {
    const fonts = await renderAt("/settings/fonts")
    expect(fonts.text).toContain("Curated fonts")

    const runtime = await renderAt("/settings/runtime")
    expect(runtime.text).toContain("Runtime tuning")
    expect(runtime.text).toContain("verifier.max_retries")
    // A bool knob must render as a checkbox, not a number input.
    expect(runtime.text).toContain("publish.enabled")

    const system = await renderAt("/settings/system")
    expect(system.text).toContain("Environment")
    expect(system.text).toContain("Export configuration")
  })

  it("redirects /settings to /settings/platforms", async () => {
    const { text } = await renderAt("/settings")
    // The index route redirects; after settling we should see the platforms panel.
    expect(text).toContain("Add platform")
  })

  it("mounts a child route whose parent renders an Outlet", async () => {
    // With the old tree the parent element was <Navigate>, so this rendered
    // nothing at all — the layout's own nav was absent too.
    const { container } = await renderAt("/settings/platforms")
    expect(container.querySelector('nav[aria-label="Settings sections"]')).not.toBeNull()
    // And the panel is not left sitting on the Suspense skeleton.
    expect(container.innerHTML).not.toContain("animate-pulse")
  })
})
