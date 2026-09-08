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
from kogniterm.capabilities.code_tools import code_analysis, codebase_search


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


def test_code_capabilities_registered():
    """Verifica que code_analysis y codebase_search estén registrados en el ToolRegistry."""
    registry = ToolRegistry()
    
    cap_analysis = registry.get_tool("code_analysis")
    assert cap_analysis is not None
    assert cap_analysis.category == "code"

    cap_search = registry.get_tool("codebase_search")
    assert cap_search is not None
    assert cap_search.category == "code"

    schemas = registry.get_schemas_for_litellm()
    names = [s["function"]["name"] for s in schemas]
    assert "code_analysis" in names
    assert "codebase_search" in names


@pytest.mark.asyncio
async def test_code_analysis_capability_execution():
    """Verifica la ejecución de análisis estático con retroalimentación visual de progreso."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sample_file = Path(tmpdir) / "sample_test.py"
        sample_file.write_text(
            "def calculate(a, b):\n"
            "    # Suma condicional\n"
            "    if a > 0:\n"
            "        return a + b\n"
            "    return b\n",
            encoding="utf-8",
        )

        # 1. Análisis raw
        raw_res = await code_analysis(analysis_type="raw", path=str(sample_file))
        assert raw_res["success"] is True
        assert raw_res["total_files"] == 1
        assert "LOC:" in raw_res["output"]

        # 2. Análisis complexity
        cc_res = await code_analysis(analysis_type="complexity", path=str(sample_file))
        assert cc_res["success"] is True
        assert "calculate" in cc_res["output"]
        assert cc_res["details"][0]["average_complexity"] >= 1.0

        # 3. Análisis maintainability
        mi_res = await code_analysis(analysis_type="maintainability", path=str(sample_file))
        assert mi_res["success"] is True
        assert "Índice de Mantenibilidad" in mi_res["output"]

        # 4. Análisis en directorio no existente
        err_res = await code_analysis(analysis_type="raw", path="/non/existent/path/12345")
        assert err_res["success"] is False


@pytest.mark.asyncio
async def test_codebase_search_capability_structure():
    """Verifica que codebase_search ejecute el flujo paso a paso y devuelva estructura limpia."""
    # Ejecutamos una búsqueda. Si la base vectorial no está indexada, debe reportarlo limpiamente sin romper
    res = await codebase_search(query="función de inicialización")
    assert "success" in res
    assert "output" in res


def test_code_analysis_skill_script_execution():
    """Verifica la ejecución de code_analysis.py como script con soporte de progreso y CLI."""
    import importlib.util
    script_path = Path(__file__).resolve().parent.parent.parent / "kogniterm" / "skills" / "bundled" / "code-tools" / "scripts" / "code_analysis.py"
    assert script_path.exists()

    spec = importlib.util.spec_from_file_location("code_analysis_module", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 1. Probar función síncrona
    out = module.code_analysis_sync("raw", str(script_path.parent))
    assert "LOC:" in out
    assert "SLOC:" in out

    # 2. Probar generador
    gen = module.code_analysis("raw", str(script_path.parent))
    chunks = list(gen)
    assert len(chunks) == 1
    assert "LOC:" in chunks[0]

    # 3. Probar get_action_description
    desc = module.get_action_description("lint", str(script_path))
    assert "lint" in desc


