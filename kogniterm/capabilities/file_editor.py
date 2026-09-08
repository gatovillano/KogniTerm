"""Capacidades nativas ultrarrápidas de manipulación de archivos y directorios para KogniTerm."""

import asyncio
import difflib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from kogniterm.capabilities.registry import tool


def _resolve_path(path_str: str) -> Path:
    """Resuelve la ruta relativa al directorio de trabajo actual o absoluta."""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


class ReadFileParams(BaseModel):
    path: str = Field(description="Ruta absoluta o relativa del archivo a leer")
    offset: Optional[int] = Field(default=None, description="Línea inicial de lectura (1-indexada)")
    limit: Optional[int] = Field(default=None, description="Cantidad máxima de líneas a leer")


class EditFileParams(BaseModel):
    path: str = Field(description="Ruta absoluta o relativa del archivo a editar")
    old_string: str = Field(description="Texto exacto a reemplazar dentro del archivo")
    new_string: str = Field(description="Nuevo texto de reemplazo")
    create_backup: bool = Field(default=True, description="Si es True, crea una copia de seguridad .bak")
    context_lines: int = Field(default=3, description="Líneas de contexto para el diff unificado")


class ReplaceAllParams(BaseModel):
    path: str = Field(description="Ruta del archivo a editar")
    old_string: str = Field(description="Texto a buscar y reemplazar en todo el archivo")
    new_string: str = Field(description="Nuevo texto de reemplazo")
    create_backup: bool = Field(default=True, description="Si es True, crea copia .bak")


class CreateFileParams(BaseModel):
    path: str = Field(description="Ruta del archivo a crear")
    content: str = Field(default="", description="Contenido inicial del archivo")
    overwrite: bool = Field(default=False, description="Si es True, sobrescribe si ya existe")


class DeleteFileParams(BaseModel):
    path: str = Field(description="Ruta del archivo a eliminar")


class ListDirectoryParams(BaseModel):
    path: str = Field(default=".", description="Ruta del directorio a listar")


