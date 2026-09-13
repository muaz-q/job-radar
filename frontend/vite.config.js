import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api/* to the FastAPI backend, so the browser talks to one
// origin and no CORS setup is needed during development.
const backend = process.env.JOB_RADAR_API ?? "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
});
