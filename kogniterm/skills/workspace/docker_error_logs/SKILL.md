---
allowlist: false
author: KogniTerm AI (Autonomous Generation)
auto_approve: true
category: autonomous
dependencies: []
description: "Muestra los errores de los contenedores Docker de las \xFAltimas 24\
  \ horas, con opciones de personalizaci\xF3n"
name: docker_error_logs
required_permissions:
- filesystem
sandbox_required: false
security_level: standard
tags:
- autonomous
- generated
version: 1.0.0
---

# Herramienta: docker_error_logs

## Descripción
Esta herramienta recopila y filtra los logs de errores de contenedores Docker de las últimas 24 horas (o un período configurable). Es útil para detectar y diagnosticar problemas en servicios contenedorizados.

## Parámetros

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `all_containers` | boolean | `False` | Si es `True`, incluye contenedores detenidos. Si es `False`, solo contenedores en ejecución. |
| `hours` | integer | `24` | Número de horas hacia atrás para buscar logs. |
| `keywords` | array of strings | `["error", "ERROR", "failed", "Failed", "exception", "Exception", "fatal", "Fatal"]` | Lista de palabras clave para filtrar logs (insensible a mayúsculas). |
| `show_tail` | integer | `50` | Número máximo de líneas de error a mostrar por contenedor. |

## Salida
La herramienta devuelve un informe en texto plano con:
- Resumen general (total de contenedores revisados, total de errores encontrados)
- Por cada contenedor con errores:
  - Nombre e ID del contenedor
  - Estado (running, exited, etc.)
  - Lista de líneas de error (con timestamp si está disponible)
- Si no se encuentran errores, se indica claramente.

## Ejemplos de uso

### 1. Ver errores de las últimas 24 horas (solo contenedores activos)
```
docker_error_logs()
```

### 2. Incluir contenedores detenidos y buscar en las últimas 48 horas
```
docker_error_logs(all_containers=True, hours=48)
```

### 3. Buscar palabras clave personalizadas
```
docker_error_logs(keywords=["panic", "critical", "CRITICAL"])
```

## Notas técnicas
- La herramienta ejecuta comandos Docker (`docker ps` y `docker logs`) y procesa los resultados localmente.
- Si no hay contenedores o no se encuentran errores, el informe será breve pero informativo.
- Los logs se obtienen con `docker logs --since <hours>h` y se filtran con `grep -i -E`.
- El tiempo de ejecución depende del número de contenedores y el volumen de logs.