@tool(
    name="read_file",
    description="Lee y retorna el contenido de un archivo con soporte de paginación por líneas.",
    params_schema=ReadFileParams,
    category="files",
)
async def read_file(
    path: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Lee el contenido de un archivo de manera asíncrona."""
    file_path = _resolve_path(path)
    if not file_path.exists():
        return {"success": False, "path": str(file_path), "error": f"El archivo '{file_path}' no existe."}
    if file_path.is_dir():
        return {"success": False, "path": str(file_path), "error": f"'{file_path}' es un directorio, usa list_directory."}

    def _sync_read():
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            if offset is None and limit is None:
                content = f.read()
                total_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
                return content, total_lines
            lines = f.readlines()
            total_lines = len(lines)
            start_idx = max(0, (offset - 1)) if offset else 0
            end_idx = start_idx + limit if limit else total_lines
            sliced = lines[start_idx:end_idx]
            return "".join(sliced), total_lines

    try:
        content, total_lines = await asyncio.to_thread(_sync_read)
        return {
            "success": True,
            "path": str(file_path),
            "content": content,
            "total_lines": total_lines,
            "size_bytes": len(content.encode("utf-8")),
        }
    except Exception as exc:
        return {"success": False, "path": str(file_path), "error": f"Error al leer archivo: {exc}"}


@tool(
    name="edit_file",
    description="Edita un archivo reemplazando texto exacto. Genera diff unificado para auditoría.",
    params_schema=EditFileParams,
    category="files",
)
async def edit_file(
    path: str,
    old_string: str,
    new_string: str,
    create_backup: bool = True,
    context_lines: int = 3,
) -> Dict[str, Any]:
    """Reemplaza la primera ocurrencia de old_string por new_string en un archivo."""
    file_path = _resolve_path(path)
    if not file_path.exists():
        return {"success": False, "path": str(file_path), "error": f"El archivo '{file_path}' no existe."}

    def _sync_edit():
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            original_content = f.read()

        target_old = old_string
        if target_old not in original_content:
            norm_orig = original_content.replace("\r\n", "\n")
            norm_target = old_string.replace("\r\n", "\n")
            if norm_target in norm_orig:
                target_old = norm_target
                original_content = norm_orig
            else:
                return {
                    "success": False,
                    "path": str(file_path),
                    "error": "El texto especificado en 'old_string' no fue encontrado en el archivo.",
                    "diff": "",
                    "old_string_found": False,
                }

        backup_path_str = None
        if create_backup:
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            with open(backup_path, "w", encoding="utf-8") as bf:
                bf.write(original_content)
            backup_path_str = str(backup_path)

        new_content = original_content.replace(target_old, new_string, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        diff_lines = list(
            difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path.name}",
                tofile=f"b/{file_path.name}",
                n=context_lines,
            )
        )
        formatted_diff = "".join(diff_lines)
        lines_changed = sum(1 for line in diff_lines if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))

        return {
            "success": True,
            "path": str(file_path),
            "diff": formatted_diff,
            "backup": backup_path_str,
            "lines_changed": lines_changed,
            "old_string_found": True,
        }

    try:
        return await asyncio.to_thread(_sync_edit)
    except Exception as exc:
        return {"success": False, "path": str(file_path), "error": f"Error al editar archivo: {exc}"}


@tool(
    name="replace_all_file",
    description="Reemplaza TODAS las ocurrencias de un texto en un archivo.",
    params_schema=ReplaceAllParams,
    category="files",
)
async def replace_all_file(
    path: str,
    old_string: str,
    new_string: str,
    create_backup: bool = True,
) -> Dict[str, Any]:
    """Reemplaza todas las apariciones de un texto en el archivo."""
    file_path = _resolve_path(path)
    if not file_path.exists():
        return {"success": False, "path": str(file_path), "error": f"El archivo '{file_path}' no existe."}

    def _sync_replace_all():
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            original_content = f.read()

        count = original_content.count(old_string)
        if count == 0:
            return {"success": False, "path": str(file_path), "error": "Texto no encontrado.", "occurrences": 0}

        backup_path_str = None
        if create_backup:
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            with open(backup_path, "w", encoding="utf-8") as bf:
                bf.write(original_content)
            backup_path_str = str(backup_path)

        new_content = original_content.replace(old_string, new_string)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        diff_lines = list(
            difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path.name}",
                tofile=f"b/{file_path.name}",
            )
        )
        return {
            "success": True,
            "path": str(file_path),
            "diff": "".join(diff_lines),
            "backup": backup_path_str,
            "occurrences_replaced": count,
        }

    try:
        return await asyncio.to_thread(_sync_replace_all)
    except Exception as exc:
        return {"success": False, "path": str(file_path), "error": f"Error al reemplazar en archivo: {exc}"}


@tool(
    name="create_file",
    description="Crea un archivo nuevo con el contenido especificado de forma segura.",
    params_schema=CreateFileParams,
    category="files",
)
async def create_file(
    path: str,
    content: str = "",
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Crea un nuevo archivo."""
    file_path = _resolve_path(path)
    if file_path.exists() and not overwrite:
        return {"success": False, "path": str(file_path), "error": f"El archivo ya existe. Usa overwrite=True si deseas sobrescribirlo."}

    def _sync_create():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": str(file_path), "size_bytes": len(content.encode("utf-8"))}

    try:
        return await asyncio.to_thread(_sync_create)
    except Exception as exc:
        return {"success": False, "path": str(file_path), "error": f"Error al crear archivo: {exc}"}


@tool(
    name="delete_file",
    description="Elimina un archivo del sistema de forma permanente.",
    params_schema=DeleteFileParams,
    category="files",
)
async def delete_file(path: str) -> Dict[str, Any]:
    """Elimina el archivo especificado."""
    file_path = _resolve_path(path)
    if not file_path.exists():
        return {"success": False, "path": str(file_path), "error": f"El archivo '{file_path}' no existe."}
    if file_path.is_dir():
        return {"success": False, "path": str(file_path), "error": f"'{file_path}' es un directorio, no un archivo."}

    try:
        await asyncio.to_thread(file_path.unlink)
        return {"success": True, "path": str(file_path), "message": "Archivo eliminado correctamente."}
    except Exception as exc:
        return {"success": False, "path": str(file_path), "error": f"Error al eliminar archivo: {exc}"}


@tool(
    name="list_directory",
    description="Lista de forma rápida los archivos y subdirectorios de una ruta.",
    params_schema=ListDirectoryParams,
    category="files",
)
async def list_directory(path: str = ".") -> Dict[str, Any]:
    """Lista el contenido de un directorio."""
    target_path = _resolve_path(path)
    if not target_path.exists():
        return {"success": False, "path": str(target_path), "error": f"La ruta no existe: {path}", "items": []}
    if not target_path.is_dir():
        return {"success": False, "path": str(target_path), "error": f"La ruta no es un directorio: {path}", "items": []}

    def _sync_list():
        items = []
        for entry in sorted(target_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                is_dir = entry.is_dir()
                size = entry.stat().st_size if not is_dir else 0
                items.append({
                    "name": entry.name,
                    "is_dir": is_dir,
                    "size_bytes": size,
                })
            except (PermissionError, OSError):
                continue
        return items

    try:
        items = await asyncio.to_thread(_sync_list)
        return {"success": True, "path": str(target_path), "items": items, "count": len(items)}
    except Exception as exc:
        return {"success": False, "path": str(target_path), "error": str(exc), "items": []}
