import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Standalone dev server for the metaverse. The main app imports ./src directly (see ../web/vite.config.ts).
export default defineConfig({ plugins: [react()], server: { port: 5174 } });
