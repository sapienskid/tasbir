// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { GenerationFeedback } from "../generation-feedback"

const { request, mutate } = vi.hoisted(() => ({ request: vi.fn(), mutate: vi.fn() }))
vi.mock("@/lib/api", () => ({ apiRequest: request }))
vi.mock("swr", () => ({ default: () => ({ data: [], mutate }) }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

let root: Root
let host: HTMLDivElement
beforeEach(async () => {
  ;(globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  request.mockReset().mockResolvedValue({})
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
  await act(async () => root.render(<GenerationFeedback taskId="task-1" format="instagram-square" />))
})
afterEach(async () => {
  await act(async () => root.unmount())
  host.remove()
})

function button(name: string): HTMLButtonElement {
  return [...host.querySelectorAll("button")].find((b) => b.textContent === name)!
}

it("ordinary approval does not opt into learning", async () => {
  await act(async () => button("Approve").click())
  const [path, options] = request.mock.calls[0]
  expect(path).toBe("/tasks/task-1/feedback")
  expect(JSON.parse(options.body)).toMatchObject({ verdict: "approve", curate: false })
})

it("requires a reason before saving an approved reference", async () => {
  await act(async () => (host.querySelector('input[type="checkbox"]') as HTMLInputElement).click())
  expect(button("Approve").disabled).toBe(true)
  expect(request).not.toHaveBeenCalled()
  expect(button("Needs improvement").disabled).toBe(false)
})

it("rejection never opts into learning, even when the checkbox was checked", async () => {
  await act(async () => (host.querySelector('input[type="checkbox"]') as HTMLInputElement).click())
  await act(async () => button("Needs improvement").click())
  expect(JSON.parse(request.mock.calls[0][1].body)).toMatchObject({ verdict: "reject", curate: false })
})
