"""Tests para garantizar que el agente conoce la terminal interactiva y el soporte de sudo."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from kogniterm.core.ai_cli_bridge.llm_bridge import (
    LLMBridge,
    _detect_interactive_sudo_refusal,
)
from kogniterm.core.ai_cli_bridge.tool_registry_adapter import ToolRegistryAdapter
from kogniterm.core.antigravity_client import AntigravityClient


def test_execute_command_capability_schema_declares_interactive_sudo():
    """El schema real enviado al LLM (capabilities/terminal.py) debe declarar PTY interactivo y sudo."""
    import kogniterm.capabilities.terminal  # noqa: F401 - asegura registro en default_tool_registry

    adapter = ToolRegistryAdapter()
    schemas = adapter.get_schemas_for_litellm()
    by_name = {s["function"]["name"]: s["function"] for s in schemas if "function" in s}

    assert "execute_command" in by_name
    exec_fn = by_name["execute_command"]
    desc_lower = exec_fn["description"].lower()
    assert "sudo" in desc_lower
    assert "interactiva" in desc_lower

    cmd_param_desc = exec_fn["parameters"]["properties"]["command"]["description"].lower()
    assert "sudo" in cmd_param_desc
    assert "interactivos" in cmd_param_desc

    assert "run_shell" in by_name
    assert "sudo" in by_name["run_shell"]["description"].lower()


def test_antigravity_map_messages_preserves_all_system_messages():
    """Un segundo SystemMessage (resumen/contexto) no debe sobreescribir el system prompt principal."""
    messages = [
        {"role": "system", "content": "CAPACIDAD REAL DE LA TERMINAL: ES INTERACTIVA Y ADMITE `sudo`"},
        {"role": "system", "content": "Resumen de conversación previa..."},
        {"role": "user", "content": "instala htop con sudo"},
    ]
    contents, system_instruction = AntigravityClient.map_messages(messages)

    assert len(contents) == 1
    assert system_instruction is not None
    parts_text = "\n".join(p["text"] for p in system_instruction["parts"])
    assert "CAPACIDAD REAL DE LA TERMINAL" in parts_text
    assert "Resumen de conversación previa" in parts_text


@pytest.mark.parametrize(
    "text,expected",
    [
        ("No puedo ejecutar comandos con sudo porque requiere contraseña.", True),
        ("Como agente no tengo acceso a una terminal interactiva para introducir tu password.", True),
        ("Esta terminal no es interactiva, así que no soporta entrada interactiva.", True),
        ("Por favor, ejecuta `sudo apt update` manualmente en tu terminal.", True),
        ("I cannot run sudo commands because this is a non-interactive shell.", True),
        ("Please run `sudo systemctl restart nginx` in your own terminal.", True),
        ("He instalado htop correctamente usando sudo apt install htop.", False),
        ("El comando sudo permite ejecutar programas con privilegios de superusuario.", False),
        ("Todo listo, el servicio nginx está activo y respondiendo en el puerto 80.", False),
    ],
)
def test_detect_interactive_sudo_refusal(text, expected):
    assert _detect_interactive_sudo_refusal(text) is expected


@pytest.mark.asyncio
async def test_llm_bridge_nudges_on_sudo_refusal():
    """Si el modelo se niega a ejecutar sudo sin tool_calls, LLMBridge lo corrige automáticamente."""
    bridge = LLMBridge(model="openai/gpt-4o-mini")
    call_count = 0

    async def fake_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        current = call_count

        async def _stream():
            if current == 1:
                delta = SimpleNamespace(
                    content="No puedo ejecutar sudo porque requiere contraseña. Por favor ejecútalo en tu terminal.",
                    tool_calls=None,
                )
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])
            else:
                tc = SimpleNamespace(
                    index=0,
                    id="call_sudo_1",
                    function=SimpleNamespace(
                        name="execute_command",
                        arguments='{"command": "sudo apt update"}',
                    ),
                )
                delta = SimpleNamespace(content="", tool_calls=[tc])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

        return _stream()

    async def fake_execute_tool(name, args):
        return {"exit_code": 0, "stdout": "Done", "stderr": ""}

    # En la 3ra llamada devolvemos respuesta final para cerrar el bucle
    async def fake_acompletion_3step(**kwargs):
        nonlocal call_count
        call_count += 1
        current = call_count

        async def _stream():
            if current == 1:
                delta = SimpleNamespace(
                    content="No puedo ejecutar sudo porque requiere contraseña.",
                    tool_calls=None,
                )
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])
            elif current == 2:
                tc = SimpleNamespace(
                    index=0,
                    id="call_sudo_1",
                    function=SimpleNamespace(
                        name="execute_command",
                        arguments='{"command": "sudo apt update"}',
                    ),
                )
                delta = SimpleNamespace(content="", tool_calls=[tc])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])
            else:
                delta = SimpleNamespace(content="Actualización completada.", tool_calls=None)
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

        return _stream()

    messages = [
        {"role": "system", "content": "Eres KogniTerm."},
        {"role": "user", "content": "Actualiza los paquetes con sudo apt update"},
    ]

    with (
        patch("litellm.acompletion", side_effect=fake_acompletion_3step),
        patch.object(bridge, "execute_tool_call", side_effect=fake_execute_tool),
        patch.object(bridge, "_resolve_model_provider", return_value=("openai/gpt-4o-mini", {})),
    ):
        events = [ev async for ev in bridge.chat(messages=messages, tools=[])]

    assert call_count == 3
    tool_starts = [e for e in events if e.get("type") == "tool_start"]
    assert len(tool_starts) == 1
    assert tool_starts[0]["name"] == "execute_command"
    assert tool_starts[0]["args"]["command"] == "sudo apt update"
    assert any("TERMINAL INTERACTIVA ACTIVA" in str(m.get("content", "")) for m in messages)


def test_code_agent_and_deep_coder_include_interactive_terminal_instruction():
    from kogniterm.core.agents.code_agent import get_system_message as code_sys
    from kogniterm.core.agents.deep_coder import get_deep_coder_system_prompt

    mock_llm = MagicMock()
    mock_llm.is_thinking_model.return_value = True

    assert "CAPACIDAD REAL DE LA TERMINAL" in code_sys(mock_llm).content
    assert "CAPACIDAD REAL DE LA TERMINAL" in get_deep_coder_system_prompt(mock_llm)
