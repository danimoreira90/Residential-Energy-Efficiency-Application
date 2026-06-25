"""get_tariff tool wrapper tests (Task 2.3, RED first).

get_tariff is a PURE LOOKUP: distributor + subclass in, regulated tariff or an
honest disclaimer out. No DB, no ChatState bill reads, no causal language, no
distributor fallback.

The snapshot loader is mocked at the import site
(``energia.chat.tools.tariff.load_snapshot``) — exactly like test_compare mocks
``bill_store``. The mock returns a real ``TariffSnapshot`` seeded with the
committed Enel RJ values so the tool's resolution + branching + message format
are tested in isolation from the snapshot DATA (which Task 2.1 tests separately).

HR-5 enforcement is explicit:
- The baixa_renda (subsidized) branch and the unknown-distributor
  ("fora do escopo") branch return a ToolMessage with NO synthesized number —
  no decimal value, no "R$". The tool never invents a tariff and never falls
  back to Enel numbers for a distributor it does not cover.
HR-6 enforcement:
- get_tariff never touches bills; its output and logs carry no UC / bill PII.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from energia.chat.tools import ALL_TOOLS
from energia.tariff.snapshot import SubclassTariff, TariffSnapshot, TariffSource

_PATCH_TARGET = "energia.chat.tools.tariff.load_snapshot"

# A standalone decimal value (the shape an invented tariff would take), e.g.
# "1.0611" or "1,06". Class labels like "B1" or "REH 3570/2026" do NOT match.
_DECIMAL_NUM = re.compile(r"\d+[.,]\d+")
# A UC / installation-number-like run (6+ consecutive digits).
_UC_LIKE = re.compile(r"\d{6,}")


def _fake_snapshot() -> TariffSnapshot:
    """Real TariffSnapshot seeded with the committed Enel RJ values."""
    return TariffSnapshot(
        distributor="Enel Distribuição Rio",
        aliases=["Enel Rio", "Enel Brasil", "Enel RJ"],
        tariff_group="B1",
        unit="BRL_per_MWh",
        source=TariffSource(
            resolution="REH 3570/2026",
            published=date(2026, 3, 10),
            url="https://example.test/reh-3570",
        ),
        effective_from=date(2026, 3, 15),
        effective_to=date(2027, 3, 14),
        subclasses={
            "convencional": SubclassTariff(
                tusd=Decimal("731.72"), te=Decimal("329.38")
            ),
            "baixa_renda": SubclassTariff(
                tusd=Decimal("566.34"),
                te=Decimal("300.77"),
                v1_supported=False,
                note="subsidized",
            ),
        },
    )


def _get_tariff_tool() -> Any:
    for t in ALL_TOOLS:
        if t.name == "get_tariff":
            return t
    raise AssertionError("get_tariff tool is not registered in ALL_TOOLS")


def _make_state() -> dict[str, Any]:
    return {
        "messages": [],
        "user_id": "u1",
        "conversation_id": "c1",
        "tokens_used": 0,
        "tokens_in": 0,
    }


def _invoke(
    tool: Any,
    state: dict[str, Any],
    call_id: str,
    distributor: str,
    subclass: str | None = None,
) -> Any:
    args: dict[str, Any] = {"state": state, "distributor": distributor}
    if subclass is not None:
        args["subclass"] = subclass
    return tool.invoke({
        "name": "get_tariff",
        "args": args,
        "id": call_id,
        "type": "tool_call",
    })


def _content_of(result: Any) -> str:
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    msgs: list[Any] = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    return cast(str, msgs[0].content)


def _payload_of(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    assert match is not None, f"success body must include a JSON object: {content!r}"
    return cast(dict[str, Any], json.loads(match.group()))


def _assert_no_invented_number(content: str) -> None:
    assert "R$" not in content, (
        f"disclaimer must not carry an R$ value — HR-5. Content was: {content!r}"
    )
    assert _DECIMAL_NUM.search(content) is None, (
        f"disclaimer must not carry a decimal number — HR-5 forbids invented "
        f"tariffs. Content was: {content!r}"
    )


def _assert_no_json_payload(content: str) -> None:
    assert re.search(r"\{.*\}", content, re.DOTALL) is None, (
        f"disclaimer branch must NOT return a tariff JSON payload: {content!r}"
    )


# ---------------------------------------------------------------------------
# Registration / schema
# ---------------------------------------------------------------------------


def test_get_tariff_is_registered_in_all_tools() -> None:
    names = [t.name for t in ALL_TOOLS]
    assert "get_tariff" in names


def test_get_tariff_llm_visible_schema_excludes_state_and_tool_call_id() -> None:
    tool = _get_tariff_tool()
    llm_args: dict[str, Any] = tool.args  # type: ignore[no-any-return]
    assert "state" not in llm_args
    assert "tool_call_id" not in llm_args
    assert "distributor" in llm_args
    assert "subclass" in llm_args


# ---------------------------------------------------------------------------
# Happy path — Enel RJ convencional
# ---------------------------------------------------------------------------


def test_get_tariff_enel_canonical_name_returns_regulated_tariff(
    mocker: Any,
) -> None:
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    result = _invoke(
        tool, _make_state(), "call_enel", distributor="Enel Distribuição Rio"
    )

    assert isinstance(result, Command)
    payload = _payload_of(_content_of(result))
    assert payload["distributor"] == "Enel Distribuição Rio"
    assert payload["subclass"] == "convencional"
    assert payload["resolution"] == "REH 3570/2026"
    assert payload["effective_from"] == "2026-03-15"
    # (731.72 + 329.38) / 1000 — Decimal-equal, trailing zero tolerant.
    assert Decimal(str(payload["base_tariff_brl_per_kwh"])) == Decimal("1.0611")


@pytest.mark.parametrize(
    "variant",
    [
        "Enel Brasil",          # alias
        "Enel RJ",              # alias
        "enel rio",             # alias, lowercase
        "ENEL DISTRIBUICAO RIO",  # canonical, upper + accents stripped
        "enel distribuição rio",  # canonical, lower + accents kept
    ],
)
def test_get_tariff_resolves_aliases_and_accent_case_variants(
    mocker: Any, variant: str
) -> None:
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    result = _invoke(tool, _make_state(), "call_variant", distributor=variant)

    payload = _payload_of(_content_of(result))
    assert payload["distributor"] == "Enel Distribuição Rio"
    assert Decimal(str(payload["base_tariff_brl_per_kwh"])) == Decimal("1.0611")


def test_get_tariff_default_subclass_is_convencional(mocker: Any) -> None:
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    result = _invoke(
        tool, _make_state(), "call_default", distributor="Enel Rio"
    )

    payload = _payload_of(_content_of(result))
    assert payload["subclass"] == "convencional"


def test_get_tariff_header_frames_regulated_tariff_not_effective_rate(
    mocker: Any,
) -> None:
    """The success header must say this is the regulated TUSD+TE tariff, NOT the
    blended effective rate and NOT a causal explanation (HR-5 / TD-018)."""
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    result = _invoke(tool, _make_state(), "call_header", distributor="Enel RJ")
    content_lower = _content_of(result).lower()

    assert "tusd" in content_lower and "te" in content_lower
    assert "regulada" in content_lower
    # Disclaims the blended-effective-rate confusion compare.py warns about.
    assert "efetiva" in content_lower


# ---------------------------------------------------------------------------
# Disclaimer paths — HR-5: ZERO numbers, no Enel fallback
# ---------------------------------------------------------------------------


def test_get_tariff_baixa_renda_returns_disclaimer_without_numbers(
    mocker: Any,
) -> None:
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    result = _invoke(
        tool, _make_state(), "call_baixa", distributor="Enel RJ",
        subclass="baixa_renda",
    )

    assert isinstance(result, Command)
    content = _content_of(result)
    _assert_no_json_payload(content)
    _assert_no_invented_number(content)
    # The disclaimer names the subsidized nature, never a discounted number.
    assert "baixa renda" in content.lower() or "subsidi" in content.lower()


@pytest.mark.parametrize("distributor", ["Light", "CPFL", "Neoenergia"])
def test_get_tariff_unknown_distributor_returns_out_of_scope_no_fallback(
    mocker: Any, distributor: str
) -> None:
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    result = _invoke(
        tool, _make_state(), "call_unknown", distributor=distributor
    )

    assert isinstance(result, Command)
    content = _content_of(result)
    _assert_no_json_payload(content)
    _assert_no_invented_number(content)
    # No silent fallback to Enel's number for a distributor we don't cover.
    assert "1.0611" not in content
    # Names that v1 only covers Enel RJ.
    assert "enel" in content.lower()


# ---------------------------------------------------------------------------
# HR-6 — no bill PII in output or logs
# ---------------------------------------------------------------------------


def test_get_tariff_output_contains_no_bill_pii(mocker: Any) -> None:
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    result = _invoke(tool, _make_state(), "call_pii", distributor="Enel RJ")
    content = _content_of(result)
    payload = _payload_of(content)

    assert set(payload.keys()) == {
        "distributor",
        "subclass",
        "resolution",
        "effective_from",
        "base_tariff_brl_per_kwh",
    }
    assert "installation" not in content.lower()
    # The only multi-digit token allowed is the date (2026-03-15); strip dates
    # before scanning for a UC-like run.
    deident = content.replace("2026-03-15", "")
    assert _UC_LIKE.search(deident) is None, (
        f"output must not contain a UC-like digit run: {content!r}"
    )


def test_get_tariff_logger_emits_no_bill_pii(
    mocker: Any, caplog: pytest.LogCaptureFixture
) -> None:
    mocker.patch(_PATCH_TARGET, return_value=_fake_snapshot())

    tool = _get_tariff_tool()
    with caplog.at_level(logging.INFO, logger="energia.chat.tools.tariff"):
        _invoke(tool, _make_state(), "call_log", distributor="Enel RJ")

    joined = " ".join(rec.getMessage() for rec in caplog.records)
    assert "installation" not in joined.lower()
    assert _UC_LIKE.search(joined) is None, (
        f"logger must not emit a UC-like digit run: {joined!r}"
    )
