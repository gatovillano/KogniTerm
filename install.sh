#!/bin/bash
# install.sh - Instalador de KogniTerm desde GitHub
# Uso: curl -fsSL https://raw.githubusercontent.com/gatovillano/KogniTerm/main/install.sh | bash

set -e

# ─── Colores ──────────────────────────────────────────────────────────────────
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

BLACK='\033[0;30m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'

BG_GREEN='\033[42m'
BG_BLUE='\033[44m'

# ─── Configuración ────────────────────────────────────────────────────────────
REPO_URL="https://github.com/gatovillano/KogniTerm.git"
INSTALL_DIR="${HOME}/.kogniterm"
VENV_DIR="${INSTALL_DIR}/venv"
PYTHON_MIN_VERSION="3.9"
LOG_FILE="/tmp/kogniterm_install_$(date +%s).log"
TOTAL_STEPS=7
CURRENT_STEP=0
INSTALL_START=$(date +%s)

# ─── Utilidades de UI ─────────────────────────────────────────────────────────

# Ancho de consola (default 70)
get_cols() { tput cols 2>/dev/null || echo 70; }

print_line() {
    local cols; cols=$(get_cols)
    printf "${DIM}%*s${RESET}\n" "$cols" "" | tr ' ' '─'
}

print_double_line() {
    local cols; cols=$(get_cols)
    printf "${CYAN}%*s${RESET}\n" "$cols" "" | tr ' ' '═'
}

# Progreso visual [████████░░░░] NN%
print_progress_bar() {
    local current=$1
    local total=$2
    local bar_width=30
    local filled=$(( bar_width * current / total ))
    local empty=$(( bar_width - filled ))
    local pct=$(( 100 * current / total ))

    printf "  ${CYAN}["
    printf "${GREEN}%${filled}s" | tr ' ' '█'
    printf "${DIM}%${empty}s" | tr ' ' '░'
    printf "${CYAN}]${RESET} ${BOLD}%3d%%${RESET}\n" "$pct"
}

# Encabezado de paso
step_header() {
    local title="$1"
    CURRENT_STEP=$(( CURRENT_STEP + 1 ))
    echo ""
    print_line
    printf "  ${BOLD}${CYAN}[%d/%d]${RESET} ${BOLD}${WHITE}%s${RESET}\n" \
        "$CURRENT_STEP" "$TOTAL_STEPS" "$title"
    print_progress_bar "$CURRENT_STEP" "$TOTAL_STEPS"
    print_line
}

# Logs con timestamp
ts() { date '+%H:%M:%S'; }

log_info() {
    printf "  ${BLUE}●${RESET}  ${WHITE}%s${RESET}\n" "$1"
    echo "[$(ts)] INFO  $1" >> "$LOG_FILE"
}

log_detail() {
    printf "  ${DIM}│  ➜ %s${RESET}\n" "$1"
    echo "[$(ts)] DETAIL $1" >> "$LOG_FILE"
}

log_success() {
    printf "  ${GREEN}✔${RESET}  ${GREEN}%s${RESET}\n" "$1"
    echo "[$(ts)] OK    $1" >> "$LOG_FILE"
}

log_warn() {
    printf "  ${YELLOW}⚠${RESET}  ${YELLOW}%s${RESET}\n" "$1"
    echo "[$(ts)] WARN  $1" >> "$LOG_FILE"
}

log_error() {
    printf "  ${RED}✖${RESET}  ${BOLD}${RED}%s${RESET}\n" "$1"
    echo "[$(ts)] ERROR $1" >> "$LOG_FILE"
}

log_cmd() {
    printf "  ${DIM}│  \$ %s${RESET}\n" "$1"
    echo "[$(ts)] CMD   \$ $1" >> "$LOG_FILE"
}

