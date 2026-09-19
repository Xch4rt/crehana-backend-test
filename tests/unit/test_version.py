"""The two copies of the version string, held equal by an assertion.

`taskmanager.__version__` is the runtime source and `pyproject.toml` carries the
packaging metadata; neither can read the other, so the only thing that can keep
them honest is a test. This is the same technique
`tests/unit/test_settings.py::test_env_example_documents_every_field` applies to
`.env.example`: two artifacts that must agree, one parity assertion, and drift
becomes a red run rather than a discovery.

`tomllib` is stdlib from Python 3.11, so reading the packaging file costs no
dependency. The file is read rather than parsed by hand for the obvious reason -
a regex over a TOML file would match `version` inside any other table that
happens to declare one.
"""

import tomllib
from pathlib import Path

import pytest

from taskmanager import __version__
from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app

pytestmark = pytest.mark.unit

# tests/unit/test_version.py -> tests/unit -> tests -> repository root.
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/taskmanager"
JWT_SECRET = "b" * 32


def test_the_runtime_version_matches_the_packaging_version() -> None:
    """`__version__` and `pyproject.toml` declare the same number."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    assert data["project"]["version"] == __version__


def test_the_openapi_document_reports_the_runtime_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The published document reads the constant, not a literal of its own."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))

    assert app.openapi()["info"]["version"] == __version__
