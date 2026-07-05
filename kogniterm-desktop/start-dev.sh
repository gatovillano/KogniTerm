#!/bin/bash

# Script de inicio rápido para KogniTerm Desktop
# Este script inicia tanto el backend como el frontend

SHOW_LOGS=false
for arg in "$@"; do
    if [ "$arg" = "--logs" ]; then
        SHOW_LOGS=true
    fi
done

echo "🚀 Iniciando KogniTerm Desktop..."
echo ""

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verificar si estamos en el directorio correcto
if [ ! -d "apps/desktop" ] || [ ! -d "apps/desktop" ]; then
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

# Instalar dependencias de node_modules si no existen
if [ ! -d "node_modules" ]; then
    echo "📦 No se encontró node_modules. Instalando dependencias de Node.js..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Error al instalar dependencias de Node.js"
        exit 1
    fi
    echo "✅ Dependencias de Node.js instaladas"
    echo ""
fi

# Comprobar si el backend ya está corriendo
BACKEND_RUNNING=false
if curl -s "http://localhost:8765/health" > /dev/null; then
    BACKEND_RUNNING=true
    echo "✅ KogniTerm Server ya está corriendo en http://localhost:8765"
    echo ""
fi

# Iniciar backend si no está corriendo
if [ "$BACKEND_RUNNING" = false ]; then
    echo "${BLUE}📡 Iniciando backend (KogniTerm Server)...${NC}"
    WORKSPACE_ARG=""
    if [ -n "$KOGNITERM_WORKSPACE" ]; then
        WORKSPACE_ARG="--workspace \"$KOGNITERM_WORKSPACE\""
    fi

    if [ "$SHOW_LOGS" = true ]; then
        if command_exists gnome-terminal; then
            gnome-terminal -- bash -c "source \$HOME/.cargo/env; source /home/gato/.kogniterm/venv/bin/activate; cd .. && echo '🐍 KogniTerm Server' && python3 -m kogniterm.server --port 8765 $WORKSPACE_ARG; exec bash"
        elif command_exists konsole; then
            konsole -e bash -c "source \$HOME/.cargo/env; source /home/gato/.kogniterm/venv/bin/activate; cd .. && echo '🐍 KogniTerm Server' && python3 -m kogniterm.server --port 8765 $WORKSPACE_ARG; exec bash" &
        elif command_exists xterm; then
            xterm -e "source \$HOME/.cargo/env; source /home/gato/.kogniterm/venv/bin/activate; cd .. && echo '🐍 KogniTerm Server' && python3 -m kogniterm.server --port 8765 $WORKSPACE_ARG; exec bash" &
        else
            echo "⚠️  No se encontró un emulador de terminal compatible."
            echo "Por favor, ejecuta manualmente en otra terminal (desde la raíz del proyecto):"
            echo "  source /home/gato/.kogniterm/venv/bin/activate && python3 -m kogniterm.server --port 8765 $WORKSPACE_ARG"
        fi
    else
        LOGS_DIR="$HOME/.kogniterm/logs"
        mkdir -p "$LOGS_DIR"
        echo "📝 Guardando logs del servidor en $LOGS_DIR/server.log"
        bash -c "source \$HOME/.cargo/env; source /home/gato/.kogniterm/venv/bin/activate; cd .. && python3 -m kogniterm.server --port 8765 $WORKSPACE_ARG" > "$LOGS_DIR/server.log" 2>&1 &
    fi
fi

# Función para esperar a que el backend esté listo
wait_for_backend() {
    local url="http://localhost:8765/health"
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

# Ejecutar la espera solo si iniciamos el backend en esta sesión
if [ "$BACKEND_RUNNING" = false ]; then
    wait_for_backend
fi

# Iniciar frontend
echo "${BLUE}🎨 Iniciando frontend (Tauri)...${NC}"
if [ "$SHOW_LOGS" = true ]; then
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
else
    LOGS_DIR="$HOME/.kogniterm/logs"
    mkdir -p "$LOGS_DIR"
    echo "📝 Guardando logs del frontend en $LOGS_DIR/tauri.log"
    bash -c "source \$HOME/.cargo/env; cd apps/desktop && npm run tauri dev" > "$LOGS_DIR/tauri.log" 2>&1 &
fi

echo ""
echo "${GREEN}✨ KogniTerm Desktop se está iniciando...${NC}"
echo ""
echo "📝 Notas:"
echo "  - Backend: http://localhost:8765"
if [ "$SHOW_LOGS" = true ]; then
    echo "  - Frontend: Se abrirá automáticamente"
    echo "  - Presiona Ctrl+C en cada terminal para detener"
else
    echo "  - Logs del servidor: $LOGS_DIR/server.log"
    echo "  - Logs del frontend: $LOGS_DIR/tauri.log"
fi
echo ""
