#!/usr/bin/env python3
"""
Tests de integración para kogniterm.core.llm_services
Valida que todos los componentes se integren correctamente.
"""

import sys
sys.path.insert(0, '.')

def test_imports():
    """Test 1: Todos los imports funcionan"""
    print("Test 1: Imports...")
    from kogniterm.core.llm_services import (
        ToolCall, ParsedToolCall, ToolDefinition,
        SYSTEM_TOOLS, get_system_tool_definitions,
        parse_tool_calls_from_text, parse_tool_calls_from_text_enhanced,
        deduplicate_tool_calls, format_tool_calls_for_litellm,
        ParseError, DuplicateToolCallError,
        LLMConfig, FAST_CONFIG, DEEP_CONFIG, TOOL_CONFIG,
        LLMError, ToolInvocationError, ToolDefinitionError,
        LLMProvider, GeminiProvider, OpenAIProvider,
        LLMService,
    )
    assert ToolCall is not None
    assert ParsedToolCall is not None
    assert FAST_CONFIG is not None
    assert SYSTEM_TOOLS is not None
    print("  ✓ PASS")


def test_config_presets():
    """Test 2: Configuraciones preset"""
    print("Test 2: Config presets...")
    from kogniterm.core.llm_services import FAST_CONFIG, TOOL_CONFIG, DEEP_CONFIG, LLMConfig
    assert FAST_CONFIG.model == "gemini-1.5-flash-latest"
    assert FAST_CONFIG.temperature == 0.5
    assert TOOL_CONFIG.model == "gemini-1.5-pro-latest"
    assert TOOL_CONFIG.temperature == 0.3
    assert DEEP_CONFIG.temperature == 0.7  # DEEP usa 0.7
    assert DEEP_CONFIG.model == "gemini-1.5-pro-latest"
    # Serialización
    d = FAST_CONFIG.to_dict()
    assert d["model"] == "gemini-1.5-flash-latest"
    c2 = LLMConfig.from_dict(d)
    assert c2.model == FAST_CONFIG.model
    print("  ✓ PASS")


def test_system_tools():
    """Test 3: Sistema de herramientas"""
    print("Test 3: System tools...")
    from kogniterm.core.llm_services import SYSTEM_TOOLS, get_system_tool_definitions, find_tool_definition
    assert len(SYSTEM_TOOLS) >= 5
    defs = get_system_tool_definitions()
    assert len(defs) == len(SYSTEM_TOOLS)
    # Buscar una tool específica
    sd = find_tool_definition("sequential_thinking")
    assert sd is not None
    assert sd.name == "sequential_thinking"
    print("  ✓ PASS")


def test_parse_tool_calls():
    """Test 4: Parseo de tool calls"""
    print("Test 4: Parse tool calls...")
    from kogniterm.core.llm_services import parse_tool_calls_from_text, parse_tool_calls_from_text_enhanced
    texto = '''
<TOOL>sequential_thinking|{"task": "test", "steps": 3}|t1|0.95</TOOL>
<TOOL>mental_model|{"model": "first_principles"}|t2|0.88</TOOL>
'''
    calls = parse_tool_calls_from_text(texto)
    assert len(calls) == 2
    assert calls[0].name == "sequential_thinking"
    assert calls[0].confidence == 0.95
    assert calls[0].args["task"] == "test"
    # Parseo mejorado
    enhanced = parse_tool_calls_from_text_enhanced(texto)
    assert len(enhanced) == 2
    print("  ✓ PASS")


def test_deduplicate():
    """Test 5: Deduplicación"""
    print("Test 5: Deduplicación...")
    from kogniterm.core.llm_services import ParsedToolCall, deduplicate_tool_calls
    c1 = ParsedToolCall(id="a1", name="tool_x", args={"k": 1}, confidence=0.8)
    c2 = ParsedToolCall(id="a2", name="tool_x", args={"k": 1}, confidence=0.9)
    c3 = ParsedToolCall(id="a3", name="tool_y", args={"k": 2}, confidence=0.7)
    dedup = deduplicate_tool_calls([c1, c2, c3])
    assert len(dedup) == 2
    # La de mayor confianza debe quedar
    tool_x = [d for d in dedup if d.name == "tool_x"][0]
    assert tool_x.confidence == 0.9
    print("  ✓ PASS")


