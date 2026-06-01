/** @type {import("vitest/config").default } */

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text"],
    },
  },
});
