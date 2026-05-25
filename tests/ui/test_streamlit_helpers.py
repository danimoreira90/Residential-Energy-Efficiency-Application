"""Tests for extracted Streamlit helper functions — CC-02 (RED first).

handle_message does not exist in streamlit_app yet when these first run.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from energia.chat.budget import TokenBudgetCallback, TokenBudgetExceeded
from energia.ui.streamlit_app import handle_message

# ── Regression guard (TD-011) ─────────────────────────────────────────────────


def test_settings_duckdb_path_must_be_redirected_under_pytest() -> None:
    """Tests must never write to the production DuckDB (data/energia.duckdb).

    tests/ui/conftest.py redirects settings.duckdb_path to a per-session temp
    file before streamlit_app is imported. If this guard ever fails, the
    redirect has regressed and the next pytest run will leak rows into the
    production database — fix the redirect before any other change.
    """
    from energia.config import settings

    prod_path = (Path(__file__).resolve().parents[2] / "data" / "energia.duckdb").resolve()
    actual_path = Path(settings.duckdb_path).resolve()
    assert actual_path != prod_path, (
        f"settings.duckdb_path resolves to the production DuckDB ({actual_path}); "
        "tests/ui/conftest.py must redirect it before streamlit_app is imported."
    )


def testhandle_message_returns_content_and_tokens_on_success(tmp_db: dict[str, str]) -> None:
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
            "oi",
            tmp_db["user_id"],
            tmp_db["conversation_id"],
            budget_cb,
            db_path=tmp_db["db_path"],
        )
    assert content == "Olá!"
    assert tokens_used == 10
    assert tokens_in == 5


def testhandle_message_returns_fallback_on_budget_exceeded(tmp_db: dict[str, str]) -> None:
    """handle_message returns a safe fallback tuple when TokenBudgetExceeded is raised."""
    budget_cb = TokenBudgetCallback()
    with patch("energia.ui.streamlit_app.GRAPH") as mock_graph:
        mock_graph.invoke.side_effect = TokenBudgetExceeded("limit hit")
        content, tokens_used, tokens_in = handle_message(
            "oi",
            tmp_db["user_id"],
            tmp_db["conversation_id"],
            budget_cb,
            db_path=tmp_db["db_path"],
        )
    assert "limite" in content.lower() or "token" in content.lower()
    assert tokens_used == 0
    assert tokens_in == 0
