import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

const API_TARGET = "http://127.0.0.1:4310"

export default defineConfig({
  // Served by `asta serve` from the same origin as /api -> relative assets.
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: { "/api": { target: API_TARGET, changeOrigin: false } },
  },
  preview: { port: 4310, strictPort: false },
})
