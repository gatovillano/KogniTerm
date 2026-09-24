import os
import pytest
import asyncio
from kogniterm.core.llm_service import LLMService
from kogniterm.server.session_pool import session_context, AgentSession
from langchain_core.messages import HumanMessage


def test_llm_service_default_platform():
    service = LLMService(use_multi_provider=False)
    assert service.get_platform() == "tui"


def test_llm_service_set_platform():
    service = LLMService(use_multi_provider=False)
    service.set_platform("desktop")
    assert service.get_platform() == "desktop"

    service.set_platform("web")
    assert service.get_platform() == "web"


def test_system_prompt_instruction_for_tui():
    service = LLMService(use_multi_provider=False, platform="tui")
    instruction = service._get_platform_instruction()
    assert "TERMINAL DE CONSOLA (TUI/CLI)" in instruction
    assert "NUNCA generes etiquetas HTML" in instruction


def test_system_prompt_instruction_for_desktop():
    service = LLMService(use_multi_provider=False, platform="desktop")
    instruction = service._get_platform_instruction()
    assert "ENTORNO GRÁFICO (WEB/DESKTOP)" in instruction
    assert "Puedes utilizar bloques o código HTML" in instruction


def test_session_context_platform_isolation():
    service = LLMService(use_multi_provider=False, platform="tui")
    assert service.get_platform() == "tui"

    with session_context(cwd=os.getcwd(), llm_service=service, platform="desktop"):
        assert service.get_platform() == "desktop"
        instruction = service._get_platform_instruction()
        assert "ENTORNO GRÁFICO (WEB/DESKTOP)" in instruction

    # Al salir del contexto, vuelve al valor original
    assert service.get_platform() == "tui"


def test_agent_session_platform():
    loop = asyncio.new_event_loop()
    try:
        service = LLMService(use_multi_provider=False)
        session = AgentSession(session_id="test-p", llm_service=service, loop=loop, platform="web")
        assert session.platform == "web"
    finally:
        loop.close()
