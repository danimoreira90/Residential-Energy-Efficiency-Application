"""Sprint 0 stub tool — demonstrates the tool-use loop end-to-end.

Removed in Sprint 1 when real bill-analysis tools ship.
"""
from langchain_core.tools import tool  # type: ignore[reportUnknownVariableType]
from pydantic import BaseModel, Field

from energia.chat.tools.registry import register_tool


class HelloInput(BaseModel):
    name: str = Field(description="Nome para cumprimentar")


@tool("hello_world", args_schema=HelloInput)
def hello_world_tool(name: str) -> dict[str, str]:
    """Retorna um cumprimento amigável. Ferramenta de demonstração — será
    removida no Sprint 1 quando ferramentas reais de análise de conta entrarem."""
    return {"greeting": f"Olá, {name}!", "tool_version": "v0.0-stub"}


register_tool(hello_world_tool)  # type: ignore[arg-type]
