---
allowed-tools: []
allowlist: false
assets: []
author: KogniTerm AI (Autonomous Generation)
auto_approve: true
category: autonomous
denied-tools: []
dependencies: []
description: "Realiza una auditor\xEDa completa del entorno Docker: estado de contenedores,\
  \ problemas de salud (healthcheck), uso de almacenamiento (system df) y an\xE1lisis\
  \ de errores en logs en una ventana de tiempo configurable."
metadata:
  format: agent-skills-compatible
name: docker_auditor
required_permissions:
- filesystem
resources: []
security_level: standard
tags:
- autonomous
- generated
version: 1.0.0
---

# Docker Auditor Skill

Esta herramienta permite auditar el estado operacional de los contenedores Docker en el sistema, identificar contenedores no saludables (`unhealthy`), analizar el uso de espacio en disco de imágenes, volúmenes y contenedores (`docker system df`), y escanear los registros de logs en busca de errores en las últimas N horas.

## Cuándo usar esta herramienta

- Para monitorear periódicamente la infraestructura Docker.
- Para identificar contenedores caídos, desactualizados o no saludables.
- Para extraer resúmenes de errores en las últimas 24 horas (u otro periodo).
- Para auditar el uso de disco del daemon Docker.

## Parámetros

- `since` (string, opcional): Ventana de tiempo para el análisis de logs (ej: `'1h'`, `'24h'`, `'7d'`). Por defecto `'24h'`.
- `output_format` (string, opcional): Formato de salida deseado: `'markdown'` o `'json'`. Por defecto `'markdown'`.
- `include_logs` (boolean, opcional): Si se deben escanear y filtrar logs buscando cadenas de error. Por defecto `true`.

## Ejemplo de uso

```json
{
  "since": "24h",
  "output_format": "markdown",
  "include_logs": true
}
```
