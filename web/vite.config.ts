import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = "http://127.0.0.1:8000";
const here = path.dirname(fileURLToPath(import.meta.url));
const mod = (name: string) => path.resolve(here, "node_modules", name);

export default defineConfig({
  plugins: [react()],
  // Fonts are served by the backend too, so they are not copied into dist.
  publicDir: false,
  resolve: {
    // The metaverse lives in ../metaverse. Point its imports at this app's node_modules
    // so there is one copy of react and three.
    alias: {
      metaverse: path.resolve(here, "../metaverse/src/index.ts"),
      react: mod("react"),
      "react-dom": mod("react-dom"),
      three: mod("three"),
      "@fontsource": mod("@fontsource"),
    },
  },
  server: {
    port: 5173,
    fs: { allow: [".."] },
    proxy: { "/api": backend, "/media": backend, "/fonts": backend },
  },
});
