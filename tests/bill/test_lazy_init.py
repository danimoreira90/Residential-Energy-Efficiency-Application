"""Fitness function: parser._client is None at module import time.

Mirrors tests/chat/test_lazy_init.py for the chat LLM. Anthropic clients must
not be constructed at import time — they require ANTHROPIC_API_KEY which is
loaded by load_dotenv() at app entry, not at import time. The parser uses a
lazy _get_client() accessor; this test characterizes that contract so future
refactors cannot regress to eager init.
"""
import energia.bill.parser as parser_module


def test_bill_parser_client_not_constructed_at_module_load() -> None:
    """importing energia.bill.parser must not instantiate anthropic.Anthropic.

    A non-None _client at import time means the module is calling
    anthropic.Anthropic() during import, which would require ANTHROPIC_API_KEY
    to be set before any test or app entry point can import the module.
    """
    assert getattr(parser_module, "_client") is None, (
        "_client was constructed at import time — bill parser must lazily init via _get_client()"
    )
