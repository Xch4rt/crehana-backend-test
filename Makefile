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

.PHONY: install env lint format typecheck arch test test-unit break-check rehearse docker-test up down run ui-install ui-dev ui-lint ui-typecheck ui-test

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

# Step one of the evaluator's path, and the replacement for the plain copy of
# .env.example the setup used to open with (D-15 as amended by ADR-084): the
# placeholder secret that file publishes is refused at boot, so copying it
# verbatim no longer produces a runnable configuration. This writes a freshly
# generated JWT_SECRET into an untracked .env instead, and it never overwrites a
# secret that is already real - so it is safe to re-run, and a developer's own
# .env survives it. The old command is described rather than spelled, so that
# grepping this repository for it stays a meaningful gate (the 01-03 convention).
#
# Deliberately the one target that needs neither Python, nor $(VENV), nor
# Docker: a POSIX shell, awk, cp, mv and either openssl or /dev/urandom. That is
# the same machine `make up` is written for - an evaluator with Docker and make
# and nothing else.
env:
	sh scripts/init-env.sh

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

# The fast host loop: the no-database slice, in about a second and a half, so
# there is no reason to run the suite less often than every edit. It needs no
# `make up`, no container and no network - which also makes it the one test
# command that works on a machine where Docker is not running.
#
# `--no-cov`, never a threshold override. `pytest.ini` also sets
# `--cov-report=xml`, so a partial run would overwrite `coverage.xml` with a
# partial number - and that file is the artifact D-11's three-way agreement is
# read off, produced by `make test`, `make docker-test` and CI. The slice does
# in fact clear 75% on its own today, which is exactly why not to gate it: a
# green that depends on a number nobody is defending fails one day for a reason
# nobody intended.
#
# A convenience subset, not a gate: it runs a strict subset of what `test` runs,
# so it adds nothing to .pre-commit-config.yaml or .github/workflows/ci.yml to
# be out of sync with. CLAUDE.md's two-places rule applies to a *new* gate.
test-unit:
	$(VENV)/bin/pytest -m unit --no-cov

# The answer to "your tests are green, but do they check anything?" - roadmap
# SC-4. The script breaks src/ on purpose five times, runs the tests that should
# care - once BEFORE the break, which must be green, and once with it - asserts
# each break turns them RED, restores the file and reports; it exits non-zero if
# any break survives, and also if pytest exits in any way that is not a test
# failure (ADR-093). It refuses to start on a dirty src/, because it restores
# with git.
#
# Deliberately in neither `test` above, nor .pre-commit-config.yaml, nor
# .github/workflows/ci.yml (D-09): it runs a large selection ten times over,
# which costs a couple of minutes, and the whole value of the ten-second commit
# loop is that nobody is tempted to skip it. This is a spot check run on demand,
# not a gate. It needs PostgreSQL up, since four of the five breaks reach the
# integration tests.
break-check:
	sh scripts/break-check.sh

# The answer to "your README is green, but is it true?" - roadmap SC-4's other
# half. The script clones the COMMITTED tree into an empty directory, builds the
# image with --no-cache, and then extracts the shell lines between README.md's
# `rehearsal:begin`/`rehearsal:end` markers and runs them. It executes the
# document rather than a transcript of it, so it goes red the day a command in
# the README stops working.
#
# It needs Docker and a clean working tree, and it has one deliberate side
# effect: it STOPS the developer's stack (plain `down`, so test_pgdata survives)
# because the ports are hard-coded, and it leaves it down, printing `make up` as
# the one command that restores it. Every `down -v` it runs is inside the clone,
# under COMPOSE_PROJECT_NAME=crehana-rehearsal.
#
# Deliberately in neither .pre-commit-config.yaml nor .github/workflows/ci.yml,
# for the same reason `break-check` is not (D-09): a --no-cache build plus a full
# containerised suite is minutes, and a ten-second commit loop is only worth
# having if nobody is tempted to skip it. A spot check run on demand - before
# delivery, and whenever the README's commands change.
#
# `sh scripts/clean-clone-rehearsal.sh --extract-only` is the dry run: it prints
# the commands it would execute and touches neither Docker nor git.
rehearse:
	sh scripts/clean-clone-rehearsal.sh

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

# ---------------------------------------------------------------------------
# The web UI (Phase 8, beyond the brief). Five targets, and they are the one
# group in this file that needs NODE and not $(VENV) - the opposite constraint
# from everything above. That is exactly why they are named `ui-*` rather than
# folded into `lint`, `typecheck` and `test`: a developer with a Python
# environment and no Node must still be able to run every backend gate, and
# `make test` must never start failing because `npm` is missing.
#
# `npm --prefix frontend`, never a `cd frontend && ...`: GNU Make 3.81 runs each
# recipe line in its own shell and this file already refuses to depend on a `cd`
# performed on a previous line.
# ---------------------------------------------------------------------------

# `npm ci` and deliberately not `npm install`: the committed lockfile is the
# source of truth for versions exactly as requirements.txt is, and `ci` installs
# from it verbatim, failing if package.json and the lock disagree. `install`
# would quietly resolve and rewrite the lock instead.
ui-install:
	npm --prefix frontend ci

# The Vite dev server on http://localhost:5173, proxying /api to the API on
# :8000 (vite.config.ts). `make up` must be running first - the proxy has an
# origin to forward to, not an API of its own.
ui-dev:
	npm --prefix frontend run dev

# eslint over the flat config, which carries the D-06 token-storage rules as
# real errors rather than as a comment nobody enforces.
ui-lint:
	npm --prefix frontend run lint

# tsc --noEmit, strict. Nothing is written to the tree.
ui-typecheck:
	npm --prefix frontend run typecheck

# vitest, once, non-interactive. jsdom plus Testing Library; every API call is
# stubbed at the fetch boundary, so this target needs neither Docker nor a
# database.
ui-test:
	npm --prefix frontend test
