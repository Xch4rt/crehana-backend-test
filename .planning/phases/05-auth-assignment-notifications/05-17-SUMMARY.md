---
phase: 05-auth-assignment-notifications
plan: 17
subsystem: security-configuration
tags: [jwt, settings, pydantic, placeholder-secret, make-env, posix-sh, validation, unicode, psycopg, sqlalchemy, hide-parameters, cr-01, wr-01, wr-02, wr-03, wr-04]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "05-VERIFICATION.md — the forged-token gap: the published .env.example secret boots and GET /auth/me answered 200 for another account"
  - phase: 05-auth-assignment-notifications
    provides: "05-REVIEW.md — CR-01 and the four warnings, each reproduced by execution with file:line"
  - phase: 05-auth-assignment-notifications
    provides: "ADR-061's 32-character HS256 floor, which this plan keeps and no longer relies on alone"
provides:
  - "`make env` + scripts/init-env.sh: a generated JWT_SECRET in an untracked .env, replacing the copy step (D-15 as amended by ADR-084)"
  - "Settings refuses any JWT_SECRET beginning `replace-me` and accepts only HS256"
  - "domain.validation.is_storable_text: the single home of what a PostgreSQL text column can hold"
  - "Login answers the ordinary 401 for an address the database cannot hold, before the transaction"
  - "RegisterUser checks full_name before the Argon2 work an anonymous caller can demand"
  - "create_async_engine(hide_parameters=True), so no DBAPIError renders a stored hash"
  - "DECISION_LOG.md ADR-084, one AI_WORKFLOW incident entry, two CLAUDE.md configuration rules"
affects: [06-test-hardening, 07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A test that boots the configuration the repository actually ships, rather than one the test supplies itself"
    - "A shipped value read out of its file by the test that asserts about it, never restated as a literal"
    - "A predicate owning a rule, with the raising guard choosing wording only, so the two cannot drift"
    - "A flag read off the real object and passed into the assertion, so removing the option fails the test"

key-files:
  created:
    - scripts/init-env.sh
    - tests/unit/test_env_bootstrap.py
  modified:
    - src/taskmanager/infrastructure/config/settings.py
    - src/taskmanager/domain/validation.py
    - src/taskmanager/application/use_cases/auth/login.py
    - src/taskmanager/application/use_cases/auth/register.py
    - src/taskmanager/infrastructure/db/engine.py
    - .env.example
    - Makefile
    - docker-compose.yml
    - tests/unit/test_settings.py
    - tests/unit/domain/test_validation.py
    - tests/unit/application/test_login.py
    - tests/unit/application/test_register_user.py
    - tests/unit/infrastructure/test_engine.py
    - tests/integration/api/test_auth.py
    - DECISION_LOG.md
    - AI_WORKFLOW.md
    - CLAUDE.md

key-decisions:
  - "Task order was load-bearing and was honoured: `make env` repaired the developer's .env and the container was rebuilt onto a generated secret BEFORE the refusal landed, because tests/integration/conftest.py builds Settings() from the real on-disk file and the reverse order would have left the suite red between two commits with --no-verify forbidden"
  - "The refusal is a prefix rule (`replace-me`) and ADR-084 states its limit rather than overselling it: an operator's own weak 32-character secret is not protected, and no code default was introduced"
  - "The secret is generated on the host in a make target, not in the container entrypoint: an entrypoint generator would mint a new secret on every start and invalidate every live token"
  - "jwt_algorithm is Literal[\"HS256\"], a closed set of one, because the 32-character floor is the HS256 floor specifically; HS512 is refused rather than accepted against a floor sized for something else"
  - "is_storable_text is public and owns the rule; _refuse_unstorable (renamed from _refuse_nul) returns early when it answers yes and only then picks a message, so the guard cannot disagree with the predicate"
  - "The login guard sits before the unit of work and the test asserts rollbacks == 0, which is what distinguishes a guard in front of the block from one inside it"
  - "The engine test reads hide_parameters off the real engine and passes that flag into the DBAPIError it renders, so removing the option from create_engine fails the test"
  - "STATE.md and ROADMAP.md were updated by hand for the reason 05-16 records; the Phase 5 checkbox, its status cell and its completion date are untouched - only the 05-17 plan box and the 17/17 count were taken"

patterns-established:
  - "Deployment assertions: the suite proves the code with its own configuration, so the shipped configuration needs a test of its own"
  - "A setup command that is safe to re-run: `make env` never overwrites a secret that is already real"

requirements-completed: [AUTH-01, AUTH-02, AUTH-04]

# Metrics
duration: 25min
completed: 2026-09-19
---

# Phase 5 Plan 17: Gap Closure Summary

**A reader of the public repository no longer has a value the API will accept as a signing key:
`make env` writes a generated secret into an untracked `.env`, `Settings` refuses the published
placeholder by name with a message that says what to run, HS256 is the only algorithm that
validates, and the two malformed inputs the reviewer turned into unauthenticated 500s now answer
401 and 422 while a DBAPIError carries no bound parameters at all.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 5 of 5
- **Files modified:** 19 (2 created, 17 modified)
- **Gates:** `make lint`, `make typecheck`, `make arch`, `make test` green — 1019 tests,
  coverage 100.00%, 9.17 s wall clock

## Task Commits

| Task | Name | Commit |
|------|------|--------|
| 1 | `make env` replaces the copy step, and the stack moves onto a generated secret | `64b2e6d` (feat) |
| 2 | Settings refuses the published placeholder and closes the algorithm set | `4d94514` (fix) |
| 3 | Unstorable text refused by the domain; an unknown-shaped login is just unknown | `172e3e0` (fix) |
| 4 | The engine hides bound parameters | `a505626` (fix) |
| 5 | ADR-084, the AI_WORKFLOW entry, the CLAUDE.md rules and the whole gate | `3326475` (docs) |

## Accomplishments

### Task 1 — the secret is generated, not published

`scripts/init-env.sh` is POSIX `sh`, 80 lines, and decides three cases in the order they are
written: no `.env` → copy `.env.example` and generate; a `JWT_SECRET` that is absent, empty or
begins `replace-me` → rewrite that one line; anything else → change nothing and exit 0. The
rewrite streams through `awk` into a temporary file beside the target and `mv`s over it, so an
interrupted run cannot leave half a `.env`; `sed -i` is avoided because its argument differs
between GNU and BSD. The secret is 64 hex characters from `openssl rand -hex 32`, falling back
to `/dev/urandom`, and is never printed.

`tests/unit/test_env_bootstrap.py` runs the real file through `sh` in a temporary directory.
The first test is the load-bearing one: it deletes `JWT_SECRET`, `DATABASE_URL` and
`TEST_DATABASE_URL` from the environment so the process cannot stand in for the file, then
builds `Settings(_env_file=<tmp>/.env)` and asserts the secret it carries is the generated one.
A length assertion alone would have passed on the 34-character placeholder this plan exists to
stop.

On this machine the developer's untracked `.env` changed in **exactly one line** (line 42,
`JWT_SECRET`), `DATABASE_URL` and every other line byte-identical, and `git status --porcelain
.env` prints nothing. The `api` service was rebuilt and reached `healthy` before the commit —
which is what kept `make test` green for the rest of the plan, since
`tests/integration/conftest.py` is the one fixture that reads the real file.

