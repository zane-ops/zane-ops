import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import babel from "vite-plugin-babel";
import tsconfigPaths from "vite-tsconfig-paths";
import { splitVendorChunks } from 'vite'; // Import splitVendorChunks

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false, // Only disable in development, ensure HTTPS in production
        ws: true, // Enable WebSocket proxying
        // Configure proxy headers for enhanced security
        headers: {
          "X-Forwarded-Host": "localhost:5173",
          "X-Forwarded-Proto": "http"
        }
      }
    }
  },
  build: {
    sourcemap: true, // Enable sourcemaps for debugging in production
    minify: 'esbuild', // Use esbuild for faster minification
    cssMinify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks: {
          // Define custom chunks for better caching
          ui: ['~/components/ui'],
          api: ['~/api/client'],
          utils: ['~/utils'],
          // You can add more chunks based on your project structure
        },
      },
    },
  },
  optimizeDeps: {
    esbuildOptions: {
      target: 'esnext', // Target the latest ECMAScript version
      supported: {
        // Ensure all features are supported
        arrow: true,
        bigint: true,
        const_enums: true,
        destructuring: true,
        for_of: true,
        nullish: true,
        object_rest_spread: true,
      },
      define: {
        'this': 'window', // fixes "ReferenceError: this is not defined"
      },
    },
  },
  plugins: [
    babel({
      filter: /\.tsx?$/,
      babelConfig: {
        presets: ["@babel/preset-typescript"],
        plugins: ["babel-plugin-react-compiler"]
      }
    }),
    reactRouter(),
    tsconfigPaths(),
    tailwindcss(),
    splitVendorChunks(), // Add splitVendorChunks plugin
  ],
});
