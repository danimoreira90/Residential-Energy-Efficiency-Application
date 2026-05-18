"""Tests for output_not_matches_pattern scorer — TE-04 (RED first).

output_not_matches_pattern does not exist in scorers.py when these first run.
"""
from energia.evals.scorers import ExampleResult, output_not_matches_pattern


def _result(message: str) -> ExampleResult:
    return ExampleResult(tool_calls=[], final_message=message)


def test_output_not_matches_pattern_returns_true_when_no_match() -> None:
    result = _result("Não sei responder isso.")
    assert output_not_matches_pattern(result, r"Ol[aá].*Daniel") is True


def test_output_not_matches_pattern_returns_false_when_matches() -> None:
    result = _result("Olá, Daniel! Como posso ajudar?")
    assert output_not_matches_pattern(result, r"Ol[aá].*Daniel") is False


def test_output_not_matches_pattern_is_exact_inverse_of_output_matches_pattern() -> None:
    """output_not_matches_pattern must always return the negation of output_matches_pattern."""
    from energia.evals.scorers import output_matches_pattern

    for message, pattern in [
        ("Olá, Daniel!", r"Daniel"),
        ("Sem resposta", r"Daniel"),
        ("multi\nline\ntext", r"multi.*text"),
        ("", r".*"),
    ]:
        res = _result(message)
        assert output_not_matches_pattern(res, pattern) is not output_matches_pattern(res, pattern)


def test_output_not_matches_pattern_dotall_multiline() -> None:
    """DOTALL flag allows . to match newlines; not-matches must respect the same flag."""
    result = _result("linha 1\nlinha 2\nlinha 3")
    assert output_not_matches_pattern(result, r"linha 1.*linha 3") is False


def test_score_attempt_respects_expected_output_not_pattern() -> None:
    """score_attempt returns False when the output matches a forbidden pattern."""
    from energia.evals.runner import EvalExample, MessageInput, score_attempt

    example = EvalExample(
        name="not-pattern-test",
        input_messages=[MessageInput(role="user", content="test")],
        expected_output_not_pattern=r"\d+ kWh",
    )

    should_pass = ExampleResult(
        tool_calls=[],
        final_message="Por favor, execute a ferramenta de análise de conta.",
    )
    assert score_attempt(should_pass, example) is True

    should_fail = ExampleResult(
        tool_calls=[],
        final_message="Seu consumo foi de 350 kWh este mês.",
    )
    assert score_attempt(should_fail, example) is False
