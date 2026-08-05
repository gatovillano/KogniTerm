"""
Web Fetch Skill - Obtiene contenido HTML de páginas web con protección contra SSRF.

Provee funcionalidad para obtener el contenido de URLs.
"""

import ipaddress
import socket
from typing import Generator
from urllib.parse import urlparse

# Metadata de la herramienta
name = "web_fetch"
description = "Útil para obtener el contenido HTML de una URL."


def _is_safe_url(url: str) -> bool:
    """
    Valida que una URL no apunte a direcciones IP privadas, loopback, link-local o metadatos.
    """
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.hostname or ""
        if not host:
            return False

        host_lower = host.lower()
        if host_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        try:
            ip_str = socket.gethostbyname(host)
            ip = ipaddress.ip_address(ip_str)
        except Exception:
            return False

        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except Exception:
        return False


def web_fetch(url: str) -> Generator[str, None, None]:
    """
    Obtiene el contenido HTML de una URL especificada.

    Args:
        url: La URL de la página web a obtener

    Yields:
        str: Contenido HTML de la página

    Raises:
        Exception: Errores de conexión o HTTP
    """
    if not _is_safe_url(url):
        yield f"Error: La URL '{url}' fue bloqueada por la política de seguridad anti-SSRF.\n"
        return

    try:
        from langchain_community.utilities import RequestsWrapper
    except ImportError:
        yield "Error: El paquete 'langchain-community' no está instalado.\n"
        yield "Ejecuta: pip install langchain-community\n"
        return

    try:
        requests_wrapper = RequestsWrapper()
        content = requests_wrapper.get(url)

        yield content

    except Exception as e:
        yield f"Error al obtener la URL {url}: {str(e)}\n"


# Función alternativa para ejecución síncrona
def web_fetch_sync(url: str) -> str:
    """
    Versión síncrona de web_fetch.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in web_fetch(url):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "La URL completa (http:// o https://) de la página a consultar",
        }
    },
    "required": ["url"],
}
