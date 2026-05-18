"""LangChain tool registry for the Energia chatbot.

Each tool file calls register_tool() on its tool instance, which adds it to the
registry. Importing each tool module here triggers that self-registration.
ALL_TOOLS is then derived from the registry — no hand-maintained list.

To add a tool in a future sprint:
  1. Create src/energia/chat/tools/<name>.py and call register_tool() at the bottom.
  2. Add one import line below — __init__.py needs no other changes.
"""
from langchain_core.tools import BaseTool

import energia.chat.tools.hello  # noqa: F401  # pyright: ignore[reportUnusedImport] — side-effect: registers hello_world_tool
from energia.chat.tools.registry import get_all_tools

ALL_TOOLS: list[BaseTool] = get_all_tools()
