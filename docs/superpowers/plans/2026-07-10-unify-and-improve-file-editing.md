# Unify and Improve File Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all file editing tools into `advanced_file_editor` and harden the matching/normalization logic to achieve surgical precision and full reliability.

**Architecture:** Route deprecated editing tools to `advanced_file_editor` with `action="full_replacement"`, refine `FlexibleMatcher` in `file_editor.py` to auto-strip line numbers, normalize newlines, auto-align indentation, restrict fuzzy matching to single-line horizontal spacing, and resolve multiple matches using proximity-based context hints.

**Tech Stack:** Python 3, pytest, regex

## Global Constraints
- Do not import external non-standard packages not already in requirements.
- Maintain existing API/argument compatibility.
- Ensure unified diff generation and RaceConditionGuard verification are preserved.

---

### Task 1: Unify Editing Tools and Deprecate Duplicates

**Files:**
- Modify: `kogniterm/skills/bundled/file-update/scripts/tool.py`
- Modify: `kogniterm/skills/bundled/file-operations/scripts/tool.py`

**Interfaces:**
- Consumes: None
- Produces: Redirection of `file_update` and `sophisticated_editor` to `advanced_file_editor`.

- [ ] **Step 1: Modify file-update tool to delegate to advanced_file_editor**
  Update `kogniterm/skills/bundled/file-update/scripts/tool.py` so that it imports and calls `advanced_file_editor` with `action="full_replacement"`.
  ```python
  # In kogniterm/skills/bundled/file-update/scripts/tool.py
  from kogniterm.skills.bundled.advanced_file_editor.scripts.tool import advanced_file_editor_tool

  def _apply_file_update(path: str, content: str) -> str:
      result = advanced_file_editor_tool(path=path, action="full_replacement", content=content, confirm=True)
      if isinstance(result, dict):
          if "message" in result:
              return result["message"]
          if "error" in result:
              return f"Error: {result['error']}"
          return str(result)
      return str(result)

  def file_update_tool(path: str, content: str, confirm: bool = False) -> dict:
      return advanced_file_editor_tool(path=path, action="full_replacement", content=content, confirm=confirm)
  ```

- [ ] **Step 2: Modify file-operations tool to redirect sophisticated_editor and advanced_file_editor**
  Update `kogniterm/skills/bundled/file-operations/scripts/tool.py` at lines 49-50 to use `advanced_file_editor_tool` from the advanced-file-editor skill to ensure atomic batch execution is used if provided:
  ```python
  # In kogniterm/skills/bundled/file-operations/scripts/tool.py
  from kogniterm.skills.bundled.advanced_file_editor.scripts.tool import advanced_file_editor_tool
  # ...
      elif operation == "sophisticated_editor" or operation == "advanced_file_editor":
          return advanced_file_editor_tool(**kwargs)
  ```

- [ ] **Step 3: Run existing tests to ensure no syntax errors**
  Run: `pytest tests/unit/test_file_editor.py`
  Expected: Command runs, but continues to show 5 failures due to matching bugs.

- [ ] **Step 4: Commit changes**
  ```bash
  git add kogniterm/skills/bundled/file-update/scripts/tool.py kogniterm/skills/bundled/file-operations/scripts/tool.py
  git commit -m "refactor: unify file-update and file-operations editing under advanced_file_editor"
  ```

---

### Task 2: Implement Input Normalization and Auto-Stripping in `FlexibleMatcher`

**Files:**
- Modify: `kogniterm/skills/bundled/file-operations/scripts/file_editor.py`

**Interfaces:**
- Consumes: Raw input parameters (`target_content`, `replacement_content`, `content`).
- Produces: Cleaned, normalized strings and original line ending style detection.

- [ ] **Step 1: Implement line number prefix stripping**
  Add a helper function `_strip_line_numbers(text: Optional[str]) -> Optional[str]` to clean up line numbers:
  ```python
  def _strip_line_numbers(text: Optional[str]) -> Optional[str]:
      if text is None:
          return None
      lines = text.splitlines(keepends=True)
      cleaned_lines = []
      for line in lines:
          # Match prefix like "  12 | " or "12 |"
          cleaned_line = re.sub(r"^\s*\d+\s*\|\s?", "", line)
          cleaned_lines.append(cleaned_line)
      return "".join(cleaned_lines)
  ```

