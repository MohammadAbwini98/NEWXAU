import { resolve } from "node:path";
import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: resolve(__dirname, "app/main/main.ts")
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: resolve(__dirname, "app/main/preload.ts")
      }
    }
  },
  renderer: {
    root: resolve(__dirname, "app/renderer"),
    plugins: [react()],
    build: {
      rollupOptions: {
        input: {
          renderer: resolve(__dirname, "app/renderer/index.html")
        }
      }
    },
    resolve: {
      alias: {
        "@shared": resolve(__dirname, "app/shared"),
        "@renderer": resolve(__dirname, "app/renderer")
      }
    }
  }
});
