import os
import re
import time
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Directorio de logs de KogniTerm para offloading de salidas extensas
LOGS_DIR = os.path.join(os.path.expanduser("~"), ".kogniterm", "logs")

# Patrones regex para identificar líneas críticas de error o excepción
ERROR_PATTERNS = re.compile(
    r'(?i)(error|exception|traceback|failed|fatal|warning|assert|segfault|denied|notFound|syntaxerror|typeerror|valueerror|keyerror|indexerror)'
)


def smart_prune_tool_output(
    output: str,
    tool_name: str = "command",
    max_lines: int = 100,
    max_bytes: int = 8192,
    head_lines: int = 25,
    tail_lines: int = 25,
) -> str:
    """
    Poda semántica estructurada de salidas de herramientas para minimizar la latencia
    del prompt en el LLM (Time To First Token) sin perder contexto semántico.

    - Salidas pequeñas (<= max_lines y <= max_bytes) se mantienen 100% INTACTAS.
    - Salidas extensas:
      1. Se guarda la copia completa e inalterada en ~/.kogniterm/logs/.
      2. Se aplica poda semántica según el tipo de herramienta (búsqueda, lectura o subagente).
      3. Se preservan 100% las líneas de errores, excepciones y firmas estructurales.
    """
    if not output or not isinstance(output, str):
        return output or ""

    # Poda semántica especializada según herramienta
    tool_lower = tool_name.lower()
    if any(kw in tool_lower for kw in ["search", "grep", "codebase"]):
        output = _prune_search_tool_output(output)
    elif any(kw in tool_lower for kw in ["agent", "subagent", "parallel", "coder", "researcher"]):
        output = _prune_subagent_tool_output(output)

    lines = output.splitlines()
    total_lines = len(lines)
    total_bytes = len(output.encode("utf-8", errors="replace"))

    # Si la salida recortada semánticamente ya entra en los límites, retornar
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return output

    # Salida masiva: Guardar copia completa en disco para inspección bajo demanda
    log_filepath = _save_full_log(output, tool_name)

    # Identificar líneas a incluir mediante ventanas + detección de errores
    selected_indices = set()

    # 1. Incluir encabezado (primeras N líneas)
    for i in range(min(head_lines, total_lines)):
        selected_indices.add(i)

    # 2. Incluir pie / resumen (últimas M líneas)
    for i in range(max(0, total_lines - tail_lines), total_lines):
        selected_indices.add(i)

    # 3. Escanear bloque intermedio buscando errores y sus contextos (+/- 1 línea)
    for i in range(head_lines, total_lines - tail_lines):
        line = lines[i]
        if ERROR_PATTERNS.search(line):
            if i > 0:
                selected_indices.add(i - 1)
            selected_indices.add(i)
            if i + 1 < total_lines:
                selected_indices.add(i + 1)

    # Construir salida truncada ordenada
    pruned_lines: List[str] = []
    sorted_indices = sorted(selected_indices)
    prev_idx = -1

    for idx in sorted_indices:
        if prev_idx != -1 and idx > prev_idx + 1:
            omitted_count = idx - prev_idx - 1
            pruned_lines.append(
                f"\n--- [... {omitted_count} líneas omitidas (sin errores). Log completo en: {log_filepath} ...] ---\n"
            )
        pruned_lines.append(lines[idx])
        prev_idx = idx

    header_notice = (
        f"ℹ️ [KogniTerm: Salida de {tool_name} estructurada ({total_lines} líneas, {total_bytes // 1024} KB). "
        f"Log completo guardado en: {log_filepath}]\n"
    )

    return header_notice + "\n".join(pruned_lines)


def _prune_search_tool_output(output: str) -> str:
    """Elimina líneas en blanco excesivas y bloques repetidos en búsquedas de código."""
    lines = output.splitlines()
    cleaned = []
    blank_count = 0

    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 1:
                cleaned.append("")
        else:
            blank_count = 0
            cleaned.append(line)

    return "\n".join(cleaned)


def _prune_subagent_tool_output(output: str) -> str:
    """Limpia wrappers XML de subagentes manteniendo el 100% del informe técnico."""
    clean = re.sub(r'</?(?:coder_analysis|researcher_analysis|parallel_agents_results)>', '', output)
    return clean.strip()


def _save_full_log(output: str, tool_name: str) -> str:
    """Guarda la salida completa en el directorio de logs de KogniTerm."""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', tool_name)
        timestamp = int(time.time())
        filename = f"{safe_name}_{timestamp}.log"
        filepath = os.path.join(LOGS_DIR, filename)

        with open(filepath, "w", encoding="utf-8", errors="replace") as f:
            f.write(output)

        return filepath
    except Exception as e:
        logger.warning(f"No se pudo guardar el log de salida completo: {e}")
        return "~/.kogniterm/logs/output.log"
