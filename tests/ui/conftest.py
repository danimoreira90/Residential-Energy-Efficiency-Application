"""Stubs for tests/ui/ — prevent Streamlit runtime errors during plain-pytest import.

Streamlit's script_runner.py explicitly states it does not support
'if __name__ == "__main__"' guards, so we mock the module instead.
chat_input returns None to keep the message-handling if-block from executing.
MagicMock's __contains__ is truthy by default, so _bootstrap_session() sees all
session-state keys as already present and skips every initialisation block.

settings.duckdb_path is also redirected to a per-session temp file BEFORE
streamlit_app is imported, so the module-level migrate() call lands in temp
rather than data/energia.duckdb. See TD-011.
"""
import os
import sys
import tempfile
from unittest.mock import MagicMock

# Redirect DuckDB writes from any module-level streamlit_app init away from
# the production data/energia.duckdb. energia.db.connect() reads
# settings.duckdb_path on every call, so mutating the singleton here is
# sufficient — energia.config.Settings is not frozen. Must run before the
# `from energia.ui.streamlit_app import handle_message` in any test module
# triggers `migrate()` at streamlit_app's module load (line 23).
from energia.config import settings

settings.duckdb_path = os.path.join(tempfile.gettempdir(), "energia_ui_tests.duckdb")

_st_stub = MagicMock()
_st_stub.chat_input.return_value = None
# MagicMock.__contains__ defaults to False, which would cause _bootstrap_session()
# to call mint_user/mint_conversation. Return True so all keys appear to exist
# and every initialisation block is skipped.
_st_stub.session_state.__contains__.return_value = True
sys.modules.setdefault("streamlit", _st_stub)
