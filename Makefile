# Every quality gate, one word behind `make`.
#
# Two constraints shape this file:
#   * GNU Make 3.81 ships with macOS, and it silently ignores the special target
#     that would run a whole recipe in a single shell (added in 3.82). So every
#     recipe line here runs in its own shell and is self-contained; two commands
#     that must share a shell would be joined with `&&` on one line, and no
#     recipe relies on a `cd` performed on a previous line.
#   * Nothing here assumes an activated virtualenv. Every tool is invoked through
#     an explicit $(VENV)/bin/ path, because an evaluator will clone, run
#     `make install`, and then type `make test` in the same shell.

.PHONY: install lint format typecheck arch test docker-test up down

VENV := .venv
PY := $(VENV)/bin/python

# Plain `python3`, never a version-suffixed interpreter name: this host has
# CPython 3.14.3 and no 3.13, so the pinned name would fail on the first line.
# pyproject.toml requires >=3.13, so 3.14 satisfies it; the 3.13 analysis target
# lives in mypy/black config, and a real 3.13 runtime lives in Docker and CI.
# The editable install is mandatory: lint-imports resolves `root_package` by
# importing `taskmanager`.
install:
	python3 -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e .
	$(VENV)/bin/pre-commit install

# isort before black, always: the reverse order oscillates.
format:
	$(VENV)/bin/isort src tests
	$(VENV)/bin/black src tests

# Check modes only. `lint` must never rewrite a file, or it would mask the very
# violation it is asked to report. Rewriting lives exclusively in `format`.
lint:
	$(VENV)/bin/black --check src tests
	$(VENV)/bin/isort --check-only src tests
	$(VENV)/bin/flake8 src tests

typecheck:
	$(VENV)/bin/mypy src tests

# The console script, never import-linter's command-line module run through
# `python -m` - that form has no __main__ guard and exits 0 with a real
# violation in place (see
# .planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt).
arch:
	$(VENV)/bin/lint-imports

# The 75% coverage gate rides along via the addopts in pytest.ini, so `make test`
# and a bare `pytest` are gated by the same bytes.
test:
	$(VENV)/bin/pytest

# Runs the suite on Python 3.13 with no host Python involved. Phase 3 replaces
# the body with a compose invocation; the target name stays, so no documentation
# has to change.
docker-test:
	docker build --target test -t taskmanager-test .
	docker run --rm taskmanager-test

up:
	@echo "docker compose arrives in Phase 3. For now: make docker-test"

down:
	@echo "docker compose arrives in Phase 3; there is nothing to stop yet."
