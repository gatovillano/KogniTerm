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
SERVER_WRAPPER_PATH="$LOCAL_BIN/kogniterm-server"
WEB_WRAPPER_PATH="$LOCAL_BIN/kogniterm-web"
DESKTOP_WRAPPER_PATH="$LOCAL_BIN/kogniterm-desktop"
GITHUB_REPO_URL="https://github.com/gatovillano/KogniTerm.git"

# Servicio de KogniTerm Server (compartido por TUI, Web y Desktop)
SERVICE_NAME="kogniterm-server"
SERVER_HOST="127.0.0.1"
SERVER_PORT="8765"
SYSTEMD_UNIT_DIR="$HOME/.config/systemd/user"
SYSTEMD_UNIT_PATH="$SYSTEMD_UNIT_DIR/$SERVICE_NAME.service"
LAUNCHD_PLIST_DIR="$HOME/Library/LaunchAgents"
LAUNCHD_PLIST_PATH="$LAUNCHD_PLIST_DIR/com.kogniterm.server.plist"

# Limpiar pantalla y asegurar interactividad desde pipes (ej. curl | bash)
clear

if [ ! -t 0 ]; then
    # stdin no es una tty (es una tubería)
    if [ -t 1 ] && [ -c /dev/tty ] && [ -r /dev/tty ]; then
        exec < /dev/tty
    else
        echo -e "${RED}❌ Error: No se puede iniciar la instalación interactiva a través de una tubería en este entorno.${RESET}"
        echo -e "Por favor, descarga y ejecuta el script directamente:"
        echo -e "  ${BOLD}curl -fsSL -O https://raw.githubusercontent.com/gatovillano/KogniTerm/main/install.sh && bash install.sh${RESET}"
        # Consumir el resto de stdin para evitar curl: (23) Failure writing output
        cat > /dev/null
        exit 1
    fi
fi

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
    git pull --no-rebase origin main
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

    create_launchers

    echo -e "\n${BOLD}${GREEN}========================================================================${RESET}"
    echo -e "${BOLD}${GREEN}    🎉 ¡KogniTerm ha sido actualizado a la última versión con éxito!${RESET}"
    echo -e "${BOLD}${GREEN}========================================================================${RESET}\n"
}

# Creación de lanzadores y accesos directos globales
create_launchers() {
    echo -e "\n${BOLD}${BLUE}Creando lanzadores y accesos directos globales...${RESET}"
    mkdir -p "$LOCAL_BIN"

    # Lanzador para kogniterm
    cat << EOF > "$WRAPPER_PATH"
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
exec kogniterm "\$@"
EOF
    chmod +x "$WRAPPER_PATH"
    echo -e "  ${GREEN}✔${RESET} Lanzador global de KogniTerm creado en: ${BOLD}${WRAPPER_PATH}${RESET}"

    # Lanzador para kogniterm-server
    cat << EOF > "$SERVER_WRAPPER_PATH"
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
exec kogniterm-server "\$@"
EOF
    chmod +x "$SERVER_WRAPPER_PATH"
    echo -e "  ${GREEN}✔${RESET} Lanzador global de KogniTerm Server creado en: ${BOLD}${SERVER_WRAPPER_PATH}${RESET}"

    # Lanzador para kogniterm-web
    cat << EOF > "$WEB_WRAPPER_PATH"
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
exec kogniterm web "\$@"
EOF
    chmod +x "$WEB_WRAPPER_PATH"
    echo -e "  ${GREEN}✔${RESET} Lanzador global de KogniTerm Web creado en: ${BOLD}${WEB_WRAPPER_PATH}${RESET}"

    # Lanzador para kogniterm-desktop (Electron v2)
    local desktop_dir=""
    if [ -f "$REPO_DIR/kogniterm-desktop/packages/desktop/out/main/index.js" ]; then
        desktop_dir="$REPO_DIR/kogniterm-desktop"
    elif [ -f "$PWD/kogniterm-desktop/packages/desktop/out/main/index.js" ]; then
        desktop_dir="$PWD/kogniterm-desktop"
    fi

    if [ -n "$desktop_dir" ]; then
        cat << EOF > "$DESKTOP_WRAPPER_PATH"
#!/usr/bin/env bash
DESKTOP_PATH="$desktop_dir"
if [ -f "\$DESKTOP_PATH/node_modules/.bin/electron" ]; then
    ELECTRON_BIN="\$DESKTOP_PATH/node_modules/.bin/electron"
elif command -v electron &>/dev/null; then
    ELECTRON_BIN="electron"
else
    ELECTRON_BIN="npx electron"
fi
exec "\$ELECTRON_BIN" "\$DESKTOP_PATH/packages/desktop/out/main/index.js" "\$@"
EOF
        chmod +x "$DESKTOP_WRAPPER_PATH"
        echo -e "  ${GREEN}✔${RESET} Lanzador global de KogniTerm Desktop creado en: ${BOLD}${DESKTOP_WRAPPER_PATH}${RESET}"
    fi

    # Asegurar permisos ejecutables para scripts auxiliares
    if [ -f "$REPO_DIR/start-web.sh" ]; then
        chmod +x "$REPO_DIR/start-web.sh"
    fi
    if [ -f "start-web.sh" ]; then
        chmod +x "start-web.sh"
    fi

    # Verificar si ~/.local/bin está en el PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo -e "  ${YELLOW}⚠️ Advertencia: ${BOLD}~/.local/bin${RESET} no está en tu variable \$PATH.${RESET}"
        echo -e "  Para ejecutar 'kogniterm' directamente, añade esto a tu ~/.bashrc o ~/.zshrc:"
        echo -e "  ${CYAN}  export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    fi
}

