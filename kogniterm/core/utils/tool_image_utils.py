"""Normalización de resultados de herramientas MCP con imágenes (screenshots).

Problema que resuelve:
  Los servidores MCP de computer-use (p. ej. computer-use-linux) devuelven el
  screenshot como ``ImageContent``. ``langchain_mcp_adapters`` lo convierte a
  bloques ``{"type": "image", "base64": ..., "mime_type": ...}``. KogniTerm los
  serializaba con ``json.dumps`` a TEXTO plano dentro de un mensaje ``tool``.
  El proveedor entonces cuenta el base64 como tokens de texto (un PNG 1080p
  supera 1M de tokens) y responde::

      API Error (400): The input token count exceeds the maximum ... 1048576

  La corrección: detectar bloques de imagen, reducir su resolución/peso y
  enviarlos como bloques de visión ``image_url`` (data URL), que los
  proveedores cuentan como ~1-2k tokens en lugar de millones.
"""

import base64
import io
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Tuple, Union

logger = logging.getLogger(__name__)

# Límites seguros
MAX_IMAGE_DIM = int(os.getenv("KOGNITERM_SCREENSHOT_MAX_DIM", "1280"))
SCREENSHOT_JPEG_QUALITY = int(os.getenv("KOGNITERM_SCREENSHOT_JPEG_QUALITY", "65"))
MAX_TEXT_CHARS = int(os.getenv("KOGNITERM_MAX_TOOL_TEXT_CHARS", "20000"))

# Un base64 de una sola línea (PNG sin comprimir) no debe tratarse por líneas
# sino truncarse por caracteres. Cualquier texto de más de esto se colapsa.
GIANT_BLOB_CHARS = 12000

_BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")


def _try_downscale(b64: str, mime: str) -> Tuple[str, str]:
    """Reduce resolución y recomprime a JPEG. Si falla, devuelve el original."""
    try:
        from PIL import Image  # import diferido: Pillow es opcional

        raw = base64.b64decode(b64, validate=False)
        img = Image.open(io.BytesIO(raw))
        if img.mode in ("RGBA", "LA", "PA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, MAX_IMAGE_DIM / max(w, h)) if max(w, h) else 1.0
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=SCREENSHOT_JPEG_QUALITY, optimize=True)
        # Si aun con 1280px sigue siendo muy pesado (pantallas con ruido),
        # reintentar a menor resolución/calidad para no saturar el contexto.
        if buf.tell() > 350 * 1024:
            small_img = img.copy()
            small_img.thumbnail((960, 960), Image.LANCZOS)
            buf = io.BytesIO()
            small_img.save(buf, format="JPEG", quality=50, optimize=True)
        small = base64.b64encode(buf.getvalue()).decode("ascii")
        logger.debug(
            "Screenshot reducido: %dx%d -> %dx%d, %d -> %d chars base64",
            w, h, img.size[0], img.size[1], len(b64), len(small),
        )
        return small, "image/jpeg"
    except ImportError:
        return b64, mime
    except Exception as exc:  # pragma: no cover - defensivo
        logger.debug("No se pudo reducir screenshot: %s", exc)
        return b64, mime


def _save_full_blob(blob: str, tool_name: str) -> str:
    """Guarda un blob gigante en disco y devuelve su ruta (para el placeholder)."""
    try:
        logs_dir = os.path.join(os.path.expanduser("~"), ".kogniterm", "logs")
        os.makedirs(logs_dir, exist_ok=True)
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", tool_name or "tool")[:40]
        path = os.path.join(logs_dir, f"{safe}_blob_{int(time.time())}.b64.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(blob)
        return path
    except Exception:
        return "~/.kogniterm/logs/"


def _looks_like_base64_image(text: str) -> bool:
    """Heurística: string larguísimo de una sola línea con alfabeto base64."""
    s = (text or "").strip()
    if len(s) < GIANT_BLOB_CHARS:
        return False
    if "\n" in s[:2000] and s.count("\n") > 5:
        return False  # texto normal multilínea, no blob
    sample = s[:4000].strip()
    if len(sample) < 1000:
        return False
    return bool(_BASE64_RE.match(sample))


def prune_giant_text(text: str, tool_name: str = "tool") -> str:
    """Trunca blobs gigantes de una sola línea (base64) que smart_prune no cubre."""
    if not isinstance(text, str) or len(text) <= MAX_TEXT_CHARS:
        # Aun así, un base64 "mediano" de 12k-20k chars ya son ~4-6k tokens
        # inútiles como texto: si parece imagen, colapsarlo igual.
        if isinstance(text, str) and _looks_like_base64_image(text):
            path = _save_full_blob(text, tool_name)
            return (
                f"[screenshot/base64 de {len(text)} chars omitido como texto. "
                f"Contenido completo en: {path}]\n"
                f"[SUGERENCIA: si necesitas ver la pantalla, vuelve a llamar a la "
                f"herramienta de screenshot; se enviará como imagen de visión.]"
            )
        return text
    if _looks_like_base64_image(text):
        path = _save_full_blob(text, tool_name)
        return (
            f"[screenshot/base64 de {len(text)} chars omitido como texto. "
            f"Contenido completo en: {path}]\n"
            f"[SUGERENCIA: si necesitas ver la pantalla, vuelve a llamar a la "
            f"herramienta de screenshot; se enviará como imagen de visión.]"
        )
    # Texto largo normal: head+tail
    head, tail = text[:8000], text[-8000:]
    path = _save_full_blob(text, tool_name)
    return (
        f"[salida de {tool_name} truncada: {len(text)} chars. Log: {path}]\n"
        f"{head}\n\n... [{len(text) - 16000} chars omitidos] ...\n\n{tail}"
    )


def _block_to_vision(block: Dict[str, Any]) -> Union[Dict[str, Any], None]:
    """Convierte un bloque MCP/LangChain a bloque de visión OpenAI o texto."""
    if not isinstance(block, dict):
        return None
    btype = str(block.get("type", "")).lower()
    if btype == "image":
        b64 = (
            block.get("base64")
            or block.get("data")
            or (block.get("image_url") or {}).get("url", "")
            if isinstance(block.get("image_url"), dict)
            else block.get("base64") or block.get("data")
        )
        mime = block.get("mime_type") or block.get("mimeType") or "image/png"
        url = block.get("url", "")
        if url and not b64:
            return {"type": "image_url", "image_url": {"url": url}}
        if isinstance(b64, str) and "base64," in b64:
            b64 = b64.split("base64,", 1)[1]
        if not b64:
            return None
        b64, mime = _try_downscale(b64.strip(), mime)
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        }
    if btype == "image_url":
        inner = block.get("image_url", {})
        url = inner.get("url", "") if isinstance(inner, dict) else ""
        if url and url.startswith("data:image") and ";base64," in url:
            head, b64 = url.split(";base64,", 1)
            mime = head.split(":", 1)[1] if ":" in head else "image/png"
            b64, mime = _try_downscale(b64, mime)
            return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        return block
    if btype == "text":
        return {"type": "text", "text": str(block.get("text", ""))}
    return None


