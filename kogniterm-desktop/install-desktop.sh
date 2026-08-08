#!/usr/bin/env bash
set -e

# Colores y Formato
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "=========================================================="
echo "    KogniTerm Desktop - Installer & OS Launcher Setup    "
echo "=========================================================="
echo -e "${RESET}"

OS_TYPE="$(uname -s)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_APP_DIR="$SCRIPT_DIR/apps/desktop"

if [ "$OS_TYPE" = "Linux" ]; then
    echo -e "${BLUE}▶ Detectado sistema Linux. Configurando lanzador XDG...${RESET}"

    BIN_DIR="$HOME/.local/bin"
    ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
    APPS_DIR="$HOME/.local/share/applications"

    mkdir -p "$BIN_DIR" "$ICON_DIR" "$APPS_DIR"

    # 1. Instalar icono en alta resolución (512x512)
    ICON_SOURCE="$DESKTOP_APP_DIR/src-tauri/icons/icon.png"
    ICON_TARGET="$ICON_DIR/kogniterm-desktop.png"
    if [ -f "$ICON_SOURCE" ]; then
        cp "$ICON_SOURCE" "$ICON_TARGET"
        echo -e "  ${GREEN}✔ Icono instalado en:${RESET} $ICON_TARGET"
    else
        echo -e "  ${YELLOW}⚠ No se encontró el icono en $ICON_SOURCE${RESET}"
    fi

    # 2. Configurar ejecutable / script wrapper
    TARGET_BIN="$BIN_DIR/kogniterm-desktop"
    RELEASE_BIN="$DESKTOP_APP_DIR/src-tauri/target/release/kogniterm-desktop"
    RELEASE_BIN_ALT="$DESKTOP_APP_DIR/src-tauri/target/release/desktop"

    if [ -f "$RELEASE_BIN" ]; then
        cp "$RELEASE_BIN" "$TARGET_BIN"
        chmod +x "$TARGET_BIN"
        echo -e "  ${GREEN}✔ Ejecutable compilado (release) instalado en:${RESET} $TARGET_BIN"
    elif [ -f "$RELEASE_BIN_ALT" ]; then
        cp "$RELEASE_BIN_ALT" "$TARGET_BIN"
        chmod +x "$TARGET_BIN"
        echo -e "  ${GREEN}✔ Ejecutable compilado instalado en:${RESET} $TARGET_BIN"
    else
        echo -e "  ${YELLOW}ℹ Generando ejecutable wrapper para KogniTerm Desktop...${RESET}"
        cat << 'EOF' > "$TARGET_BIN"
#!/usr/bin/env bash
# Cargar variables de entorno necesarias para lanzadores GUI de escritorio
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

if [ -d "$HOME/.nvm/versions/node" ]; then
    LATEST_NODE="$(ls -d $HOME/.nvm/versions/node/v* 2>/dev/null | tail -n 1)/bin"
    if [ -d "$LATEST_NODE" ]; then
        export PATH="$LATEST_NODE:$PATH"
    fi
fi

if [ -f "$HOME/.profile" ]; then
    source "$HOME/.profile" 2>/dev/null || true
fi

DESKTOP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../apps/desktop" 2>/dev/null && pwd)"
if [ ! -d "$DESKTOP_DIR" ]; then
    DESKTOP_DIR="$HOME/Proyectos/Gemini-Interpreter/kogniterm-desktop/apps/desktop"
fi

cd "$DESKTOP_DIR" && npm run tauri dev
EOF
        chmod +x "$TARGET_BIN"
        echo -e "  ${GREEN}✔ Wrapper ejecutable creado en:${RESET} $TARGET_BIN"
    fi

    # 3. Crear archivo .desktop en ~/.local/share/applications/
    DESKTOP_FILE="$APPS_DIR/kogniterm-desktop.desktop"
    cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=KogniTerm Desktop
GenericName=AI-Powered Terminal
Comment=Terminal asistida por Inteligencia Artificial para desarrolladores
Exec=$TARGET_BIN
Icon=kogniterm-desktop
Terminal=false
Categories=Development;Utility;TerminalEmulator;
StartupWMClass=kogniterm-desktop
Keywords=terminal;ai;kogniterm;shell;gemini;
EOF

    chmod +x "$DESKTOP_FILE"
    echo -e "  ${GREEN}✔ Lanzador .desktop instalado en:${RESET} $DESKTOP_FILE"

    # 4. Actualizar cachés de iconos y menú de escritorio
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$APPS_DIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    fi

    echo -e "\n${GREEN}${BOLD}🎉 ¡KogniTerm Desktop está disponible en tu lanzador de aplicaciones de Linux!${RESET}"

elif [ "$OS_TYPE" = "Darwin" ]; then
    echo -e "${BLUE}▶ Detectado sistema macOS...${RESET}"
    APP_BUNDLE="$DESKTOP_APP_DIR/src-tauri/target/release/bundle/macos/KogniTerm Desktop.app"
    if [ -d "$APP_BUNDLE" ]; then
        cp -R "$APP_BUNDLE" "/Applications/"
        echo -e "  ${GREEN}✔ KogniTerm Desktop.app instalado exitosamente en /Applications/${RESET}"
    else
        echo -e "  ${YELLOW}⚠ Para compilar el paquete .app de macOS ejecuta:${RESET}"
        echo -e "  cd \"$DESKTOP_APP_DIR\" && npm run tauri build"
    fi
else
    echo -e "Sistema operativo no soportado: $OS_TYPE"
    exit 1
fi
