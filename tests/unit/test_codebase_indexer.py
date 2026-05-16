from pathlib import Path

import kogniterm.core.context.codebase_indexer as codebase_indexer


class _StubEmbeddingsService:
    def __init__(self):
        pass

    def generate_embeddings(self, texts):
        return [[1.0] for _ in texts]


def test_list_code_files_keeps_only_app_source_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(codebase_indexer.ConfigManager, "get_config", lambda self, key=None: {})
    monkeypatch.setattr(codebase_indexer, "EmbeddingsService", _StubEmbeddingsService)

    (tmp_path / "kogniterm" / "core").mkdir(parents=True)
    (tmp_path / "kogniterm-desktop" / "src").mkdir(parents=True)
    (tmp_path / "kogniterm-android" / "app" / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()

    allowed_py = tmp_path / "kogniterm" / "core" / "app.py"
    allowed_js = tmp_path / "kogniterm-desktop" / "src" / "main.js"
    allowed_ts = tmp_path / "kogniterm-android" / "app" / "src" / "main.ts"

    allowed_py.write_text("print('app')\n", encoding="utf-8")
    allowed_js.write_text("console.log('desktop')\n", encoding="utf-8")
    allowed_ts.write_text("console.log('android')\n", encoding="utf-8")

    (tmp_path / "README.md").write_text("repo docs\n", encoding="utf-8")
    (tmp_path / "debug_tool.py").write_text("print('debug')\n", encoding="utf-8")
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("documentation\n", encoding="utf-8")

    indexer = codebase_indexer.CodebaseIndexer(str(tmp_path))
    code_files = indexer.list_code_files(str(tmp_path))

    assert str(allowed_py) in code_files
    assert str(allowed_js) in code_files
    assert str(allowed_ts) in code_files
    assert str(tmp_path / "README.md") not in code_files
    assert str(tmp_path / "debug_tool.py") not in code_files
    assert str(tmp_path / "tests" / "test_app.py") not in code_files
    assert str(tmp_path / "docs" / "guide.md") not in code_files
