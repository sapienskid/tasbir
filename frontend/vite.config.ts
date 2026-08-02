import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// Docker dev: point at the api service; local dev: localhost:8000.
const apiProxy = process.env.VITE_API_PROXY ?? "http://localhost:8000"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api": apiProxy,
    },
  },
  build: {
    chunkSizeWarningLimit: 900,
  },
})
