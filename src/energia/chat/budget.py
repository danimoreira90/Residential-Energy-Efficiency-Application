"""TokenBudgetCallback — enforces HR-7 per-session Anthropic token budget.

Warns at 50% and 80% of settings.session_token_budget.
Raises TokenBudgetExceeded when cumulative tokens exceed the budget.
"""
import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from energia.config import settings

logger = logging.getLogger(__name__)


class TokenBudgetExceeded(Exception):
    """Raised when the per-session token budget (HR-7) is exceeded."""


class TokenBudgetCallback(BaseCallbackHandler):
    """Tracks cumulative token usage and enforces settings.session_token_budget."""

    def __init__(self) -> None:
        super().__init__()
        self._tokens_in: int = 0
        self._tokens_out: int = 0
        self._warned_50: bool = False
        self._warned_80: bool = False

    @property
    def total_tokens(self) -> int:
        return self._tokens_in + self._tokens_out

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        generations = response.generations
        if not generations or not generations[0]:
            return
        gen = generations[0][0]
        if not isinstance(gen, ChatGeneration):
            return
        msg = gen.message
        if not isinstance(msg, AIMessage) or msg.usage_metadata is None:
            return
        usage = msg.usage_metadata

        self._tokens_in += usage["input_tokens"]
        self._tokens_out += usage["output_tokens"]

        budget = settings.session_token_budget
        pct = self.total_tokens / budget

        if pct >= 0.5 and not self._warned_50:
            self._warned_50 = True
            logger.warning(
                "Token budget 50%% used: %d / %d tokens.",
                self.total_tokens,
                budget,
            )

        if pct >= 0.8 and not self._warned_80:
            self._warned_80 = True
            logger.warning(
                "Token budget 80%% used: %d / %d tokens.",
                self.total_tokens,
                budget,
            )

        if self.total_tokens > budget:
            raise TokenBudgetExceeded(
                f"Session token budget exceeded: {self.total_tokens} > {budget}. "
                "Please start a new session."
            )
