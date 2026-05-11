"""Tests for ALL_TOOLS registry and hello_world stub tool (Task 0.5 — RED first)."""
from energia.chat.tools import ALL_TOOLS
from energia.chat.tools.hello import hello_world_tool


def test_hello_world_tool_has_correct_schema() -> None:
    """Tool schema exposes 'name' as a required string field."""
    from pydantic import BaseModel

    schema = hello_world_tool.args_schema
    assert schema is not None
    assert isinstance(schema, type) and issubclass(schema, BaseModel)
    assert "name" in schema.model_fields


def test_hello_world_tool_invocation_returns_greeting() -> None:
    """Direct invocation (no LLM) returns greeting dict with expected keys."""
    result = hello_world_tool.invoke({"name": "Daniel"})
    assert isinstance(result, dict)
    assert result["greeting"] == "Olá, Daniel!"
    assert "tool_version" in result


def test_all_tools_list_contains_hello_world() -> None:
    """ALL_TOOLS registry includes the hello_world stub."""
    names = [t.name for t in ALL_TOOLS]
    assert "hello_world" in names
