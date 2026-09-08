"""Tests unitarios para el nuevo subsistema de Capabilities de KogniTerm."""

import pytest
import tempfile
import os
from pathlib import Path
from pydantic import BaseModel, Field

from kogniterm.capabilities.registry import (
    ToolRegistry,
    ToolDefinition,
    tool,
    default_tool_registry,
)
from kogniterm.capabilities.file_editor import (
    read_file,
    create_file,
    edit_file,
    replace_all_file,
    delete_file,
    list_directory,
)
from kogniterm.capabilities.terminal import execute_command, run_shell


class SampleParams(BaseModel):
    query: str = Field(description="Texto de prueba")
    count: int = Field(default=1, description="Cantidad")


def test_tool_registry_registration_and_caching():
    registry = ToolRegistry()
    initial_count = registry.count()

    @tool(
        name="custom_speed_test",
        description="Herramienta de prueba de alta velocidad",
        params_schema=SampleParams,
    )
    def my_sample_tool(query: str, count: int = 1):
        return f"{query} * {count}"

    assert registry.count() == initial_count + 1
    tool_def = registry.get_tool("custom_speed_test")
    assert tool_def is not None
    assert tool_def.name == "custom_speed_test"

    schemas = registry.get_schemas_for_litellm()
    assert any(s["function"]["name"] == "custom_speed_test" for s in schemas)

    # Limpieza
    registry.unregister("custom_speed_test")
    assert registry.get_tool("custom_speed_test") is None


@pytest.mark.asyncio
async def test_file_capabilities_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_doc.txt"

        # 1. Crear archivo
        create_res = await create_file(path=str(test_file), content="Línea 1\nLínea 2\nLínea 3\n")
        assert create_res["success"] is True
        assert test_file.exists()

        # 2. Leer archivo
        read_res = await read_file(path=str(test_file))
        assert read_res["success"] is True
        assert "Línea 2" in read_res["content"]
        assert read_res["total_lines"] == 3

        # 3. Editar archivo (reemplazar Línea 2)
        edit_res = await edit_file(
            path=str(test_file),
            old_string="Línea 2",
            new_string="Línea Modificada",
            create_backup=True,
        )
        assert edit_res["success"] is True
        assert edit_res["lines_changed"] >= 1
        assert "Línea Modificada" in test_file.read_text(encoding="utf-8")

        # 4. Replace all
        rep_res = await replace_all_file(
            path=str(test_file),
            old_string="Línea",
            new_string="Fila",
        )
        assert rep_res["success"] is True
        assert rep_res["occurrences_replaced"] == 3
        assert "Fila 1" in test_file.read_text(encoding="utf-8")

        # 5. Listar directorio
        list_res = await list_directory(path=tmpdir)
        assert list_res["success"] is True
        assert any(item["name"] == "test_doc.txt" for item in list_res["items"])

        # 6. Eliminar archivo
        del_res = await delete_file(path=str(test_file))
        assert del_res["success"] is True
        assert not test_file.exists()


@pytest.mark.asyncio
async def test_terminal_capability_execution():
    res = await execute_command(command="echo 'Hola KogniTerm'")
    assert res["exit_code"] == 0
    assert "Hola KogniTerm" in res["stdout"]
    # Verificar que el marcador ##KOGNITERM_DONE_MARKER## fue filtrado limpiamente
    assert "##KOGNITERM_DONE_MARKER##" not in res["stdout"]


@pytest.mark.asyncio
async def test_terminal_capability_echo_off_environment():
    # Simular ejecución en subshell donde ECHO está desactivado mediante stty -echo
    # Debe seguir funcionando y no bloquearse en espera del marcador limpio
    cmd = "bash -c 'stty -echo 2>/dev/null; echo salida_sin_eco'"
    res = await execute_command(command=cmd)
    assert res["exit_code"] == 0
    assert "salida_sin_eco" in res["stdout"]
    assert "##KOGNITERM_DONE_MARKER##" not in res["stdout"]
