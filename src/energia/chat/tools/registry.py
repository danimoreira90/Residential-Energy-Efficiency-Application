"""Tool registry — tools self-register here; ALL_TOOLS is derived from this."""
from langchain_core.tools import BaseTool

_REGISTRY: list[BaseTool] = []
_NAMES: set[str] = set()


def register_tool(tool: BaseTool) -> None:
    """Add a tool to the registry. Raises ValueError if the name is already taken."""
    if tool.name in _NAMES:
        raise ValueError(f"Tool '{tool.name}' is already registered")
    _REGISTRY.append(tool)
    _NAMES.add(tool.name)


def get_all_tools() -> list[BaseTool]:
    """Return a copy of all registered tools."""
    return list(_REGISTRY)
