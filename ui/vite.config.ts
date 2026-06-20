import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8787",
      "/config": "http://127.0.0.1:8787",
      "/tokens": "http://127.0.0.1:8787",
      "/generate-tokens": "http://127.0.0.1:8787",
      "/formats": "http://127.0.0.1:8787",
      "/asset": "http://127.0.0.1:8787",
      "/generate": "http://127.0.0.1:8787",
      "/generate-from-content": "http://127.0.0.1:8787",
      "/webhook": "http://127.0.0.1:8787",
      "/settings": "http://127.0.0.1:8787",
      "/templates": "http://127.0.0.1:8787",
      "/render-html": "http://127.0.0.1:8787",
      "/edited-content": "http://127.0.0.1:8787",
      "/save-to-r2": "http://127.0.0.1:8787",
      "/openapi.json": "http://127.0.0.1:8787",
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@shared': path.resolve(__dirname, '../shared'),
    },
  },
})
