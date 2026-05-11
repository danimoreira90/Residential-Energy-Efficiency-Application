"""LangChain @tool wrappers around domain functions.

Each tool is a thin wrapper: domain logic lives in the corresponding domain
module (bill/, tariff/, solar/), which remains testable without any LangChain
or Anthropic imports. The wrapper adds the @tool decorator, docstring-as-
description, and args_schema= for input validation.

Sprint 0: hello_world stub — demonstrates tool-use loop.
Sprint 1 adds: parse_bill_image_tool, store_bill_tool, list_user_bills_tool,
               compare_bill_periods_tool, detect_consumption_anomaly_tool.
Sprint 2 adds: current_bandeira_tool, get_tariff_tool,
               simulate_tarifa_branca_tool.
Sprint 3 adds: estimate_solar_system_tool, solar_payback_tool.
"""
from langchain_core.tools import BaseTool

from energia.chat.tools.hello import hello_world_tool

ALL_TOOLS: list[BaseTool] = [hello_world_tool]