# Spinner animado que envuelve un comando
run_with_spinner() {
    local msg="$1"
    shift
    local spin_chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0

    # Ejecutar el comando en segundo plano redirigiendo output al log
    "$@" >> "$LOG_FILE" 2>&1 &
    local pid=$!

    printf "  ${CYAN}%s${RESET}  %s " "${spin_chars:0:1}" "$msg"

    while kill -0 "$pid" 2>/dev/null; do
        i=$(( (i + 1) % ${#spin_chars} ))
        printf "\r  ${CYAN}%s${RESET}  %s " "${spin_chars:$i:1}" "$msg"
        sleep 0.1
    done

    wait "$pid"
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        printf "\r  ${GREEN}✔${RESET}  %s ${GREEN}(listo)${RESET}\n" "$msg"
    else
        printf "\r  ${RED}✖${RESET}  %s ${RED}(falló)${RESET}\n" "$msg"
        log_error "Comando fallido. Revisa el log: $LOG_FILE"
        exit 1
    fi

    echo "[$(ts)] CMD_DONE exit=$exit_code: $*" >> "$LOG_FILE"
    return $exit_code
}

check_command() {
    local cmd="$1"
    local version_flag="${2:---version}"
    if ! command -v "$cmd" &> /dev/null; then
        log_error "'$cmd' no encontrado. Por favor, instálalo primero."
        exit 1
    fi
    local ver
    ver=$("$cmd" $version_flag 2>&1 | head -1) || true
    log_success "$cmd detectado — ${ver}"
}

check_python_version() {
    local python_version=$1
    local required_version="$2"
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        log_error "Se requiere Python ${required_version}+. Detectado: $python_version"
        exit 1
    fi
}

elapsed_time() {
    local end; end=$(date +%s)
    local delta=$(( end - INSTALL_START ))
    printf '%dm %ds' $(( delta / 60 )) $(( delta % 60 ))
}

# ─── BANNER ───────────────────────────────────────────────────────────────────
clear
echo ""
printf "${GREEN}"
cat << "BANNER"
  ╔═══════════════════════════════════════════════════════════════╗
  ║                                                               ║
  ║   ░█░█░█▀█░█▀▀░█▀█░▀█▀░▀█▀░█▀▀░█▀▄░█▄█                   ║
  ║   ░█▀▄░█░█░█░█░█░█░░█░░░█░░█▀▀░█▀▄░█░█                   ║
  ║   ░▀░▀░▀▀▀░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀░▀░▀░▀░▀                   ║
  ║                                                               ║
  ║        KogniTerm — Agente Evolutivo de Terminal              ║
  ║                    Versión 0.5.0                              ║
  ╚═══════════════════════════════════════════════════════════════╝
BANNER
printf "${RESET}"
echo ""
printf "  ${DIM}Instalador interactivo  •  Log: ${LOG_FILE}${RESET}\n"
echo ""
print_double_line

# ─── PASO 1: Verificar dependencias del sistema ───────────────────────────────
step_header "Verificando dependencias del sistema"

log_info "Buscando herramientas requeridas..."

log_detail "Verificando git"
check_command "git" "--version"

log_detail "Verificando curl"
check_command "curl" "--version"

log_detail "Buscando intérprete Python (>= ${PYTHON_MIN_VERSION})"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    log_error "Python no encontrado. Instala Python ${PYTHON_MIN_VERSION}+ y vuelve a intentarlo."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
check_python_version "$PYTHON_VERSION" "$PYTHON_MIN_VERSION"
log_detail "Versión de Python: ${PYTHON_VERSION}"

PYTHON_PATH=$(command -v "$PYTHON_CMD")
log_detail "Ruta del intérprete: ${PYTHON_PATH}"

# Verificar pip
if ! $PYTHON_CMD -m pip --version &>/dev/null; then
    log_error "pip no encontrado para ${PYTHON_CMD}. Instala python3-pip."
    exit 1
fi
PIP_VERSION=$($PYTHON_CMD -m pip --version 2>&1 | awk '{print $2}')
log_detail "pip versión: ${PIP_VERSION}"

log_success "Todas las dependencias del sistema están presentes"

# ─── PASO 2: Configurar directorio de instalación ─────────────────────────────
step_header "Configurar directorio de instalación"

echo ""
printf "  ${CYAN}Directorio de instalación${RESET} [${BOLD}${INSTALL_DIR}${RESET}]: "
read -r custom_install_dir
INSTALL_DIR="${custom_install_dir:-$INSTALL_DIR}"
VENV_DIR="${INSTALL_DIR}/venv"
ENV_FILE="${INSTALL_DIR}/.env"

log_info "Directorio seleccionado: ${INSTALL_DIR}"

# Verificar espacio en disco
AVAILABLE_KB=$(df -k "$(dirname "$INSTALL_DIR")" 2>/dev/null | tail -1 | awk '{print $4}' || echo 0)
AVAILABLE_MB=$(( AVAILABLE_KB / 1024 ))
log_detail "Espacio disponible en disco: ${AVAILABLE_MB} MB"
if [ "$AVAILABLE_MB" -lt 500 ]; then
    log_warn "Poco espacio disponible (${AVAILABLE_MB} MB). Se recomiendan al menos 500 MB."
fi

# ─── PASO 3: Clonar o actualizar repositorio ──────────────────────────────────
step_header "Obtener código fuente"

if [ -d "${INSTALL_DIR}/.git" ]; then
    log_warn "KogniTerm ya está instalado en ${INSTALL_DIR}"

    CURRENT_COMMIT=$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || echo "desconocido")
    CURRENT_BRANCH=$(git -C "$INSTALL_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    log_detail "Commit actual: ${CURRENT_COMMIT}  •  Rama: ${CURRENT_BRANCH}"

    echo ""
    printf "  ${YELLOW}⚠${RESET}  ¿Actualizar a la última versión? (y/N): "
    read -r update_confirm
    if [[ $update_confirm =~ ^[Yy]$ ]]; then
        log_info "Actualizando desde origin/${CURRENT_BRANCH}..."
        log_cmd "git -C ${INSTALL_DIR} pull origin ${CURRENT_BRANCH}"
        run_with_spinner "Descargando últimos cambios" git -C "$INSTALL_DIR" pull origin "$CURRENT_BRANCH"
        NEW_COMMIT=$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || echo "desconocido")
        log_detail "Commit actualizado: ${CURRENT_COMMIT} → ${NEW_COMMIT}"
        log_success "Repositorio actualizado"
    else
        log_info "Manteniendo versión existente (${CURRENT_COMMIT})"
    fi
else
    log_info "Clonando repositorio desde GitHub..."
    log_cmd "git clone ${REPO_URL} ${INSTALL_DIR}"
    run_with_spinner "Clonando KogniTerm" git clone "$REPO_URL" "$INSTALL_DIR"

    CLONED_COMMIT=$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || echo "desconocido")
    CLONED_BRANCH=$(git -C "$INSTALL_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    log_detail "Commit clonado: ${CLONED_COMMIT}  •  Rama: ${CLONED_BRANCH}"

    # Contar archivos clonados
    FILE_COUNT=$(find "$INSTALL_DIR" -type f ! -path '*/.git/*' | wc -l)
    log_detail "Archivos descargados: ${FILE_COUNT}"
    log_success "Repositorio clonado correctamente"
fi

# ─── PASO 4: Crear entorno virtual Python ─────────────────────────────────────
step_header "Configurar entorno virtual Python"

if [ -d "$VENV_DIR" ]; then
    log_warn "Entorno virtual ya existe en: ${VENV_DIR}"
    log_detail "Reutilizando entorno existente"
else
    log_info "Creando entorno virtual con ${PYTHON_CMD}..."
    log_cmd "${PYTHON_CMD} -m venv ${VENV_DIR}"
    run_with_spinner "Creando entorno virtual" "$PYTHON_CMD" -m venv "$VENV_DIR"
    log_detail "Ruta del entorno: ${VENV_DIR}"
    log_success "Entorno virtual creado"
fi

log_info "Activando entorno virtual..."
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
log_detail "Python activo: $(which python)"
log_detail "pip activo:    $(which pip)"

# ─── PASO 5: Instalar paquetes ────────────────────────────────────────────────
step_header "Instalar KogniTerm y dependencias"

# Actualizar pip primero
log_info "Actualizando pip a la última versión..."
log_cmd "pip install --upgrade pip"
run_with_spinner "Actualizando pip" pip install --upgrade pip

PIP_NEW_VERSION=$(pip --version 2>&1 | awk '{print $2}')
log_detail "pip actualizado a: ${PIP_NEW_VERSION}"

# Instalar KogniTerm
log_info "Instalando KogniTerm en modo editable..."
log_cmd "pip install -e ${INSTALL_DIR}"

# Obtener lista de dependencias para mostrar progreso
DEPS_COUNT=0
if [ -f "${INSTALL_DIR}/pyproject.toml" ]; then
    DEPS_COUNT=$(grep -c '^\s*"' "${INSTALL_DIR}/pyproject.toml" 2>/dev/null || echo 0)
elif [ -f "${INSTALL_DIR}/requirements.txt" ]; then
    DEPS_COUNT=$(grep -cv '^\s*#\|^\s*$' "${INSTALL_DIR}/requirements.txt" 2>/dev/null || echo 0)
fi
[ "$DEPS_COUNT" -gt 0 ] && log_detail "Dependencias declaradas: ~${DEPS_COUNT} paquetes"

run_with_spinner "Instalando paquetes (puede tomar varios minutos)" pip install -e "$INSTALL_DIR"

# Mostrar paquetes instalados
INSTALLED_PKGS=$(pip list 2>/dev/null | wc -l)
log_detail "Paquetes instalados en el entorno: ${INSTALLED_PKGS}"

# Verificar que kogniterm fue instalado
if command -v kogniterm &>/dev/null; then
    KT_VERSION=$(kogniterm --version 2>&1 | head -1 || echo "instalado")
    log_success "kogniterm disponible — ${KT_VERSION}"
else
    log_warn "El ejecutable 'kogniterm' no está en el PATH del venv todavía"
fi

# ─── PASO 6: Configurar proveedor LLM ────────────────────────────────────────
step_header "Configurar proveedor de LLM"

# Asegurar que el .env exista
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "${INSTALL_DIR}/.env.example" ]; then
        log_warn ".env no encontrado → copiando desde .env.example para inicializar"
        cp "${INSTALL_DIR}/.env.example" "$ENV_FILE"
    else
        touch "$ENV_FILE"
    fi
fi

printf "\n  ${WHITE}KogniTerm soporta múltiples proveedores de LLM.${RESET}\n"
printf "  ${DIM}Los valores se guardarán en: %s${RESET}\n\n" "$ENV_FILE"

# Menú de selección de proveedor
printf "  ${BOLD}Selecciona el proveedor de LLM:${RESET}\n\n"
printf "  ${CYAN}[1]${RESET} OpenAI (api.openai.com)\n"
printf "  ${CYAN}[2]${RESET} Groq  (api.groq.com)\n"
printf "  ${CYAN}[3]${RESET} Google Gemini\n"
printf "  ${CYAN}[4]${RESET} Anthropic (Claude)\n"
printf "  ${CYAN}[5]${RESET} Ollama (local)\n"
printf "  ${CYAN}[6]${RESET} Otro (compatible con OpenAI)\n"
printf "  ${CYAN}[0]${RESET} Omitir — configurar manualmente más tarde\n"
echo ""
printf "  ${CYAN}→${RESET} Opción [0-6]: "
read -r provider_choice

configure_env_value() {
    local key="$1"
    local value="$2"
    local file="$3"
    # Reemplaza la línea si existe (comentada o no), o agrega al final
    if grep -q "^#*\s*${key}=" "$file" 2>/dev/null; then
        sed -i "s|^#*\s*${key}=.*|${key}=\"${value}\"|" "$file"
    else
        echo "${key}=\"${value}\"" >> "$file"
    fi
}

LLM_CONFIGURED=false

case "$provider_choice" in
    1)
        LLM_PROVIDER_NAME="OpenAI"
        LLM_PROVIDER_VAL="openai"
        LLM_ENDPOINT_DEFAULT="https://api.openai.com/v1"
        LLM_MODEL_HINT="gpt-4o, gpt-4o-mini, gpt-4-turbo"
        ;;
    2)
        LLM_PROVIDER_NAME="Groq"
        LLM_PROVIDER_VAL="openai"
        LLM_ENDPOINT_DEFAULT="https://api.groq.com/openai/v1"
        LLM_MODEL_HINT="llama3-8b-8192, mixtral-8x7b-32768, gemma2-9b-it"
        ;;
    3)
        LLM_PROVIDER_NAME="Google Gemini"
        LLM_PROVIDER_VAL="google"
        LLM_ENDPOINT_DEFAULT=""
        LLM_MODEL_HINT="gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash"
        ;;
    4)
        LLM_PROVIDER_NAME="Anthropic"
        LLM_PROVIDER_VAL="openai"
        LLM_ENDPOINT_DEFAULT="https://api.anthropic.com/v1"
        LLM_MODEL_HINT="claude-opus-4-5, claude-sonnet-4-5, claude-haiku-3-5"
        ;;
    5)
        LLM_PROVIDER_NAME="Ollama"
        LLM_PROVIDER_VAL="openai"
        LLM_ENDPOINT_DEFAULT="http://localhost:11434/v1"
        LLM_MODEL_HINT="llama3, mistral, codellama, phi3"
        ;;
    6)
        LLM_PROVIDER_NAME="Personalizado"
        LLM_PROVIDER_VAL="openai"
        LLM_ENDPOINT_DEFAULT=""
        LLM_MODEL_HINT="nombre-de-tu-modelo"
        ;;
    *)
        log_warn "Configuración LLM omitida. Edita manualmente: ${ENV_FILE}"
        LLM_CONFIGURED=skip
        ;;
