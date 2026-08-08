# Plan de Implementación: Icono e Integración en Lanzadores para KogniTerm Desktop

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el icono oficial de KogniTerm Desktop ("Terminal Inteligente") en múltiples formatos y configurar la instalación nativa en el lanzador de aplicaciones de Linux y macOS.

**Architecture:** Generación de un master icon HD con la herramienta `generate_image`, conversión a la matriz de iconos de Tauri (`.png`, `.ico`, `.icns`), actualización de `tauri.conf.json`, y creación del script de instalación `install-desktop.sh` junto con la entrada `kogniterm-desktop.desktop`.

**Tech Stack:** Tauri 2, XDG Desktop Specification, Bash, PIL/Pillow or `@tauri-apps/cli`.

## Global Constraints
- Nombres de producto: `KogniTerm Desktop`
- Identificador de la aplicación: `com.kogniterm.desktop`
- Ubicación de iconos en Tauri: `kogniterm-desktop/apps/desktop/src-tauri/icons/`
- Entrada de escritorio Linux: `kogniterm-desktop.desktop`

---

### Task 1: Generar el Icono Master y Generar la Matriz de Iconos Tauri

**Files:**
- Create: `kogniterm-desktop/apps/desktop/src-tauri/icons/master_icon.png`
- Modify: `kogniterm-desktop/apps/desktop/src-tauri/icons/32x32.png`
- Modify: `kogniterm-desktop/apps/desktop/src-tauri/icons/128x128.png`
- Modify: `kogniterm-desktop/apps/desktop/src-tauri/icons/128x128@2x.png`
- Modify: `kogniterm-desktop/apps/desktop/src-tauri/icons/icon.png`
- Modify: `kogniterm-desktop/apps/desktop/src-tauri/icons/icon.ico`
- Modify: `kogniterm-desktop/apps/desktop/src-tauri/icons/icon.icns`

**Interfaces:**
- Produces: Matriz completa de iconos para Tauri en `kogniterm-desktop/apps/desktop/src-tauri/icons/`.

- [ ] **Step 1: Generar la imagen master PNG usando `generate_image`**
  - Indicación: Icono de app en estilo squircle, terminal cibernético oscuro con prompt `>_` en neón cian entrelazado con red neuronal brillante.

- [ ] **Step 2: Ejecutar el comando de generación de iconos de Tauri**
  - Comando: `npx @tauri-apps/cli icon kogniterm-desktop/apps/desktop/src-tauri/icons/master_icon.png --out kogniterm-desktop/apps/desktop/src-tauri/icons` (o script equivalente con pillow/icns/ico si offline).

- [ ] **Step 3: Verificar que todos los archivos de iconos existan**
  - Verificar existencia de `icon.png`, `128x128.png`, `32x32.png`, `icon.ico`, `icon.icns`.

---

### Task 2: Configurar el Manifiesto de Tauri (`tauri.conf.json`)

**Files:**
- Modify: `kogniterm-desktop/apps/desktop/src-tauri/tauri.conf.json`

**Interfaces:**
- Consumes: Iconos generados en Task 1.
- Produces: Configuración de producto y bundling para KogniTerm Desktop.

- [ ] **Step 1: Editar `tauri.conf.json` para actualizar nombre, identificador y metadatos de bundle**

  Actualizar `productName` a `"KogniTerm Desktop"`, `identifier` a `"com.kogniterm.desktop"`, y ajustar la sección `bundle`:
  ```json
  {
    "$schema": "https://schema.tauri.app/config/2",
    "productName": "KogniTerm Desktop",
    "version": "0.1.0",
    "identifier": "com.kogniterm.desktop",
    "build": {
      "beforeDevCommand": "npm run dev",
      "devUrl": "http://localhost:1420",
      "beforeBuildCommand": "npm run build",
      "frontendDist": "../dist"
    },
    "app": {
      "windows": [
        {
          "title": "KogniTerm Desktop",
          "width": 1200,
          "height": 800
        }
      ],
      "security": {
        "csp": null
      }
    },
    "bundle": {
      "active": true,
      "targets": "all",
      "category": "DeveloperTool",
      "shortDescription": "AI-Powered Terminal & Workspace",
      "longDescription": "KogniTerm Desktop es un entorno de terminal inteligente asistido por IA.",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico",
        "icons/icon.png"
      ]
    }
  }
  ```

- [ ] **Step 2: Validar el formato JSON**
  - Run: `python3 -m json.tool kogniterm-desktop/apps/desktop/src-tauri/tauri.conf.json > /dev/null`
  - Expected: PASS (código de salida 0)

---

### Task 3: Crear el Archivo de Entrada para el Lanzador de Linux (`kogniterm-desktop.desktop`)

**Files:**
- Create: `kogniterm-desktop/apps/desktop/kogniterm-desktop.desktop`

**Interfaces:**
- Produces: Archivo de entrada Desktop Entry conforme al estándar XDG.

- [ ] **Step 1: Crear `kogniterm-desktop.desktop`**

  ```ini
  [Desktop Entry]
  Type=Application
  Name=KogniTerm Desktop
  GenericName=AI-Powered Terminal
  Comment=Terminal asistida por Inteligencia Artificial para desarrolladores
  Exec=kogniterm-desktop
  Icon=kogniterm-desktop
  Terminal=false
  Categories=Development;System;Utility;Terminal;
  StartupWMClass=kogniterm-desktop
  Keywords=terminal;ai;kogniterm;shell;gemini;
  ```

