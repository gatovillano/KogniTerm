"""Tests de regresión para sesiones MCP persistentes.

Reproduce el bug original: servidores con estado (browser-use, playwright,
etc.) que guardan contexto en memoria — pestaña de navegador, cookies,
historial de la conversación—. Con el diseño antiguo (`load_mcp_tools` con
`session=None`), cada invocación arrancaba un servidor nuevo y lo mataba al
terminar: el navegador se abría y se cerraba de inmediato sin continuidad.

El servidor de prueba guarda un contador en memoria: si la sesión persiste,
la segunda llamada lo ve; con una sesión por invocación siempre devolvería 1.
"""

import sys

import pytest

from kogniterm.core.mcp.mcp_manager import MCPManager, PersistentMCPTool

try:
    import mcp.server.fastmcp  # noqa: F401
    _HAS_FASTMCP = True
except ImportError:
    _HAS_FASTMCP = False


# Servidor MCP con estado en memoria (equivalente al navegador de browser-use).
_STATEFUL_SERVER_SCRIPT = """
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('stateful_test')
_STATE = {'visits': 0, 'last_url': None}

@mcp.tool()
def navigate(url: str) -> str:
    '''Simula abrir una página en un navegador (mantiene estado entre llamadas).'''
    _STATE['visits'] += 1
    _STATE['last_url'] = url
    return f"visit #{_STATE['visits']} -> {url}"

@mcp.tool()
def current_page() -> str:
    '''Devuelve la página abierta actualmente y cuántas visitas lleva.'''
    return f"visits={_STATE['visits']} url={_STATE['last_url']}"

if __name__ == '__main__':
    mcp.run()
"""


def _stateful_server_conf():
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-c", _STATEFUL_SERVER_SCRIPT],
        "disabled": False,
    }


@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_FASTMCP, reason="mcp.server.fastmcp not installed")
async def test_stateful_server_keeps_state_between_invocations(tmp_path, monkeypatch):
    """El estado del servidor debe sobrevivir entre invocaciones de herramientas."""
    monkeypatch.setattr(MCPManager, "_instance", None)
    manager = MCPManager.get_instance()
    monkeypatch.setattr(
        manager.config_manager, "get_mcp_servers",
        lambda: {"browser_like": _stateful_server_conf()},
    )

    await manager.reload()
    assert manager.server_statuses["browser_like"]["status"] == "connected"

    navigate = manager.get_tool("navigate")
    current_page = manager.get_tool("current_page")
    assert navigate is not None and current_page is not None
    assert isinstance(navigate, PersistentMCPTool)

    # 1ª acción del agente: abrir una página.
    r1 = await navigate.ainvoke({"url": "https://example.com"})
    assert "https://example.com" in str(r1)
    assert "visit #1" in str(r1)

    # 2ª acción: el servidor DEBE recordar la anterior (aquí fallaba el bug:
    # se abría un servidor nuevo y el contador volvía a 1).
    r2 = await navigate.ainvoke({"url": "https://example.org"})
    assert "visit #2" in str(r2), (
        "La sesión MCP se reinició entre invocaciones: el servidor con estado "
        "perdió el contexto (bug de browser-use: el navegador se cerraba y "
        "reabría en cada acción)."
    )

    # 3ª acción: consultar el estado actual debe reflejar ambas visitas.
    r3 = await current_page.ainvoke({})
    assert "visits=2" in str(r3)
    assert "https://example.org" in str(r3)

    manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_FASTMCP, reason="mcp.server.fastmcp not installed")
async def test_persistent_tools_also_work_via_sync_invoke(monkeypatch):
    """`invoke()` síncrono (bash_agent y otros) debe reutilizar la misma sesión."""
    monkeypatch.setattr(MCPManager, "_instance", None)
    manager = MCPManager.get_instance()
    monkeypatch.setattr(
        manager.config_manager, "get_mcp_servers",
        lambda: {"browser_like": _stateful_server_conf()},
    )

    await manager.reload()
    navigate = manager.get_tool("navigate")
    assert navigate is not None

    r1 = navigate.invoke({"url": "https://a.example"})
    r2 = navigate.invoke({"url": "https://b.example"})
    assert "visit #1" in str(r1)
    assert "visit #2" in str(r2), "invoke() síncrono no reutilizó la sesión persistente"

    manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_FASTMCP, reason="mcp.server.fastmcp not installed")
async def test_reload_closes_old_sessions_and_reconnects(monkeypatch):
    """Tras un reload, las sesiones viejas se cierran y las nuevas quedan vivas."""
    monkeypatch.setattr(MCPManager, "_instance", None)
    manager = MCPManager.get_instance()
    monkeypatch.setattr(
        manager.config_manager, "get_mcp_servers",
        lambda: {"browser_like": _stateful_server_conf()},
    )

    await manager.reload()
    old_session = manager._sessions.get("browser_like")
    assert old_session is not None

    await manager.reload()
    new_session = manager._sessions.get("browser_like")
    assert new_session is not None
    assert new_session is not old_session, "El reload no creó una sesión nueva"

    # La sesión nueva debe funcionar (estado reiniciado, esperado tras reload).
    navigate = manager.get_tool("navigate")
    r = await navigate.ainvoke({"url": "https://fresh.example"})
    assert "visit #1" in str(r)

    manager.shutdown()