def test_format_litellm():
    """Test 6: Formato LiteLLM"""
    print("Test 6: Formato LiteLLM...")
    from kogniterm.core.llm_services import ParsedToolCall, format_tool_calls_for_litellm
    c = ParsedToolCall(id="t1", name="tool_x", args={"k": 1}, confidence=0.8)
    fmt = format_tool_calls_for_litellm([c])
    assert len(fmt) == 1
    assert fmt[0]["id"] == "t1"
    assert fmt[0]["function"]["name"] == "tool_x"
    import json
    args = json.loads(fmt[0]["function"]["arguments"])
    assert args["k"] == 1
    print("  ✓ PASS")


def test_providers():
    """Test 7: Proveedores"""
    print("Test 7: Proveedores...")
    from kogniterm.core.llm_services import GeminiProvider, OpenAIProvider, LLMConfig
    gp = GeminiProvider(LLMConfig("gemini-1.5-flash-latest", 0.5))
    assert gp.config.model == "gemini-1.5-flash-latest"
    op = OpenAIProvider(LLMConfig("gpt-4o-mini", 0.5))
    assert op.config.model == "gpt-4o-mini"
    print("  ✓ PASS")


def test_service_creation():
    """Test 8: Servicio LLM"""
    print("Test 8: Servicio LLM...")
    from kogniterm.core.llm_services import LLMService, FAST_CONFIG, GeminiProvider
    gp = GeminiProvider(FAST_CONFIG)
    svc = LLMService(gp)
    assert svc.provider is not None
    assert svc.provider.config.model == "gemini-1.5-flash-latest"
    print("  ✓ PASS")


def test_errors():
    """Test 9: Jerarquía de errores"""
    print("Test 9: Jerarquía de errores...")
    from kogniterm.core.llm_services import (
        LLMError, ToolInvocationError, ToolDefinitionError,
        LLMConnectionError, LLMTimeoutError, LLMRateLimitError,
        InvalidToolCallError, ParseError, DuplicateToolCallError,
    )
    # ToolInvocationError hereda de LLMError
    assert issubclass(ToolInvocationError, LLMError)
    assert issubclass(ToolDefinitionError, LLMError)
    assert issubclass(LLMConnectionError, LLMError)
    assert issubclass(LLMTimeoutError, LLMError)
    assert issubclass(LLMRateLimitError, LLMError)
    assert issubclass(InvalidToolCallError, LLMError)
    assert issubclass(ParseError, Exception)
    assert issubclass(DuplicateToolCallError, ParseError)
    print("  ✓ PASS")


def test_integration_flow():
    """Test 10: Flujo completo de integración"""
    print("Test 10: Flujo completo...")
    from kogniterm.core.llm_services import (
        GeminiProvider, FAST_CONFIG,
        parse_tool_calls_from_text,
        deduplicate_tool_calls,
        format_tool_calls_for_litellm,
        get_system_tool_definitions,
        LLMService,
    )
    # 1. Crear servicio
    gp = GeminiProvider(FAST_CONFIG)
    svc = LLMService(gp)
    # 2. Obtener tools del sistema
    defs = get_system_tool_definitions()
    assert len(defs) > 0
    # 3. Parsear tool calls
    texto = '<TOOL>sequential_thinking|{"task": "plan"}|t1|0.9</TOOL>'
    calls = parse_tool_calls_from_text(texto)
    assert len(calls) == 1
    # 4. Deduplicar
    dedup = deduplicate_tool_calls(calls)
    assert len(dedup) == 1
    # 5. Formatear para LiteLLM
    fmt = format_tool_calls_for_litellm(dedup)
    assert len(fmt) == 1
    print("  ✓ PASS")


if __name__ == "__main__":
    tests = [
        test_imports,
        test_config_presets,
        test_system_tools,
        test_parse_tool_calls,
        test_deduplicate,
        test_format_litellm,
        test_providers,
        test_service_creation,
        test_errors,
        test_integration_flow,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*60}")
    print(f"Resultados: {passed}/{len(tests)} PASSED")
    if failed > 0:
        print(f"            {failed} FAILED")
        sys.exit(1)
    else:
        print("✓ TODOS LOS TESTS PASARON")
    print(f"{'='*60}")
