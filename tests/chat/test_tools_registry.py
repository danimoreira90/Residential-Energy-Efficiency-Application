"""Tests for the tool registry — CC-04 (RED first).

registry.py does not exist yet when these tests are first run.
"""
import pytest

from energia.chat.tools import ALL_TOOLS
from energia.chat.tools.registry import get_all_tools, register_tool


def test_all_tools_derived_from_registry() -> None:
    """ALL_TOOLS in __init__ must equal the live registry — no parallel list."""
    assert ALL_TOOLS == get_all_tools()


def test_hello_world_self_registers_on_import() -> None:
    """hello_world_tool registers itself when its module is imported."""
    names = {t.name for t in get_all_tools()}
    assert "hello_world" in names


def test_register_tool_rejects_duplicate() -> None:
    """Registering a name that is already in the registry raises ValueError."""
    hello = next(t for t in get_all_tools() if t.name == "hello_world")
    with pytest.raises(ValueError, match="already registered"):
        register_tool(hello)


def test_get_all_tools_returns_copy() -> None:
    """Mutating the returned list does not corrupt the registry."""
    snapshot = get_all_tools()
    snapshot.clear()
    assert len(get_all_tools()) > 0
