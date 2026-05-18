"""Tests for extracted Streamlit helper functions — CC-02 (RED first).

handle_message does not exist in streamlit_app yet when these first run.
"""
from unittest.mock import MagicMock, patch

from energia.chat.budget import TokenBudgetCallback, TokenBudgetExceeded
from energia.ui.streamlit_app import handle_message


def testhandle_message_returns_content_and_tokens_on_success() -> None:
    """handle_message returns (ai_content, tokens_used, tokens_in) on success."""
    mock_result = {
        "messages": [MagicMock(content="Olá!")],
        "tokens_used": 10,
        "tokens_in": 5,
    }
    budget_cb = TokenBudgetCallback()
    with patch("energia.ui.streamlit_app.GRAPH") as mock_graph:
        mock_graph.invoke.return_value = mock_result
        content, tokens_used, tokens_in = handle_message(
            "oi", "user-id", "conv-id", budget_cb
        )
    assert content == "Olá!"
    assert tokens_used == 10
    assert tokens_in == 5


def testhandle_message_returns_fallback_on_budget_exceeded() -> None:
    """handle_message returns a safe fallback tuple when TokenBudgetExceeded is raised."""
    budget_cb = TokenBudgetCallback()
    with patch("energia.ui.streamlit_app.GRAPH") as mock_graph:
        mock_graph.invoke.side_effect = TokenBudgetExceeded("limit hit")
        content, tokens_used, tokens_in = handle_message(
            "oi", "user-id", "conv-id", budget_cb
        )
    assert "limite" in content.lower() or "token" in content.lower()
    assert tokens_used == 0
    assert tokens_in == 0
