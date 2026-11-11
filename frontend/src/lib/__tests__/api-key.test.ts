import { beforeEach, afterEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tasbir:apikey:v1"
let storage: Map<string, string>
let cookies: Map<string, string>
let lastCookie: string

beforeEach(() => {
  vi.resetModules()
  storage = new Map()
  cookies = new Map()
  lastCookie = ""
  vi.stubGlobal("location", { protocol: "https:" })
  vi.stubGlobal("localStorage", {
    getItem: vi.fn((key: string) => storage.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
    removeItem: vi.fn((key: string) => storage.delete(key)),
  })
  vi.stubGlobal("document", {
    get cookie() { return [...cookies].map(([key, value]) => `${key}=${value}`).join("; ") },
    set cookie(value: string) {
      lastCookie = value
      const [pair] = value.split(";")
      const index = pair.indexOf("=")
      const key = pair.slice(0, index)
      if (value.includes("Max-Age=0;")) cookies.delete(key)
      else cookies.set(key, pair.slice(index + 1))
    },
  })
})

afterEach(() => vi.unstubAllGlobals())

describe("remembering the API key", () => {
  it("survives a new tab/module and migrates existing saved keys to a secure host cookie", async () => {
    storage.set(STORAGE_KEY, "existing-key")
    expect((await import("../api")).getApiKey()).toBe("existing-key")
    expect(lastCookie).toContain("__Host-tasbir-key-v1=existing-key")
    expect(lastCookie).toContain("Max-Age=31536000; Path=/; Secure; SameSite=Strict")
    vi.resetModules()
    expect((await import("../api")).getApiKey()).toBe("existing-key")
  })

  it("recovers across visits when localStorage writes fail or data disappears", async () => {
    storage.set(STORAGE_KEY, "old-key")
    vi.mocked(localStorage.setItem).mockImplementation(() => { throw new Error("quota") })
    const api = await import("../api")
    api.setApiKey(" remembered key ")
    vi.resetModules()
    expect((await import("../api")).getApiKey()).toBe("remembered key")
  })

  it("reports a persistence failure instead of pretending the key was saved", async () => {
    vi.mocked(localStorage.setItem).mockImplementation(() => { throw new Error("blocked") })
    vi.stubGlobal("document", { cookie: "" })
    vi.stubGlobal("location", { protocol: "http:" })
    const api = await import("../api")
    expect(() => api.setApiKey("key")).toThrow("Allow site storage")
    expect(api.getApiKey()).toBe("")
  })

  it("clears both stores so the key cannot reappear on the next visit", async () => {
    const api = await import("../api")
    api.setApiKey("key")
    api.clearApiKey()
    vi.resetModules()
    expect((await import("../api")).getApiKey()).toBe("")
    expect(storage.size).toBe(0)
    expect(cookies.size).toBe(0)
  })

  it("does not write a credential cookie over HTTP", async () => {
    vi.stubGlobal("location", { protocol: "http:" })
    const api = await import("../api")
    api.setApiKey("key")
    expect(storage.get(STORAGE_KEY)).toBe("key")
    expect(cookies.size).toBe(0)
  })
})
