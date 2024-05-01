import path from "node:path";
import { TanStackRouterVite } from "@tanstack/router-vite-plugin";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 5678
  },

  plugins: [react(), TanStackRouterVite()],
  resolve: {
    alias: {
      "~": path.resolve(__dirname, "./src")
    }
  }
});
