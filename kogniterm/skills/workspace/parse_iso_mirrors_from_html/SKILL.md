---
allowlist: false
author: KogniTerm AI (Autonomous Generation)
auto_approve: true
category: autonomous
dependencies: []
description: "Parsea una p\xE1gina HTML de directorio de mirrors y extrae URLs de\
  \ archivos ISO"
name: parse_iso_mirrors_from_html
required_permissions:
- filesystem
sandbox_required: false
security_level: standard
tags:
- autonomous
- generated
version: 1.0.0
---

# Skill: parse_iso_mirrors_from_html

## Descripción
Esta skill obtiene el contenido HTML de una URL de directorio de mirrors (como los que usan AlmaLinux o Rocky Linux) y extrae todas las URLs que apuntan a archivos `.iso`. Es útil para obtener dinámicamente la lista de mirrors disponibles sin hardcodear URLs.

## Parámetros
- **html_url** (string, requerido): URL de la página HTML que contiene los enlaces a ISOs.
- **iso_pattern** (string, opcional): Patrón regex para filtrar archivos ISO. Default: `\.iso$` (cualquier URL que termine en .iso).
- **base_url** (string, opcional): URL base para construir URLs completas si los enlaces en el HTML son relativos. Si no se provee, se asume que los enlaces son absolutos.

## Comportamiento
1. Realiza un `curl -s` a `html_url` para obtener el HTML.
2. Extrae todos los enlaces `href` que coincidan con `iso_pattern`.
3. Si los enlaces son relativos y se provee `base_url`, los convierte a URLs absolutas.
4. Elimina duplicados y devuelve la lista de URLs, una por línea.

## Ejemplo de uso
```python
mirrors = parse_iso_mirrors_from_html(
    html_url="https://mirrors.almalinux.org/isos/x86_64/9.7.html",
    iso_pattern=r"AlmaLinux-9-latest-x86_64-(dvd|minimal)\.iso$"
)
```

## Notas
- Esta skill no valida que las URLs sean funcionales; solo extrae enlaces.
- El HTML se parsea con `grep -o 'href="[^"]*"'` y luego se filtra.
- Si no se encuentran enlaces, devuelve cadena vacía.