---
name: execute_command
version: 1.0.0
author: "KogniTerm Core"
description: "Ejecuta comandos en la terminal del sistema y devuelve su salida"
category: "system"
tags: ["bash", "shell", "terminal", "execution", "command"]
dependencies: []
required_permissions: ["execute", "filesystem"]
security_level: "elevated"
allowlist: true
auto_approve: false
sandbox_required: true
---

# Instrucciones para el LLM

Esta skill permite ejecutar comandos en el sistema operativo.

## Herramientas disponibles:

### execute_command

Ejecuta un comando en la shell y devuelve la salida.

**Parámetros:**
- `command` (string, requerido): El comando a ejecutar
- `timeout` (integer, opcional): Timeout en segundos (default: 30, max: 300)

**Ejemplo:**
```json
{
  "tool": "execute_command",
  "args": {
    "command": "ls -la",
    "timeout": 10
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: elevated** - Requiere aprobación del usuario
- **Permisos requeridos:** execute, filesystem
- **Requiere allowlisting:** true
- **Ejecución en sandbox:** true (Docker)

### Comandos peligrosos (requieren aprobación):

Los siguientes comandos requieren aprobación manual del usuario:
- `rm -rf`, `rm -r`, `rm -f`
- `sudo`, `su`
- `chmod 777`, `chown`
- `dd`, `mkfs`
- Comandos que contengan `> /dev/sd*`
- Cualquier comando que pueda modificar el sistema

## Uso recomendado:

1. Usa esta herramienta para ejecutar comandos del sistema
2. Verifica los resultados antes de proceder
3. Si el comando falla, revisa los permisos y la sintaxis
4. Para comandos de solo lectura (ls, cat, grep), el usuario puede tener auto_approve enabled
