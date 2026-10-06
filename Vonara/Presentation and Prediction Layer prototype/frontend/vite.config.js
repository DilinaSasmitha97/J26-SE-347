import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the UI runs on Vite's server and forwards API calls to
// the component's demo server (uvicorn demo_api:app --port 8004). In
// production `npm run build` writes dist/, which demo_api.py serves itself.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8004",
      "/demo": "http://localhost:8004",
    },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1600 },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.js"],
    css: false,
  },
});
