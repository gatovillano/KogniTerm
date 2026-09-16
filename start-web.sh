#!/usr/bin/env bash
set -euo pipefail

# Script de inicio rápido para KogniTerm Web
# Inicia el backend y sirve el cliente web estático

SHOW_LOGS=false
FRONTEND_PORT=3000
BACKEND_PORT=8765
OPEN_BROWSER=true
DETACH=false

for arg in "$@"; do
  case "$arg" in
    --logs) SHOW_LOGS=true ;;
    --no-browser) OPEN_BROWSER=false ;;
    --detach|-d) DETACH=true ;;
    --frontend-port=*) FRONTEND_PORT="${arg#*=}" ;;
    --backend-port=*) BACKEND_PORT="${arg#*=}" ;;
    --help|-h)
      echo "Uso: $0 [opciones]"
      echo ""
      echo "Opciones:"
      echo "  --logs           Muestra logs en terminal"
      echo "  --no-browser     No abre el navegador automáticamente"
      echo "  -d, --detach     Ejecuta en segundo plano y retorna a la terminal"
      echo "  --frontend-port=N Puerto del frontend (default: 3000)"
      echo "  --backend-port=N  Puerto del backend (default: 8765)"
      echo "  --help           Muestra esta ayuda"
      exit 0
      ;;
  esac
done

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Directorios base del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/kogniterm"

# Priorizar la aplicación moderna en kogniterm-desktop/apps/desktop
if [ -d "${SCRIPT_DIR}/kogniterm-desktop/apps/desktop" ]; then
  FRONTEND_SRC_DIR="${SCRIPT_DIR}/kogniterm-desktop/apps/desktop"
  FRONTEND_DIST="${FRONTEND_SRC_DIR}/dist"
else
  FRONTEND_SRC_DIR="${SCRIPT_DIR}/kogniterm-web"
  FRONTEND_DIST="${FRONTEND_SRC_DIR}/dist"
fi

LOGS_DIR="${HOME}/.kogniterm/logs"
SERVER_LOG="${LOGS_DIR}/web-server.log"
BACKEND_LOG="${LOGS_DIR}/web-backend.log"

echo "🧭 Directorio del proyecto: ${SCRIPT_DIR}"
echo "🎨 Directorio del frontend: ${FRONTEND_SRC_DIR}"
echo ""

# Verificar dependencias básicas
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

if ! command_exists python3; then
  echo "❌ Python 3 no está instalado"
  exit 1
fi

if ! command_exists npm && ! command_exists npx; then
  echo "⚠️  npm/npx no encontrado, usaré solo servidor Python como fallback"
fi

# Verificar estructura y compilar si es necesario
if [ ! -d "${FRONTEND_DIST}" ]; then
  if command_exists npm && [ -f "${FRONTEND_SRC_DIR}/package.json" ]; then
    echo "${BLUE}📦 Build no encontrado. Compilando frontend en ${FRONTEND_SRC_DIR}...${NC}"
    (cd "${FRONTEND_SRC_DIR}" && npm run build)
  else
    echo "❌ No se encontró el build del frontend en: ${FRONTEND_DIST}"
    echo "   Primero ejecuta el build en ${FRONTEND_SRC_DIR}."
    exit 1
  fi
fi

# Sincronizar hacia kogniterm-web/dist para compatibilidad hacia atrás
if [ -d "${FRONTEND_DIST}" ] && [ "${FRONTEND_DIST}" != "${SCRIPT_DIR}/kogniterm-web/dist" ]; then
  mkdir -p "${SCRIPT_DIR}/kogniterm-web"
  rm -rf "${SCRIPT_DIR}/kogniterm-web/dist"
  cp -r "${FRONTEND_DIST}" "${SCRIPT_DIR}/kogniterm-web/dist"
fi

if [ ! -d "${BACKEND_DIR}" ]; then
  echo "❌ No se encontró el backend en: ${BACKEND_DIR}"
  exit 1
fi

# Preparar logs
mkdir -p "${LOGS_DIR}"

# Verificar si el backend ya está corriendo
BACKEND_RUNNING=false
if curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
  BACKEND_RUNNING=true
  echo "✅ Backend ya está corriendo en http://localhost:${BACKEND_PORT}"
else
  # Buscar proceso del backend aunque /health no responda
  if pgrep -f "kogniterm.server" >/dev/null 2>&1; then
    BACKEND_RUNNING=true
    echo "✅ Proceso de KogniTerm Server detectado en el puerto ${BACKEND_PORT}"
  fi
fi

