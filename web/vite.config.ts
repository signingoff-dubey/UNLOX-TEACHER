import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  // Fonts are served by the backend too, so they are not copied into dist.
  publicDir: false,
  server: {
    port: 5173,
    proxy: { "/api": backend, "/media": backend, "/fonts": backend },
  },
});