esac

if [ "$LLM_CONFIGURED" != "skip" ]; then
    echo ""
    log_info "Proveedor seleccionado: ${LLM_PROVIDER_NAME}"
    echo ""

    # Modelo
    printf "  ${BOLD}Modelo${RESET} ${DIM}(ej: %s)${RESET}\n" "$LLM_MODEL_HINT"
    printf "  ${CYAN}→${RESET} Nombre del modelo: "
    read -r llm_model_input
    if [ -z "$llm_model_input" ]; then
        llm_model_input="${LLM_MODEL_HINT%%,*}"  # primer ejemplo como fallback
        log_warn "Sin entrada — usando: ${llm_model_input}"
    fi

    # API Key
    echo ""
    printf "  ${BOLD}API Key${RESET}\n"
    printf "  ${DIM}(se ocultará al escribir)${RESET}\n"
    printf "  ${CYAN}→${RESET} Tu API key: "
    read -rs llm_api_key_input
    echo ""
    if [ -z "$llm_api_key_input" ]; then
        log_warn "API key vacía — recuerda configurarla en ${ENV_FILE}"
        llm_api_key_input="REEMPLAZA_CON_TU_API_KEY"
    else
        log_detail "API key recibida (${#llm_api_key_input} caracteres)"
    fi

    # Endpoint (solo para compatible OpenAI)
    if [ "$LLM_PROVIDER_VAL" = "openai" ] && [ -n "$LLM_ENDPOINT_DEFAULT" ]; then
        echo ""
        printf "  ${BOLD}Endpoint API${RESET} ${DIM}(Enter para usar: %s)${RESET}\n" "$LLM_ENDPOINT_DEFAULT"
        printf "  ${CYAN}→${RESET} URL del endpoint: "
        read -r llm_endpoint_input
        llm_endpoint_input="${llm_endpoint_input:-$LLM_ENDPOINT_DEFAULT}"
    fi

    # Escribir en .env
    log_info "Escribiendo configuración en ${ENV_FILE}..."

    configure_env_value "LLM_PROVIDER" "$LLM_PROVIDER_VAL"       "$ENV_FILE"
    configure_env_value "LLM_MODEL"    "$llm_model_input"         "$ENV_FILE"
    configure_env_value "LLM_API_KEY"  "$llm_api_key_input"       "$ENV_FILE"

    if [ "$LLM_PROVIDER_VAL" = "openai" ] && [ -n "$llm_endpoint_input" ]; then
        configure_env_value "LLM_API_ENDPOINT" "$llm_endpoint_input" "$ENV_FILE"
    fi

    if [ "$LLM_PROVIDER_VAL" = "google" ]; then
        configure_env_value "GOOGLE_API_KEY" "$llm_api_key_input" "$ENV_FILE"
        configure_env_value "GEMINI_MODEL"   "$llm_model_input"   "$ENV_FILE"
    fi

    log_success "Configuración LLM guardada"
    log_detail  "Proveedor:  ${LLM_PROVIDER_VAL}"
    log_detail  "Modelo:     ${llm_model_input}"
    [ -n "$llm_endpoint_input" ] && log_detail "Endpoint:   ${llm_endpoint_input}"
