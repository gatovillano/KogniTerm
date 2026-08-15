import re
from kogniterm.core.utils.tool_utils import sanitize_tool_name, normalize_tool_parameters_schema, convert_langchain_tool_to_litellm
from kogniterm.core.antigravity_client import AntigravityClient
from langchain_core.tools import tool


def test_sanitize_tool_name_hyphens_and_special_chars():
    assert sanitize_tool_name("project-analyzer") == "project_analyzer"
    assert sanitize_tool_name("email-manager") == "email_manager"
    assert sanitize_tool_name("native-photo-organizer") == "native_photo_organizer"
    assert sanitize_tool_name("parse-iso-mirrors-from-html") == "parse_iso_mirrors_from_html"
    assert sanitize_tool_name("tool.with.dots") == "tool_with_dots"
    assert sanitize_tool_name("tool:with:colons") == "tool_with_colons"


def test_sanitize_tool_name_leading_digits():
    res = sanitize_tool_name("123_my_tool")
    assert res == "_123_my_tool"
    assert re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', res)


def test_sanitize_tool_name_empty_or_none():
    assert sanitize_tool_name(None) == "_unnamed_function"
    assert sanitize_tool_name("") == "_unnamed_function"


def test_sanitize_tool_name_max_length():
    long_name = "a" * 100
    res = sanitize_tool_name(long_name)
    assert len(res) == 64


def test_normalize_tool_parameters_schema_sanitizes_properties():
    schema = {
        "type": "object",
        "properties": {
            "source-dir": {"type": "string"},
            "dest-dir": {"type": "string"},
        },
        "required": ["source-dir", "dest-dir"]
    }
    normalized = normalize_tool_parameters_schema(schema)
    assert "source_dir" in normalized["properties"]
    assert "dest_dir" in normalized["properties"]
    assert normalized["required"] == ["source_dir", "dest_dir"]


def test_convert_langchain_tool_to_litellm_sanitizes_name():
    @tool
    def sample_func(arg_one: str) -> str:
        """Sample function."""
        return arg_one

    sample_func.name = "my-custom-tool"
    converted = convert_langchain_tool_to_litellm(sample_func)
    assert converted["function"]["name"] == "my_custom_tool"


def test_antigravity_client_sanitize_tool_name():
    assert AntigravityClient._sanitize_tool_name("docker-auditor") == "docker_auditor"


def test_sanitize_tool_name_long_prefix_uniqueness():
    name1 = "_kogniterm_dynamic_skills_Cloud_Security_Container_Hardening_script1"
    name2 = "_kogniterm_dynamic_skills_Cloud_Security_Container_Hardening_script2"

    s1 = sanitize_tool_name(name1)
    s2 = sanitize_tool_name(name2)

    assert len(s1) == 64
    assert len(s2) == 64
    assert s1 != s2


def test_map_tools_deduplicates_duplicate_function_names():
    tools = [
        {"type": "function", "function": {"name": "same_tool_name", "description": "desc 1"}},
        {"type": "function", "function": {"name": "same_tool_name", "description": "desc 2"}},
    ]
    gemini_tools = AntigravityClient.map_tools(tools)
    decls = gemini_tools[0]["functionDeclarations"]
    assert len(decls) == 1
    assert decls[0]["name"] == "same_tool_name"

