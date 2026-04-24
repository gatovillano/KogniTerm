#!/usr/bin/env python3
"""
Skill: Photo Organizer
Organiza fotografías en carpetas por fecha de modificación (año/mes/día).
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

# Parámetros del esquema
def parameters_schema():
    return {
        "type": "object",
        "properties": {
            "source_dir": {"type": "string", "description": "Directorio fuente con fotos"},
            "dest_dir": {"type": "string", "description": "Directorio destino organizado"},
            "copy": {"type": "boolean", "description": "Si True, copia; si False, mueve"},
            "extensions": {"type": "array", "items": {"type": "string"}, "description": "Extensiones de archivo a considerar"}
        },
        "required": ["source_dir", "dest_dir"]
    }

# Registro global
parameters_schema = parameters_schema()

def run(args):
    source_dir = Path(args["source_dir"]).expanduser()
    dest_dir = Path(args["dest_dir"]).expanduser()
    copy = args.get("copy", True)
    extensions = args.get("extensions", [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"])
    
    if not source_dir.exists():
        return f"Error: directorio fuente no existe: {source_dir}"
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    moved_count = 0
    for ext in extensions:
        for img_path in source_dir.rglob(f"*{ext}"):
            if img_path.is_file():
                mtime = datetime.fromtimestamp(img_path.stat().st_mtime)
                year_folder = mtime.strftime("%Y")
                month_folder = mtime.strftime("%m")
                day_folder = mtime.strftime("%d")
                
                target_subdir = dest_dir / year_folder / month_folder / day_folder
                target_subdir.mkdir(parents=True, exist_ok=True)
                
                target_path = target_subdir / img_path.name
                
                if copy:
                    shutil.copy2(img_path, target_path)
                    action = "Copiado"
                else:
                    shutil.move(str(img_path), str(target_path))
                    action = "Movido"
                
                print(f"{action}: {img_path.relative_to(source_dir)} -> {target_subdir.relative_to(dest_dir)}")
                moved_count += 1
    
    return f"Organización completada: {moved_count} archivos procesados."

if __name__ == "__main__":
    # Modo de prueba
    import sys
    test_source = sys.argv[1] if len(sys.argv) > 1 else "/home/gato/Pictures"
    test_dest = sys.argv[2] if len(sys.argv) > 2 else "/tmp/organized_photos"
    print(run({"source_dir": test_source, "dest_dir": test_dest, "copy": False}))