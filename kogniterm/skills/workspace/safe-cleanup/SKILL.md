---
allowlist: false
author: KogniTerm AI (Autonomous Generation)
auto_approve: true
category: autonomous
dependencies: []
description: "Skill de limpieza segura para proyectos. Identifica y elimina archivos\
  \ temporales, backups, cach\xE9 y build artifacts de forma segura con reporte y\
  \ confirmaci\xF3n."
name: safe-cleanup
required_permissions:
- filesystem
sandbox_required: false
security_level: standard
tags:
- autonomous
- generated
version: 1.0.0
---

# Skill: Limpieza Segura de Proyecto (safe_cleanup)

## Propósito
Limpia archivos de basura técnica del proyecto de forma segura y controlada.

## Capacidades
1. **Escaneo inteligente**: Identifica archivos por categorías:
   - Build artifacts (compilaciones, dist, build, .next, .tsbuildinfo)
   - Archivos temporales (.tmp, .temp, .log, .cache)
   - Backups (.bak, .backup, .old, ~)
   - Caché de dependencias (node_modules/.cache, __pycache__, .pytest_cache)
   - Archivos duplicados conocidos
   - Directorios de builds móviles (android/app/build, ios/build)

2. **Modo seguro por defecto**: 
   - Solo genera reporte sin eliminar
   - Muestra tamaño total y conteo por categoría
   - Lista archivos específicos

3. **Limpieza controlada**:
   - Pide confirmación explícita
   - Mueve a carpeta `trash/` en lugar de eliminar directamente
   - Genera log de operación en `cleanup_log.json`
   - Permite recuperación si hay errores

4. **Filtros personalizables**:
   - `dry_run`: Solo simula (default: True)
   - `categories`: Lista de categorías a limpiar (default: todas)
   - `exclude_patterns`: Patrones a excluir
   - `move_to_trash`: Mover a carpeta trash en lugar de eliminar (default: True)

## Parámetros
- `project_path`: Ruta del proyecto (default: directorio actual)
- `dry_run`: Simulación sin eliminar (default: True)
- `categories`: Categorías a procesar ["build", "temp", "backup", "cache", "duplicates"]
- `exclude_patterns`: Lista de patrones glob a excluir
- `generate_report`: Generar archivo de reporte (default: True)

## Ejemplos de uso
1. `safe_cleanup(dry_run=True)` - Solo analiza y reporta
2. `safe_cleanup(dry_run=False, categories=["build", "temp"])` - Limpia builds y temporales
3. `safe_cleanup(dry_run=False, move_to_trash=True)` - Elimina moviendo a trash/

## Seguridad
- NUNCA elimina archivos sin confirmación en dry_run=False
- Todo lo movido a `trash/` puede recuperarse
- Log detallado de cada operación
- Verifica que el archivo exista antes de borrar