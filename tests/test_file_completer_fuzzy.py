import pytest
import os
from kogniterm.terminal.file_completer import fuzzy_match_files, FileCompleter

def test_exact_filename_match():
    files = [
        "kogniterm/terminal/file_completer.py",
        "kogniterm/terminal/terminal.py",
        "kogniterm/terminal/tui/tui_app.py",
    ]
    results = fuzzy_match_files("file_completer.py", files)
    assert len(results) > 0
    assert results[0][1] == "kogniterm/terminal/file_completer.py"

def test_filename_without_extension_match():
    files = [
        "kogniterm/terminal/file_completer.py",
        "kogniterm/terminal/terminal.py",
    ]
    results = fuzzy_match_files("file_completer", files)
    assert len(results) > 0
    assert results[0][1] == "kogniterm/terminal/file_completer.py"

def test_fuzzy_subsequence_match():
    files = [
        "kogniterm/terminal/file_completer.py",
        "kogniterm/terminal/tui/tui_app.py",
    ]
    results = fuzzy_match_files("ktfcomp", files)
    assert len(results) > 0
    assert results[0][1] == "kogniterm/terminal/file_completer.py"

def test_no_match_returns_empty():
    files = ["kogniterm/terminal/terminal.py"]
    results = fuzzy_match_files("nonexistentxyz999", files)
    assert results == []

def test_suggester_search_files():
    from kogniterm.terminal.tui.components.status_footer import KogniTermSuggester
    suggester = KogniTermSuggester()
    suggester.cached_files_list = [
        "kogniterm/terminal/file_completer.py",
        "kogniterm/terminal/terminal.py"
    ]
    matches = suggester.search_files("file_completer")
    assert len(matches) > 0
    assert matches[0][1] == "kogniterm/terminal/file_completer.py"