### Task 2 — the placeholder cannot boot the application

A `@field_validator("jwt_secret")` refuses any value whose casefolded form starts with
`replace-me`, with the message *"JWT_SECRET is still the .env.example placeholder. Run `make env`
to write a generated secret into .env."* `Field(min_length=32)` stays. `jwt_algorithm` becomes
`Literal["HS256"]`; `tokens.py` takes `algorithm: str` and needed no change.

Three pieces of prose the code had outgrown were corrected: the module docstring now names the
mechanism that keeps its promise, the `test_database_url` comment names `make env`, and the D-26
comment's boast that `.env.example` clears the floor — the defect itself, written down — is
replaced by the truth.

`test_the_shipped_placeholder_is_refused` parses the value out of `.env.example` rather than
restating it, so it tracks whatever the repository publishes. Verified at the command line:
`Settings(_env_file='.env.example')` exits 1 with `make env` in its stderr, and `HS512` with a
valid generated secret exits 1 too.

### Task 3 — 401 and 422 where there were two 500s

`is_storable_text(value)` answers one question — can a PostgreSQL text column hold this? — and
is the only place the rule is written. `_refuse_unstorable` (renamed from `_refuse_nul`) calls
it, returns when the answer is yes, and only then chooses between the existing NUL wording and a
new one for text that is not valid Unicode. `require_text` and `optional_text` keep their single
call site, so list names, task titles and every description are closed against a lone surrogate
without a second guard.

`Login.execute` short-circuits before the `async with`: `dummy_verify`, then the same
`AuthenticationError(_REFUSAL)` both other legs raise. The unit test compares the document field
by field against the unknown-address refusal and asserts `rollbacks == 0` — the unknown-address
leg leaves it at 1, so that assertion is what says the guard runs in front of the block and no
connection is taken out for an impossible lookup.

`RegisterUser` calls `require_text(command.full_name, ...)` after the password guard and before
`hash`, so a name the database cannot hold no longer costs an Argon2 hash. Two HTTP tests land
in `tests/integration/api/test_auth.py`: a NUL in `username` (compared body to body against the
unknown-address 401) and a raw JSON body carrying `"A\ud800B"` in `full_name` (422,
`errors == {"field": "full_name"}`, the escape absent from the response).

### Task 4 — a hash cannot ride a DBAPIError into a log

`create_async_engine(..., pool_pre_ping=True, hide_parameters=True)`. The test reads
`create_engine(a_settings()).sync_engine.hide_parameters` off the real engine, asserts it is
`True`, then constructs a users-INSERT `DBAPIError` with an Argon2-shaped parameter **passing
that same flag through** — so deleting the option from the builder fails the test rather than
leaving it asserting about a literal. Both renderings were checked at the interpreter first:
with the flag off the `$argon2id$` string is present, with it on it is not.

