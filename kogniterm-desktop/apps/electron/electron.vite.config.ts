import { fileURLToPath } from "node:url";
import { defineConfig } from "electron-vite";

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));

// outDir separado por bundle: si comparten carpeta, el segundo build vacía la
// salida del primero (emptyOutDir).
// El preload se emite como CommonJS (.cjs) porque Electron lo ejecuta en un
// contexto sandboxed que no admite ESM.
export default defineConfig({
  main: {
    build: {
      outDir: "out/main",
      rollupOptions: { input: r("./src/main.ts") },
    },
  },
  preload: {
    build: {
      outDir: "out/preload",
      rollupOptions: {
        input: r("./src/preload.ts"),
        output: { format: "cjs", entryFileNames: "preload.cjs" },
      },
    },
  },
});
