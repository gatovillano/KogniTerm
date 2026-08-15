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
    max_lines: int = 200,
    max_bytes: int = 15360,
    head_lines: int = 25,
    tail_lines: int = 35,
) -> str:
    """
    Recorta e inspecciona inteligentemente salidas de herramientas extensas.

    - Salidas dentro de los límites de líneas/bytes se mantienen 100% INTACTAS.
    - Salidas masivas:
      1. Se guarda la salida completa e inalterada en ~/.kogniterm/logs/.
      2. Se preservan las primeras N líneas (encabezado) y últimas M líneas (resumen).
      3. Se escanear y preservan todas las líneas intermedias que contienen errores o excepciones.
      4. Se incluye la referencia al archivo de log completo para lectura bajo demanda.
    """
    if not output or not isinstance(output, str):
        return output or ""

    lines = output.splitlines()
    total_lines = len(lines)
    total_bytes = len(output.encode("utf-8", errors="replace"))

    # Si la salida está dentro de los límites normales, se retorna intacta
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return output

    # Salida extensa: Guardar copia completa en disco para inspección bajo demanda
    log_filepath = _save_full_log(output, tool_name)

    # Identificar líneas a incluir
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
            # Agregar la línea de error y contexto inmediato
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
        f"ℹ️ [KogniTerm: Salida de {tool_name} extensa ({total_lines} líneas, {total_bytes // 1024} KB). "
        f"Se muestran líneas clave y errores. Log completo en: {log_filepath}]\n"
    )

    return header_notice + "\n".join(pruned_lines)


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