fi

# ─── PASO 7: Configuración final y symlink ────────────────────────────────────
step_header "Creación de enlace simbólico global"

# Symlink global
echo ""
printf "  ${CYAN}?${RESET}  ¿Deseas crear un enlace simbólico global para 'kogniterm'? (y/N): "
read -r symlink_confirm
if [[ $symlink_confirm =~ ^[Yy]$ ]]; then
    SYMLINK_PATH="/usr/local/bin/kogniterm"
    if [ -w "$(dirname "$SYMLINK_PATH")" ]; then
        ln -sf "${VENV_DIR}/bin/kogniterm" "$SYMLINK_PATH"
        log_success "Symlink creado: ${SYMLINK_PATH} → ${VENV_DIR}/bin/kogniterm"
    else
        log_warn "Sin permisos de escritura en $(dirname "$SYMLINK_PATH"). Ejecuta manualmente:"
        printf "  ${DIM}│  sudo ln -sf %s/bin/kogniterm %s${RESET}\n" "$VENV_DIR" "$SYMLINK_PATH"
    fi
else
    log_info "Symlink omitido"
fi

# ─── RESUMEN FINAL ────────────────────────────────────────────────────────────
echo ""
print_double_line
printf "\n"
printf "  ${BOLD}${GREEN}✔  ¡KogniTerm instalado exitosamente!${RESET}\n"
printf "\n"
print_double_line

