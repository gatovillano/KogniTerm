"""Capacidades nativas de búsqueda y obtención de contenido web para KogniTerm."""

import asyncio
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import ipaddress
import socket
from pydantic import BaseModel, Field

from kogniterm.capabilities.registry import tool


class WebSearchParams(BaseModel):
    query: str = Field(description="Consulta o términos de búsqueda en la web")
    max_results: int = Field(default=5, description="Número máximo de resultados a retornar")


class WebFetchParams(BaseModel):
    url: str = Field(description="URL de la página web a consultar")


def _is_safe_url(url: str) -> bool:
    """Valida contra ataques de SSRF (evita acceso a red local o metadatos internos)."""
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
            return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
        except Exception:
            return False
    except Exception:
        return False


@tool(
    name="web_fetch",
    description="Obtiene y procesa el contenido textual de una página web segura.",
    params_schema=WebFetchParams,
    category="web",
)
async def web_fetch(url: str) -> Dict[str, Any]:
    """Descarga de forma segura el contenido de una URL."""
    if not _is_safe_url(url):
        return {"success": False, "url": url, "error": "URL no permitida o insegura (SSRF protection)."}

    def _sync_fetch():
        import urllib.request
        from bs4 import BeautifulSoup

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; KogniTermBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_html = response.read().decode("utf-8", errors="replace")

        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Limitar a primeros 8000 caracteres para respuesta rápida
        truncated = text[:8000]
        return truncated

    try:
        content = await asyncio.to_thread(_sync_fetch)
        return {"success": True, "url": url, "content": content}
    except Exception as exc:
        return {"success": False, "url": url, "error": f"Error al acceder a URL: {exc}"}


@tool(
    name="web_search",
    description="Realiza una búsqueda rápida en la web y devuelve títulos, resúmenes y enlaces.",
    params_schema=WebSearchParams,
    category="web",
)
async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Busca en la web usando DuckDuckGo o Tavily si está disponible."""
    def _sync_search():
        import os
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=tavily_key)
                res = client.search(query=query, max_results=max_results)
                return {"success": True, "provider": "tavily", "results": res.get("results", [])}
            except Exception:
                pass

        # Fallback usando DuckDuckGo API pública o duckduckgo_search si existe
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return {"success": True, "provider": "duckduckgo", "results": results}
        except Exception:
            pass

        return {
            "success": False,
            "error": "No hay proveedor de búsqueda configurado. Configura TAVILY_API_KEY o instala duckduckgo_search.",
            "results": [],
        }

    try:
        return await asyncio.to_thread(_sync_search)
    except Exception as exc:
        return {"success": False, "error": f"Error en búsqueda web: {exc}", "results": []}
