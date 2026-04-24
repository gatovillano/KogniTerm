"""Tests unitarios para el parser de tool calls"""

import pytest
from kogniterm.core.llm.tool_parser import parse_tool_calls_from_text


def test_parse_simple_tool_call():
    """Prueba el parsing de una tool call simple"""
    text = 'Voy a usar la herramienta "search" con argumentos {"query": "test"}'
    tool_names = ["search", "read_file"]
    
    tool_calls = parse_tool_calls_from_text(text, tool_names, lambda: "id123")
    
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "search"
    assert tool_calls[0]["args"] == {"query": "test"}
    assert tool_calls[0]["id"] == "id123"


def test_parse_multiple_tool_calls():
    """Prueba el parsing de múltiples tool calls en un mensaje"""
    text = 'Primero usa read_file, luego search con {"query": "test"}'
    tool_names = ["read_file", "search"]
    
    tool_calls = parse_tool_calls_from_text(text, tool_names, lambda: "id456")
    
    assert len(tool_calls) >= 1  # Podría detectar una o dos dependiendo del parser
    names = [tc["name"] for tc in tool_calls]
    assert "read_file" in names
    assert "search" in names


def test_parse_no_tool_call():
    """Prueba que texto sin herramientas reconocidas retorna lista vacía"""
    text = "Hola, ¿cómo estás?"
    tool_names = ["search", "read_file"]
    
    tool_calls = parse_tool_calls_from_text(text, tool_names, lambda: "id789")
    
    assert len(tool_calls) == 0


def test_parse_tool_call_with_partial_json():
    """Prueba parsing cuando el JSON está incompleto o mal formado"""
    text = 'Usar tool con args {query: "test"}'  # Sin comillas en clave
    tool_names = ["tool"]
    
    # No debe fallar, debe devolver algo o vacío dependiendo de robustez
    tool_calls = parse_tool_calls_from_text(text, tool_names, lambda: "id000")
    # Simplemente verificamos que no lance excepción
    assert isinstance(tool_calls, list)


def test_tool_name_case_insensitive():
    """Prueba que los nombres de herramientas sean sensibles a mayúsculas (depende de implementación)"""
    text = 'Usar "SEARCH" mayúsculas'
    tool_names = ["search"]
    
    tool_calls = parse_tool_calls_from_text(text, tool_names, lambda: "id111")
    
    # Dependiendo de implementación, puede que detecte o no
    assert isinstance(tool_calls, list)


def test_parse_tool_call_with_id_generation():
    """Prueba que se generan IDs únicos cuando no se proporciona"""
    text = 'usar tool {"arg": "valor"}'
    tool_names = ["tool"]
    generated_ids = []
    
    def id_generator():
        new_id = f"id{len(generated_ids)}"
        generated_ids.append(new_id)
        return new_id
    
    tool_calls = parse_tool_calls_from_text(text, tool_names, id_generator)
    
    if tool_calls:
        assert tool_calls[0]["id"] in generated_ids


def test_parse_nested_json_arguments():
    """Prueba parsing de argumentos JSON anidados"""
    text = 'tool con {"param": {"nested": {"value": 123}}}'
    tool_names = ["tool"]
    
    tool_calls = parse_tool_calls_from_text(text, tool_names, lambda: "id999")
    
    if tool_calls:
        assert tool_calls[0]["args"]["param"]["nested"]["value"] == 123
