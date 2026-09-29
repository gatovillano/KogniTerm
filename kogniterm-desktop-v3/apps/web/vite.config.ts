import { defineConfig } from "vite"
import solid from "vite-plugin-solid"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  // Rutas relativas: imprescindible para cargar con file:// en Electron
  // (con "/" los assets apuntan a la raíz del sistema y la ventana sale en negro).
  base: "./",
  plugins: [solid(), tailwindcss()],
  server: {
    port: 4444,
    proxy: {
      // evita CORS en dev: /kapi -> backend nativo
      "/kapi": {
        target: process.env.VITE_KOGNITERM_API ?? "http://127.0.0.1:8765",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/kapi/, ""),
      },
    },
  },
  build: { outDir: "dist" },
})