# ──────────────────────────────────────────────────────────────────────────────
# KogniTerm Server como servicio de inicio automático
#
# El backend es multi-cliente: lo comparten la TUI, la Web y Desktop. Si se
# registra como servicio (systemd/launchd) arranca solo y queda disponible para
# todos ellos. KogniTerm Desktop, aun así, lo levanta en segundo plano si lo
# encuentra apagado.
# ──────────────────────────────────────────────────────────────────────────────

# Detecta el gestor de servicios disponible (systemd de usuario / launchd)
detect_service_manager() {
    case "$(uname -s)" in
        Darwin)
            echo "launchd"
            ;;
        Linux)
            if command -v systemctl &>/dev/null && systemctl --user show-environment &>/dev/null 2>&1; then
                echo "systemd"
            else
                echo "none"
            fi
            ;;
        *)
            echo "none"
            ;;
    esac
}

# ¿Responde el backend en /health?
server_is_up() {
    curl -fsS -m 3 "http://$SERVER_HOST:$SERVER_PORT/health" &>/dev/null
}

# Libera el puerto 8765 si hay un servidor arrancado manualmente, para que el
# servicio pueda tomar el puerto sin conflictos.
free_server_port() {
    if server_is_up; then
        echo -e "  ${YELLOW}•${RESET} Deteniendo la instancia actual del servidor para evitar conflicto de puerto..."
        "$VENV_DIR/bin/kogniterm-server" stop --port "$SERVER_PORT" &>/dev/null
        sleep 1
    fi
}

service_install_systemd() {
    mkdir -p "$SYSTEMD_UNIT_DIR"
    cat << EOF > "$SYSTEMD_UNIT_PATH"
[Unit]
Description=KogniTerm Server (backend multi-cliente para TUI, Web y Desktop)
Documentation=https://github.com/gatovillano/KogniTerm
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/kogniterm-server --host $SERVER_HOST --port $SERVER_PORT
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=20
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
    echo -e "  ${GREEN}✔${RESET} Unidad creada en: ${BOLD}$SYSTEMD_UNIT_PATH${RESET}"

    systemctl --user daemon-reload &>/dev/null
    free_server_port
    if systemctl --user enable --now "$SERVICE_NAME" &>/dev/null; then
        echo -e "  ${GREEN}✔${RESET} Servicio habilitado y arrancado."
    else
        echo -e "  ${YELLOW}⚠ No se pudo arrancar el servicio.${RESET}"
        echo -e "  ${DIM}Revisa: journalctl --user -u $SERVICE_NAME${RESET}"
        echo -e "  ${DIM}Puedes arrancar el backend manualmente con: kogniterm-server${RESET}"
        return 1
    fi

    # Para que arranque también al iniciar el equipo, sin iniciar sesión
    if command -v loginctl &>/dev/null; then
        if loginctl show-user "$USER" --property=Linger 2>/dev/null | grep -q "Linger=yes"; then
            echo -e "  ${GREEN}✔${RESET} Arranque automático previo al login: ya activo (linger)."
        else
            read -p "  ¿Arrancar también al encender el equipo, antes de iniciar sesión? (Y/n): " linger_opt
            linger_opt="${linger_opt:-y}"
            if [[ "$linger_opt" =~ ^[Yy]$ ]]; then
                if loginctl enable-linger "$USER" 2>/dev/null || sudo -n loginctl enable-linger "$USER" 2>/dev/null; then
                    echo -e "  ${GREEN}✔${RESET} Arranque automático previo al login habilitado (linger)."
                else
                    echo -e "  ${YELLOW}⚠ No se pudo habilitar 'linger'. Ejecuta: sudo loginctl enable-linger $USER${RESET}"
                fi
            fi
        fi
    fi
}

