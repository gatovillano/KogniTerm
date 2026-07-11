import pytest
from pathlib import Path
from kogniterm.core.delegation.command_rules import CommandRulesResolver


@pytest.fixture
def temp_rules_file(tmp_path):
    rules_content = """
rules:
  - pattern: "^git status$"
    action: "allow"
  - pattern: "^rm -rf .*$"
    action: "deny"
  - pattern: "^sudo .*$"
    action: "deny"
  - pattern: "^pip install .*$"
    action: "ask"
"""
    rules_file = tmp_path / "command_rules.yaml"
    rules_file.write_text(rules_content)
    return rules_file


def test_default_rules_allow():
    resolver = CommandRulesResolver()
    resolver.load_rules()
    assert resolver.resolve("git status") == "allow"
    assert resolver.resolve("ls -la") == "allow"
    assert resolver.resolve("pwd") == "allow"
    assert resolver.resolve("cat README.md") == "allow"


def test_default_rules_deny():
    resolver = CommandRulesResolver()
    resolver.load_rules()
    assert resolver.resolve("rm -rf /") == "deny"
    assert resolver.resolve("sudo apt install vim") == "deny"
    assert resolver.resolve("dd if=/dev/zero of=/dev/sda") == "deny"


def test_default_fallback_is_ask():
    resolver = CommandRulesResolver()
    resolver.load_rules()
    # Unknown command should default to 'ask'
    assert resolver.resolve("pip install flask") == "ask"
    assert resolver.resolve("python script.py") == "ask"


def test_user_rules_take_precedence(temp_rules_file):
    resolver = CommandRulesResolver(rules_file_path=str(temp_rules_file))
    resolver.load_rules()

    # User-defined rules
    assert resolver.resolve("git status") == "allow"
    assert resolver.resolve("rm -rf /home") == "deny"
    assert resolver.resolve("sudo systemctl restart nginx") == "deny"
    assert resolver.resolve("pip install flask") == "ask"

    # Default fallback
    assert resolver.resolve("an_unknown_command") == "ask"


def test_resolve_strips_whitespace():
    resolver = CommandRulesResolver()
    resolver.load_rules()
    # Whitespace-padded command should still resolve correctly
    assert resolver.resolve("  git status  ") == "allow"


def test_lazy_load_on_resolve():
    """resolve() should auto-load rules if not loaded yet."""
    resolver = CommandRulesResolver()
    # Do NOT call load_rules() manually
    result = resolver.resolve("ls")
    assert result in ("allow", "ask", "deny")  # resolved without explicit load
