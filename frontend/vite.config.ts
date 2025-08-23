import { execSync } from "node:child_process";
import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import babel from "vite-plugin-babel";
import tsconfigPaths from "vite-tsconfig-paths";

const commitHash =
  process.env.COMMIT_SHA ??
  execSync("git rev-parse --short HEAD").toString().trim();

export default defineConfig({
  define: {
    __BUILD_ID__: JSON.stringify(commitHash)
  },
  server: {
    port: 5173,
    allowedHosts: ["zn.fkiss.me"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  plugins: [
    babel({
      filter: /\.tsx?$/,
      babelConfig: {
        presets: ["@babel/preset-typescript"],
        plugins: ["babel-plugin-react-compiler"]
      }
    }),
    tailwindcss(),
    reactRouter(),
    tsconfigPaths()
  ]
});
