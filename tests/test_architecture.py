"""Architecture guard tests — static checks that enforce structural rules.

These tests parse source files with ast or plain text search; they never
import the modules under test.  A failure here means a structural constraint
has been broken, not a runtime bug.
"""
import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).parent.parent / "src" / "energia"

# ── AF-03 ─────────────────────────────────────────────────────────────────────

_MODELS_FORBIDDEN = {
    "duckdb",
    "langgraph",
    "langchain",
    "langchain_core",
    "langsmith",
    "sqlalchemy",
    "fastapi",
    "streamlit",
    "anthropic",
}


def test_models_imports_only_stdlib_and_pydantic() -> None:
    """AF-03: src/energia/models.py must not import any framework or infrastructure module."""
    src = _SRC_ROOT / "models.py"
    tree = ast.parse(src.read_text(encoding="utf-8"), filename=str(src))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _MODELS_FORBIDDEN:
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in _MODELS_FORBIDDEN:
                violations.append(node.module)

    assert not violations, (
        f"models.py has forbidden infrastructure imports: {violations}"
    )


# ── TE-08 ─────────────────────────────────────────────────────────────────────


def test_eval_runner_does_not_wire_duckdb_audit_callback() -> None:
    """TE-08: eval runner must not reference DuckDBAuditCallback.

    Wiring that callback into run_example would cause a foreign-key violation
    because the runner uses synthetic IDs ('eval-runner', 'eval-<name>') that
    do not exist in the users/conversations tables.
    """
    src = _SRC_ROOT / "evals" / "runner.py"
    assert "DuckDBAuditCallback" not in src.read_text(encoding="utf-8")


# ── LGPD langsmith guard ──────────────────────────────────────────────────────


def test_langsmith_not_imported_anywhere_in_src() -> None:
    """LGPD guard: langsmith must not be imported anywhere under src/energia/.

    langsmith is a listed dependency but deliberately unused — importing it
    would risk routing bill data (PII) to a cloud trace service.
    """
    violations: list[str] = []
    for py_file in sorted(_SRC_ROOT.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "langsmith":
                        violations.append(str(py_file))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] == "langsmith":
                    violations.append(str(py_file))

    assert not violations, f"langsmith imported in: {violations}"
