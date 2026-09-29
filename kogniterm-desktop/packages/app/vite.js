import { readFileSync } from "node:fs"
import solidPlugin from "vite-plugin-solid"
import tailwindcss from "@tailwindcss/vite"
import { fileURLToPath } from "url"

const theme = fileURLToPath(new URL("./public/oc-theme-preload.js", import.meta.url))

const channel = (() => {
  const raw = process.env.KOGNITERM_CHANNEL
  if (raw === "dev" || raw === "beta" || raw === "prod") return raw
  if (process.env.KOGNITERM_CHANNEL === "latest") return "prod"
  return "dev"
})()

/**
 * @type {import("vite").PluginOption}
 */
export default [
  {
    name: "kogniterm-desktop:config",
    config() {
      return {
        resolve: {
          dedupe: ["solid-js", "solid-js/web", "@kogniterm/ui", "@kogniterm/app"],
          alias: [
            { find: /^@opencode-ai\/ui\/(.*)$/, replacement: "@kogniterm/ui/$1" },
            { find: "@opencode-ai/ui", replacement: "@kogniterm/ui" },
            { find: /^@opencode-ai\/app\/(.*)$/, replacement: "@kogniterm/app/$1" },
            { find: "@opencode-ai/app", replacement: "@kogniterm/app" },
            { find: /^@kogniterm\/app\/src\/(.*)$/, replacement: fileURLToPath(new URL("./src/$1", import.meta.url)) },
            { find: /^@kogniterm\/app$/, replacement: fileURLToPath(new URL("./src/index.ts", import.meta.url)) },
            { find: /^@kogniterm\/app\/(.*)$/, replacement: fileURLToPath(new URL("./src/$1", import.meta.url)) },
            { find: /^lru_map$/, replacement: fileURLToPath(new URL("./src/utils/lru_map-shim.ts", import.meta.url)) },
            { find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url)) },
          ],
        },
        define: {
          "import.meta.env.VITE_KOGNITERM_CHANNEL": JSON.stringify(channel),
        },
        optimizeDeps: {
          include: ["lru_map", "@pierre/diffs", "@pierre/trees"],
          // @opencode-ai/core expone .ts crudos con `export namespace`
          // que esbuild pre-empaqueta mal (pantalla en blanco). Se excluye
          // para que Vite los sirva por el pipeline normal de transform.
          // @opencode-ai/session-ui tiene .tsx que esbuild compila con JSX
          // clásico (React is not defined); debe procesarlo vite-plugin-solid.
          exclude: ["@opencode-ai/core", "@opencode-ai/session-ui"],
        },
        worker: {
          format: "es",
        },
      }
    },
  },
  {
    name: "kogniterm-desktop:theme-preload",
    transformIndexHtml(html) {
      return html.replace(
        '<script id="oc-theme-preload-script" src="/oc-theme-preload.js"></script>',
        `<script id="oc-theme-preload-script">${readFileSync(theme, "utf8")}</script>`,
      )
    },
  },
  tailwindcss(),
  solidPlugin(),
]