- [ ] **Step 2: Integrate input normalization into advanced_file_editor**
  At the beginning of `advanced_file_editor` and `_apply_operation_pure` in `kogniterm/skills/bundled/file-operations/scripts/file_editor.py`, preprocess and strip line numbers from inputs, and normalize `\r\n` to `\n`:
  ```python
  # Detect original newline endings of the file
  has_crlf = "\r\n" in original_content
  # Normalize file content to LF
  original_content_lf = original_content.replace("\r\n", "\n")

  # Clean inputs
  target_cleaned = _strip_line_numbers(target_content).replace("\r\n", "\n") if target_content is not None else None
  replacement_cleaned = _strip_line_numbers(replacement_content).replace("\r\n", "\n") if replacement_content is not None else None
  content_cleaned = _strip_line_numbers(content_arg).replace("\r\n", "\n") if content_arg is not None else None
  ```

- [ ] **Step 3: Restore original newlines before writing back**
  Before writing/returning success, convert `\n` back to `\r\n` if `has_crlf` is True:
  ```python
  if has_crlf:
      new_content = new_content.replace("\n", "\r\n")
  ```

- [ ] **Step 4: Run tests to verify progress**
  Run: `pytest tests/unit/test_file_editor.py`
  Expected: Basic matching works, some tests might still fail due to fuzzy matching / proximity bugs.

- [ ] **Step 5: Commit changes**
  ```bash
  git add kogniterm/skills/bundled/file-operations/scripts/file_editor.py
  git commit -m "feat: implement line-number stripping and newline normalization in file_editor"
  ```

---

### Task 3: Improve Fuzzy Matching, Indentation Alignment, and Context Hint Proximity

**Files:**
- Modify: `kogniterm/skills/bundled/file-operations/scripts/file_editor.py`

- [ ] **Step 1: Fix fuzzy matching to not cross newlines**
  Change the fuzzy matching logic in `FlexibleMatcher.find_match` to only match horizontal spaces. Replace `\s*` or `\s+` with horizontal space matching (`[ \t]*` and `[ \t]+`):
  ```python
  # Horizontal fuzzy matching
  tokens = [t for t in re.split(r'[ \t]+', target.strip()) if t]
  if not tokens:
      return []
  pattern_parts = [r'[ \t]*'.join(re.escape(t) for t in tokens)]
  pattern = ''.join(pattern_parts)
  # Compile without re.DOTALL to prevent matching newlines
  regex = re.compile(pattern)
  ```
  Wait, if the target itself has multiple lines, split the target by lines, and perform fuzzy matching for each line sequentially!
  Let's write a robust multi-line matching:
  ```python
  # If target is multiline:
  target_lines = target.splitlines()
  # For each line, generate a regex pattern that matches horizontal whitespace flexibly.
  # Combine them using \n or \r?\n.
  line_patterns = []
  for line in target_lines:
      line_tokens = [t for t in re.split(r'[ \t]+', line.strip()) if t]
      if line_tokens:
          line_patterns.append(r'[ \t]*'.join(re.escape(t) for t in line_tokens))
      else:
          line_patterns.append(r'')
  pattern = r'\n[ \t]*'.join(line_patterns)
  regex = re.compile(pattern)
  ```

- [ ] **Step 2: Implement auto-indentation offset adjustment**
  When applying replacement content in `replace_block`, detect the indentation level difference between the matched target in the file and the original target:
  ```python
  # In _apply_operation_pure under replace_block / replace_lines:
  # Extract the line prefix/indentation of the match and the target
  match_line = lines[m["line_start"] - 1]
  match_indent = len(match_line) - len(match_line.lstrip())
  target_line = target_content.splitlines()[0] if target_content else ""
  target_indent = len(target_line) - len(target_line.lstrip())
  indent_diff = match_indent - target_indent

  # Apply indent_diff to each line of replacement_content
  if indent_diff != 0:
      replacement_lines = replacement_cleaned.splitlines(keepends=True)
      adjusted_lines = []
      for line in replacement_lines:
          if line.strip():  # Only indent non-empty lines
              if indent_diff > 0:
                  adjusted_lines.append(" " * indent_diff + line)
              else:
                  # Strip up to abs(indent_diff) spaces
                  adjusted_lines.append(line[min(abs(indent_diff), len(line) - len(line.lstrip())):])
          else:
              adjusted_lines.append(line)
      replacement_cleaned = "".join(adjusted_lines)
  ```

