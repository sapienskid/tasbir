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
    motifs: [{ id: "auto", label: "From the article" }, { id: "field-mesh", label: "Warped grid" }],
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
afterEach(async () => { await act(async () => root.unmount()); host.remove() })

async function select(id: string, value: string) {
  await act(async () => {
    const input = host.querySelector<HTMLSelectElement>(`#${id}`)!
    input.value = value
    input.dispatchEvent(new Event("change", { bubbles: true }))
  })
}

function button(label: string) {
  return [...host.querySelectorAll("button")].find((element) => element.textContent === label)!
}

it("disables AI artwork until Cloudflare is available", () => {
  expect(host.querySelector<HTMLOptionElement>('#cover-engine option[value="ai"]')?.disabled).toBe(true)
  expect(host.textContent).toContain("Cloudflare Workers AI")
})

it("queues the selected brand, composition, and canvas then opens the cover task", async () => {
  await select("cover-motif", "field-mesh")
  await select("cover-size", "1080x1080")
  await select("cover-ground", "black")
  await act(async () => host.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })))
  const [path, init] = request.mock.calls[0]
  expect(path).toBe("/covers")
  expect(JSON.parse(init.body)).toMatchObject({
    design_system_id: "brand", motif: "field-mesh", width: 1080, height: 1080, ground: "black",
  })
  expect(init.body).not.toContain("#")
  expect(host.querySelector("[data-result]")).not.toBeNull()
})

it("preserves the preview seed for generation and clears outdated previews", async () => {
  await act(async () => button("Preview drawing").click())
  expect(host.querySelector("[data-preview]")?.textContent).toBe("preview-art")
  const previewRequest = JSON.parse(request.mock.calls[0][1].body)
  expect(previewRequest.seed).not.toBe("")
  await select("cover-ground", "black")
  expect(host.querySelector("[data-preview]")).toBeNull()
  await act(async () => button("Generate covers").click())
  expect(JSON.parse(request.mock.calls[1][1].body).seed).toBe(previewRequest.seed)
})

it("surfaces queue errors and leaves the form usable", async () => {
  request.mockRejectedValueOnce(new Error("Cover queue unavailable"))
  await act(async () => button("Generate covers").click())
  expect(host.querySelector('[role="alert"]')?.textContent).toBe("Cover queue unavailable")
  expect(button("Generate covers").disabled).toBe(false)
})
