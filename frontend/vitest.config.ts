import path from "node:path"
import { defineConfig } from "vitest/config"

// Unit tests cover the framework-free editor logic in src/lib (store, save
// queue, preview sequencer, DOM patch helpers) and route-tree wiring. Files
// that touch the DOM opt into jsdom with a `// @vitest-environment jsdom`
// docblock; `.tsx` is included so React components/routing can be rendered.
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
})
