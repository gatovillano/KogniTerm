"""
Parseo de tool calls desde texto LLM.

Soporta múltiples estrategias de parseo:
- Explícito: marcadores como <TOOL>...</TOOL>
- JSON: bloques ```json o JSON inline
- Legacy: formatos antiguos
- Bullets: listas con - o *
"""
import json
import re
from typing import List, Optional, Tuple

from kogniterm.core.llm_services.types import ParsedToolCall


class ParseError(Exception):
    """Error durante el parseo de tool calls."""


class DuplicateToolCallError(ParseError):
    """Se encontraron tool calls duplicadas."""


def _normalize_json_string(text: str) -> str:
    """Normaliza un string JSON quitando comillas extras y limpiando."""
    text = text.strip()
    # Si está triple-backtiqueado, quitarlo
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def _extract_json_block(text: str) -> Optional[str]:
    """Extrae el primer bloque JSON válido de un texto."""
    text = _normalize_json_string(text)

    # Intentar parsear todo el texto como JSON
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Buscar objeto JSON entre llaves balanceadas
    brace_count = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{' and start is None:
            start = i
            brace_count = 1
        elif ch == '{' and start is not None:
            brace_count += 1
        elif ch == '}' and start is not None:
            brace_count -= 1
            if brace_count == 0:
                candidate = text[start:i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue
    return None


def _parse_tool_calls_explicit(text: str) -> List[ParsedToolCall]:
    """
    Parsea tool calls marcados explícitamente con etiquetas.

    Formato:
        <TOOL>nombre|args_json|id|confianza</TOOL>
    """
    results = []
    pattern = r'<TOOL>(.*?)</TOOL>'
    for match in re.finditer(pattern, text, re.DOTALL):
        content = match.group(1).strip()
        parts = content.split('|')
        if len(parts) >= 3:
            name = parts[0].strip()
            args_str = parts[1].strip()
            tool_id = parts[2].strip()
            confidence = float(parts[3].strip()) if len(parts) > 3 else 1.0
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            results.append(
                ParsedToolCall(
                    id=tool_id,
                    name=name,
                    args=args,
                    confidence=confidence,
                    source_pattern="explicit",
                    raw_text=content,
                )
            )
    return results


def _parse_tool_calls_json(text: str) -> List[ParsedToolCall]:
    """
    Parsea tool calls en formato JSON.

    Espera una lista de objetos o un objeto simple con:
        - name/id o tool_name/tool_id
        - arguments o args
    """
    results = []
    json_text = _extract_json_block(text)
    if not json_text:
        return results

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return results

    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        return results

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("tool_name")
        tool_id = item.get("id") or item.get("tool_id") or f"json_{idx}"
        args = item.get("arguments") or item.get("args") or {}
        confidence = float(item.get("confidence", 1.0))
        if name:
            results.append(
                ParsedToolCall(
                    id=tool_id,
                    name=name,
                    args=args if isinstance(args, dict) else {},
                    confidence=confidence,
                    source_pattern="json",
                    raw_text=json.dumps(item),
                )
            )
    return results


def _parse_tool_calls_legacy(text: str) -> List[ParsedToolCall]:
    """
    Parsea el formato legacy: TOOL:nombre|args_json|id|confianza.
    """
    results = []
    pattern = r'TOOL:\s*([^|]+)\|([^|]+)\|([^|\s]+)(?:\|([^\s]+))?'
    for match in re.finditer(pattern, text):
        name = match.group(1).strip()
        args_str = match.group(2).strip()
        tool_id = match.group(3).strip()
        conf_str = match.group(4)
        confidence = float(conf_str) if conf_str else 1.0
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}
        results.append(
            ParsedToolCall(
                id=tool_id,
                name=name,
                args=args,
                confidence=confidence,
                source_pattern="legacy",
                raw_text=match.group(0),
            )
        )
    return results


def _parse_tool_calls_bullets(text: str) -> List[ParsedToolCall]:
    """
    Parsea tool calls en formato de lista con bullets.

    Espera líneas como:
        - [nombre] id=xxx args={...} conf=0.9
    """
    results = []
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line.startswith(('-', '*')):
            continue
        line = line[1:].strip()
        # Buscar patrón: [nombre] ...
        m = re.match(r'\[([^\]]+)\](.*)', line)
        if not m:
            continue
        name = m.group(1).strip()
        rest = m.group(2).strip()
        tool_id = "bullet_" + str(len(results))
        confidence = 1.0
        args = {}
        # Extraer id=...
        id_m = re.search(r'id=(\S+)', rest)
        if id_m:
            tool_id = id_m.group(1)
        # Extraer conf=...
        conf_m = re.search(r'conf=([0-9.]+)', rest)
        if conf_m:
            try:
                confidence = float(conf_m.group(1))
            except ValueError:
                pass
        # Extraer args={...}
        args_m = re.search(r'args=({.*?})(?:\s|$)', rest)
        if args_m:
            try:
                args = json.loads(args_m.group(1))
            except json.JSONDecodeError:
                pass
        results.append(
            ParsedToolCall(
                id=tool_id,
                name=name,
                args=args,
                confidence=confidence,
                source_pattern="bullets",
                raw_text=line,
            )
        )
    return results


def deduplicate_tool_calls(calls: List[ParsedToolCall]) -> List[ParsedToolCall]:
    """
    Elimina duplicados por firma única (nombre:args_json).
    Conserva el de mayor confianza.
    """
    seen: dict[str, ParsedToolCall] = {}
    for call in calls:
        key = f"{call.name}:{json.dumps(call.args, sort_keys=True)}"
        if key not in seen or call.confidence > seen[key].confidence:
            seen[key] = call
    return list(seen.values())


def parse_tool_calls_from_text(
    text: str,
    strategy: str = "all",
    deduplicate: bool = True,
) -> List[ParsedToolCall]:
    """
    Parsea tool calls desde texto LLM usando estrategias especificadas.

    Args:
        text: Texto a parsear
        strategy: "explicit", "json", "legacy", "bullets", o "all"
        deduplicate: Si True, elimina duplicados

    Returns:
        Lista de tool calls parseadas
    """
    all_calls: List[ParsedToolCall] = []

    strategies = {
        "explicit": _parse_tool_calls_explicit,
        "json": _parse_tool_calls_json,
        "legacy": _parse_tool_calls_legacy,
        "bullets": _parse_tool_calls_bullets,
    }

    if strategy == "all":
        for func in strategies.values():
            all_calls.extend(func(text))
    elif strategy in strategies:
        all_calls.extend(strategies[strategy](text))
    else:
        raise ValueError(f"Estrategia desconocida: {strategy}")

    if deduplicate:
        all_calls = deduplicate_tool_calls(all_calls)

    # Ordenar por confianza descendente
    all_calls.sort(key=lambda c: c.confidence, reverse=True)

    return all_calls


def parse_tool_calls_from_text_enhanced(
    text: str,
    deduplicate: bool = True,
    require_at_least_one: bool = False,
) -> List[ParsedToolCall]:
    """
    Parseo mejorado con múltiples estrategias y validación.

    Si require_at_least_one=True y no se encuentran tool calls,
    lanza ParseError.

    Args:
        text: Texto a parsear
        deduplicate: Eliminar duplicados
        require_at_least_one: Requerir al menos una tool call

    Returns:
        Lista de tool calls parseadas

    Raises:
        ParseError: Si require_at_least_one y no se encuentran tool calls
    """
    calls = parse_tool_calls_from_text(
        text, strategy="all", deduplicate=deduplicate
    )
    if require_at_least_one and not calls:
        raise ParseError("No se encontraron tool calls en el texto")
    return calls


def format_tool_calls_for_litellm(
    calls: List[ParsedToolCall],
) -> List[dict]:
    """
    Convierte ParsedToolCall al formato esperado por LiteLLM.
    """
    formatted = []
    for call in calls:
        formatted.append(
            {
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.args),
                },
                "id": getattr(call, "id", None),
            }
        )
    return formatted
