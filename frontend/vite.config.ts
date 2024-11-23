import path from "node:path";
import { TanStackRouterVite } from "@tanstack/router-vite-plugin";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const ReactCompilerConfig = {};
// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 5678,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  plugins: [
    react({
      babel: {
        plugins: [["babel-plugin-react-compiler", ReactCompilerConfig]]
      }
    }),
    TanStackRouterVite()
  ],
  resolve: {
    alias: {
      "~": path.resolve(__dirname, "./src")
    }
  }
});
