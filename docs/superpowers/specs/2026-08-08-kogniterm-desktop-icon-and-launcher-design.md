# Especificación de Diseño: Icono e Integración en Lanzadores para KogniTerm Desktop

**Fecha**: 2026-08-08  
**Estado**: Aprobado  
**Proyecto**: KogniTerm Desktop (`kogniterm-desktop`)

---

## 1. Visión General y Objetivos
KogniTerm Desktop requiere un icono representativo de alta calidad ("Terminal Inteligente") y una integración completa con los lanzadores de aplicaciones nativos de sistemas operacionales Linux (GNOME, KDE, XFCE, etc.) y macOS (Finder, Launchpad, Dock).

El objetivo es:
1. Diseñar e implementar un nuevo conjunto de iconos oficiales multi-resolución (`.png`, `.ico`, `.icns`).
2. Configurar Tauri Bundler para generar paquetes de distribución oficial (`.deb`, `.AppImage`, `.dmg`).
3. Proporcionar un script de instalación rápida (`install-desktop.sh`) que instale localmente la aplicación con su icono y acceso directo en el sistema operativo sin depender de empaquetadores de producción.

---

## 2. Iconografía y Branding

### Concepto Visual ("Terminal Inteligente")
- **Formato Base**: Squircle (cuadrado de esquinas redondeadas modernas estilo macOS/GNOME).
- **Paleta de Colores**:
  - Fondo: Oscuro azabache/grafito profundo (`#0B0F19` a `#141B2D`) con gradiente sutil.
  - Acentos principales: Cian neón eléctrico (`#00F2FE` / `#4FACFE`) para el prompt de terminal y nodos de red neuronal.
  - Acentos secundarios: Ámbar/Dorado tenue (`#FFB300`) para simular actividad cognitiva/IA.
- **Elementos**:
  - Marco minimalista de terminal de comandos con tres puntos en la cabecera.
  - Símbolo central de prompt (`>_`) integrado armoniosamente con nodos de sinopsis de IA.

### Matriz de Archivos de Iconos (`kogniterm-desktop/apps/desktop/src-tauri/icons/`)
- `master_icon.png`: Imagen fuente 1024x1024 en formato PNG con canal alfa (transparencia).
- `icon.png`: PNG 512x512 para escritorios Linux y alta definición.
- `32x32.png`, `128x128.png`, `128x128@2x.png`: Resoluciones estándar de Tauri.
- `icon.ico`: Formato Windows Icon (conteniendo tamaños 16, 32, 48, 64, 128, 256px).
- `icon.icns`: Formato macOS Apple Icon Image.

---

## 3. Integración en Sistemas Operativos

### A. Linux (FDF XDG Desktop Entry Standard)
- **Ruta de Icono**: `~/.local/share/icons/hicolor/512x512/apps/kogniterm-desktop.png`
- **Ruta de Acceso Directo**: `~/.local/share/applications/kogniterm-desktop.desktop`
- **Contenido del Archivo `.desktop`**:
  ```ini
  [Desktop Entry]
  Type=Application
  Name=KogniTerm Desktop
  GenericName=AI-Powered Terminal & Workspace
  Comment=Terminal asistida por Inteligencia Artificial
  Exec=/home/USER/.local/bin/kogniterm-desktop
  Icon=kogniterm-desktop
  Terminal=false
  Categories=Development;System;Utility;Terminal;
  StartupWMClass=kogniterm-desktop
  Keywords=terminal;ai;kogniterm;shell;gemini;
  ```
- **Post-instalación**: Ejecutar `gtk-update-icon-cache` y `update-desktop-database` para actualizar la caché del menú de aplicaciones inmediatamente.

### B. macOS (App Bundle Structure)
- **Ruta de Instalación**: `/Applications/KogniTerm Desktop.app`
- **Contenido del Bundle**:
  - `Contents/Info.plist`: Propiedad `CFBundleIconFile` apuntando a `icon.icns`.
  - `Contents/Resources/icon.icns`: Icono nativo de alta resolución.
- **Post-instalación**: Registro automático en Launchpad y Finder.

---

## 4. Configuración de Tauri (`tauri.conf.json`)

Se actualizará la sección `bundle` e `identifier` en `kogniterm-desktop/apps/desktop/src-tauri/tauri.conf.json`:
- `productName`: `"KogniTerm Desktop"`
- `identifier`: `"com.kogniterm.desktop"`
- `bundle`:
  - `active`: `true`
  - `targets`: `["deb", "appimage", "dmg", "app"]`
  - `icon`: Arreglo de rutas a las versiones de iconos generadas.
  - `category`: `"DeveloperTool"`
  - `shortDescription`: `"AI-Powered Terminal Workspace"`

---

## 5. Script de Instalación Rápida (`install-desktop.sh`)

Ubicación: `kogniterm-desktop/install-desktop.sh`

### Comportamiento del Script:
1. Detectar Sistema Operativo (`uname -s`: Linux o Darwin/macOS).
2. Compilar la aplicación desktop usando `npm run tauri build` (o crear ejecutable de desarrollo si no hay toolchain de Rust instalado).
3. **En Linux**:
   - Copiar ejecutable compilado a `~/.local/bin/kogniterm-desktop`.
   - Crear directorios `~/.local/share/icons/hicolor/512x512/apps/` y `~/.local/share/applications/` si no existen.
   - Copiar `icon.png` a la ruta de iconos.
   - Generar/copiar `kogniterm-desktop.desktop` ajustando dinámicamente la ruta absoluta del binario.
   - Refrescar cachés de escritorio.
4. **En macOS**:
   - Mover el `.app` compilado a `/Applications/KogniTerm Desktop.app`.

---

## 6. Plan de Verificación

1. **Verificación de Iconos**:
   - Confirmar generación limpia de `32x32.png`, `128x128.png`, `icon.png`, `icon.ico` e `icon.icns`.
2. **Verificación en Linux**:
   - Ejecutar `install-desktop.sh`.
   - Comprobar que el archivo `~/.local/share/applications/kogniterm-desktop.desktop` existe y es válido (`desktop-file-validate`).
   - Comprobar disponibilidad en el menú de aplicaciones del entorno de escritorio.
3. **Verificación en macOS (si aplica/emulación)**:
   - Verificar estructura correcta del paquete `.app` e `Info.plist`.
