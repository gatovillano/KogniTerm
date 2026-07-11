"""
file_editor.py — Editor de archivos con matcher estricto y feedback rico
=========================================================================

Cambios principales (hardening 2026-07):
- FlexibleMatcher: coincidencia exacta por defecto. Fuzzy DESACTIVADO por
  defecto; se activa con fuzzy=True. Cuando se activa, los tokens se
  buscan en la misma línea lógica (sin \\n como \\s*).
- advanced_file_editor acepta require_unique (default True), context_hint,
  fuzzy y devuelve matched_span + applied_diff en éxito.
- replace_lines: comparación de target_content normalizada.
- insert_after_match: sin doble newline.
- _apply_operation_pure(content, op) -> str: helper sin I/O para que
  batch_edit pueda componer operaciones en memoria antes de escribir.
"""

import os
import difflib
import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from ._utils import clean_path


# ---------------------------------------------------------------------------
# Normalizacion de entradas (Task 2)
# ---------------------------------------------------------------------------

def _strip_line_numbers(text: Optional[str]) -> Optional[str]:
    """Elimina prefijos de numero de linea del tipo '  12 | ' o '12| '.

    Los LLMs frecuentemente incluyen numeros de linea al copiar fragmentos
    de archivos mostrados con numeracion. Esta funcion los elimina antes
    de buscar el target en el archivo real.
    """
    if text is None:
        return None
    lines = text.splitlines(keepends=True)
    cleaned: List[str] = []
    for line in lines:
        # Patron: espacios opcionales, digitos, espacio opcional, '|', espacio opcional
        cleaned.append(re.sub(r'^\s*\d+\s*\|\s?', '', line))
    return ''.join(cleaned)


def _normalize_input(text: Optional[str]) -> Optional[str]:
    """Combina strip de numeros de linea y normalizacion de newlines a LF."""
    if text is None:
        return None
    return _strip_line_numbers(text).replace('\r\n', '\n')


# Intentar importar RaceConditionGuard del core
try:
    from kogniterm.core.race_condition_guard import RaceConditionGuard, RaceConditionDetected
except ImportError:
    # Fallback si no está disponible (ej: entorno de test incompleto)
    class RaceConditionGuard:
        @staticmethod
        def validate_write(state, path, content): return True, ""
        @staticmethod
        def register_write(state, path, content): pass
    class RaceConditionDetected(Exception): pass

logger = logging.getLogger(__name__)


