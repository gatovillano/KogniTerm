#!/bin/bash

# Script de inicio rápido para KogniTerm Desktop
# Este script inicia tanto el backend como el frontend en terminales separadas

echo "🚀 Iniciando KogniTerm Desktop..."
echo ""

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verificar si estamos en el directorio correcto
if [ ! -d "apps/server" ] || [ ! -d "apps/desktop" ]; then
    echo "❌ Error: Este script debe ejecutarse desde el directorio kogniterm-desktop/"
    exit 1
fi

# Función para verificar si un comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verificar dependencias
echo "🔍 Verificando dependencias..."

if ! command_exists python3; then
    echo "❌ Python 3 no está instalado"
    exit 1
fi

if ! command_exists npm; then
    echo "❌ npm no está instalado"
    exit 1
fi

echo "✅ Dependencias verificadas"
echo ""

# Iniciar backend en una nueva terminal
echo "${BLUE}📡 Iniciando backend (FastAPI)...${NC}"
if command_exists gnome-terminal; then
    gnome-terminal -- bash -c "source \$HOME/.cargo/env; cd apps/server && echo '🐍 Backend Python/FastAPI' && python3 dev.py; exec bash"
elif command_exists konsole; then
    konsole -e bash -c "source \$HOME/.cargo/env; cd apps/server && echo '🐍 Backend Python/FastAPI' && python3 dev.py; exec bash" &
elif command_exists xterm; then
    xterm -e "source \$HOME/.cargo/env; cd apps/server && echo '🐍 Backend Python/FastAPI' && python3 dev.py; exec bash" &
else
    echo "⚠️  No se encontró un emulador de terminal compatible."
    echo "Por favor, ejecuta manualmente en otra terminal:"
    echo "  cd apps/server && python3 dev.py"
fi

# Función para esperar a que el backend esté listo
wait_for_backend() {
    local url="http://localhost:8001/api/health"
    local max_attempts=120
    local attempt=1

    echo "⏳ Esperando a que el backend esté listo en $url..."
    
    while ! curl -s "$url" > /dev/null; do
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Error: El backend no inició a tiempo tras $max_attempts intentos."
            exit 1
        fi
        
        printf "."
        attempt=$((attempt + 1))
        sleep 1
    done
    
    echo -e "\n✅ Backend detectado y listo!"
}

# Ejecutar la espera antes de iniciar el frontend
wait_for_backend

# Iniciar frontend en otra terminal
echo "${BLUE}🎨 Iniciando frontend (Tauri)...${NC}"
if command_exists gnome-terminal; then
    gnome-terminal -- bash -c "source \$HOME/.cargo/env; cd apps/desktop && echo '⚛️  Frontend Tauri/React' && npm run tauri dev; exec bash"
elif command_exists konsole; then
    konsole -e bash -c "source \$HOME/.cargo/env; cd apps/desktop && echo '⚛️  Frontend Tauri/React' && npm run tauri dev; exec bash" &
elif command_exists xterm; then
    xterm -e "source \$HOME/.cargo/env; cd apps/desktop && echo '⚛️  Frontend Tauri/React' && npm run tauri dev; exec bash" &
else
    echo "⚠️  No se encontró un emulador de terminal compatible."
    echo "Por favor, ejecuta manualmente en otra terminal:"
    echo "  cd apps/desktop && npm run tauri dev"
fi

echo ""
echo "${GREEN}✨ KogniTerm Desktop está iniciando...${NC}"
echo ""
echo "📝 Notas:"
echo "  - Backend: http://localhost:8001"
echo "  - Frontend: Se abrirá automáticamente"
echo "  - Presiona Ctrl+C en cada terminal para detener"
echo ""
