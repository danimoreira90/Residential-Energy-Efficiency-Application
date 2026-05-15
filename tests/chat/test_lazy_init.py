"""Fitness functions for CC-01 / AF-01 — lazy LLM and GRAPH initialization.

RED before fix: nodes._llm and _llm_with_tools are real objects at import time;
                graph.GRAPH is in module __dict__ at import time.
GREEN after fix: both are None / absent until first use.
"""
import sys

import energia.chat.graph as graph_module
import energia.chat.nodes as nodes_module


def test_llm_not_constructed_at_module_load() -> None:
    """importing energia.chat.nodes must not instantiate ChatAnthropic."""
    # getattr avoids pyright reportPrivateUsage for the underscore name.
    assert getattr(nodes_module, "_llm") is None, (
        "_llm was constructed at import time — fix CC-01: move to _get_llm_with_tools()"
    )


def test_llm_with_tools_not_constructed_at_module_load() -> None:
    """importing energia.chat.nodes must not call .bind_tools()."""
    assert getattr(nodes_module, "_llm_with_tools") is None, (
        "_llm_with_tools was constructed at import time — fix CC-01"
    )


def test_graph_not_in_module_dict_at_import() -> None:
    """importing energia.chat.graph must not call build_graph() eagerly.

    After the fix, GRAPH is accessible via __getattr__ but is NOT pre-built
    into the module __dict__.  This also means importing the module no longer
    requires ANTHROPIC_API_KEY to be present in the environment (AF-01).
    """
    # Reload the module so we see what happens on a fresh import, not the
    # cached state after other tests may have triggered __getattr__.
    import importlib

    fresh = importlib.reload(graph_module)
    # After reload, before any access to GRAPH, it must not be in __dict__.
    assert "GRAPH" not in vars(fresh), (
        "GRAPH is constructed at module load time — fix CC-01 / AF-01: "
        "replace 'GRAPH = build_graph()' with lazy __getattr__"
    )
    # Restore the module reference so other tests are unaffected.
    sys.modules["energia.chat.graph"] = fresh
