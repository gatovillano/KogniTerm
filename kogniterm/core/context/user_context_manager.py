"""
user_context_manager.py — Gestor de Contexto Global de Usuario (Nivel Home)

Mantiene un archivo Markdown persistente en `~/.kogniterm/user_context.md` que
almacena información relevante y duradera sobre el usuario: identidad,
preferencias de trabajo, stack tecnológico, proyectos activos y estilo de
comunicación. A diferencia de `llm_context.md` (que vive por proyecto/workspace),
este contexto es GLOBAL y se comparte entre todos los proyectos de KogniTerm.

Filosofía (inspirada en KAI/KognitoAI):
- Carga en cada turno, inyectada en el system prompt bajo un header claro.
- Escritura proactiva por el agente vía herramientas de memoria.
- Formato Markdown simple, editable a mano por el usuario.
"""

import os
import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Plantilla inicial que se crea la primera vez que se accede al contexto.
_DEFAULT_TEMPLATE = """# 🧑 Perfil de Usuario (Contexto Global KogniTerm)

> Este archivo es la memoria global del usuario. Se inyecta en el system prompt
> de KogniTerm en TODOS los proyectos. Edítalo a mano o pide al agente que lo
> actualice cuando haya información nueva y duradera sobre ti.

## Identidad
- Nombre: (completar)
- Ubicación / Zona horaria: (completar)
- Idioma preferido: Español

## Preferencias de Trabajo
- (ej. Prefiero respuestas concisas y directas)
- (ej. Umo Markdown con emojis moderados)

## Stack y Herramientas
- (ej. Python, TypeScript, Bitwig Studio, Ableton Live)

## Proyectos Activos
- (ej. KognitoAI, Cuerpo Libre Fotografía, KogniTerm)

## Notas y Contexto Relevante
- (Cualquier dato que el agente deba recordar siempre)
"""


