// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { ApiKeyDialog } from "../api-key-dialog"
import { ApiKeyPrompt } from "../api-key-prompt"
import { clearApiKey, getApiKey, setApiKey } from "@/lib/api"

let root: Root
let container: HTMLDivElement
beforeEach(() => {
  ;(globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  localStorage.clear()
  clearApiKey()
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(async () => {
  vi.restoreAllMocks()
  await act(async () => root.unmount())
  container.remove()
})
async function click(label: string) {
  const button = [...document.querySelectorAll("button")].find((b) => b.textContent?.trim() === label)
  expect(button).toBeTruthy()
  await act(async () => button!.click())
}

it("loads the current key when reopened after another prompt saved it", async () => {
  await act(async () => root.render(<ApiKeyDialog />))
  setApiKey("saved-by-first-run-prompt")
  await click("API Key")
  expect((document.getElementById("api-key") as HTMLInputElement).value).toBe("saved-by-first-run-prompt")
  await click("Save")
  expect(getApiKey()).toBe("saved-by-first-run-prompt")
  expect(localStorage.getItem("tasbir:apikey:v1")).toBe("saved-by-first-run-prompt")
})

it("keeps the first-run prompt closed when a saved key exists", async () => {
  setApiKey("remembered")
  await act(async () => root.render(<ApiKeyPrompt />))
  expect(document.querySelector('[role="dialog"]')).toBeNull()
})

it("shows storage failure and leaves the dialog open", async () => {
  setApiKey("existing")
  await act(async () => root.render(<ApiKeyDialog />))
  await click("API Key")
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota exceeded") })
  await click("Save")
  expect(document.querySelector('[role="alert"]')?.textContent).toContain("Allow site storage")
  expect(document.querySelector('[role="dialog"]')).not.toBeNull()
})
