"""Stubs for tests/ui/ — prevent Streamlit runtime errors during plain-pytest import.

Streamlit's script_runner.py explicitly states it does not support
'if __name__ == "__main__"' guards, so we mock the module instead.
chat_input returns None to keep the message-handling if-block from executing.
MagicMock's __contains__ is truthy by default, so _bootstrap_session() sees all
session-state keys as already present and skips every initialisation block.
"""
import sys
from unittest.mock import MagicMock

_st_stub = MagicMock()
_st_stub.chat_input.return_value = None
# MagicMock.__contains__ defaults to False, which would cause _bootstrap_session()
# to call mint_user/mint_conversation. Return True so all keys appear to exist
# and every initialisation block is skipped.
_st_stub.session_state.__contains__.return_value = True
sys.modules.setdefault("streamlit", _st_stub)
