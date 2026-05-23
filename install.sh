#!/bin/bash
# install.sh - Instalador de KogniTerm desde GitHub
# Uso: curl -fsSL https://raw.githubusercontent.com/gatovillano/KogniTerm/main/install.sh | bash

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuración
REPO_URL="https://github.com/gatovillano/KogniTerm.git"
INSTALL_DIR="${HOME}/.kogniterm"
VENV_DIR="${INSTALL_DIR}/venv"
PYTHON_MIN_VERSION="3.9"

# Funciones de utilidad
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 no encontrado. Por favor, instálalo primero."
        exit 1
    fi
}

check_python_version() {
    local python_version=$1
    local required_version="$2"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
        log_error "Se requiere Python ${required_version} o superior. Versión detectada: $python_version"
        exit 1
    fi
}

# Banner
echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██   ██  ██████  ██   ██ ██    ██ ███    ██  ██████      ║
║   ██   ██ ██    ██ ██   ██ ██    ██ ████   ██ ██    ██     ║
║   ███████ ██    ██ ███████ ██    ██ ██ ██  ██ ██    ██     ║
║   ██   ██ ██    ██ ██   ██ ██    ██ ██  ██ ██ ██    ██     ║
║   ██   ██  ██████  ██   ██  ██████  ██   ████  ██████      ║
║                                                               ║
║          KogniTerm - Agente Evolutivo de Terminal            ║
║               Versión 0.5.0                                   ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Verificar dependencias
log_info "Verificando dependencias del sistema..."

check_command "git"
check_command "curl"

# Verificar Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    log_error "Python no encontrado. Por favor, instala Python ${PYTHON_MIN_VERSION} o superior."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
check_python_version "$PYTHON_VERSION" "$PYTHON_MIN_VERSION"

log_success "Python ${PYTHON_VERSION} detectado ✓"

# Preguntar directorio de instalación
read -p "Directorio de instalación [${INSTALL_DIR}]: " custom_install_dir
INSTALL_DIR="${custom_install_dir:-$INSTALL_DIR}"

# Clonar o actualizar repositorio
log_info "Preparando instalación en ${INSTALL_DIR}..."

if [ -d "${INSTALL_DIR}/.git" ]; then
    log_warn "KogniTerm ya está instalado en ${INSTALL_DIR}"
    read -p "¿Deseas actualizar a la última versión? (y/N): " update_confirm
    if [[ $update_confirm =~ ^[Yy]$ ]]; then
        log_info "Actualizando repositorio..."
        cd "${INSTALL_DIR}" && git pull origin main
    else
        log_info "Usando versión existente."
    fi
else
    log_info "Clonando repositorio..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Crear entorno virtual
log_info "Configurando entorno virtual..."
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_CMD -m venv "$VENV_DIR"
    log_success "Entorno virtual creado ✓"
else
    log_warn "Entorno virtual ya existe."
fi

# Activar entorno virtual e instalar
log_info "Instalando KogniTerm y dependencias..."
source "$VENV_DIR/bin/activate"

# Actualizar pip
pip install --upgrade pip -q

# Instalar en modo editable
pip install -e . -q

log_success "KogniTerm instalado correctamente ✓"

# Configurar variables de entorno
log_info "Configurando variables de entorno..."
ENV_FILE="${INSTALL_DIR}/.env"

if [ ! -f "$ENV_FILE" ]; then
    log_warn "Archivo .env no encontrado. Copiando desde .env.example..."
    cp "${INSTALL_DIR}/.env.example" "$ENV_FILE"
    log_info "Por favor, edita ${ENV_FILE} con tus API keys."
fi

# Crear symlink global (opcional)
read -p "¿Deseas crear un enlace simbólico global para 'kogniterm'? (y/N): " symlink_confirm
if [[ $symlink_confirm =~ ^[Yy]$ ]]; then
    SYMLINK_PATH="/usr/local/bin/kogniterm"
    if [ -w "$(dirname "$SYMLINK_PATH")" ]; then
        ln -sf "${VENV_DIR}/bin/kogniterm" "$SYMLINK_PATH"
        log_success "Symlink creado en ${SYMLINK_PATH} ✓"
    else
        log_warn "No se pudo crear symlink. Ejecuta manualmente:"
        echo "  sudo ln -sf ${VENV_DIR}/bin/kogniterm /usr/local/bin/kogniterm"
    fi
fi

# Mensaje final
echo ""
log_success "═══════════════════════════════════════════════════════════════"
log_success "  KogniTerm instalado correctamente!"
log_success "═══════════════════════════════════════════════════════════════"
echo ""
log_info "Para ejecutar KogniTerm:"
echo "  1. cd ${INSTALL_DIR}"
echo "  2. source venv/bin/activate"
echo "  3. kogniterm"
echo ""
log_info "O si creaste el symlink global:"
echo "  kogniterm"
echo ""
log_info "Configura tus API keys en: ${ENV_FILE}"
echo ""
log_info "¡Disfruta de tu agente evolutivo de terminal! 🚀"
echo ""
