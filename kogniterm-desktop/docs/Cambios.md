# Cambios

## Corrección de validación de directorio en start-dev.sh

**Fecha:** 2025-06-23

**Problema:**
El script `start-dev.sh` fallaba con el error "Este script debe ejecutarse desde el directorio kogniterm-desktop/" aunque se ejecutara desde la ruta correcta. La causa era una validación de directorio obsoleta que buscaba la carpeta `apps/server`, la cual no existe en la estructura actual del proyecto.

**Cambios realizados:**
- Se reemplazó la referencia `apps/server` por `apps/desktop` en la validación del script (línea 15).
- El script ahora correctamente detecta el directorio `apps/desktop` y procede con la iniciación del backend y frontend.
- Se verificó que el backend se inicia en `http://localhost:8765` y el frontend Tauri/React se lanza desde `apps/desktop`.

**Archivos modificados:**
- `start-dev.sh`

## Corrección de activación de entorno virtual para el backend

**Fecha:** 2025-06-23

**Problema:**
El backend de KogniTerm fallaba al iniciar con `ModuleNotFoundError: No module named 'pydantic_settings'`. El script `start-dev.sh` ejecutaba `python3 -m kogniterm.server` sin activar el entorno virtual donde están instaladas las dependencias Python del proyecto.

**Cambios realizados:**
- Se identificó que el entorno virtual del backend está ubicado en `/home/gato/.kogniterm/venv/` y contiene todas las dependencias (incluyendo `pydantic-settings`).
- Se modificó `start-dev.sh` para activar el entorno virtual antes de ejecutar el servidor, agregando `source /home/gato/.kogniterm/venv/bin/activate` en las líneas de inicio del backend para gnome-terminal, konsole y xterm.
- Se actualizó también el mensaje de fallback para que el usuario sepa cómo activar el entorno virtual manualmente.

**Archivos modificados:**
- `start-dev.sh`
