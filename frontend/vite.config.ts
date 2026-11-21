import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// `npm run dev`: http://localhost:5173, API calls go to the Python server on :8000.
// `npm run build`: writes the finished site into ../webui, which the Python server serves.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "../webui", emptyOutDir: true },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: true, css: false },
});