def normalize_tool_result(
    raw: Any, tool_name: str = "tool"
) -> Union[str, List[Dict[str, Any]]]:
    """Normaliza el resultado crudo de una herramienta MCP/LangChain.

    Returns:
        str si es solo texto (podado), o lista de bloques de visión
        ``[{"type": "text", ...}, {"type": "image_url", ...}]`` si hay imágenes.
    """
    from kogniterm.core.utils.output_pruner import smart_prune_tool_output

    # Caso 1: lista de bloques (formato langchain_mcp_adapters)
    if isinstance(raw, list):
        texts: List[str] = []
        visions: List[Dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                texts.append(item)
                continue
            if not isinstance(item, dict):
                texts.append(str(item))
                continue
            conv = _block_to_vision(item)
            if conv is None:
                # Bloque desconocido: serializar podado
                try:
                    texts.append(json.dumps(item, ensure_ascii=False)[:4000])
                except Exception:
                    texts.append(str(item)[:4000])
            elif conv.get("type") == "text":
                texts.append(conv["text"])
            else:
                visions.append(conv)
        text = "\n".join(t for t in texts if t).strip()
        if text:
            text = smart_prune_tool_output(text, tool_name=tool_name)
            text = prune_giant_text(text, tool_name)
        if visions:
            parts: List[Dict[str, Any]] = []
            parts.append({
                "type": "text",
                "text": (text or f"[screenshot de '{tool_name}' adjunto como imagen]"),
            })
            parts.extend(visions)
            return parts
        return text or "Operación completada (sin salida)."

    # Caso 2: dict con claves de imagen (algunos servidores devuelven esto)
    if isinstance(raw, dict):
        for key in ("base64", "data", "image", "screenshot"):
            val = raw.get(key)
            if isinstance(val, str) and len(val) > 2000:
                mime = raw.get("mime_type") or raw.get("mimeType") or "image/png"
                conv = _block_to_vision({"type": "image", "base64": val, "mime_type": mime})
                label = str(raw.get("text", "") or f"screenshot de '{tool_name}'")[:500]
                return [{"type": "text", "text": label}, conv]  # type: ignore
        text = json.dumps(raw, ensure_ascii=False)
        text = smart_prune_tool_output(text, tool_name=tool_name)
        return prune_giant_text(text, tool_name)

    # Caso 3: string (incluye ToolMessage.content ya aplanado)
    if isinstance(raw, str):
        text = smart_prune_tool_output(raw, tool_name=tool_name)
        return prune_giant_text(text, tool_name)

    if raw is None:
        return "Operación completada (sin salida)."
    text = str(raw)
    text = smart_prune_tool_output(text, tool_name=tool_name)
    return prune_giant_text(text, tool_name)


def serialize_for_provider(content: Union[str, List[Dict[str, Any]]]) -> Union[str, List[Dict[str, Any]]]:
    """El contenido lista ya es válido para LiteLLM/OpenAI; el str se pasa tal cual."""
    return content


def content_length_for_log(content: Union[str, List[Dict[str, Any]]]) -> str:
    """Resumen corto para logs sin volcar base64."""
    if isinstance(content, str):
        return f"{len(content)} chars"
    n_img = sum(1 for p in content if isinstance(p, dict) and p.get("type") == "image_url")
    n_txt = sum(len(str(p.get("text", ""))) for p in content if isinstance(p, dict) and p.get("type") == "text")
    return f"multimodal[{n_img} img, {n_txt} text chars]"