class UserContextManager:
    """Gestiona la lectura/escritura del contexto global de usuario.

    Singleton por proceso para evitar releer disco en cada turno. Usa un lock
    para escrituras concurrentes seguras (el agente puede escribir desde
    herramientas mientras otro hilo lee).
    """

    _instance: Optional["UserContextManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        home = os.path.expanduser("~")
        self.base_dir = os.path.join(home, ".kogniterm")
        self.file_path = os.path.join(self.base_dir, "user_context.md")
        self._cache: Optional[str] = None
        self._cache_mtime: float = 0.0
        self._write_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "UserContextManager":
        """Devuelve la instancia singleton, creándola si es necesario."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_file(self) -> None:
        """Crea el directorio y el archivo con la plantilla si no existen."""
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            if not os.path.exists(self.file_path):
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(_DEFAULT_TEMPLATE)
                logger.info("UserContextManager: creado %s con plantilla inicial.", self.file_path)
        except Exception as e:
            logger.warning("UserContextManager: no se pudo asegurar el archivo: %s", e)

    def get_context(self, use_cache: bool = True) -> str:
        """Lee el contexto global del usuario.

        Usa un cache en memoria invalidado por mtime para evitar releer disco
        en cada turno del bucle agéntico.
        """
        try:
            if not os.path.exists(self.file_path):
                self._ensure_file()

            mtime = os.path.getmtime(self.file_path)
            if use_cache and self._cache is not None and mtime == self._cache_mtime:
                return self._cache

            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self._cache = content
            self._cache_mtime = mtime
            return content
        except Exception as e:
            logger.warning("UserContextManager: error leyendo contexto: %s", e)
            return ""

    def is_populated(self) -> bool:
        """True si el archivo tiene contenido real más allá de la plantilla.

        Compara el conjunto de bullets actuales contra los que trae la plantilla
        por defecto. Si todos los bullets presentes ya estaban en la plantilla
        (o son placeholders), se considera no poblado.
        """
        content = self.get_context()
        if not content:
            return False

        def _bullets(text: str) -> set:
            out = set()
            for ln in text.splitlines():
                s = ln.strip()
                if s.startswith("- "):
                    body = s[2:].strip().lower()
                    # Normalizar placeholders a una forma canónica
                    if body.startswith(("(completar", "(ej.", "(cualquier", "(opcional")):
                        body = "<placeholder>"
                    out.add(body)
            return out

        template_bullets = _bullets(_DEFAULT_TEMPLATE)
        current_bullets = _bullets(content)
        # Hay contenido nuevo si existe algún bullet actual que no esté en la plantilla
        extra = current_bullets - template_bullets
        # Ignorar placeholders genéricos normalizados
        extra = {b for b in extra if b != "<placeholder>"}
        return len(extra) > 0

    def append_note(self, section: str, note: str) -> bool:
        """Añade una nota (bullet) bajo una sección existente (o la crea).

        Estrategia: localiza el header `## <section>` por coincidencia parcial
        insensible a mayúsculas y desplaza la nueva nota inmediatamente después
        del header (antes del primer bullet placeholder), preservando el resto
        del documento intacto. Si la sección no existe, la crea al final.

        Args:
            section: Nombre de la sección (ej. "Proyectos Activos").
            note: Texto de la nota a añadir (se formatea como bullet).
        """
        with self._write_lock:
            try:
                content = self.get_context(use_cache=False)
                if not content:
                    self._ensure_file()
                    content = self.get_context(use_cache=False)

                lines = content.splitlines()
                note_line = f"- {note.strip()}"
                section_lower = section.strip().lower()

                # Evitar duplicados exactos dentro de la sección objetivo
                header_idx = None
                for i, ln in enumerate(lines):
                    if ln.startswith("## ") and section_lower in ln.lower():
                        header_idx = i
                        break

                if header_idx is not None:
                    # Verificar si la nota ya existe en esta sección
                    end_idx = len(lines)
                    for j in range(header_idx + 1, len(lines)):
                        if lines[j].startswith("## "):
                            end_idx = j
                            break
                    section_body = lines[header_idx + 1:end_idx]
                    if any(note_line == s.strip() for s in section_body):
                        return True  # Ya existe, no duplicar

                    # Insertar justo después del header
                    lines.insert(header_idx + 1, note_line)
                else:
                    # Sección no encontrada: crearla al final
                    if lines and lines[-1].strip():
                        lines.append("")
                    lines.append(f"## {section}")
                    lines.append(note_line)

                new_content = "\n".join(lines).rstrip() + "\n"
                return self._write(new_content)
            except Exception as e:
                logger.warning("UserContextManager: error en append_note: %s", e)
                return False

    def update_field(self, field_label: str, value: str) -> bool:
        """Actualiza o crea un campo tipo '- Label: valor' en cualquier sección."""
        with self._write_lock:
            try:
                content = self.get_context(use_cache=False)
                lines = content.splitlines()
                field_lower = field_label.strip().lower()
                out = []
                replaced = False
                for ln in lines:
                    stripped = ln.strip()
                    if stripped.startswith("- ") and ":" in stripped:
                        label = stripped[2:].split(":", 1)[0].strip().lower()
                        if label == field_lower:
                            indent = ln[: len(ln) - len(ln.lstrip())]
                            out.append(f"{indent}- {field_label.strip()}: {value.strip()}")
                            replaced = True
                            continue
                    out.append(ln)

                if not replaced:
                    # Añadir bajo "Identidad" si existe, si no al final
                    final = []
                    placed = False
                    for ln in out:
                        final.append(ln)
                        if ln.startswith("## Identidad"):
                            placed = True
                            continue
                        if placed and ln.startswith("## "):
                            final.pop()
                            final.append(f"- {field_label.strip()}: {value.strip()}")
                            final.append("")
                            final.append(ln)
                            placed = False
                    if placed:
                        final.append(f"- {field_label.strip()}: {value.strip()}")
                    out = final

                new_content = "\n".join(out).rstrip() + "\n"
                return self._write(new_content)
            except Exception as e:
                logger.warning("UserContextManager: error en update_field: %s", e)
                return False

    def _write(self, content: str) -> bool:
        """Escribe el contenido al disco de forma atómica y refresca el cache."""
        try:
            tmp_path = self.file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, self.file_path)
            self._cache = content
            self._cache_mtime = os.path.getmtime(self.file_path)
            return True
        except Exception as e:
            logger.warning("UserContextManager: error escribiendo: %s", e)
            return False

    def invalidate_cache(self) -> None:
        """Fuerza la relectura desde disco en la próxima llamada."""
        self._cache = None
        self._cache_mtime = 0.0
