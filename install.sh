#!/usr/bin/env bash

# ==============================================================================
#                 KogniTerm - Script de Instalación y Actualización
# ==============================================================================

# Colores y formatos
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Directorios de destino
KOGNITERM_DIR="$HOME/.kogniterm"
REPO_DIR="$KOGNITERM_DIR/repo"
VENV_DIR="$KOGNITERM_DIR/venv"
LOCAL_BIN="$HOME/.local/bin"
WRAPPER_PATH="$LOCAL_BIN/kogniterm"
GITHUB_REPO_URL="https://github.com/gatovillano/KogniTerm.git"

# Limpiar pantalla y asegurar interactividad desde pipes (ej. curl | bash)
clear
exec < /dev/tty

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo -e "  ░█░█░█▀█░█▀▀░█▀█░▀█▀░▀█▀░█▀▀░█▀▄░█▄█"
    echo -e "  ░█▀▄░█░█░█░█░█░█░░█░░░█░░█▀▀░█▀▄░█░█"
    echo -e "  ░▀░▀░▀▀▀░▀▀▀░▀░▀░░▀░░░▀░░▀▀▀░▀░▀░▀░▀"
    echo -e "   -- Tu Terminal Asistida por IA --  "
    echo -e "${RESET}"
}

print_banner

# Verificar si git está instalado
check_git() {
    if ! command -v git &>/dev/null; then
        echo -e "${RED}❌ Error: 'git' no está instalado en este sistema.${RESET}"
        echo -e "Por favor, instala git y vuelve a correr este instalador."
        exit 1
    fi
}

# Verificar dependencias básicas de Python
check_python() {
    if ! command -v python3 &>/dev/null; then
        echo -e "${RED}❌ Error: Python 3 no está instalado en este sistema.${RESET}"
        exit 1
    fi
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
    echo -e "  ${GREEN}✔${RESET} Python detectado: ${BOLD}v${PYTHON_VERSION}${RESET}"
}

# Asistente de configuración de LLM
configure_llm() {
    echo -e "\n${BOLD}${BLUE}--- Configuración de Proveedor de LLM ---${RESET}"
    echo -e "Selecciona tu proveedor de LLM:"
    echo -e "  1) OpenRouter (Access to multiple models)"
    echo -e "  2) Google AI (Gemini nativo)"
    echo -e "  3) OpenAI (GPT-4, GPT-3.5)"
    echo -e "  4) Anthropic (Claude)"
    echo -e "  5) Ollama Local (servidor local)"
    echo -e "  6) Ollama Cloud (Ollama Models)"
    echo -e "  7) KiloCode Gateway (Routing inteligente)"
    read -p "Opción (1-7): " prov_opt

    case "$prov_opt" in
        1)
            PROV_KEY="openrouter"
            DEFAULT_MODEL="openrouter/google/gemini-2.0-flash-exp:free"
            MODEL_PROMPT="openrouter/google/gemini-2.0-flash-exp:free, openrouter/anthropic/claude-3.5-sonnet"
            ;;
        2)
            PROV_KEY="google"
            DEFAULT_MODEL="gemini/gemini-1.5-flash"
            MODEL_PROMPT="gemini/gemini-1.5-flash, gemini/gemini-1.5-pro"
            ;;
        3)
            PROV_KEY="openai"
            DEFAULT_MODEL="gpt-4o-mini"
            MODEL_PROMPT="gpt-4o, gpt-4o-mini, gpt-4-turbo"
            ;;
        4)
            PROV_KEY="anthropic"
            DEFAULT_MODEL="claude-3-5-sonnet-20240620"
            MODEL_PROMPT="claude-3-5-sonnet-20240620, claude-3-opus-20240229"
            ;;
        5)
            PROV_KEY="ollama"
            DEFAULT_MODEL="ollama/llama3"
            MODEL_PROMPT="ollama/llama3, ollama/mistral, ollama/codellama"
            ;;
        6)
            PROV_KEY="ollama_cloud"
            DEFAULT_MODEL="ollama/llama3"
            MODEL_PROMPT="ollama/llama3, ollama/mistral"
            ;;
        7)
            PROV_KEY="kilocode"
            DEFAULT_MODEL="kilocode/kilo/auto"
            MODEL_PROMPT="kilocode/kilo/auto, kilocode/stepfun/step-3.7-flash:free"
            ;;
        *)
            echo -e "${YELLOW}Opción no válida. Omitiendo configuración de LLM.${RESET}"
            PROV_KEY=""
            ;;
    esac

    if [ -n "$PROV_KEY" ]; then
        read -p "Nombre del modelo [default: $DEFAULT_MODEL] (ej: $MODEL_PROMPT): " model_input
        model_input="${model_input:-$DEFAULT_MODEL}"

        if [ "$PROV_KEY" = "ollama" ]; then
            read -p "Introduce la URL de tu servidor Ollama local [default: http://localhost:11434/v1]: " ollama_url
            ollama_url="${ollama_url:-http://localhost:11434/v1}"
            
            echo -e "\n  Guardando configuración de Ollama Local..."
            "$VENV_DIR/bin/kogniterm" config set ollama_api_base "$ollama_url" &>/dev/null
            "$VENV_DIR/bin/kogniterm" config set ollama_provider_target "local" &>/dev/null
        elif [ "$PROV_KEY" = "ollama_cloud" ]; then
            echo -e "\n  Configurando Ollama Cloud..."
            "$VENV_DIR/bin/kogniterm" config set ollama_provider_target "cloud" &>/dev/null
            read -rs -p "Ingresa tu API Key para Ollama Cloud (OLLAMA_CLOUD_API_KEY): " apikey_input
            echo ""
            "$VENV_DIR/bin/kogniterm" config set "api_key_ollama_cloud" "$apikey_input" &>/dev/null
        else
            read -rs -p "Ingresa tu API Key para $PROV_KEY: " apikey_input
            echo ""
            echo -e "\n  Guardando configuración de API Key..."
            "$VENV_DIR/bin/kogniterm" config set "api_key_$PROV_KEY" "$apikey_input" &>/dev/null
        fi

        # Guardar modelo por defecto
        "$VENV_DIR/bin/kogniterm" config set default_model "$model_input" &>/dev/null
        echo -e "  ${GREEN}✔${RESET} Configuración de LLM guardada en ~/.kogniterm/config.json"
    fi
}