### Task 5 — the record, and the gate

**ADR-084** in the house four-part format: the floor sized to a length and never checked against
the one value the repository publishes; the three options (refuse and keep the copy step;
generate in the entrypoint; generate on the host and refuse at boot) with the entrypoint option
rejected because a secret that changes on every container start invalidates every live token;
and consequences stated plainly, including what the prefix rule does *not* protect against. Two
earlier occurrences of the old command that state a present or future fact — ADR-027's decision
line and the Phase 7 "four settled commands" line — carry a short parenthetical pointer; the
narrative paragraphs of earlier decisions were left as the record of their time.

**AI_WORKFLOW.md** gains one dated entry: sixteen plans, 998 tests and 100% coverage did not
catch that the signing key the documented setup installs is published here, and the reason is
that every test supplies its own secret — the suite measured the code and nobody measured the
deployment.

**CLAUDE.md** § Project Rules → Configuration gains two bullets, each naming its enforcing test
by the path and name actually written. `git diff CLAUDE.md` touches no line inside a `GSD:*`
block.

## Live verification against the rebuilt container

The `api` service was rebuilt a second time from the committed tree, since the phase
re-verification probes it over HTTP. `api healthy`, `db healthy`, `GET /health` 200.

| Probe | Result |
|-------|--------|
| `GET /api/v1/auth/me` with a token forged offline using the published placeholder | **401** `application/problem+json` (was 200 with another account's profile) |
| `POST /api/v1/auth/login` with `username=a%00b@example.com` | **401** `application/problem+json` (was 500) |
| `POST /api/v1/auth/register` with `full_name: "A\ud800B"` | **422** `application/problem+json`, `code=validation_error`, `errors={"field": "full_name"}` (was 500) |

## Deviations from Plan

Three, all small, none changing what the plan decided.

**1. [Rule 3 — blocking] The Makefile and script comments describe the old copy command instead
of spelling it.** The plan's own acceptance criterion is that
`grep -rn "cp .env.example .env" Makefile docker-compose.yml .env.example` prints nothing, and
the plan also asks the `env` target's comment to say it replaces that command. Both were
satisfiable only by the project's established prose-not-literal convention (01-03), so the
comments name "the plain copy of `.env.example` the setup used to open with" and say why the
command is described rather than spelled. Same call in `scripts/init-env.sh`.

**2. [Rule 1 — correctness] The plan's login test asserts the repository was never asked; the
fake has no such recorder.** `FakeUserRepository` records `added` and `stored`, not lookups, and
adding a recorder would have modified `tests/unit/application/fakes.py`, which is outside this
plan's `files_modified`. `rollbacks == 0` proves the same property more strongly — the
unknown-address leg leaves it at 1 — and the test says so in a comment.

**3. [Rule 1 — correctness] Escapes for unstorable text are never written as literals in source.**
`is_storable_text`'s docstring spells the surrogate with a doubled backslash and the tests build
it with `chr(0xD800)`, so no source file in this repository contains an unencodable character.
The existing NUL tests already set that precedent with `"a\x00b"`.

Nothing outside the plan's `files_modified` was touched, except `.planning/STATE.md`,
`.planning/ROADMAP.md` and this summary, which the workflow owns.

## Out of scope, as instructed

IN-01 (login applies no password bound), IN-02 (PyJWT judges expiry by the wall clock), IN-03
(the stale entrypoint reference in `passwords.py`) and IN-04 (the first `dummy_verify` per
process is twice as slow) were not planned and not written. They remain in `05-REVIEW.md`.

## Docker commands run

`docker compose up -d --build api` (twice: Task 1 and Task 5), `docker compose ps --format
'{{.Service}} {{.Health}}'` for polling. Nothing else. No `down`, no `-v`, no prune, no Alembic
downgrade, and no container outside this project's compose project was touched. The `db` service
ran untouched throughout and its rehearsal accounts were left in place.

## Verification Results

- `make lint` — black, isort, flake8 over 181 files: clean
- `make typecheck` — `mypy --strict` over `src` and `tests`: no issues in 181 source files
- `make arch` — import-linter: 4 contracts kept, 0 broken
- `make test` — **1019 passed**, coverage **100.00%**, `Required test coverage of 75% reached`,
  9.17 s
- No `# pragma: no cover` anywhere in `src/`, no `omit` entry added to `pytest.ini` or
  `pyproject.toml`
- `grep -rn "cp .env.example .env" Makefile docker-compose.yml .env.example src/ CLAUDE.md`
  prints nothing
- `git status --porcelain .env` prints nothing; `.env`'s `JWT_SECRET` does not match `replace-me`

## Requirements

`AUTH-01`, `AUTH-02` and `AUTH-04` were already ticked by plan 05-16 and remain Complete in
`.planning/REQUIREMENTS.md`; this plan makes AUTH-04's "tokens are signed with an env-provided
secret and a pinned algorithm" true of the deployment as well as of the code. No count changed:
**56/69**.
