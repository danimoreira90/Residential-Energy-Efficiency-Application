"""Smoke tests: every top-level package and critical sub-module imports cleanly.

Each test performs a real import and asserts a meaningful attribute — not a
bare `assert True`. If any of these fail, the package scaffold is broken and
no other test is meaningful.
"""


def test_import_energia() -> None:
    import energia

    assert energia.__doc__ is not None
    assert "chatbot" in energia.__doc__


def test_import_config() -> None:
    from energia.config import Settings, settings

    assert isinstance(settings, Settings)
    assert settings.anthropic_model == "claude-sonnet-4-6"
    assert settings.session_token_budget == 200_000
    assert settings.aneel_base_url.startswith("https://")


def test_import_db() -> None:
    from energia import db

    assert callable(db.connect)


def test_import_bill() -> None:
    from energia import bill

    assert bill.__doc__ is not None
    assert "parser" in bill.__doc__


def test_import_tariff() -> None:
    from energia import tariff

    assert tariff.__doc__ is not None
    assert "ANEEL" in tariff.__doc__


def test_import_solar() -> None:
    from energia import solar

    assert solar.__doc__ is not None
    assert "pvlib" in solar.__doc__


def test_import_chat_tools() -> None:
    from energia.chat.tools import ALL_TOOLS

    assert isinstance(ALL_TOOLS, list)
    assert len(ALL_TOOLS) == 0  # Sprint 0: stub tool added in Task 0.5


def test_import_ui() -> None:
    from energia import ui

    assert ui.__doc__ is not None
    assert "Streamlit" in ui.__doc__
