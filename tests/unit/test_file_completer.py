import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.file_completer import FileCompleter


class MockDocument:
    def __init__(self, text_before_cursor, word_before_cursor=""):
        self.text_before_cursor = text_before_cursor
        self._word_before_cursor = word_before_cursor

    def get_word_before_cursor(self, WORD=True):
        return self._word_before_cursor


@pytest.fixture
def file_completer(monkeypatch):
    # Mockear las funciones de carga en background para evitar hilos activos en los tests
    monkeypatch.setattr(FileCompleter, "_start_background_load_files", lambda self: None)
    monkeypatch.setattr(FileCompleter, "_start_background_load_containers", lambda self: None)

    completer = FileCompleter(skill_manager=None, workspace_directory="/mock/workspace", show_indicator=False)
    # Definir un conjunto controlado de archivos
    completer._cached_files = [
        "README.md",
        "kogniterm/terminal/file_completer.py",
        "kogniterm/terminal/terminal.py",
        "kogniterm/core/session_manager.py",
        "docs/guidelines.md",
        "tests/unit/test_file_completer.py",
        "setup.py",
        "pyproject.toml",
        "docs/images/logo.png",
    ]
    return completer


def test_trigger_detection(file_completer):
    # 1. Al inicio de la línea
    doc1 = MockDocument("@")
    completions = list(file_completer.get_completions(doc1, None))
    assert len(completions) > 0
    assert any(c.text == "README.md" for c in completions)

    # 2. Precedido por espacio
    doc2 = MockDocument("hello @")
    completions = list(file_completer.get_completions(doc2, None))
    assert len(completions) > 0

    # 3. Precedido por delimitador como "="
    doc3 = MockDocument("filepath=@")
    completions = list(file_completer.get_completions(doc3, None))
    assert len(completions) > 0

    # 4. Correo electrónico (NO debe disparar completación de archivos)
    doc_email = MockDocument("test@email.com")
    completions = list(file_completer.get_completions(doc_email, None))
    assert len(completions) == 0


def test_multi_term_search(file_completer):
    # Buscar "kogni term file"
    doc = MockDocument("@kogni term file")
    completions = list(file_completer.get_completions(doc, None))
    
    # Debe coincidir únicamente con "kogniterm/terminal/file_completer.py"
    # ya que tiene "kogni" (en kogniterm), "term" (en terminal) y "file" (en file_completer.py)
    assert len(completions) == 1
    assert completions[0].text == "kogniterm/terminal/file_completer.py"


def test_fuzzy_scoring_relevance(file_completer):
    # Buscar "term"
    # Debe preferir "kogniterm/terminal/terminal.py" o carpetas de terminal a coincidencia parcial interna como "session_manager.py"
    doc = MockDocument("@term")
    completions = [c.text for c in file_completer.get_completions(doc, None)]
    
    # "kogniterm/terminal/terminal.py" tiene coincidencia exacta de "terminal" en el base_name
    # y de "term" al principio del base_name. Debería estar primero que "session_manager.py" (que no coincide con "term")
    # y probablemente antes que "kogniterm/core/session_manager.py" (donde "term" está en "kogniterm").
    assert len(completions) > 0
    assert completions[0] in ("kogniterm/terminal/terminal.py", "kogniterm/terminal/file_completer.py")


def test_extension_bonus(file_completer):
    # Buscar ".md"
    doc = MockDocument("@.md")
    completions = [c.text for c in file_completer.get_completions(doc, None)]
    
    # README.md y docs/guidelines.md deben aparecer al principio
    assert len(completions) >= 2
    assert completions[0].endswith(".md")
    assert completions[1].endswith(".md")


def test_empty_query_root_listing(file_completer):
    # Buscar solo "@"
    doc = MockDocument("@")
    completions = [c.text for c in file_completer.get_completions(doc, None)]
    
    # Debería devolver elementos raíz o carpetas directas en la raíz
    # como README.md, setup.py, pyproject.toml y directorios docs/, kogniterm/, tests/
    assert "README.md" in completions
    assert "setup.py" in completions
    assert "pyproject.toml" in completions
