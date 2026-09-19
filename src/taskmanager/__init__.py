"""The application package, and the one runtime source of its version.

Every other `__init__.py` in this project is zero bytes on purpose - no
re-export barrels, import from the defining module - so this file is the single
deliberate exception, and it exists for a reason worth writing down. `/health`
reports a version (D-08) and so does the OpenAPI document; before this constant
there were three copies of the string, in `main.py`, in `pyproject.toml` and in
a test literal, with nothing making them agree.

`__version__` below is the **runtime** source: `main.py` and `/health` read it
and nothing else states it. `pyproject.toml` keeps its own value as *packaging*
metadata - a build backend cannot be told to import the package it is about to
build - and `tests/unit/test_version.py` asserts the two are equal, so drift is
a failing test rather than an inconsistency somebody notices in a review.

The rejected alternative is `importlib.metadata.version("taskmanager")`, which
would leave one literal instead of two. It fails on a bare checkout: the package
is importable there only because `pytest.ini` sets `pythonpath = src`, and
nothing has installed distribution metadata for it, so the call raises
`PackageNotFoundError` in exactly the environment the test suite runs in.
"""

from typing import Final

__version__: Final[str] = "0.1.0"
