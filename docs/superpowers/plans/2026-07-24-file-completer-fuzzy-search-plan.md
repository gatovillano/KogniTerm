# File Completer Fuzzy Search & Full-Width Popup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve file completion search in KogniTerm to use character-based fuzzy matching and expand the `@` completion popup to span the full width of the input bar.

**Architecture:** Implement a unified `fuzzy_match_files` engine in `kogniterm/terminal/file_completer.py`, integrate it into `KogniTermSuggester`, and update `tui_app.py` to position and style `#command_popup` dynamically over `#input_container`.

**Tech Stack:** Python 3.10+, Textual TUI, Rich, Pytest.

## Global Constraints
- Python 3.10+
- Must maintain backward compatibility with `FileCompleter` for prompt_toolkit.
- No breaking changes to existing `%` command completion or `:` docker completion.

---

### Task 1: Character-Based Fuzzy Matcher Function & Tests

**Files:**
- Create: `tests/test_file_completer_fuzzy.py`
- Modify: `kogniterm/terminal/file_completer.py`

**Interfaces:**
- Consumes: `query: str`, `cached_files: List[str]`, `workspace_directory: Optional[str]`, `max_results: int`
- Produces: `fuzzy_match_files(query, cached_files, workspace_directory=None, max_results=20) -> List[Tuple[float, str, str]]`

- [ ] **Step 1: Write the failing unit tests for fuzzy matching**

```python
# tests/test_file_completer_fuzzy.py
import pytest
from kogniterm.terminal.file_completer import fuzzy_match_files

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
    results = fuzzy_match_files("nonexistentxyz", files)
    assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_file_completer_fuzzy.py -v`
Expected: FAIL with `ImportError: cannot import name 'fuzzy_match_files'`.

- [ ] **Step 3: Implement `fuzzy_match_files` in `file_completer.py` and update `FileCompleter`**

In `kogniterm/terminal/file_completer.py`:
Add top-level function `fuzzy_match_files(query, cached_files, workspace_directory=None, max_results=20)` with fuzzy subsequence matching, scoring hierarchy (exact basename +2000, exact basename base +1500, substring +1000, boundary +100, gap penalty -10), metadata icon mapping, and score sorting.
Update `FileCompleter.get_completions` to call `fuzzy_match_files`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_file_completer_fuzzy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_file_completer_fuzzy.py kogniterm/terminal/file_completer.py
git commit -m "feat: implement character-based fuzzy file matcher algorithm"
```

---

### Task 2: Integrate `fuzzy_match_files` into `KogniTermSuggester`

**Files:**
- Modify: `kogniterm/terminal/tui/components/status_footer.py`

**Interfaces:**
- Consumes: `fuzzy_match_files` from `kogniterm.terminal.file_completer`
- Produces: `KogniTermSuggester.search_files(query: str, max_results: int = 20) -> List[Tuple[float, str, str]]`

- [ ] **Step 1: Write test for `KogniTermSuggester.search_files`**

Add test to `tests/test_file_completer_fuzzy.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_file_completer_fuzzy.py -k "test_suggester_search_files" -v`
Expected: FAIL with `AttributeError: 'KogniTermSuggester' object has no attribute 'search_files'`.

- [ ] **Step 3: Implement `search_files` in `KogniTermSuggester`**

In `kogniterm/terminal/tui/components/status_footer.py`:
Import `fuzzy_match_files` and add `search_files(self, query: str, max_results: int = 20)` method returning matched tuples/paths.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_file_completer_fuzzy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add kogniterm/terminal/tui/components/status_footer.py tests/test_file_completer_fuzzy.py
git commit -m "feat: expose search_files fuzzy method on KogniTermSuggester"
```

---

### Task 3: Full-Width Popup Layout & TUI `@` Completion Integration

**Files:**
- Modify: `kogniterm/terminal/tui/tui_app.py`

**Interfaces:**
- Consumes: `suggester.search_files(search_term)`
- Produces: Dynamic full-width `#command_popup` panel positioned directly on top of active input container.

- [ ] **Step 1: Update `#command_popup` CSS and `_reposition_popup` in `tui_app.py`**

- In `#command_popup` CSS rules, remove `width: 44;` and configure layer, border, background, and max-height.
- Update `_reposition_popup(self, input_widget, current_value)`:
  - Locate container: check `input_widget.parent` (or `#input_container` if visible).
  - Target region width: `target_region.width`.
  - Position X: `target_region.x`.
  - Position Y: `max(0, target_region.y - popup_h)`.
  - Apply `self.command_popup.styles.width = popup_w` and `self.command_popup.styles.offset = (popup_x, popup_y)`.

- [ ] **Step 2: Update `@` handling in `on_input_changed` and `on_text_area_changed`**

Replace old token-map search with `suggester.search_files(search_term, max_results=20)`.
Render each item in `command_popup` as a `ListItem` containing formatted text: Icon + relative path + right-aligned category.

- [ ] **Step 3: Verify tests pass**

Run: `python3 -m pytest tests/test_file_completer_fuzzy.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add kogniterm/terminal/tui/tui_app.py
git commit -m "feat: stretch completion popup over inputbar and use fuzzy file search"
```