printf "\n  ${BOLD}${WHITE}📋  Resumen de instalación${RESET}\n\n"
printf "  ${DIM}%-22s${RESET}  %s\n"  "Directorio:"     "$INSTALL_DIR"
printf "  ${DIM}%-22s${RESET}  %s\n"  "Entorno virtual:" "$VENV_DIR"
printf "  ${DIM}%-22s${RESET}  %s\n"  "Python:"          "$PYTHON_CMD $PYTHON_VERSION"
printf "  ${DIM}%-22s${RESET}  %s\n"  "Configuración:"   "$ENV_FILE"
printf "  ${DIM}%-22s${RESET}  %s\n"  "Log de instalación:" "$LOG_FILE"
printf "  ${DIM}%-22s${RESET}  %s\n"  "Tiempo total:"    "$(elapsed_time)"

printf "\n"
print_line
printf "\n  ${BOLD}${WHITE}🚀  Cómo ejecutar KogniTerm${RESET}\n\n"
printf "  ${DIM}# Opción A — desde el directorio de instalación:${RESET}\n"
printf "  ${CYAN}source %s/bin/activate${RESET}\n" "$VENV_DIR"
printf "  ${CYAN}kogniterm${RESET}\n\n"

if [[ $symlink_confirm =~ ^[Yy]$ ]]; then
    printf "  ${DIM}# Opción B — comando global:${RESET}\n"
    printf "  ${CYAN}kogniterm${RESET}\n\n"
fi

printf "  ${DIM}# Editar configuración (API keys):${RESET}\n"
printf "  ${CYAN}nano %s${RESET}\n" "$ENV_FILE"

printf "\n"
print_double_line
printf "\n  ${DIM}¿Problemas? Revisa el log detallado:${RESET}\n"
printf "  ${DIM}cat %s${RESET}\n\n" "$LOG_FILE"
