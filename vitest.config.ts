import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@shared": resolve(__dirname, "app/shared"),
      "@renderer": resolve(__dirname, "app/renderer")
    }
  },
  test: {
    environment: "jsdom",
    include: ["app/**/*.test.ts", "app/**/*.test.tsx"],
    restoreMocks: true,
    clearMocks: true
  }
});
