"""Tests for TokenBudgetCallback (HR-7) — Task 0.5, RED first."""
import logging
import uuid
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from energia.chat.budget import TokenBudgetCallback, TokenBudgetExceeded
from energia.config import settings


def _make_llm_result(input_tokens: int, output_tokens: int) -> LLMResult:
    """Build a minimal LLMResult carrying usage_metadata on an AIMessage."""
    msg = AIMessage(
        content="response",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    )
    gen = ChatGeneration(message=msg)
    return LLMResult(generations=[[gen]])


def test_budget_callback_raises_at_threshold() -> None:
    """on_llm_end raises TokenBudgetExceeded when cumulative tokens exceed budget."""
    cb = TokenBudgetCallback()
    # Just over the budget in one shot
    big_result = _make_llm_result(
        input_tokens=settings.session_token_budget,
        output_tokens=1,
    )
    with pytest.raises(TokenBudgetExceeded):
        cb.on_llm_end(response=big_result, run_id=uuid.uuid4())


def test_budget_callback_warns_at_50_percent(caplog: Any) -> None:
    """on_llm_end at 50% of budget emits a WARNING log (exactly once)."""
    cb = TokenBudgetCallback()
    half_tokens = settings.session_token_budget // 2
    half_result = _make_llm_result(input_tokens=half_tokens, output_tokens=0)

    with caplog.at_level(logging.WARNING, logger="energia.chat.budget"):
        cb.on_llm_end(response=half_result, run_id=uuid.uuid4())

    assert any("50%" in r.message or "budget" in r.message.lower() for r in caplog.records)


def test_budget_callback_warns_at_80_percent(caplog: Any) -> None:
    """on_llm_end at 80% of budget emits a WARNING log exactly once (_warned_80 idempotency)."""
    cb = TokenBudgetCallback()
    eighty_pct = int(settings.session_token_budget * 0.8)
    result_80 = _make_llm_result(input_tokens=eighty_pct, output_tokens=0)

    with caplog.at_level(logging.WARNING, logger="energia.chat.budget"):
        cb.on_llm_end(response=result_80, run_id=uuid.uuid4())

    warning_80_records = [r for r in caplog.records if "80%" in r.message]
    assert len(warning_80_records) == 1

    # A second call past 80% must NOT fire the warning again.
    caplog.clear()
    result_extra = _make_llm_result(input_tokens=1, output_tokens=0)
    with caplog.at_level(logging.WARNING, logger="energia.chat.budget"):
        cb.on_llm_end(response=result_extra, run_id=uuid.uuid4())

    assert not any("80%" in r.message for r in caplog.records)
