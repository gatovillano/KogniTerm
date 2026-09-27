#!/bin/bash

# Script de producción para KogniTerm Desktop v2 (Electron + SolidJS)

SHOW_LOGS=false
REBUILD=false
for arg in "$@"; do
    if [ "$arg" = "--logs" ]; then
        SHOW_LOGS=true
    fi
    if [ "$arg" = "--build" ]; then
        REBUILD=true
    fi
done

echo "🚀 Iniciando KogniTerm Desktop v2 (Producción)..."
echo ""

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

export PATH="$SCRIPT_DIR/node_modules/.bin:$SCRIPT_DIR/packages/desktop/node_modules/.bin:$PATH"
export ELECTRON_DISABLE_SANDBOX=1

# Verificar si estamos en el directorio correcto
if [ ! -d "packages/desktop" ]; then
    echo "❌ Error: Este script debe ejecutarse desde el directorio kogniterm-desktop/"
    exit 1
fi

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verificación y autosanación del binario de Electron
if [ ! -f "node_modules/electron/path.txt" ] && [ ! -f "packages/desktop/node_modules/electron/path.txt" ]; then
    echo "⚡ Instalando binario de Electron..."
    (cd packages/desktop && node node_modules/electron/install.js) 2>/dev/null || true
fi

# Compilar producción si no existe out/main/index.js o out/renderer/index.html, se solicita --build o hay archivos fuente modificados
if [ ! -f "packages/desktop/out/main/index.js" ] || [ ! -f "packages/desktop/out/renderer/index.html" ] || [ "$REBUILD" = true ] || [ -n "$(find packages/desktop/src packages/app/src packages/ui/src -newer packages/desktop/out/main/index.js 2>/dev/null | head -n 1)" ]; then
    echo "📦 Compilando paquetes de producción..."
    (cd packages/desktop && npm run build)
fi

ELECTRON_BIN=""
if [ -f "packages/desktop/node_modules/.bin/electron" ]; then
    ELECTRON_BIN="$SCRIPT_DIR/packages/desktop/node_modules/.bin/electron"
elif [ -f "node_modules/.bin/electron" ]; then
    ELECTRON_BIN="$SCRIPT_DIR/node_modules/.bin/electron"
elif command_exists electron; then
    ELECTRON_BIN="electron"
else
    echo "❌ No se encontró el ejecutable de Electron."
    exit 1
fi

echo "${BLUE}🎨 Lanzando KogniTerm Desktop en Producción...${NC}"

if [ "$SHOW_LOGS" = true ]; then
    "$ELECTRON_BIN" packages/desktop/out/main/index.js
else
    LOGS_DIR="$HOME/.kogniterm/logs"
    mkdir -p "$LOGS_DIR"
    echo "📝 Guardando logs del escritorio en $LOGS_DIR/desktop.log"
    nohup "$ELECTRON_BIN" packages/desktop/out/main/index.js > "$LOGS_DIR/desktop.log" 2>&1 &
fi

echo ""
echo "${GREEN}✨ KogniTerm Desktop v2 iniciado correctamente.${NC}"
