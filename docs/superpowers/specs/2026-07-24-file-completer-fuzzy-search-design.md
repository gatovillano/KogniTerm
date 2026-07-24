# Design Spec: Character-Based Fuzzy File Search & Extended Completion Panel for KogniTerm

**Date**: 2026-07-24
**Topic**: Enhanced `@` File Completion Search & Extended Full-Width InputBar Menu Panel

---

## 1. Overview
Currently, KogniTerm's `@` file completion in `tui_app.py` relies on exact token lookups (`_file_token_map`) and restrictive substring matching in `file_completer.py`. When a user types partial paths, filename basenames without extensions, or character sequences (e.g. `@file_completer` or `@ktfcomp`), no results or unexpected results are displayed. Additionally, the completion popup (`#command_popup`) is styled with a narrow fixed width (`44` characters) aligned near the cursor rather than spanning the full width of the input bar.

This design introduces a unified character-based fuzzy matching algorithm for file completions and transforms the completion popup into an extended full-width panel positioned directly above the input bar.

---

## 2. Architecture & Components

```
+-----------------------------------------------------------------------+
|  KogniTerm TUI (tui_app.py)                                          |
|                                                                       |
|  ChatInput / TextArea / Input                                         |
|  +-----------------------------------------------------------------+  |
|  |  User types: @file_completer.py                                 |  |
|  +-----------------------------------------------------------------+  |
|                               ^                                       |
|                               | (reposition & show full-width)        |
|  #command_popup (ListView) -- Extended Panel (Width = InputBar Width) |
|  +-----------------------------------------------------------------+  |
|  | 🐍 kogniterm/terminal/file_completer.py            python       |  |
|  | 📝 docs/superpowers/specs/...                       texto        |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
                                |
                                v
               KogniTermSuggester / FileCompleter
              (kogniterm/terminal/file_completer.py)
                                |
            +-------------------+-------------------+
            |                                       |
            v                                       v
  fuzzy_match_files()                    cached_files_list
  (Subsequence Fuzzy Engine)            (Background Walk Cache)
```

---

## 3. Component Details

### A. Unified Fuzzy Search Engine (`kogniterm/terminal/file_completer.py`)
Add a top-level helper function `fuzzy_match_files(query: str, files: List[str], workspace_dir: str = "", max_results: int = 20) -> List[Tuple[float, str, str]]`:

1. **Subsequence Check**:
   - Normalize `query` and candidate `file` paths to lowercase with `/` path separators.
   - Match if all characters of `query` appear in sequence within the candidate path.
2. **Scoring Hierarchy**:
   - **Exact Basename Match**: Query matches `os.path.basename(file)` exactly $\rightarrow$ **+2000 pts**.
   - **Exact Basename Base Match**: Query matches basename without extension (e.g. `file_completer` $\rightarrow$ `file_completer.py`) $\rightarrow$ **+1500 pts**.
   - **Exact Substring in Basename**: Query is a contiguous substring in basename $\rightarrow$ **+1000 pts** (+300 if at start).
   - **Exact Substring in Path**: Query is a contiguous substring anywhere in path $\rightarrow$ **+600 pts**.
   - **Boundary Matches**: Characters matching right after `/`, `_`, `-`, or `.` $\rightarrow$ **+100 pts** per boundary.
   - **Contiguous Character Bonus**: Consecutive matched characters in subsequence $\rightarrow$ **+50 pts** per char.
   - **Gap Penalty**: Penalty for distance between matched characters in subsequence $\rightarrow$ **-10 pts** per gap.
   - **Path Depth Tie-Breaker**: Shorter path depth preferred $\rightarrow$ **-20 pts** per `/`.
3. **Metadata & Icons**:
   - Map extension to category (`📁 dir`, `🐍 python`, `📝 texto`, `⚙️ config`, `🌐 js/ts`, `🖥️ shell`, `🎨 web`, `📄 archivo`).

### B. `FileCompleter` & `KogniTermSuggester` Integration
- `FileCompleter.get_completions()`: Use `fuzzy_match_files()` for `@` completions.
- `KogniTermSuggester`:
  - Provide `search_files(query: str, max_results: int = 20)` method calling `fuzzy_match_files()`.
  - Retain background workspace scanner `_update_files()` to keep `cached_files_list` up-to-date.

### C. Extended Popup Panel UI (`tui_app.py` & CSS)
1. **CSS Styling (`#command_popup`)**:
   - Change `#command_popup` CSS width from fixed `44` to dynamic full width.
   - Enhanced panel styling with subtle background (`#1e1e2e`), clear border (`#3b82f6`), and hover/highlight states.
2. **Positioning (`_reposition_popup`)**:
   - Determine target container (`#input_container` or active input widget).
   - Set `popup_x = target_region.x` and `popup_w = target_region.width`.
   - Set `popup_y = max(0, target_region.y - popup_h)`.
   - Update `self.command_popup.styles.width = popup_w` and `self.command_popup.styles.offset = (popup_x, popup_y)`.
3. **Item Rendering**:
   - Render completions with wide layout: Icon + Relative Path + Category Tag (right-aligned).

---

## 4. Verification Plan

### Automated Tests
- Run `pytest` or Python unit tests verifying `fuzzy_match_files()`:
  - Exact match (`file_completer.py`) scores highest.
  - Substring match (`file_completer`) returns `.py` file.
  - Subsequence match (`ktfcomp`) returns `kogniterm/terminal/file_completer.py`.
  - Non-matching queries return empty list.

### Manual / Integration Verification
- Execute KogniTerm TUI and test `@` completions:
  - Type `@file_completer.py` $\rightarrow$ verify exact match appears at top.
  - Type `@file_completer` $\rightarrow$ verify `kogniterm/terminal/file_completer.py` appears.
  - Type `@ktfcomp` $\rightarrow$ verify fuzzy character match works.
  - Observe completion menu popup $\rightarrow$ verify it stretches to the full width of the input bar.
