// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import CoversPage from "../covers"

const { request, meta } = vi.hoisted(() => ({
  request: vi.fn(),
  meta: {
    width: 1600, height: 900, ai_available: false,
    motifs: [{ id: "field-synthesis", label: "Generative composition" }, { id: "auto", label: "From the article" }, { id: "field-mesh", label: "Warped grid" }],
    sizes: [{ label: "Landscape", width: 1600, height: 900 }, { label: "Square", width: 1080, height: 1080 }],
  },
}))
vi.mock("@/lib/api", () => ({ apiRequest: request }))
vi.mock("swr", () => ({ default: () => ({ data: meta }) }))
vi.mock("@/hooks/use-library", () => ({ useDesignSystems: () => ({
  data: [{ id: "brand", name: "My brand", is_active: true }],
}) }))
vi.mock("@/components/tasks/preview-frame", () => ({
  FitScaledFrame: ({ html }: { html: string }) => <div data-preview>{html}</div>,
}))

let root: Root
let host: HTMLDivElement
beforeEach(async () => {
  vi.useFakeTimers()
  ;(globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  meta.ai_available = false
  request.mockReset().mockImplementation((path: string) => Promise.resolve(
    path === "/covers/preview" ? { html: "preview-art" } : { task_id: "cover-task" }
  ))
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
  await act(async () => root.render(
    <MemoryRouter initialEntries={["/covers"]}>
      <Routes>
        <Route path="/covers" element={<CoversPage />} />
        <Route path="/covers/:taskId" element={<div data-result>Queued cover</div>} />
      </Routes>
    </MemoryRouter>
  ))
})
afterEach(async () => {
  await act(async () => root.unmount())
  host.remove()
  vi.useRealTimers()
})

async function select(id: string, value: string) {
  await act(async () => {
    const input = host.querySelector<HTMLSelectElement>(`#${id}`)!
    input.value = value
    input.dispatchEvent(new Event("change", { bubbles: true }))
  })
}
async function settlePreview() {
  await act(async () => { await vi.advanceTimersByTimeAsync(400) })
}
function button(label: string) {
  return [...host.querySelectorAll("button")].find((element) => element.textContent === label)!
}

it("disables AI artwork until Cloudflare is available", () => {
  expect(host.querySelector<HTMLOptionElement>('#cover-engine option[value="ai"]')?.disabled).toBe(true)
  expect(host.textContent).toContain("Cloudflare Workers AI")
})

it("automatically previews with a visible seed after a short debounce", async () => {
  expect(request).not.toHaveBeenCalled()
  expect(button("Generate covers").disabled).toBe(true)
  expect(button("Preview drawing")).toBeUndefined()
  await settlePreview()
  expect(request).toHaveBeenCalledTimes(1)
  expect(request.mock.calls[0][0]).toBe("/covers/preview")
  expect(JSON.parse(request.mock.calls[0][1].body).seed).toBe(host.querySelector<HTMLInputElement>("#cover-seed")!.value)
  expect(host.querySelector("[data-preview]")?.textContent).toBe("preview-art")
  expect(button("Generate covers").disabled).toBe(false)
})

it("debounces changes and queues the latest brand, composition, and canvas", async () => {
  await select("cover-motif", "field-mesh")
  await select("cover-size", "1080x1080")
  await select("cover-ground", "black")
  await settlePreview()
  expect(request).toHaveBeenCalledTimes(1)
  await act(async () => button("Generate covers").click())
  const [path, init] = request.mock.calls[1]
  expect(path).toBe("/covers")
  expect(JSON.parse(init.body)).toMatchObject({
    design_system_id: "brand", motif: "field-mesh", width: 1080, height: 1080, ground: "black",
  })
  expect(init.body).not.toContain("#")
  expect(host.querySelector("[data-result]")).not.toBeNull()
})

it("shuffle refreshes automatically and Generate keeps that exact seed", async () => {
  await settlePreview()
  const first = JSON.parse(request.mock.calls[0][1].body)
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Randomize seed"]')!.click())
  expect(button("Generate covers").disabled).toBe(true)
  await settlePreview()
  const next = JSON.parse(request.mock.calls[1][1].body)
  expect(next.seed).not.toBe(first.seed)
  expect(next.seed).toBe(host.querySelector<HTMLInputElement>("#cover-seed")!.value)
  await act(async () => button("Generate covers").click())
  expect(JSON.parse(request.mock.calls[2][1].body).seed).toBe(next.seed)
})

it("aborts an outdated request and ignores its late response", async () => {
  const resolve: Array<(value: { html: string }) => void> = []
  request.mockImplementation(() => new Promise<{ html: string }>((done) => { resolve.push(done) }))
  await settlePreview()
  const oldSignal = request.mock.calls[0][1].signal as AbortSignal
  await select("cover-ground", "black")
  expect(oldSignal.aborted).toBe(true)
  await settlePreview()
  await act(async () => { resolve[1]({ html: "latest-art" }) })
  await act(async () => { resolve[0]({ html: "outdated-art" }) })
  expect(host.querySelector("[data-preview]")?.textContent).toBe("latest-art")
  expect(button("Generate covers").disabled).toBe(false)
})

it("clears a failed preview and prevents generation from an outdated drawing", async () => {
  await settlePreview()
  request.mockRejectedValueOnce(new Error("Preview unavailable"))
  await select("cover-ground", "black")
  await settlePreview()
  expect(host.querySelector("[data-preview]")).toBeNull()
  expect(host.querySelector('[role="alert"]')?.textContent).toBe("Preview unavailable")
  expect(button("Generate covers").disabled).toBe(true)
})

it("does not automatically call the image model when switching to AI", async () => {
  meta.ai_available = true
  await select("cover-engine", "ai")
  await settlePreview()
  expect(request).not.toHaveBeenCalled()
  expect(button("Generate covers").disabled).toBe(false)
})

it("surfaces queue errors and leaves the form usable", async () => {
  await settlePreview()
  request.mockRejectedValueOnce(new Error("Cover queue unavailable"))
  await act(async () => button("Generate covers").click())
  expect(host.querySelector('[role="alert"]')?.textContent).toBe("Cover queue unavailable")
  expect(button("Generate covers").disabled).toBe(false)
})