- [ ] **Step 3: Implement proximity-based context hint resolver**
  In `FlexibleMatcher.find_unique`, implement distance calculation:
  ```python
  # Find all context hint matches
  hint_matches = []
  if context_hint:
      # Search for hint exact/fuzzy
      hint_matches = FlexibleMatcher.find_match(content, context_hint, fuzzy=True)

  if len(matches) > 1:
      if context_hint and hint_matches:
          best_match = None
          min_dist = float('inf')
          for m in matches:
              for h in hint_matches:
                  dist = abs(m["line_start"] - h["line_start"])
                  if dist < min_dist and dist <= 20:
                      min_dist = dist
                      best_match = m
          if best_match:
              return best_match
      raise MultipleMatchesError(target=target, matches=matches, hint=context_hint)
  ```

- [ ] **Step 4: Run tests to verify the fixes**
  Run: `pytest tests/unit/test_file_editor.py`
  Expected: More tests passing (like `test_fuzzy_does_not_cross_newlines` and `test_context_hint_disambiguates`).

- [ ] **Step 5: Commit changes**
  ```bash
  git add kogniterm/skills/bundled/file-operations/scripts/file_editor.py
  git commit -m "feat: improve fuzzy match, indentation alignment and context hint proximity"
  ```

---

### Task 4: Fix Newline Insertion and Agent Fallbacks

**Files:**
- Modify: `kogniterm/skills/bundled/file-operations/scripts/file_editor.py`
- Modify: `kogniterm/core/agents/bash_agent.py`

- [ ] **Step 1: Fix duplicate newline bugs in insert_after_match/insert_before_match**
  Ensure newline addition checks actual line endings:
  ```python
  # In file_editor.py insert_after_match:
  text = content_arg
  # If matching content ends with newline, do not prepend another newline unless text doesn't start with newline
  if m["matched_text"].endswith("\n") or content[:m["end"]].endswith("\n"):
      # Clean up starting newlines of text if redundant
      if text.startswith("\n"):
          text = text[1:]
  else:
      if not text.startswith("\n"):
          text = "\n" + text
  if not text.endswith("\n"):
      text = text + "\n"
  ```

- [ ] **Step 2: Correct fallback tool execution in bash_agent.py**
  In `kogniterm/core/agents/bash_agent.py` at line 1046-1052:
  ```python
  elif tool_name in ["advanced_file_editor", "advanced_file_editor_tool"]:
      from kogniterm.skills.bundled.advanced_file_editor.scripts.tool import advanced_file_editor_tool
      args_to_pass = dict(exception.tool_args)
      args_to_pass["confirm"] = True
      edit_result = advanced_file_editor_tool(**args_to_pass)
      content = edit_result
  ```

- [ ] **Step 3: Run existing unit tests**
  Run: `pytest tests/unit/test_file_editor.py`
  Expected: All 30 tests pass.

- [ ] **Step 4: Add new tests for auto-stripping and auto-indentation**
  Append new tests to `tests/unit/test_file_editor.py`:
  ```python
  def test_auto_strip_line_numbers(self, tmp_file):
      result = advanced_file_editor(
          path=tmp_file,
          action="replace_block",
          target_content="   1 | def foo():\n   2 |     return 1",
          replacement_content="def foo():  # stripped\n    return 42",
          confirm=True,
      )
      assert result["status"] == "success"
  ```

- [ ] **Step 5: Verify all tests pass**
  Run: `pytest tests/unit/test_file_editor.py`
  Expected: All tests pass.

- [ ] **Step 6: Commit changes**
  ```bash
  git add kogniterm/skills/bundled/file-operations/scripts/file_editor.py kogniterm/core/agents/bash_agent.py tests/unit/test_file_editor.py
  git commit -m "fix: fix newline insertions and correct agent approval fallback execution"
  ```