# Asistente de configuración de Telegram
configure_telegram() {
    echo -e "\n${BOLD}${BLUE}--- Configuración de Bot de Telegram ---${RESET}"
    echo -e "Iniciando el asistente interactivo..."
    "$VENV_DIR/bin/kogniterm" config telegram setup
}

# Buscar y aplicar actualizaciones vía Git
update_kogniterm() {
    echo -e "\n${BOLD}${BLUE}🔄 Buscando actualizaciones en GitHub...${RESET}"
    check_git

    if [ ! -d "$REPO_DIR/.git" ]; then
        echo -e "${RED}❌ Error: No se encontró un repositorio git válido en ${REPO_DIR}.${RESET}"
        echo -e "Por favor, reinstala KogniTerm."
        return 1
    fi

    cd "$REPO_DIR" || exit 1

    # Comprobar cambios locales y guardarlos
    local stash_created=false
    if ! git diff-index --quiet HEAD --; then
        echo -e "  ${YELLOW}⚠️ Se detectaron cambios locales. Guardándolos temporalmente con git stash...${RESET}"
        git stash
        stash_created=true
    fi

    echo -e "  Sincronizando con repositorio remoto..."
    git pull origin main
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error al hacer git pull.${RESET}"
        [ "$stash_created" = true ] && git stash pop
        return 1
    fi

    if [ "$stash_created" = true ]; then
        echo -e "  Restaurando tus cambios locales..."
        git stash pop
    fi

    echo -e "  Actualizando entorno virtual..."
    "$VENV_DIR/bin/pip" install -e .
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error al reinstalar el paquete.${RESET}"
        return 1
    fi

    echo -e "\n${BOLD}${GREEN}========================================================================${RESET}"
    echo -e "${BOLD}${GREEN}    🎉 ¡KogniTerm ha sido actualizado a la última versión con éxito!${RESET}"
    echo -e "${BOLD}${GREEN}========================================================================${RESET}\n"
}

