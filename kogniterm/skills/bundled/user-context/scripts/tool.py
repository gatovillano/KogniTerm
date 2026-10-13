"""
user-context — Herramientas para gestionar el Contexto Global de Usuario.

Expone operaciones sobre `~/.kogniterm/user_context.md`, la memoria global
del usuario compartida entre todos los proyectos de KogniTerm. Permite al
agente guardar de forma proactiva información duradera sobre el usuario
(identidad, preferencias, stack, proyectos) para que sea recordada siempre.

Convención: las funciones públicas terminan en `_tool` para que el
SkillLoader las exponga como herramientas independientes.
"""

from typing import Optional


def _get_manager():
    from kogniterm.core.context.user_context_manager import UserContextManager
    return UserContextManager.get_instance()


def user_context_read_tool() -> str:
    """Lee el contexto global de usuario completo (~/.kogniterm/user_context.md).

    Úsalo para consultar el perfil persistente del usuario antes de responder,
    o para verificar qué información ya está guardada antes de escribir.
    """
    try:
        ucm = _get_manager()
        content = ucm.get_context()
        if not content:
            return "El contexto global de usuario está vacío o no existe."
        populated = "poblado" if ucm.is_populated() else "aún sin poblar (plantilla)"
        return f"Contexto global de usuario ({populated}):\n\n{content}"
    except Exception as e:
        return f"Error leyendo el contexto global de usuario: {e}"


def user_context_update_field_tool(field_label: str, value: str) -> str:
    """Crea o actualiza un campo '- Label: valor' en el contexto global de usuario.

    Args:
        field_label: Etiqueta del campo (ej. 'Nombre', 'Ubicación', 'Idioma preferido').
        value: Valor a asignar al campo.
    """
    if not field_label or not value:
        return "Error: se requieren 'field_label' y 'value'."
    try:
        ucm = _get_manager()
        ok = ucm.update_field(field_label, value)
        if ok:
            return f"Campo '{field_label}' actualizado a '{value}' en el contexto global de usuario."
        return f"No se pudo actualizar el campo '{field_label}'."
    except Exception as e:
        return f"Error actualizando campo '{field_label}': {e}"


def user_context_append_note_tool(section: str, note: str) -> str:
    """Añade una nota (bullet) bajo una sección del contexto global de usuario.

    Args:
        section: Nombre de la sección (ej. 'Proyectos Activos', 'Stack y Herramientas',
                 'Preferencias de Trabajo'). Si no existe, se crea al final.
        note: Texto de la nota a guardar.
    """
    if not section or not note:
        return "Error: se requieren 'section' y 'note'."
    try:
        ucm = _get_manager()
        ok = ucm.append_note(section, note)
        if ok:
            return f"Nota añadida a la sección '{section}' del contexto global de usuario."
        return f"No se pudo añadir la nota a la sección '{section}'."
    except Exception as e:
        return f"Error añadiendo nota a '{section}': {e}"
