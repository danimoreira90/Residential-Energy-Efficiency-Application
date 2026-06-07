"""RED tests for bill-upload wiring in handle_message — Task 1.3 Stage C1.

Contract under test:
- handle_message gains an optional `bill_image: BillImageRef | None = None`.
- When bill_image is provided, the graph_state passed to GRAPH.invoke contains
  pending_bill_image with the supplied bytes and media_type.
- When bill_image is provided, the HumanMessage in graph_state.messages has its
  content prefixed with a signal naming the parse_bill tool — so the LLM knows
  to call it on this turn.
- When bill_image is None (default), pending_bill_image is absent and the
  HumanMessage content is the user_input verbatim — pre-Stage-C behavior is
  preserved.
- A module-level helper `_normalize_media_type` maps the non-standard
  "image/jpg" to "image/jpeg" and leaves the other supported MIMEs alone, so
  bytes coming out of st.file_uploader can be handed to parse_bill_image
  without per-browser MIME confusion.

All GRAPH calls are mocked — no real Anthropic traffic.
"""
from typing import Any, cast
from unittest.mock import MagicMock, patch

from energia.chat.budget import TokenBudgetCallback
from energia.chat.state import BillImageRef


def _mock_graph_result() -> dict[str, Any]:
    return {
        "messages": [MagicMock(content="ok")],
        "tokens_used": 5,
        "tokens_in": 2,
    }


def _captured_state(mock_graph: MagicMock) -> dict[str, Any]:
    """Extract the graph_state dict that handle_message passed to GRAPH.invoke."""
    call = mock_graph.invoke.call_args
    state: dict[str, Any] = call.args[0]
    return state


def test_handle_message_injects_pending_bill_image_when_bill_image_provided(
    tmp_db: dict[str, str],
) -> None:
    """When bill_image is passed, graph state must include pending_bill_image
    carrying the exact bytes and media_type — that is how parse_bill (Stage B)
    reads it via InjectedState."""
    from energia.ui.streamlit_app import handle_message

    bill_image: BillImageRef = {"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"}
    budget_cb = TokenBudgetCallback()

    with patch("energia.ui.streamlit_app.GRAPH") as mock_graph:
        mock_graph.invoke.return_value = _mock_graph_result()
        handle_message(
            "analise minha conta",
            tmp_db["user_id"],
            tmp_db["conversation_id"],
            budget_cb,
            db_path=tmp_db["db_path"],
            bill_image=bill_image,
        )

    state = _captured_state(mock_graph)
    assert "pending_bill_image" in state
    pending: dict[str, Any] = state["pending_bill_image"]
    assert pending["image_bytes"] == b"\x89PNG\r\n"
    assert pending["media_type"] == "image/png"


def test_handle_message_prefixes_human_message_with_parse_bill_signal(
    tmp_db: dict[str, str],
) -> None:
    """When bill_image is passed, the HumanMessage content sent to the graph
    must name the parse_bill tool — that is the runtime LLM signal that an
    image is attached on this turn. The user's actual text must still be there."""
    from langchain_core.messages import HumanMessage

    from energia.ui.streamlit_app import handle_message

    bill_image: BillImageRef = {"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"}
    budget_cb = TokenBudgetCallback()

    with patch("energia.ui.streamlit_app.GRAPH") as mock_graph:
        mock_graph.invoke.return_value = _mock_graph_result()
        handle_message(
            "analise minha conta",
            tmp_db["user_id"],
            tmp_db["conversation_id"],
            budget_cb,
            db_path=tmp_db["db_path"],
            bill_image=bill_image,
        )

    state = _captured_state(mock_graph)
    messages: list[Any] = state["messages"]
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, HumanMessage)
    content = cast(str, msg.content)
    assert "parse_bill" in content, (
        "the signal must name the parse_bill tool by id so the LLM routes to it"
    )
    assert "analise minha conta" in content, (
        "the user's actual text must be preserved inside the hinted turn"
    )


def test_handle_message_omits_signal_and_pending_image_when_no_bill_image(
    tmp_db: dict[str, str],
) -> None:
    """Regression guard for the pre-Stage-C contract: without bill_image the
    graph state must NOT carry pending_bill_image and the HumanMessage must
    contain only the user_input — no parse_bill signal, no other prefix."""
    from langchain_core.messages import HumanMessage

    from energia.ui.streamlit_app import handle_message

    budget_cb = TokenBudgetCallback()

    with patch("energia.ui.streamlit_app.GRAPH") as mock_graph:
        mock_graph.invoke.return_value = _mock_graph_result()
        handle_message(
            "olá",
            tmp_db["user_id"],
            tmp_db["conversation_id"],
            budget_cb,
            db_path=tmp_db["db_path"],
        )

    state = _captured_state(mock_graph)
    assert state.get("pending_bill_image") is None
    messages: list[Any] = state["messages"]
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, HumanMessage)
    content = cast(str, msg.content)
    assert content == "olá", (
        "without bill_image, user content must pass through untouched"
    )
    assert "parse_bill" not in content


def test_normalize_media_type_maps_image_jpg_to_image_jpeg() -> None:
    """_normalize_media_type maps the non-standard image/jpg → image/jpeg and
    leaves every other parser-accepted MIME untouched. parse_bill_image's
    SUPPORTED_MEDIA_TYPES does not include image/jpg, so the uploader caller
    must normalize before constructing BillImageRef."""
    # _normalize_media_type is module-internal but legitimately tested directly
    # from outside the module — the helper has no public counterpart and the
    # test pins its mapping contract.
    from energia.ui.streamlit_app import (
        _normalize_media_type,  # pyright: ignore[reportPrivateUsage]
    )

    assert _normalize_media_type("image/jpg") == "image/jpeg"
    assert _normalize_media_type("image/jpeg") == "image/jpeg"
    assert _normalize_media_type("image/png") == "image/png"
    assert _normalize_media_type("image/gif") == "image/gif"
    assert _normalize_media_type("image/webp") == "image/webp"
