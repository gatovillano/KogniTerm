#!/bin/bash

# Script de inicio para KogniTerm Desktop (Nativa: Electron + SolidJS + FastAPI)

SHOW_LOGS=false
REBUILD=false
IS_DEV=false

for arg in "$@"; do
    if [ "$arg" = "--logs" ]; then
        SHOW_LOGS=true
    fi
    if [ "$arg" = "--build" ]; then
        REBUILD=true
    fi
    if [ "$arg" = "--dev" ]; then
        IS_DEV=true
    fi
done

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

export PATH="$SCRIPT_DIR/node_modules/.bin:$SCRIPT_DIR/apps/electron/node_modules/.bin:$PATH"
export ELECTRON_DISABLE_SANDBOX=1

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Localizar binario de Electron
ELECTRON_BIN=""
if [ -f "$SCRIPT_DIR/node_modules/.bin/electron" ]; then
    ELECTRON_BIN="$SCRIPT_DIR/node_modules/.bin/electron"
elif [ -f "$SCRIPT_DIR/apps/electron/node_modules/.bin/electron" ]; then
    ELECTRON_BIN="$SCRIPT_DIR/apps/electron/node_modules/.bin/electron"
elif command_exists electron; then
    ELECTRON_BIN="electron"
else
    echo "❌ No se encontró el ejecutable de Electron en kogniterm-desktop."
    exit 1
fi

LOGS_DIR="$HOME/.kogniterm/logs"
mkdir -p "$LOGS_DIR"

if [ "$IS_DEV" = true ]; then
    echo -e "${YELLOW}🛠️  Iniciando KogniTerm Desktop en modo Desarrollo...${NC}"
    # Modo dev con Vite + Electron Dev
    if [ "$SHOW_LOGS" = true ]; then
        npm run dev:electron
    else
        setsid npm run dev:electron > "$LOGS_DIR/desktop.log" 2>&1 &
        echo -e "${GREEN}✨ KogniTerm Desktop (Dev) lanzado en segundo plano.${NC}"
    fi
    exit 0
fi

echo -e "${BLUE}🚀 Iniciando KogniTerm Desktop (Producción)...${NC}"

# Compilar si no existe la salida o si se solicita --build
if [ ! -f "apps/web/dist/index.html" ] || [ ! -f "apps/electron/out/main/main.js" ] || [ "$REBUILD" = true ]; then
    echo "📦 Compilando aplicación..."
    npm run build
fi

export NODE_ENV=production

if [ "$SHOW_LOGS" = true ]; then
    "$ELECTRON_BIN" "$SCRIPT_DIR/apps/electron/out/main/main.js"
else
    echo "📝 Guardando logs del escritorio en $LOGS_DIR/desktop.log"
    setsid "$ELECTRON_BIN" "$SCRIPT_DIR/apps/electron/out/main/main.js" > "$LOGS_DIR/desktop.log" 2>&1 &
    echo -e "${GREEN}✨ KogniTerm Desktop iniciado correctamente.${NC}"
fi
