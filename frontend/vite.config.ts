import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: { port: 5173, host: true },
  build: { chunkSizeWarningLimit: 800 }, // one small SPA bundle; splitting would only add requests
});