- [ ] **Step 2: Validar la sintaxis del archivo `.desktop`**
  - Run: `desktop-file-validate kogniterm-desktop/apps/desktop/kogniterm-desktop.desktop` (si la herramienta está instalada).

---

### Task 4: Crear el Script de Instalación del Escritorio (`install-desktop.sh`)

**Files:**
- Create: `kogniterm-desktop/install-desktop.sh`

**Interfaces:**
- Consumes: `kogniterm-desktop.desktop` y `src-tauri/icons/icon.png`.
- Produces: Script de instalación ejecutable para registrar KogniTerm Desktop en el sistema.

- [ ] **Step 1: Escribir `kogniterm-desktop/install-desktop.sh`**

  ```bash
  #!/usr/bin/env bash
  set -e

  # Colores
  GREEN='\033[0;32m'
  BLUE='\033[0;34m'
  YELLOW='\033[1;33m'
  RESET='\033[0m'

  echo -e "${BLUE}=== Instalador de Lanzador de KogniTerm Desktop ===${RESET}"

  OS_TYPE="$(uname -s)"
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  DESKTOP_APP_DIR="$SCRIPT_DIR/apps/desktop"

  if [ "$OS_TYPE" = "Linux" ]; then
      BIN_DIR="$HOME/.local/bin"
      ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
      APPS_DIR="$HOME/.local/share/applications"

      mkdir -p "$BIN_DIR" "$ICON_DIR" "$APPS_DIR"

      # Copiar icono
      echo -e "${GREEN}✔ Instalando icono en $ICON_DIR/kogniterm-desktop.png${RESET}"
      cp "$DESKTOP_APP_DIR/src-tauri/icons/icon.png" "$ICON_DIR/kogniterm-desktop.png"

      # Crear wrapper o copiar binario ejecutable
      EXECUTABLE_PATH="$DESKTOP_APP_DIR/src-tauri/target/release/desktop"
      TARGET_BIN="$BIN_DIR/kogniterm-desktop"

      if [ -f "$EXECUTABLE_PATH" ]; then
          cp "$EXECUTABLE_PATH" "$TARGET_BIN"
          chmod +x "$TARGET_BIN"
          echo -e "${GREEN}✔ Executable instalado en $TARGET_BIN${RESET}"
      else
          echo -e "${YELLOW}⚠ Aviso: No se encontró ejecutable compilado en release.${RESET}"
          echo -e "Creando script wrapper para modo desarrollo..."
          cat << EOF > "$TARGET_BIN"
  #!/usr/bin/env bash
  cd "$DESKTOP_APP_DIR" && npm run tauri dev
  EOF
          chmod +x "$TARGET_BIN"
      fi

      # Crear archivo .desktop ajustado
      DESKTOP_FILE="$APPS_DIR/kogniterm-desktop.desktop"
      cat << EOF > "$DESKTOP_FILE"
  [Desktop Entry]
  Type=Application
  Name=KogniTerm Desktop
  GenericName=AI-Powered Terminal
  Comment=Terminal asistida por Inteligencia Artificial
  Exec=$TARGET_BIN
  Icon=kogniterm-desktop
  Terminal=false
  Categories=Development;System;Utility;Terminal;
  StartupWMClass=kogniterm-desktop
  Keywords=terminal;ai;kogniterm;shell;gemini;
  EOF

      chmod +x "$DESKTOP_FILE"
      echo -e "${GREEN}✔ Acceso directo instalado en $DESKTOP_FILE${RESET}"

      # Actualizar cachés de menú si existen comandos
      if command -v update-desktop-database &>/dev/null; then
          update-desktop-database "$APPS_DIR" || true
      fi
      if command -v gtk-update-icon-cache &>/dev/null; then
          gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true
      fi

      echo -e "\n${GREEN}🚀 ¡KogniTerm Desktop ya está disponible en tu lanzador de aplicaciones!${RESET}"

  elif [ "$OS_TYPE" = "Darwin" ]; then
      echo -e "${BLUE}Detectado sistema macOS...${RESET}"
      APP_BUNDLE="$DESKTOP_APP_DIR/src-tauri/target/release/bundle/macos/KogniTerm Desktop.app"
      if [ -d "$APP_BUNDLE" ]; then
          cp -R "$APP_BUNDLE" "/Applications/"
          echo -e "${GREEN}✔ KogniTerm Desktop.app instalado en /Applications/${RESET}"
      else
          echo -e "${YELLOW}⚠ Compila primero el paquete con: cd $DESKTOP_APP_DIR && npm run tauri build${RESET}"
      fi
  else
      echo "Sistema no soportado: $OS_TYPE"
      exit 1
  fi
  ```

- [ ] **Step 2: Dar permisos de ejecución a `install-desktop.sh`**
  - Run: `chmod +x kogniterm-desktop/install-desktop.sh`

---

### Task 5: Verificación de la Instalación y Pruebas

**Files:**
- Test execution of `install-desktop.sh`.

- [ ] **Step 1: Ejecutar el script `install-desktop.sh`**
  - Run: `bash kogniterm-desktop/install-desktop.sh`
  - Expected: PASS con salida conteniendo `✔ Acceso directo instalado en .../kogniterm-desktop.desktop`

- [ ] **Step 2: Verificar la existencia del icono y el archivo `.desktop`**
  - Run: `test -f ~/.local/share/applications/kogniterm-desktop.desktop && test -f ~/.local/share/icons/hicolor/512x512/apps/kogniterm-desktop.png`
  - Expected: PASS (código de salida 0)