service_install_launchd() {
    mkdir -p "$LAUNCHD_PLIST_DIR" "$KOGNITERM_DIR/logs"
    cat << EOF > "$LAUNCHD_PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kogniterm.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/kogniterm-server</string>
        <string>--host</string>
        <string>$SERVER_HOST</string>
        <string>--port</string>
        <string>$SERVER_PORT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$KOGNITERM_DIR/logs/server-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$KOGNITERM_DIR/logs/server-launchd.err</string>
</dict>
</plist>
EOF
    echo -e "  ${GREEN}✔${RESET} LaunchAgent creado en: ${BOLD}$LAUNCHD_PLIST_PATH${RESET}"

    free_server_port
    launchctl unload "$LAUNCHD_PLIST_PATH" &>/dev/null
    if launchctl load -w "$LAUNCHD_PLIST_PATH" &>/dev/null; then
        echo -e "  ${GREEN}✔${RESET} Servicio cargado y arrancado."
    else
        echo -e "  ${YELLOW}⚠ No se pudo cargar el LaunchAgent.${RESET}"
        echo -e "  ${DIM}Revisa: launchctl list | grep kogniterm${RESET}"
        echo -e "  ${DIM}Puedes arrancar el backend manualmente con: kogniterm-server${RESET}"
        return 1
    fi
}

service_install() {
    local mgr
    mgr="$(detect_service_manager)"
    case "$mgr" in
        systemd) service_install_systemd ;;
        launchd) service_install_launchd ;;
        *)
            echo -e "  ${YELLOW}⚠ No se detectó systemd ni launchd en este sistema.${RESET}"
            echo -e "  Arranca el servidor manualmente cuando lo necesites: ${CYAN}kogniterm-server${RESET}"
            return 1
            ;;
    esac
}

service_uninstall() {
    local mgr
    mgr="$(detect_service_manager)"
    case "$mgr" in
        systemd)
            systemctl --user disable --now "$SERVICE_NAME" &>/dev/null
            rm -f "$SYSTEMD_UNIT_PATH"
            systemctl --user daemon-reload &>/dev/null
            systemctl --user reset-failed "$SERVICE_NAME" &>/dev/null
            echo -e "  ${GREEN}✔${RESET} Servicio eliminado."
            ;;
        launchd)
            launchctl unload -w "$LAUNCHD_PLIST_PATH" &>/dev/null
            rm -f "$LAUNCHD_PLIST_PATH"
            echo -e "  ${GREEN}✔${RESET} LaunchAgent eliminado."
            ;;
        *)
            echo -e "  ${YELLOW}⚠ No hay servicio registrado en este sistema.${RESET}"
            ;;
    esac
}

