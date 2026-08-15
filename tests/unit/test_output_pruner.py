import os
import pytest
from kogniterm.core.utils.output_pruner import smart_prune_tool_output, LOGS_DIR


def test_small_output_not_pruned():
    small_output = "Line 1\nLine 2\nLine 3"
    result = smart_prune_tool_output(small_output, tool_name="test_tool", max_lines=200)
    assert result == small_output


def test_large_output_pruned_with_log_saved():
    # Generar 500 líneas
    lines = [f"Normal log line {i}" for i in range(500)]
    # Inyectar un error en la línea 250
    lines[250] = "CRITICAL: Traceback (most recent call last): ValueError: Invalid parameter"
    large_output = "\n".join(lines)

    pruned = smart_prune_tool_output(large_output, tool_name="test_large_tool", max_lines=100)

    # Verificar que el resultado fue recortado y contiene el aviso de log
    assert "Salida de test_large_tool extensa" in pruned
    assert ".kogniterm/logs" in pruned
    # Verificar que las primeras líneas y las últimas líneas estén presentes
    assert "Normal log line 0" in pruned
    assert "Normal log line 499" in pruned
    # Verificar que la línea de error intermedia fue preservada
    assert "ValueError: Invalid parameter" in pruned


def test_empty_output_handled():
    assert smart_prune_tool_output("") == ""
    assert smart_prune_tool_output(None) == ""
