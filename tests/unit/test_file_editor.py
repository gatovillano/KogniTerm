"""
Tests para el editor de archivos endurecido (2026-07).

Cubre:
- replace_block con target unico, duplicado, ambiguo, corto
- fuzzy opt-in con whitespace flexible (NO newlines)
- context_hint desambiguando
- replace_lines con target_content y newlines distintos
- insert_after_match sin doble newline
- batch_edit atomico (todo o nada)
- rollback_transaction
- read_file_tool con/sin with_line_numbers
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# Setup de path para imports relativos del skill
TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent.parent
SKILL_DIR = PROJECT_ROOT / "kogniterm" / "skills" / "bundled" / "file-operations" / "scripts"
ADV_DIR = PROJECT_ROOT / "kogniterm" / "skills" / "bundled" / "advanced-file-editor" / "scripts"

# Importar via importlib (los directorios tienen guiones)
import importlib.util
from types import ModuleType


def _load_module(name: str, path: Path, package: str = "_test_pkg"):
    if package not in sys.modules:
        pkg = ModuleType(package)
        pkg.__path__ = [str(path.parent)]
        sys.modules[package] = pkg
    full_name = f"{package}.{name}"
    spec = importlib.util.spec_from_file_location(full_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = package
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_utils = _load_module("_utils", SKILL_DIR / "_utils.py")
_file_editor = _load_module("file_editor", SKILL_DIR / "file_editor.py")
_file_read = _load_module("file_read", SKILL_DIR / "file_read.py")
_adv_tool = _load_module("tool", ADV_DIR / "tool.py")

advanced_file_editor = _file_editor.advanced_file_editor
read_file_tool = _file_read.read_file_tool
FlexibleMatcher = _file_editor.FlexibleMatcher
MultipleMatchesError = _file_editor.MultipleMatchesError
batch_edit = _adv_tool.batch_edit
_transaction_manager = _adv_tool._transaction_manager


# ---------------------------------------------------------------------------
# FlexibleMatcher
# ---------------------------------------------------------------------------

class TestFlexibleMatcher:
    def test_exact_match_unique(self):
        content = "def foo():\n    return 1\n"
        matches = FlexibleMatcher.find_match(content, "def foo():")
        assert len(matches) == 1
        assert matches[0]["line_start"] == 1
        assert matches[0]["fuzzy"] is False
        assert matches[0]["score"] == 1.0

    def test_exact_match_multiple(self):
        content = "x = 1\nx = 1\nx = 2\n"
        matches = FlexibleMatcher.find_match(content, "x = 1")
        assert len(matches) == 2

    def test_fuzzy_disabled_by_default(self):
        # Target con whitespace distinto al del archivo; sin fuzzy, NO matchea.
        content = "def foo():\n    return 1\n"
        matches = FlexibleMatcher.find_match(content, "def foo():    return 1")
        assert matches == []

    def test_fuzzy_opt_in_within_line(self):
        # fuzzy=True: debe encontrar la linea completa con espacios flexibles.
        content = "def foo():\n    return 1\n"
        matches = FlexibleMatcher.find_match(content, "def foo():    return 1", fuzzy=True)
        assert len(matches) >= 1
        assert matches[0]["fuzzy"] is True
        # Score > 0.6 (umbral).
        assert matches[0]["score"] > 0.6

    def test_fuzzy_does_not_cross_newlines(self):
        # fuzzy NO debe atravesar multiples lineas (eso era el bug original).
        content = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        matches = FlexibleMatcher.find_match(
            content, "def foo():    pass    def bar():", fuzzy=True
        )
        # El target pide 4 tokens en una sola linea; el archivo no tiene
        # un lugar donde aparezcan 4 tokens seguidos. matches debe ser vacio.
        assert matches == []

    def test_find_unique_no_match(self):
        assert FlexibleMatcher.find_unique("abc", "xyz") is None

    def test_find_unique_multiple_raises(self):
        content = "x = 1\nx = 1\n"
        with pytest.raises(MultipleMatchesError) as exc_info:
            FlexibleMatcher.find_unique(content, "x = 1")
        # Mensaje debe mencionar las lineas y sugerir desambiguar.
        assert "veces" in str(exc_info.value).lower() or "veces" in str(exc_info.value)
        assert "context_hint" in str(exc_info.value) or "context_hint" in str(exc_info.value)

    def test_find_unique_with_context_hint(self):
        content = (
            "def foo():\n"
            "    return 1\n"
            "\n"
            "def bar():\n"
            "    return 1\n"
        )
        # Hay dos "    return 1". context_hint="def bar" debe elegir el segundo.
        m = FlexibleMatcher.find_unique(
            content, "    return 1", context_hint="def bar"
        )
        assert m is not None
        assert m["line_start"] == 5

    def test_context_hint_still_fails_if_no_match(self):
        content = "x = 1\nx = 2\nx = 1\n"
        with pytest.raises(MultipleMatchesError):
            FlexibleMatcher.find_unique(
                content, "x = 1", context_hint="this does not exist anywhere"
            )


# ---------------------------------------------------------------------------
# advanced_file_editor - replace_block
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_file():
    """Crea un archivo temporal con contenido conocido."""
    fd, path = tempfile.mkstemp(suffix=".py", text=True)
    os.close(fd)
    original = (
        "def foo():\n"
        "    return 1\n"
        "\n"
        "def bar():\n"
        "    return 1\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(original)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestReplaceBlock:
    def test_unique_target_success(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="def foo():",
            replacement_content="def foo():  # edited",
            confirm=True,
        )
        assert result["status"] == "success"
        assert "matched_span" in result
        assert result["matched_span"]["fuzzy"] is False
        assert result["matched_span"]["line_start"] == 1
        assert "applied_diff" in result
        with open(tmp_file, "r", encoding="utf-8") as f:
            assert "def foo():  # edited" in f.read()

    def test_duplicate_target_fails_by_default(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="    return 1",
            replacement_content="    return 42",
            confirm=True,
        )
        assert "error" in result
        # El error debe mencionar que aparece varias veces.
        assert "2" in result["error"] or "veces" in result["error"].lower()

    def test_short_target_with_many_occurrences(self, tmp_file):
        # `}` aparece 2 veces. Sin fuzzy, debe fallar.
        with open(tmp_file, "w") as f:
            f.write("if a:\n    pass\nif b:\n    pass\n")
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="    pass",
            replacement_content="    pass  # ok",
            confirm=True,
        )
        assert "error" in result

    def test_fuzzy_does_not_run_by_default(self, tmp_file):
        # El target tiene whitespace ligeramente distinto (2 espacios vs 4).
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="def foo():  return 1",  # 2 espacios vs 4
            replacement_content="def foo():  return 999",
            confirm=True,
        )
        # Sin fuzzy, no hay match exacto -> error.
        assert "error" in result

    def test_fuzzy_with_explicit_optin(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="def foo():  return 1",
            replacement_content="def foo():  return 999",
            confirm=True,
            fuzzy=True,
        )
        assert result["status"] == "success"
        assert result["matched_span"]["fuzzy"] is True

    def test_context_hint_disambiguates(self, tmp_file):
        # target "    return 1" aparece 2 veces; context_hint="def bar" elige el segundo.
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="    return 1",
            replacement_content="    return 99",
            context_hint="def bar",
            confirm=True,
        )
        assert result["status"] == "success"
        with open(tmp_file) as f:
            content = f.read()
        # La linea 2 sigue siendo 1, la linea 5 es 99.
        lines = content.splitlines()
        assert "return 1" in lines[1]
        assert "return 99" in lines[4]


# ---------------------------------------------------------------------------
# replace_lines
# ---------------------------------------------------------------------------

class TestReplaceLines:
    def test_basic(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_lines",
            line_number=2,
            replacement_content="    return 999\n",
            confirm=True,
        )
        assert result["status"] == "success"
        with open(tmp_file) as f:
            assert "return 999" in f.read()
            assert "return 1" not in f.read().split("\ndef bar")[0]

    def test_target_content_validates_with_normalized_newlines(self, tmp_file):
        # target_content con \n normal, archivo con \r\n en el rango.
        with open(tmp_file, "wb") as f:
            f.write(b"def foo():\r\n    return 1\r\n\r\ndef bar():\r\n    return 1\r\n")
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_lines",
            line_number=2,
            end_line=2,
            target_content="    return 1\n",  # normalizado
            replacement_content="    return 999\n",
            confirm=True,
        )
        assert result["status"] == "success"

    def test_target_content_mismatch_fails(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_lines",
            line_number=2,
            end_line=2,
            target_content="    return 999",  # no coincide con la linea 2
            replacement_content="    return 0\n",
            confirm=True,
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# insert_after_match
# ---------------------------------------------------------------------------

class TestInsertAfterMatch:
    def test_no_double_newline_at_line_end(self, tmp_file):
        # Insertar despues de "def foo():" (termina en \n).
        result = advanced_file_editor(
            path=tmp_file,
            action="insert_after_match",
            target_content="def foo():",
            content="    # comment",
            confirm=True,
        )
        assert result["status"] == "success"
        with open(tmp_file) as f:
            content = f.read()
        # No debe haber "\n\n\n" (doble newline no intencional).
        # El patron correcto es: "def foo():\n    # comment\n    return 1\n..."
        lines = content.splitlines()
        # Buscar "# comment" y verificar que NO hay linea en blanco entre
        # el comment y return 1.
        idx = next(i for i, l in enumerate(lines) if "# comment" in l)
        # La siguiente linea debe ser "    return 1" (o lo que estaba antes).
        # Si hay una linea vacia, hay doble newline.
        assert lines[idx + 1].strip() != "", (
            f"Doble newline detectado. Lineas: {lines}"
        )


# ---------------------------------------------------------------------------
# batch_edit atomicidad
# ---------------------------------------------------------------------------

@pytest.fixture
def batch_file():
    fd, path = tempfile.mkstemp(suffix=".txt", text=True)
    os.close(fd)
    with open(path, "w") as f:
        f.write("line1\nline2\nline3\nline4\nline5\n")
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestBatchEdit:
    def test_atomic_success(self, batch_file):
        result = batch_edit(
            path=batch_file,
            operations=[
                {"action": "replace_block", "target_content": "line1", "replacement_content": "LINE1"},
                {"action": "replace_block", "target_content": "line3", "replacement_content": "LINE3"},
            ],
            confirm=True,
        )
        assert result["status"] == "success"
        assert result["atomic"] is True
        with open(batch_file) as f:
            content = f.read()
        assert "LINE1" in content
        assert "LINE3" in content
        assert "line2" in content
        assert "line4" in content

    def test_atomic_failure_writes_nothing(self, batch_file):
        # Guardar contenido original.
        with open(batch_file) as f:
            original = f.read()

        # La 2ª operacion falla: target "line3" + require_unique=True, pero
        # "line3" es unico, asi que usamos un target inexistente.
        result = batch_edit(
            path=batch_file,
            operations=[
                {"action": "replace_block", "target_content": "line1", "replacement_content": "LINE1"},
                {"action": "replace_block", "target_content": "this_does_not_exist", "replacement_content": "X"},
            ],
            confirm=True,
        )
        assert result["status"] == "rolled_back"
        assert result["atomic"] is True
        assert result["summary"]["failed_at"] == 1

        # CRITICO: el archivo en disco NO debe tener cambios.
        with open(batch_file) as f:
            after = f.read()
        assert after == original, f"Archivo modificado parcialmente: {after!r}"

    def test_atomic_with_fuzzy_disabled(self, batch_file):
        # La 2ª operacion usa un target que NO existe en el archivo (sin fuzzy).
        # El archivo tiene "line2\nline3" exactamente, pero el target tiene
        # un espacio extra dentro del token ("line 2") que no matchea sin fuzzy.
        # -> falla la 2ª op -> ninguna operacion se escribe (atomicidad).
        with open(batch_file) as f:
            original = f.read()
        result = batch_edit(
            path=batch_file,
            operations=[
                {"action": "replace_block", "target_content": "line1", "replacement_content": "A"},
                {"action": "replace_block", "target_content": "line 2\nline3", "replacement_content": "B"},
            ],
            confirm=True,
        )
        assert result["status"] == "rolled_back"
        with open(batch_file) as f:
            assert f.read() == original

    def test_rollback_transaction(self, batch_file):
        # Crear una tx, no aplicarla, luego rollback.
        tx = _transaction_manager.create_transaction(batch_file, [{"action": "noop"}])
        # Modificar el archivo manualmente.
        with open(batch_file, "w") as f:
            f.write("MODIFIED OUTSIDE\n")
        # Rollback debe restaurar el original.
        assert _transaction_manager.rollback_transaction(tx.transaction_id) is True
        with open(batch_file) as f:
            assert f.read() == "line1\nline2\nline3\nline4\nline5\n"


# ---------------------------------------------------------------------------
# read_file_tool
# ---------------------------------------------------------------------------

class TestReadFileTool:
    def test_with_line_numbers_default(self, tmp_file):
        result = read_file_tool(tmp_file)
        assert "error" not in result
        assert result["with_line_numbers"] is True
        # Formato esperado: "   1 | def foo():"
        assert "1 | def foo():" in result["content"]
        assert "2 |     return 1" in result["content"]

    def test_with_line_numbers_disabled(self, tmp_file):
        result = read_file_tool(tmp_file, with_line_numbers=False)
        assert "error" not in result
        assert result["with_line_numbers"] is False
        # Sin numeros de linea.
        assert "1 |" not in result["content"]
        assert "def foo():" in result["content"]

    def test_start_end_line_with_numbers(self, tmp_file):
        result = read_file_tool(tmp_file, start_line=2, end_line=3)
        # start_line=2 -> debe empezar a numerar desde 2.
        assert "2 |     return 1" in result["content"]
        assert "3 |" in result["content"]
        # La linea 1 no debe aparecer.
        assert "1 | def foo():" not in result["content"]


# ---------------------------------------------------------------------------
# Validacion de entrada
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_unknown_action(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file, action="nonsense_action", confirm=True
        )
        assert "error" in result

    def test_replace_block_missing_target(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file, action="replace_block", replacement_content="X", confirm=True
        )
        assert "error" in result

    def test_insert_line_zero(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file, action="insert_line", line_number=0, content="X", confirm=True
        )
        assert "error" in result

    def test_requires_confirmation_when_no_confirm(self, tmp_file):
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="def foo():",
            replacement_content="def foo():  # ok",
            confirm=False,
        )
        assert result["status"] == "requires_confirmation"
        # Debe incluir diff y matched_span incluso en preview.
        assert "diff" in result
        assert "matched_span" in result
        # El archivo NO debe haberse modificado.
        with open(tmp_file) as f:
            assert "def foo():" in f.read()
            assert "# ok" not in f.read()


# ---------------------------------------------------------------------------
# Normalizacion de entradas: auto-strip de numeros de linea y CRLF
# ---------------------------------------------------------------------------

class TestInputNormalization:
    def test_auto_strip_line_numbers(self, tmp_file):
        """target_content con prefijos '  N | ' debe funcionar igual que sin ellos."""
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="   1 | def foo():\n   2 |     return 1",
            replacement_content="def foo():  # stripped\n    return 42",
            confirm=True,
        )
        assert result["status"] == "success"
        with open(tmp_file) as f:
            content = f.read()
        assert "return 42" in content
        assert "stripped" in content

    def test_strip_line_numbers_replacement(self, tmp_file):
        """replacement_content con prefijos tambien se limpia."""
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="def foo():",
            replacement_content="   1 | def foo():  # ok",
            confirm=True,
        )
        assert result["status"] == "success"
        with open(tmp_file) as f:
            content = f.read()
        # El prefijo de linea debe haber sido eliminado.
        assert "1 | def foo" not in content
        assert "def foo():  # ok" in content

    def test_crlf_file_replace_block(self, tmp_file):
        """Archivo con CRLF: replace_block con target LF debe funcionar."""
        with open(tmp_file, "wb") as f:
            f.write(b"def foo():\r\n    return 1\r\n\r\ndef bar():\r\n    return 1\r\n")
        result = advanced_file_editor(
            path=tmp_file,
            action="replace_block",
            target_content="def foo():\n    return 1",  # LF normal
            replacement_content="def foo():\n    return 999",
            confirm=True,
        )
        assert result["status"] == "success"
        raw = open(tmp_file, "rb").read()
        # El archivo debe seguir usando CRLF.
        assert b"\r\n" in raw
        assert b"999" in raw
