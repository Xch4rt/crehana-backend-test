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

.PHONY: install lint format typecheck arch test docker-test up down run

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

# Runs the suite on Python 3.13 with no host Python and no host PostgreSQL
# involved. The target name is unchanged, exactly as Phase 1 promised when it was
# still a two-line build-and-run; the body is now a compose invocation, which is
# the whole difference: the container reaches the `db` service over the compose
# network, so the *integration* tests run here too rather than being silently
# skipped. That makes this the zero-host-setup path D-03 describes - the one an
# evaluator with nothing but Docker can use.
#
# `run` rather than `up`: this service is invoked and exits with the suite's
# status. `--rm` leaves no stopped container behind, `--build` guarantees the
# image matches the working tree instead of whatever was built last.
docker-test:
	docker compose run --rm --build test

# The evaluator's path, and the reason it runs in the foreground: `up` streams
# the database and API logs, so a failed migration or a refused connection is
# visible instead of hidden behind a later `docker compose logs`.
up:
	docker compose up --build

# Stops and removes the containers, and keeps the data volume. The reset that
# also discards it is `docker compose down -v` - needed whenever the initdb
# scripts change, because the postgres image runs them only against an empty
# data directory.
down:
	docker compose down

# The host-side fast loop, and the reason no docker-compose.override.yml exists.
# `docker compose up` deliberately runs the production-like image (D-16): no bind
# mount of src/, no auto-restart-on-edit watcher, non-root, real entrypoint, real
# healthcheck. Reloading a container that was built to be immutable is a
# different thing pretending to be the same thing, so the edit-run loop lives
# here instead - the host virtualenv against the compose database, which
# .env.example already points at on localhost.
#
# `make up` (or `docker compose up -d db`) must be running first, and the
# explicit $(VENV)/bin/ path is used for the same reason as every other target:
# nothing here assumes an activated virtualenv.
run:
	$(VENV)/bin/uvicorn --factory taskmanager.main:create_app --reload
