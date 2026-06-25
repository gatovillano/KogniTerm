---
allowlist: false
author: KogniTerm AI (Autonomous Generation)
auto_approve: true
category: autonomous
dependencies: []
description: "Organiza fotograf\xEDas en carpetas por a\xF1o/mes seg\xFAn fecha de\
  \ modificaci\xF3n"
name: photo-organizer
required_permissions:
- filesystem
security_level: standard
tags:
- autonomous
- generated
version: 1.0.0
---

# Photo Organizer Skill

## Descripción
Esta skill organiza fotografías en carpetas por fecha de modificación (Año/Mes/Día).

## Parámetros de entrada
- `source_dir` (requerido): Directorio fuente con fotos (puede incluir subdirectorios)
- `dest_dir` (requerido): Directorio destino donde se creará la estructura organizada
- `copy` (opcional, booleano): Si es `True`, copia las fotos; si `False`, las mueve. Por defecto: `True`
- `extensions` (opcional, lista): Extensiones de archivo a considerar. Por defecto: `[".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]

## Ejemplo de uso
```python
run({
    "source_dir": "/home/gato/Pictures",
    "dest_dir": "/media/kingston/photos",
    "copy": True,
    "extensions": [".jpg", ".jpeg", ".png"]
})
```

## Comportamiento
- Recorre recursivamente `source_dir` buscando imágenes
- Agrupa por año/mes según `st_mtime` (fecha de modificación)
- Crea estructura `Año/MM/DD` en `dest_dir`
- Preserva metadatos si `copy=True` (usa `shutil.copy2`)