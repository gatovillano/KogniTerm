#!/bin/bash

# Script de inicio rápido para KogniTerm Desktop v2 (Electron + SolidJS)

SHOW_LOGS=false
for arg in "$@"; do
    if [ "$arg" = "--logs" ]; then
        SHOW_LOGS=true
    fi
done

echo "🚀 Iniciando KogniTerm Desktop v2..."
echo ""

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

export PATH="$SCRIPT_DIR/node_modules/.bin:$SCRIPT_DIR/packages/desktop/node_modules/.bin:$PATH"

# Verificar si estamos en el directorio correcto
if [ ! -d "packages/desktop" ]; then
    echo "❌ Error: Este script debe ejecutarse desde el directorio kogniterm-desktop/"
    exit 1
fi

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verificar dependencias
echo "🔍 Verificando dependencias..."

if ! command_exists node; then
    echo "❌ Node.js no está instalado"
    exit 1
fi

if ! command_exists npm; then
    echo "❌ npm no está instalado"
    exit 1
fi

echo "✅ Dependencias verificadas"
echo ""

# Instalar dependencias de node_modules si no existen
if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependencias de Node.js..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Error al instalar dependencias de Node.js"
        exit 1
    fi
    echo "✅ Dependencias instaladas"
    echo ""
fi

# Hacer ejecutable el script
chmod +x "$SCRIPT_DIR/start-dev.sh" 2>/dev/null || true

echo "${BLUE}🎨 Iniciando KogniTerm Desktop (Electron + SolidJS)...${NC}"

if [ "$SHOW_LOGS" = true ]; then
    npm --workspace=@kogniterm/desktop run dev
else
    LOGS_DIR="$HOME/.kogniterm/logs"
    mkdir -p "$LOGS_DIR"
    echo "📝 Guardando logs del escritorio en $LOGS_DIR/desktop.log"
    npm --workspace=@kogniterm/desktop run dev > "$LOGS_DIR/desktop.log" 2>&1 &
fi

echo ""
echo "${GREEN}✨ KogniTerm Desktop v2 iniciado correctamente.${NC}"