# Instalación limpia desde cero
install_from_scratch() {
    check_python
    check_git

    echo -e "\n${BOLD}${BLUE}[1/4] Preparando directorios...${RESET}"
    mkdir -p "$KOGNITERM_DIR"

    # Verificar si es desarrollo local
    local install_source=""
    if [ -f "pyproject.toml" ] && [ -d "kogniterm" ]; then
        echo -e "  Se detectó código fuente local en el directorio actual."
        echo -e "  1) Instalar usando la carpeta local actual: ${BOLD}$PWD${RESET}"
        echo -e "  2) Clonar el repositorio oficial desde GitHub"
        read -p "  Selecciona el origen (1 o 2) [default: 1]: " source_opt
        source_opt="${source_opt:-1}"
        if [ "$source_opt" = "1" ]; then
            install_source="$PWD"
        fi
    fi

    if [ -z "$install_source" ]; then
        echo -e "  Clonando repositorio de GitHub en ${REPO_DIR}..."
        rm -rf "$REPO_DIR"
        git clone "$GITHUB_REPO_URL" "$REPO_DIR"
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Error al clonar el repositorio.${RESET}"
            exit 1
        fi
        install_source="$REPO_DIR"
    fi

    echo -e "\n${BOLD}${BLUE}[2/4] Creando entorno virtual aislado (venv)...${RESET}"
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error al crear el entorno virtual.${RESET}"
        exit 1
    fi

    echo -e "  Actualizando pip..."
    "$VENV_DIR/bin/pip" install --upgrade pip &>/dev/null

    echo -e "\n${BOLD}${BLUE}[3/4] Instalando KogniTerm en modo editable...${RESET}"
    "$VENV_DIR/bin/pip" install -e "$install_source"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error al instalar dependencias.${RESET}"
        exit 1
    fi

    echo -e "\n${BOLD}${BLUE}[4/4] Creando lanzador global...${RESET}"
    mkdir -p "$LOCAL_BIN"
    cat << EOF > "$WRAPPER_PATH"
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
exec kogniterm "\$@"
EOF
    chmod +x "$WRAPPER_PATH"
    echo -e "  ${GREEN}✔${RESET} Lanzador global creado en: ${BOLD}${WRAPPER_PATH}${RESET}"

    # Verificar si ~/.local/bin está en el PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo -e "  ${YELLOW}⚠️ Advertencia: ${BOLD}~/.local/bin${RESET} no está en tu variable \$PATH.${RESET}"
        echo -e "  Para ejecutar 'kogniterm' directamente, añade esto a tu ~/.bashrc o ~/.zshrc:"
        echo -e "  ${CYAN}  export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    fi

    # Configuración de servicios
    read -p "¿Deseas configurar un proveedor de LLM ahora? (Y/n): " llm_conf
    llm_conf="${llm_conf:-y}"
    if [[ "$llm_conf" =~ ^[Yy]$ ]]; then
        configure_llm
    fi

    read -p "¿Deseas configurar el Bot de Telegram ahora? (y/N): " tg_conf
    tg_conf="${tg_conf:-n}"
    if [[ "$tg_conf" =~ ^[Yy]$ ]]; then
        configure_telegram
    fi

    echo -e "\n${BOLD}${GREEN}========================================================================${RESET}"
    echo -e "${BOLD}${GREEN}       🎉 ¡KogniTerm ha sido instalado y configurado con éxito!${RESET}"
    echo -e "${BOLD}${GREEN}========================================================================${RESET}"
    echo -e "  Ejecuta ${BOLD}kogniterm${RESET} para empezar.\n"
}

# ──────────────────────────────────────────────────────────────────────────────
# Menú Principal
# ──────────────────────────────────────────────────────────────────────────────
if [ -d "$VENV_DIR" ] && { [ -d "$REPO_DIR/.git" ] || [ -f "$REPO_DIR/pyproject.toml" ]; }; then
    echo -e "${WHITE}${BOLD}KogniTerm ya se encuentra instalado en este sistema.${RESET}"
    echo -e "¿Qué acción deseas realizar?\n"
    echo -e "  ${BOLD}1)${RESET} Buscar y aplicar actualizaciones (Git Pull + pip install)"
    echo -e "  ${BOLD}2)${RESET} Configurar/Cambiar proveedor LLM y API Keys"
    echo -e "  ${BOLD}3)${RESET} Configurar/Activar Bot de Telegram"
    echo -e "  ${BOLD}4)${RESET} Reinstalar KogniTerm por completo (Instalación limpia)"
    echo -e "  ${BOLD}5)${RESET} Salir"
    echo ""
    read -p "Selecciona una opción (1-5): " menu_opt

    case "$menu_opt" in
        1)
            update_kogniterm
            ;;
        2)
            configure_llm
            ;;
        3)
            configure_telegram
            ;;
        4)
            echo -e "${YELLOW}⚠️ Advertencia: Esto eliminará el entorno virtual y el repositorio actual.${RESET}"
            read -p "¿Estás seguro que deseas reinstalar desde cero? (y/N): " confirm_reinstall
            if [[ "$confirm_reinstall" =~ ^[Yy]$ ]]; then
                install_from_scratch
            else
                echo -e "Reinstalación cancelada."
            fi
            ;;
        5)
            echo -e "¡Hasta luego!"
            exit 0
            ;;
        *)
            echo -e "${RED}Opción inválida.${RESET}"
            exit 1
            ;;
    esac
else
    # Primera instalación
    install_from_scratch
fi