# Iniciar backend si es necesario
if [ "${BACKEND_RUNNING}" = false ]; then
  echo "${BLUE}🐍 Iniciando backend en puerto ${BACKEND_PORT}...${NC}"

  if [ -f "${SCRIPT_DIR}/.venv/bin/activate" ]; then
    VENV_ACTIVATE="${SCRIPT_DIR}/.venv/bin/activate"
  elif [ -f "${SCRIPT_DIR}/venv/bin/activate" ]; then
    VENV_ACTIVATE="${SCRIPT_DIR}/venv/bin/activate"
  elif [ -f "${HOME}/.kogniterm/venv/bin/activate" ]; then
    VENV_ACTIVATE="${HOME}/.kogniterm/venv/bin/activate"
  else
    VENV_ACTIVATE=""
  fi

  BACKEND_CMD=""
  if [ -n "${VENV_ACTIVATE}" ]; then
    BACKEND_CMD="source ${VENV_ACTIVATE} && "
  fi
  WORKSPACE_ARG=""
  if [ -n "${KOGNITERM_WORKSPACE:-}" ]; then
    WORKSPACE_ARG="--workspace \"${KOGNITERM_WORKSPACE}\""
  fi
  BACKEND_CMD="${BACKEND_CMD}python3 -m kogniterm.server --port ${BACKEND_PORT} ${WORKSPACE_ARG}"

  if [ "${SHOW_LOGS}" = true ]; then
    echo "🧾 Mostrando logs del backend..."
    bash -lc "${BACKEND_CMD}" > >(tee "${BACKEND_LOG}") 2> >(tee "${BACKEND_LOG}" >&2) &
  else
    bash -lc "${BACKEND_CMD}" > "${BACKEND_LOG}" 2>&1 &
  fi

  BACKEND_PID=$!
  echo "🆔 Backend PID: ${BACKEND_PID}"

  # Esperar healthcheck
  echo "⏳ Esperando a que el backend responda..."
  for i in {1..120}; do
    if curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
      echo "${GREEN}✅ Backend listo en http://localhost:${BACKEND_PORT}${NC}"
      break
    fi
    sleep 1
    if [ "$i" -eq 120 ]; then
      echo "❌ El backend no respondió a tiempo. Revisa ${BACKEND_LOG}"
      exit 1
    fi
  done
else
  echo ""
fi

# Comprobar si el frontend ya está corriendo en el puerto
FRONTEND_RUNNING=false
if curl -sf "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
  FRONTEND_RUNNING=true
  echo "✅ Frontend ya está corriendo en http://localhost:${FRONTEND_PORT}"
fi

FRONTEND_CMD=""
FRONTEND_PID=""

if [ "${FRONTEND_RUNNING}" = false ]; then
  # Elegir servidor frontend
  if command_exists npx; then
    echo "${BLUE}🌐 Sirviendo cliente web con npx serve en puerto ${FRONTEND_PORT}...${NC}"
    FRONTEND_CMD="npx -y serve -s ${FRONTEND_DIST} -l ${FRONTEND_PORT}"
  elif command_exists python3; then
    echo "${BLUE}🐍 Sirviendo cliente web con Python HTTP server en puerto ${FRONTEND_PORT}...${NC}"
    FRONTEND_CMD="python3 -m http.server ${FRONTEND_PORT} --directory ${FRONTEND_DIST}"
  else
    echo "❌ No se encontró ni npx ni python3 para servir el frontend"
    exit 1
  fi

  if [ "${SHOW_LOGS}" = true ]; then
    echo "🧾 Mostrando logs del frontend..."
    bash -lc "${FRONTEND_CMD}" > >(tee "${SERVER_LOG}") 2> >(tee "${SERVER_LOG}" >&2) &
  else
    bash -lc "${FRONTEND_CMD}" > "${SERVER_LOG}" 2>&1 &
  fi

  FRONTEND_PID=$!
  echo "🆔 Frontend PID: ${FRONTEND_PID}"
fi

# Definir limpieza si se ejecuta en primer plano
cleanup() {
  echo -e "\n${YELLOW}🛑 Deteniendo KogniTerm Web...${NC}"
  if [ -n "${BACKEND_PID:-}" ]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ]; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  exit 0
}

if [ "${DETACH}" = false ]; then
  trap cleanup SIGINT SIGTERM
fi

# Abrir navegador
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
BACKEND_URL="http://localhost:${BACKEND_PORT}"

if [ "${OPEN_BROWSER}" = true ]; then
  echo ""
  echo "${YELLOW}🌍 Abriendo navegador en ${FRONTEND_URL} ...${NC}"
  if command_exists xdg-open; then
    xdg-open "${FRONTEND_URL}" >/dev/null 2>&1 || true
  elif command_exists open; then
    open "${FRONTEND_URL}" >/dev/null 2>&1 || true
  elif command_exists wslview; then
    wslview "${FRONTEND_URL}" >/dev/null 2>&1 || true
  fi
fi

# Resumen final
echo ""
echo "${GREEN}✨ KogniTerm Web iniciado${NC}"
echo ""
echo "📌 URLs:"
echo "  - Frontend : ${FRONTEND_URL}"
echo "  - Backend  : ${BACKEND_URL}"
echo ""
echo "📝 Logs:"
echo "  - Backend  : ${BACKEND_LOG}"
echo "  - Frontend : ${SERVER_LOG}"
echo ""

if [ "${DETACH}" = true ]; then
  echo "✨ Ejecutándose en segundo plano."
  if [ -n "${BACKEND_PID:-}" ] || [ -n "${FRONTEND_PID:-}" ]; then
    echo "🛑 Para detener:"
    echo "  kill ${BACKEND_PID:-} ${FRONTEND_PID:-}"
  fi
  echo ""
  exit 0
fi

echo "🛑 Presiona Ctrl+C para detener (o usa -d / --detach para segundo plano)"
echo ""

# Esperar procesos
wait
