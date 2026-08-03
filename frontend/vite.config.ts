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
    rollupOptions: {
      output: {
        // Split the stable third-party stack into its own chunks so the app
        // entry stays small and vendors are cached independently of deploys.
        // Only explicit shared deps are grouped — everything else falls back
        // to Vite's default so the lazy Monaco/GrapesJS/ReactFlow chunks stay
        // on-demand.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined
          if (id.includes("/react/") || id.includes("/react-dom/") || id.includes("/scheduler/") || id.includes("react-router") || id.includes("swr")) {
            return "vendor-react"
          }
          if (id.includes("radix-ui") || id.includes("lucide-react") || id.includes("sonner") || id.includes("next-themes")) {
            return "vendor-ui"
          }
          return undefined
        },
      },
    },
  },
})
