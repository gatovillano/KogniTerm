import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@kogniterm/types": path.resolve(__dirname, "./src/types"),
      "@kogniterm/ui": path.resolve(__dirname, "./src/ui"),
    },
  },
  server: {
    port: 3000,
  },
});
