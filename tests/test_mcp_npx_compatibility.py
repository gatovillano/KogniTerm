import pytest
import os
import shutil
from pathlib import Path
from kogniterm.core.mcp.env_utils import (
    get_node_search_paths,
    get_enhanced_path,
    resolve_executable,
    normalize_mcp_config,
    parse_claude_or_mcp_json,
    format_mcp_exception,
)
from kogniterm.core.mcp.mcp_manager import MCPManager


def test_get_node_search_paths():
    paths = get_node_search_paths()
    assert isinstance(paths, list)
    assert len(paths) > 0
    # Al menos debe contener rutas comunes de sistema
    assert any("/usr/bin" in p or "/bin" in p or ".nvm" in p for p in paths)


def test_get_enhanced_path():
    base_path = "/usr/bin:/bin"
    enhanced = get_enhanced_path(base_path)
    parts = enhanced.split(os.pathsep)
    assert "/usr/bin" in parts
    assert "/bin" in parts


def test_normalize_mcp_config_npx_string_with_args():
    cfg = {
        "transport": "stdio",
        "command": "npx @modelcontextprotocol/server-memory foo bar",
        "args": ["baz"],
    }
    norm = normalize_mcp_config(cfg)
    assert norm["transport"] == "stdio"
    # Debe haber separado el comando base y los args
    assert norm["command"].endswith("npx") or norm["command"] == "npx"
    # Debe haber inyectado -y automáticamente
    assert norm["args"][0] == "-y"
    assert norm["args"][1] == "@modelcontextprotocol/server-memory"
    assert norm["args"][2] == "foo"
    assert norm["args"][3] == "bar"
    assert norm["args"][4] == "baz"
    # Debe haber inyectado PATH y variables anti-prompt
    assert "PATH" in norm["env"]
    assert norm["env"]["npm_config_yes"] == "true"
    assert norm["env"]["CI"] == "1"


def test_normalize_mcp_config_npx_already_has_y():
    cfg = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "hyperresearch-ai-docs-mcp"],
    }
    norm = normalize_mcp_config(cfg)
    # No debe duplicar -y
    assert norm["args"].count("-y") == 1
    assert norm["args"] == ["-y", "hyperresearch-ai-docs-mcp"]


def test_normalize_mcp_config_url_auto_sse():
    cfg = {
        "command": "https://mcp.hyperresearch.ai/mcp"
    }
    norm = normalize_mcp_config(cfg)
    assert norm["transport"] == "sse"
    assert norm["url"] == "https://mcp.hyperresearch.ai/mcp"
    assert "command" not in norm


def test_parse_claude_or_mcp_json_full_block():
    raw = """{
      "mcpServers": {
        "hyperresearch": {
          "command": "npx",
          "args": ["-y", "hyperresearch-ai-docs-mcp"],
          "env": {
            "TOKEN": "xyz"
          }
        }
      }
    }"""
    parsed = parse_claude_or_mcp_json(raw)
    assert len(parsed) == 1
    name, conf = parsed[0]
    assert name == "hyperresearch"
    assert conf["transport"] == "stdio"
    assert conf["command"].endswith("npx") or conf["command"] == "npx"
    assert conf["args"] == ["-y", "hyperresearch-ai-docs-mcp"]
    assert conf["env"]["TOKEN"] == "xyz"


def test_parse_claude_or_mcp_json_single_server():
    raw = {
        "command": "npx -y hyperresearch-ai-docs-mcp"
    }
    parsed = parse_claude_or_mcp_json(raw, fallback_name="docs")
    assert len(parsed) == 1
    name, conf = parsed[0]
    assert name == "docs"
    assert conf["args"] == ["-y", "hyperresearch-ai-docs-mcp"]


def test_format_mcp_exception():
    e1 = ValueError("Error simple")
    assert format_mcp_exception(e1) == "Error simple"

    # ExceptionGroup simulation si está disponible
    try:
        eg = ExceptionGroup("grupo", [RuntimeError("Fallo conexion"), ValueError("Parametro invalido")])
        formatted = format_mcp_exception(eg)
        assert "Fallo conexion" in formatted
        assert "Parametro invalido" in formatted
    except NameError:
        pass


@pytest.mark.asyncio
async def test_mcp_manager_test_connection_npx():
    manager = MCPManager.get_instance()
    # Probamos con un comando npx con espacio para verificar normalización
    cfg = {
        "transport": "stdio",
        "command": "npx @modelcontextprotocol/server-memory",
    }
    # Solo ejecutamos si npx está instalado en el sistema
    if shutil.which("npx", path=get_enhanced_path()):
        res = await manager.test_connection(cfg)
        assert res["status"] in ("ok", "error")
        if res["status"] == "ok":
            assert len(res["tools"]) > 0
            assert "create_entities" in res["tools"]


def test_discover_external_mcp_servers_claude_code(tmp_path, monkeypatch):
    from kogniterm.core.mcp.external_sync import discover_external_mcp_servers
    import json

    # Simular ~/.claude.json con servidores globales y de proyecto
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_claude_json = fake_home / ".claude.json"
    fake_claude_json.write_text(json.dumps({
        "mcpServers": {
            "hyperresearch": {
                "type": "http",
                "url": "https://mcp.hyperresearch.ai/mcp"
            }
        },
        "projects": {
            str(tmp_path / "myproj"): {
                "mcpServers": {
                    "project-local-mcp": {
                        "command": "node index.js"
                    }
                }
            }
        }
    }), encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Descubrir para el proyecto simulado
    discovered = discover_external_mcp_servers(str(tmp_path / "myproj"))
    assert "hyperresearch" in discovered
    assert discovered["hyperresearch"]["transport"] == "http"
    assert discovered["hyperresearch"]["url"] == "https://mcp.hyperresearch.ai/mcp"
    assert discovered["hyperresearch"]["source"] == "claude_code"

    assert "project-local-mcp" in discovered
    assert discovered["project-local-mcp"]["source"] == "claude_code_project"


def test_config_manager_external_mcp_integration(tmp_path, monkeypatch):
    from kogniterm.terminal.config_manager import ConfigManager
    import json

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_kogniterm = fake_home / ".kogniterm"
    fake_kogniterm.mkdir()
    fake_claude_json = fake_home / ".claude.json"
    fake_claude_json.write_text(json.dumps({
        "mcpServers": {
            "claude-srv": {
                "type": "http",
                "url": "https://example.com/mcp"
            }
        }
    }), encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_DIR", fake_kogniterm)
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_FILE", fake_kogniterm / "config.json")

    cm = ConfigManager()
    servers = cm.get_mcp_servers()
    assert "claude-srv" in servers
    assert servers["claude-srv"]["source"] == "claude_code"

    # Probar borrado / exclusión
    cm.delete_mcp_server("claude-srv", scope="global")
    servers_after_del = cm.get_mcp_servers()
    assert "claude-srv" not in servers_after_del

