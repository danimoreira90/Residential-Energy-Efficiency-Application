"""RED tests for the file-uploader reset helper — Task 1.3 C1 follow-up.

Pins the lifecycle contract for `_bump_uploader_key`, the private helper that
the Streamlit page calls after every chat turn that carried an upload (success
or failure). Bumping the key is what forces st.file_uploader to instantiate a
fresh, empty widget on the next render — replacing the consumed_bill_upload_key
dedup pattern.

The page-level wiring (file_uploader(key=...) and the post-handle_message
st.rerun() inside the `if user_input := st.chat_input(...)` branch) is manual
smoke. Crucially, that wiring also guarantees the bump only fires after a
user-sent message — a user who uploads but hasn't sent keeps their file. Those
tests do not exercise that page-level invariant directly; they pin only the
helper's pure mutation contract.
"""
from typing import Any


def test_bump_uploader_key_increments_when_present() -> None:
    """Given an existing uploader_key, the bump increments it by exactly 1."""
    from energia.ui.streamlit_app import (
        _bump_uploader_key,  # pyright: ignore[reportPrivateUsage]
    )

    session_state: dict[str, Any] = {"uploader_key": 3}
    _bump_uploader_key(session_state)
    assert session_state["uploader_key"] == 4


def test_bump_uploader_key_initializes_when_missing() -> None:
    """Given a session_state with no uploader_key, the bump initialises to 0
    and immediately increments — landing at 1, not 0. Landing at 0 would mean
    the first reset produced the same key as the initial widget render, and
    Streamlit would keep the file."""
    from energia.ui.streamlit_app import (
        _bump_uploader_key,  # pyright: ignore[reportPrivateUsage]
    )

    session_state: dict[str, Any] = {}
    _bump_uploader_key(session_state)
    assert session_state["uploader_key"] == 1


def test_bump_uploader_key_does_not_touch_unrelated_keys() -> None:
    """The helper writes exactly one key — uploader_key — and leaves every
    other session_state entry byte-for-byte intact. Guards against accidental
    blast-radius creep into adjacent session_state fields (messages,
    conversation_id, budget_cb, etc.)."""
    from energia.ui.streamlit_app import (
        _bump_uploader_key,  # pyright: ignore[reportPrivateUsage]
    )

    sentinel_messages = [{"role": "user", "content": "olá"}]
    session_state: dict[str, Any] = {
        "uploader_key": 7,
        "messages": sentinel_messages,
        "conversation_id": "conv-xyz",
        "user_id": "user-abc",
    }
    _bump_uploader_key(session_state)
    assert session_state["uploader_key"] == 8
    assert session_state["messages"] is sentinel_messages
    assert session_state["conversation_id"] == "conv-xyz"
    assert session_state["user_id"] == "user-abc"
    assert set(session_state.keys()) == {
        "uploader_key",
        "messages",
        "conversation_id",
        "user_id",
    }
