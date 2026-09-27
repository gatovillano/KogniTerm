import { defineConfig } from "vite"
import solidPlugin from "vite-plugin-solid"
import { iconsSpritesheet } from "vite-plugin-icons-spritesheet"
import fs from "fs"

export default defineConfig({
  plugins: [
    solidPlugin(),
    providerIconsPlugin(),
    iconsSpritesheet([
      {
        withTypes: true,
        inputDir: "src/assets/icons/file-types",
        outputDir: "src/components/file-icons",
        formatter: "prettier",
      },
      {
        withTypes: true,
        inputDir: "src/assets/icons/provider",
        outputDir: "src/components/provider-icons",
        formatter: "prettier",
        iconNameTransformer: (iconName) => iconName,
      },
    ]),
  ],
  server: { port: 3001 },
  build: {
    target: "esnext",
  },
  worker: {
    format: "es",
  },
})

function providerIconsPlugin() {
  return {
    name: "provider-icons-plugin",
    configureServer() {
      void fetchProviderIcons()
    },
    buildStart() {
      void fetchProviderIcons()
    },
  }
}

async function fetchProviderIcons() {
  try {
    const url = process.env.OPENCODE_MODELS_URL || "https://models.opencode.ai"
    const res = await fetch(`${url}/api.json`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) return
    const json = await res.json()
    const providers = Object.keys(json)
    await Promise.all(
      providers.map((provider) =>
        fetch(`${url}/logos/${provider}.svg`, { signal: AbortSignal.timeout(3000) })
          .then((r) => (r.ok ? r.text() : null))
          .then((svg) => {
            if (svg) fs.writeFileSync(`./src/assets/icons/provider/${provider}.svg`, svg)
          })
          .catch(() => {}),
      ),
    )
  } catch (error) {
    // Graceful fallback when network is unavailable or offline
  }
}