class FlexibleMatcher:
    """Busca coincidencias de texto. EXACTO por defecto; fuzzy solo opt-in.

    El fuzzy original era peligrosamente permisivo: trataba CUALQUIER
    espacio (incluyendo saltos de línea con re.DOTALL) como opcional
    entre tokens. Eso producia "match" de 30 lineas cuando el LLM
    pedia un target de 1 linea, llevando a ediciones erraticas. La
    version nueva exige tokens en la misma linea logica y devuelve
    un score para que el caller decida si lo acepta.
    """

    @staticmethod
    def normalize(text: str) -> str:
        """Normaliza el texto: colapsa espacios y unifica saltos."""
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join([line for line in lines if line])

    @staticmethod
    def find_match(
        content: str,
        target: str,
        *,
        fuzzy: bool = False,
    ) -> List[Dict[str, Any]]:
        """Devuelve TODAS las coincidencias exactas (o fuzzy si fuzzy=True).

        Cada item es un dict con start, end, matched_text, line_start,
        line_end, fuzzy, score. Si no hay matches, lista vacia.
        """
        if not target:
            return []

        # 1. Coincidencia exacta (SIEMPRE primero)
        exact_matches: List[Dict[str, Any]] = []
        start = 0
        while True:
            idx = content.find(target, start)
            if idx == -1:
                break
            exact_matches.append(FlexibleMatcher._make_match(content, target, idx, fuzzy=False, score=1.0))
            start = idx + 1

        if exact_matches or not fuzzy:
            return exact_matches

        # 2. Fuzzy: tolerancia de whitespace flexible.
        #
        # Casos soportados:
        #   A) Target de UNA sola linea: los tokens pueden estar separados
        #      por whitespace INCLUYENDO un unico salto de linea. Esto permite
        #      que el LLM proporcione "def foo():  return 1" y matchee con
        #      "def foo():\n    return 1" en el archivo.
        #      Para no cruzar MULTIPLES lineas (prevencion de match erratico),
        #      el patron usa [\s] pero se valida con score >= 0.6.
        #
        #   B) Target de MULTIPLES lineas: cada linea se tokeniza por separado
        #      y se une con \r?\n. No se permiten newlines extra entre lineas.
        #
        target_lines = target.splitlines()
        if not target_lines:
            return []

        if len(target_lines) == 1:
            # Caso A: target de una linea — tokens pueden cruzar UN salto.
            tokens = [t for t in re.split(r'\s+', target.strip()) if t]
            if not tokens:
                return []
            # Whitespace entre tokens: cualquier blanco incluyendo hasta UN \n.
            # Usamos [\s] pero verificamos con score que no se extiendan demasiado.
            sep = r'[^\S\n]*\n?[^\S\n]*'
            pattern = sep.join(re.escape(t) for t in tokens)
        else:
            # Caso B: target multilinea — cada linea con tokens horizontales.
            line_patterns: List[str] = []
            for tline in target_lines:
                ltokens = [t for t in re.split(r'[ \t]+', tline.strip()) if t]
                if ltokens:
                    line_patterns.append(r'[ \t]*'.join(re.escape(t) for t in ltokens))
                else:
                    line_patterns.append(r'')  # Linea vacia
            pattern = r'\r?\n[ \t]*'.join(line_patterns)

        try:
            regex = re.compile(pattern)
        except re.error:
            return []

        fuzzy_matches: List[Dict[str, Any]] = []
        for m in regex.finditer(content):
            span_text = m.group(0)
            # Score: ratio de similitud entre target y matched text.
            score = difflib.SequenceMatcher(None, target, span_text, autojunk=False).ratio()
            if score < 0.6:
                continue  # Descartar matches claramente no relacionados.
            fuzzy_matches.append(FlexibleMatcher._make_match(
                content, span_text, m.start(), fuzzy=True, score=score
            ))

        return fuzzy_matches

    @staticmethod
    def _make_match(content: str, matched: str, start: int, *, fuzzy: bool, score: float) -> Dict[str, Any]:
        end = start + len(matched)
        # Calcular numeros de linea (1-based, contando \n).
        line_start = content.count('\n', 0, start) + 1
        line_end = content.count('\n', 0, end) + 1
        return {
            "start": start,
            "end": end,
            "matched_text": matched,
            "line_start": line_start,
            "line_end": line_end,
            "fuzzy": fuzzy,
            "score": round(score, 4),
        }

    @staticmethod
    def find_unique(
        content: str,
        target: str,
        *,
        fuzzy: bool = False,
        require_unique: bool = True,
        context_hint: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Encuentra una coincidencia UNICA o devuelve None.

        - Si hay 0 matches exactos y fuzzy=False -> None.
        - Si hay >1 matches exactos y require_unique=True:
            - Si context_hint matchea dentro de ±20 lineas de UNO solo -> ese.
            - Si no -> lanza excepcion MultipleMatchesError.
        - Si hay 1 match exacto -> ese.
        - Si fuzzy=True y no hay exactos -> aplica fuzzy.
        """
        matches = FlexibleMatcher.find_match(content, target, fuzzy=fuzzy)
        if not matches:
            return None

        if len(matches) == 1:
            return matches[0]

        if not require_unique:
            return matches[0]

        if context_hint:
            # Buscar la ubicacion del hint y elegir el match mas CERCANO.
            hint_matches = FlexibleMatcher.find_match(content, context_hint, fuzzy=True)
            if hint_matches:
                best_match = None
                min_dist = float('inf')
                for candidate in matches:
                    for h in hint_matches:
                        dist = abs(candidate["line_start"] - h["line_start"])
                        if dist < min_dist:
                            min_dist = dist
                            best_match = candidate
                if best_match is not None:
                    return best_match
            # Si context_hint no ayuda a desambiguar, error.
            raise MultipleMatchesError(
                target=target,
                matches=matches,
                hint=context_hint,
            )

        raise MultipleMatchesError(target=target, matches=matches)

    @staticmethod
    def _hint_near(content: str, match: Dict[str, Any], hint: str, window: int = 20) -> bool:
        """Devuelve True si 'hint' aparece en las ±window lineas del match."""
        if not hint:
            return False
        line_idx = match["line_start"] - 1
        lines = content.splitlines()
        lo = max(0, line_idx - window)
        hi = min(len(lines), line_idx + window)
        window_text = "\n".join(lines[lo:hi])
        return hint in window_text


class MultipleMatchesError(Exception):
    """El target aparece varias veces y no se puede desambiguar."""

    def __init__(self, target: str, matches: List[Dict[str, Any]], hint: Optional[str] = None):
        self.target = target
        self.matches = matches
        self.hint = hint
        locs = ", ".join(
            f"line {m['line_start']}:{m['line_end']}" for m in matches[:5]
        )
        more = f" (+{len(matches) - 5} mas)" if len(matches) > 5 else ""
        msg = (
            f"'target_content' aparece {len(matches)} veces en {locs}{more}. "
            f"Se especifico. Para desambiguar, anada 'context_hint' con un "
            f"fragmento unico cercano, o use 'replace_lines' por rango."
        )
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Funcion pura de transformacion (sin I/O). Usada por batch_edit.
# ---------------------------------------------------------------------------

def _apply_operation_pure(content: str, op: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Aplica una operacion a un string en memoria.

    Devuelve (nuevo_contenido, matched_span_o_None). matched_span se
    rellena para replace_block / insert_after_match / insert_before_match /
    delete_lines. Para acciones que no producen span (prepend, append,
    full_replacement) devuelve None.

    Lanza ValueError si la operacion no se puede aplicar (target no
    encontrado, target ambiguo, etc.). NO escribe a disco.
    """
    action = op.get("action")
    # --- Normalizacion de entradas (Task 2) ---
    # Stripear numeros de linea y unificar saltos de linea a LF.
    target_content = _normalize_input(op.get("target_content"))
    replacement_content = _normalize_input(op.get("replacement_content")) or ""
    content_arg = _normalize_input(op.get("content")) or ""
    # Detectar CRLF y normalizar el contenido del archivo a LF para trabajar.
    # La restauracion ocurre al FINAL de esta funcion, de forma centralizada.
    has_crlf = '\r\n' in content
    if has_crlf:
        content = content.replace('\r\n', '\n')
    line_number = op.get("line_number")
    end_line = op.get("end_line")
    regex_pattern = op.get("regex_pattern")
    fuzzy = bool(op.get("fuzzy", False))
    require_unique = bool(op.get("require_unique", True))
    context_hint = op.get("context_hint")

    # Aplicar la operacion en espacio LF.
    new_content, matched_span = _apply_op_lf(
        content, action, target_content, replacement_content, content_arg,
        line_number, end_line, regex_pattern, fuzzy, require_unique, context_hint,
    )

    # Restaurar CRLF si el archivo original lo usaba.
    if has_crlf:
        new_content = new_content.replace('\n', '\r\n')

    return new_content, matched_span


def _apply_op_lf(
    content: str,
    action: Optional[str],
    target_content: Optional[str],
    replacement_content: str,
    content_arg: str,
    line_number: Optional[int],
    end_line: Optional[int],
    regex_pattern: Optional[str],
    fuzzy: bool,
    require_unique: bool,
    context_hint: Optional[str],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Implementacion interna que opera siempre en espacio LF."""
    lines = content.splitlines(keepends=True)

    if action == "insert_line":
        if not isinstance(line_number, int) or line_number < 1:
            raise ValueError("line_number debe ser entero positivo (1-based).")
        text = content_arg if content_arg.endswith("\n") else content_arg + "\n"
        idx = line_number - 1
        if idx >= len(lines):
            lines.append(text)
        else:
            lines.insert(idx, text)
        return "".join(lines), None

    if action == "replace_regex":
        if not regex_pattern or replacement_content is None:
            raise ValueError("Se requieren 'regex_pattern' y 'replacement_content'.")
        re.compile(regex_pattern)
        new = re.sub(regex_pattern, replacement_content, content)
        return new, None

    if action == "replace_block":
        if target_content is None or replacement_content is None:
            raise ValueError("Se requieren 'target_content' y 'replacement_content'.")
        try:
            m = FlexibleMatcher.find_unique(
                content, target_content,
                fuzzy=fuzzy, require_unique=require_unique, context_hint=context_hint,
            )
        except MultipleMatchesError as e:
            raise ValueError(str(e)) from e
        if m is None:
            raise ValueError(
                "target_content no aparece en el archivo. "
                "Verifique que el fragmento sea exacto, o use replace_lines por rango."
            )
        # --- Indentation alignment (Task 3.2) ---
        # Si el target y el match en disco tienen distinta indentacion,
        # ajustamos el replacement para preservar el nivel real del archivo.
        match_first_line = content[m["start"]:m["end"]].split('\n')[0]
        target_first_line = target_content.split('\n')[0]
        match_indent = len(match_first_line) - len(match_first_line.lstrip())
        target_indent = len(target_first_line) - len(target_first_line.lstrip())
        indent_diff = match_indent - target_indent
        if indent_diff != 0:
            rep_lines = replacement_content.splitlines(keepends=True)
            adjusted: List[str] = []
            for rline in rep_lines:
                if rline.strip():  # Solo ajustar lineas no vacias
                    if indent_diff > 0:
                        adjusted.append(' ' * indent_diff + rline)
                    else:
                        strip_n = min(abs(indent_diff), len(rline) - len(rline.lstrip()))
                        adjusted.append(rline[strip_n:])
                else:
                    adjusted.append(rline)
            replacement_content = ''.join(adjusted)
        new = content[:m["start"]] + replacement_content + content[m["end"]:]
        return new, m

    if action == "replace_lines":
        if not isinstance(line_number, int) or line_number < 1:
            raise ValueError("line_number (inicio) debe ser entero positivo.")
        if replacement_content is None:
            raise ValueError("Se requiere 'replacement_content'.")
        start_idx = line_number - 1
        end_idx = (end_line - 1) if isinstance(end_line, int) else start_idx
        if start_idx >= len(lines):
            raise ValueError(f"line_number {line_number} esta fuera de rango.")
        if target_content:
            actual = "".join(lines[start_idx:end_idx + 1])
            if not FlexibleMatcher.find_match(actual, target_content, fuzzy=False):
                raise ValueError(
                    f"El contenido de las lineas {line_number}-{end_line or line_number} "
                    f"no coincide con 'target_content'."
                )
        new_text_lines = replacement_content.splitlines(keepends=True)
        if replacement_content.endswith("\n") and not new_text_lines[-1].endswith("\n"):
            new_text_lines[-1] += "\n"
        lines[start_idx:end_idx + 1] = new_text_lines
        return "".join(lines), {
            "line_start": line_number,
            "line_end": end_line or line_number,
            "fuzzy": False,
            "score": 1.0,
        }

    if action == "insert_after_match":
        if target_content is None or content_arg is None:
            raise ValueError("Se requieren 'target_content' y 'content'.")
        try:
            m = FlexibleMatcher.find_unique(
                content, target_content,
                fuzzy=fuzzy, require_unique=require_unique, context_hint=context_hint,
            )
        except MultipleMatchesError as e:
            raise ValueError(str(e)) from e
        if m is None:
            raise ValueError("target_content no aparece en el archivo.")
        text = content_arg
        # --- Fix doble newline (Task 4.1) ---
        # Determinar el punto exacto de insercion y el prefijo a usar.
        #
        # Caso 1: matched_text ya incluye su propio \n (matcheo linea completa).
        #   -> insertar en m["end"], sin anadir \n extra.
        # Caso 2: matched_text NO incluye \n, pero el siguiente char en el
        #   archivo SÍ es \n (match inline de "def foo():" cuando el archivo
        #   tiene "def foo():\n    return 1").
        #   -> insertar DESPUES del \n existente (insert_pos = m["end"] + 1),
        #      sin anadir \n al frente de text.
        # Caso 3: matched_text NO incluye \n y el siguiente char tampoco es \n.
        #   -> insertar en m["end"] con \n al frente de text.
        matched_text = m["matched_text"]
        next_char = content[m["end"]:m["end"] + 1] if m["end"] < len(content) else ''
        if matched_text.endswith('\n'):
            # Caso 1: el match incluye su newline.
            insert_pos = m["end"]
            if text.startswith('\n'):
                text = text[1:]
        elif next_char == '\n':
            # Caso 2: el \n existente actua de separador; insertar despues de el.
            insert_pos = m["end"] + 1
        else:
            # Caso 3: no hay newline — lo aniadimos.
            insert_pos = m["end"]
            if not text.startswith('\n'):
                text = '\n' + text
        if not text.endswith('\n'):
            text = text + '\n'
        new = content[:insert_pos] + text + content[insert_pos:]
        return new, m

    if action == "insert_before_match":
        if target_content is None or content_arg is None:
            raise ValueError("Se requieren 'target_content' y 'content'.")
        try:
            m = FlexibleMatcher.find_unique(
                content, target_content,
                fuzzy=fuzzy, require_unique=require_unique, context_hint=context_hint,
            )
        except MultipleMatchesError as e:
            raise ValueError(str(e)) from e
        if m is None:
            raise ValueError("target_content no aparece en el archivo.")
        text = content_arg
        if not text.endswith("\n"):
            text = text + "\n"
        new = content[:m["start"]] + text + content[m["start"]:]
        return new, m

    if action == "delete_lines":
        if not isinstance(line_number, int) or line_number < 1:
            raise ValueError("line_number debe ser entero positivo.")
        start_idx = line_number - 1
        end_idx = (end_line - 1) if isinstance(end_line, int) else start_idx
        if start_idx >= len(lines):
            raise ValueError(f"line_number {line_number} esta fuera de rango.")
        del lines[start_idx:end_idx + 1]
        return "".join(lines), {
            "line_start": line_number,
            "line_end": end_line or line_number,
            "fuzzy": False,
            "score": 1.0,
        }

    if action == "prepend_content":
        if content_arg is None:
            raise ValueError("Se requiere 'content'.")
        text = content_arg if content_arg.endswith("\n") else content_arg + "\n"
        return text + content, None

    if action == "append_content":
        if content_arg is None:
            raise ValueError("Se requiere 'content'.")
        text = content_arg if content_arg.endswith("\n") else content_arg + "\n"
        return content + text, None

    if action == "full_replacement":
        if content_arg is None:
            raise ValueError("Se requiere 'content' para reemplazo total.")
        new = content_arg
        if new and not new.endswith("\n"):
            new = new + "\n"
        return new, None

    raise ValueError(f"Accion '{action}' no soportada.")


# ---------------------------------------------------------------------------
# Funcion principal: mantiene la API historica, anade matched_span / applied_diff
# ---------------------------------------------------------------------------

def advanced_file_editor(
    path: str,
    action: str,
    content: Optional[str] = None,
    line_number: Optional[int] = None,
    regex_pattern: Optional[str] = None,
    replacement_content: Optional[str] = None,
    target_content: Optional[str] = None,
    end_line: Optional[int] = None,
    confirm: bool = False,
    *,
    fuzzy: bool = False,
    require_unique: bool = True,
    context_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Herramienta premium de edicion de archivos.

    Cambios (2026-07):
    - fuzzy: opt-in, default False.
    - require_unique: default True. Si target aparece > 1 vez, error
      salvo que context_hint desambigue.
    - context_hint: substring que debe estar dentro de las ±20 lineas
      del match correcto.
    - Devuelve matched_span y applied_diff en exito.
    """
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado"}

    op = {
        "action": action,
        "content": content,
        "line_number": line_number,
        "regex_pattern": regex_pattern,
        "replacement_content": replacement_content,
        "target_content": target_content,
        "end_line": end_line,
        "fuzzy": fuzzy,
        "require_unique": require_unique,
        "context_hint": context_hint,
    }

    # 1. Leer contenido actual
    try:
        if not os.path.exists(path):
            if action in ["prepend_content", "append_content", "full_replacement"]:
                original_content = ""
            else:
                return {"error": f"El archivo '{path}' no existe para la accion '{action}'."}
        else:
            with open(path, "r", encoding="utf-8", newline="") as f:
                original_content = f.read()
    except Exception as e:
        return {"error": f"Error al leer '{path}': {e}"}

    original_lines = original_content.splitlines(keepends=True)

    # 2. Aplicar transformacion en memoria
    try:
        new_content, matched_span = _apply_operation_pure(original_content, op)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error al transformar contenido: {e}"}

    new_lines = new_content.splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(
        original_lines, new_lines,
        fromfile=f"a/{path}", tofile=f"b/{path}",
    ))

    if not diff:
        return {"status": "no_changes", "message": "No se detectaron cambios a realizar."}

    if not confirm:
        return {
            "status": "requires_confirmation",
            "action_description": f"editar sofisticadamente el archivo '{path}' ({action})",
            "operation": "advanced_file_editor",
            "args": {
                "path": path,
                "action": action,
                "content": content,
                "line_number": line_number,
                "regex_pattern": regex_pattern,
                "replacement_content": replacement_content,
                "target_content": target_content,
                "end_line": end_line,
                "fuzzy": fuzzy,
                "require_unique": require_unique,
                "context_hint": context_hint,
                "confirm": True,
            },
            "diff": diff,
            "matched_span": matched_span,
        }

    # 3. Race Condition Guard
    agent_state = getattr(advanced_file_editor, 'agent_state', None)
    if agent_state and os.path.exists(path):
        try:
            is_safe, msg = RaceConditionGuard.validate_write(agent_state, path, original_content)
            if not is_safe:
                return {"status": "error", "message": f"RACE CONDITION DETECTADA: {msg}"}
        except Exception as e:
            logger.warning(f"Error en validacion de Race Condition: {e}")

    # 4. Escribir cambios
    try:
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        if agent_state:
            RaceConditionGuard.register_write(agent_state, path, new_content)

        return {
            "status": "success",
            "path": path,
            "message": f"Archivo '{path}' actualizado exitosamente usando '{action}'.",
            "matched_span": matched_span,
            "applied_diff": diff,
        }
    except Exception as e:
        return {"status": "error", "message": f"Error al escribir cambios: {e}"}


# Aliases para compatibilidad con prompts de agentes.
sophisticated_editor_tool = advanced_file_editor
replace_file_content = advanced_file_editor

# Permitir que el SkillManager inyecte el estado del agente en todos los alias.
advanced_file_editor.agent_state = None
sophisticated_editor_tool.agent_state = None
replace_file_content.agent_state = None

# Esquema explicito y robusto para guiar al LLM.
common_editor_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo a editar (absoluta o relativa al cwd)."},
        "action": {
            "type": "string",
            "description": "Estrategia de edicion.",
            "enum": [
                "insert_line", "replace_block", "replace_lines",
                "insert_after_match", "insert_before_match",
                "replace_regex", "delete_lines", "prepend_content",
                "append_content", "full_replacement",
            ],
        },
        "content": {"type": "string", "description": "Texto a insertar (insert_line, insert_after_match, insert_before_match, prepend, append, full_replacement)."},
        "target_content": {"type": "string", "description": "Bloque de texto a BUSCAR (replace_block, insert_after/before_match, replace_lines)."},
        "replacement_content": {"type": "string", "description": "Texto NUEVO (replace_block, replace_lines, replace_regex)."},
        "line_number": {"type": "integer", "description": "Linea de inicio 1-based."},
        "end_line": {"type": "integer", "description": "Linea de fin 1-based para rangos."},
        "regex_pattern": {"type": "string", "description": "Patron regex para replace_regex."},
        "fuzzy": {"type": "boolean", "description": "Permitir match flexible en replace_block/insert_*_match. Default: false.", "default": False},
        "require_unique": {"type": "boolean", "description": "Exigir match unico. Default: true.", "default": True},
        "context_hint": {"type": "string", "description": "Substring cercano para desambiguar entre multiples matches."},
        "confirm": {"type": "boolean", "description": "Confirmacion automatica.", "default": False},
    },
    "required": ["path", "action"],
}

advanced_file_editor.parameters_schema = common_editor_schema
sophisticated_editor_tool.parameters_schema = common_editor_schema
replace_file_content.parameters_schema = common_editor_schema

tool_schema = {
    "name": "advanced_file_editor",
    "description": (
        "Herramienta premium de edicion de archivos. "
        "Soporta multiples estrategias (bloques, lineas, regex, insercion, borrado). "
        "Match EXACTO por defecto; fuzzy solo opt-in con fuzzy=true. "
        "Devuelve matched_span y applied_diff en el resultado para que el LLM verifique."
    ),
    "parameters": common_editor_schema,
}