service_status() {
    local mgr
    mgr="$(detect_service_manager)"
    case "$mgr" in
        systemd)
            if systemctl --user is-enabled "$SERVICE_NAME" &>/dev/null; then
                echo -e "  Servicio: ${GREEN}habilitado${RESET} (arranque automático)"
            else
                echo -e "  Servicio: ${YELLOW}no registrado${RESET}"
            fi
            systemctl --user is-active --quiet "$SERVICE_NAME" \
                && echo -e "  Estado:    ${GREEN}activo${RESET}" \
                || echo -e "  Estado:    ${YELLOW}detenido${RESET}"
            ;;
        launchd)
            if [ -f "$LAUNCHD_PLIST_PATH" ]; then
                echo -e "  Servicio: ${GREEN}registrado${RESET} (arranque automático)"
            else
                echo -e "  Servicio: ${YELLOW}no registrado${RESET}"
            fi
            launchctl list | grep -q "com.kogniterm.server" \
                && echo -e "  Estado:    ${GREEN}activo${RESET}" \
                || echo -e "  Estado:    ${YELLOW}detenido${RESET}"
            ;;
        *)
            echo -e "  Servicio: ${YELLOW}no disponible en este sistema${RESET}"
            ;;
    esac

    if server_is_up; then
        echo -e "  Backend:   ${GREEN}respondiendo${RESET} en http://$SERVER_HOST:$SERVER_PORT"
    else
        echo -e "  Backend:   ${YELLOW}sin respuesta${RESET} en http://$SERVER_HOST:$SERVER_PORT"
    fi
    echo -e "  Logs:      ${DIM}$REPO_DIR/.kogniterm/logs/server.log${RESET}"
}

# Asistente interactivo de inicio automático
configure_autostart() {
    echo -e "\n${BOLD}${BLUE}--- Inicio automático de KogniTerm Server ---${RESET}"
    local mgr
    mgr="$(detect_service_manager)"

    case "$mgr" in
        systemd) echo "  Se detectó systemd (servicio a nivel de usuario)." ;;
        launchd) echo "  Se detectó launchd (macOS)." ;;
        *)
            echo -e "  ${YELLOW}⚠ No se detectó un gestor de servicios en este sistema.${RESET}"
            echo -e "  Puedes arrancar el backend manualmente con: ${CYAN}kogniterm-server${RESET}"
            echo -e "  ${DIM}KogniTerm Desktop lo levantará igual en segundo plano cuando lo abras.${RESET}"
            return 0
            ;;
    esac

    echo "  El backend lo comparten la TUI, la Web y KogniTerm Desktop."
    echo "  Como servicio, arrancará solo y quedará disponible para todos los clientes."
    read -p "  ¿Deseas registrarlo para que inicie automáticamente? (Y/n): " auto_opt
    auto_opt="${auto_opt:-y}"

    if [[ "$auto_opt" =~ ^[Yy]$ ]]; then
        if service_install; then
            echo -e "  ${GREEN}✔${RESET} KogniTerm Server queda como servicio del sistema."
            echo -e "  ${DIM}Para desinstalarlo más tarde: bash install.sh → opción 5.${RESET}"
        fi
    else
        echo -e "  ${DIM}Omitido.${RESET} KogniTerm Desktop lo arrancará en segundo plano si lo necesita."
    fi
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
            REPO_DIR="$PWD"
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

    if [ -d "$install_source/kogniterm-desktop" ]; then
        echo -e "\n${BOLD}${BLUE}[3.5/4] Preparando KogniTerm Desktop v2 (Electron)...${RESET}"
        if command -v npm &>/dev/null; then
            (cd "$install_source/kogniterm-desktop" && npm install && node node_modules/electron/install.js) &>/dev/null || true
            echo -e "  ${GREEN}✔${RESET} Dependencias de KogniTerm Desktop e instalador de Electron listos."
        else
            echo -e "  ${YELLOW}⚠️ npm no detectado. Instala Node.js/npm para usar KogniTerm Desktop.${RESET}"
        fi
    fi

    echo -e "\n${BOLD}${BLUE}[4/4] Creando lanzadores globales...${RESET}"
    create_launchers

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

    configure_autostart

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
    echo -e "  ${BOLD}5)${RESET} Gestionar inicio automático de KogniTerm Server (servicio)"
    echo -e "  ${BOLD}6)${RESET} Salir"
    echo ""
    read -p "Selecciona una opción (1-6): " menu_opt

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
            echo -e "\n${BOLD}${BLUE}--- Gestión del servicio KogniTerm Server ---${RESET}"
            service_status
            echo ""
            read -p "¿Registrar/actualizar el servicio de inicio automático? (y/N): " svc_opt
            if [[ "$svc_opt" =~ ^[Yy]$ ]]; then
                configure_autostart
            else
                read -p "¿Eliminar el servicio si estuviera registrado? (y/N): " rm_opt
                if [[ "$rm_opt" =~ ^[Yy]$ ]]; then
                    service_uninstall
                else
                    echo -e "  ${DIM}Sin cambios.${RESET}"
                fi
            fi
            ;;
        6)
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
