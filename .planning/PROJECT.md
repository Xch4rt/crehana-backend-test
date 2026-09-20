# Task Manager API — Crehana Backend Technical Challenge

## What This Is

A REST API for managing task lists and their tasks, built with Python and FastAPI as the
deliverable for Crehana's Backend Technical Challenge. It is aimed at the Crehana evaluators:
it must satisfy every line of the challenge brief literally, and on top of that demonstrate
a disciplined, transparent AI-assisted engineering workflow (human direction, automated
quality gates, verified output) rather than "AI wrote it".

## Core Value

Every requirement in the challenge PDF is met to the letter and is provable in under five
minutes by an evaluator: `docker compose up`, run the tests, read the docs.

## Requirements

### Validated

Validated in Phase 1: Foundation & Quality Gates (2026-09-18) — every gate green locally
and on two real CI runs (`Xch4rt/crehana-backend-test`).
- [x] `pytest.ini` file configuring pytest
- [x] `.flake8` file with configuration
- [x] black configured
- [x] Linters (flake8) and formatting (black, isort)
- [x] Test coverage >= 75% of the project — enforced by `--cov-fail-under=75` in `pytest.ini`,
      proven to fail on an untested module (`evidence/coverage-gate-red.txt`)
- [x] Dockerfile (multistage) — three-stage, non-root runtime, `test` stage runs the suite on
      Python 3.13; `docker-compose.yml` remains Active (Phase 3)

Validated in Phase 2: Domain & Error Contract (2026-09-18) — 4/4 success criteria verified,
151 tests, 100% coverage, code review warnings fixed (WR-05 deferred to Phase 3 by locked D-14).
- [x] Error handling with custom exceptions — closed `DomainError` hierarchy (12 leaves, stable
      `code`, typed `details`), no `HTTPException` outside `presentation`
- [x] Architecture boundaries enforced by an automated test — import-linter contracts plus
      `tests/architecture/test_domain_is_stdlib_only.py` (AST walk against
      `sys.stdlib_module_names`; proven to catch a planted `import greenlet` that
      import-linter alone reports as KEPT — ADR-022)
- [x] Consistent error contract (RFC 9457 Problem Details) from a single exception-handling
      point — `register_exception_handlers()` in `create_app()`, one `problem()` builder,
      `WWW-Authenticate` on 401, fixed body on any 500, proven against a test-only probe router

Validated in Phase 3: Persistence & Runnable Stack (2026-09-19) — 5/5 success criteria verified,
293 tests, 100% coverage, `docker compose up` cold-start proven (`evidence/03-10-cold-start.txt`);
code review: CR-01 + 5 warnings fixed, WR-02/WR-05 deliberately left open (see 03-REVIEW.md).
- [x] A real database (PostgreSQL) — `postgres:18-alpine`, SQLAlchemy 2.0 async over psycopg 3,
      Alembic `0001_baseline` proven to round-trip, every constraint proven by a refused statement
- [x] Docker container that runs the application — runtime stage waits for the DB, runs
      `alembic upgrade head`, serves as uid 999 with a `HEALTHCHECK` on `/health`
- [x] docker-compose — `db` + `api` (+ `test` behind a profile); one command reaches `api healthy`
- [x] `docker-compose.yml`
- [x] Explicit transaction boundary — `SqlAlchemyUnitOfWork` implements the application port,
      repositories never `commit()` (AST-enforced), use cases own `async with uow:`

Validated in Phase 4: Task Lists & Tasks (2026-09-19) — 5/5 success criteria and 15/15
requirements verified against the live stack, 599 tests, 100% host coverage, eleven routes;
code review: CR-01 (lost update under concurrent writes) + 5 warnings open (see 04-REVIEW.md
and the STATE.md blocker).
- [x] Create, get, update and delete task lists — five routes under `/api/v1/task-lists`,
      not-owned answers 404 exactly like absent (ADR-008), duplicate name answers 409
- [x] Create, get, update and delete tasks inside a list — nested routes, wrong-list 404 on
      every verb, merge-patch semantics through the typed `Unset` sentinel
- [x] Change the status of a task — dedicated status endpoint, forbidden transitions answer
      409 naming `from`/`to`, `status` proven not writable through the generic PATCH
- [x] List all tasks of a list with filters by status or priority, plus an extra field with
      the completion percentage — statistics cover the whole list whatever the filter; no N+1,
      asserted by a statement counter
- [x] Strong typing with Pydantic — every HTTP boundary has request and response models
      (`extra="forbid"`); application DTOs are frozen dataclasses per ADR-020

Validated in Phase 5: Auth, Assignment & Notifications (2026-09-19) — all twelve AUTH/ASGN/NOTF
requirements verified against the live stack, 1019 tests, 100% host coverage, nineteen
operations. The first verification found a gap (the published `.env.example` placeholder was
accepted as the JWT signing key, and a token was forged against the running container); plan
05-17 closed it with `make env` plus a boot-time refusal (ADR-084) and closed four review
warnings; re-verification passed 6/6. Four info-level review items remain open (see
05-REVIEW.md), and ADR-066/ADR-067 record two conceded security properties.
- [x] Login and authentication with JWT protecting endpoints — register, OAuth2 password
      login, `/auth/me`; every route is either one of three named open ones or requires the
      bearer scheme; 404 for what the caller cannot see, 403 for what they may not do
- [x] Task assignment: assign a responsible user to each task — owner-only assign/unassign,
      the assignee may read a task and change its status, `GET /users` and
      `GET /tasks/assigned-to-me` make ids and work discoverable
- [x] Fake notification: simulated email invitation to users (no real sending) — sent through
      the `EmailNotifier` port after the commit as one JSON log line; a failing notifier never
      undoes the assignment

Validated in Phase 6: Test Hardening & Coverage (2026-09-19) — TEST-01..05 verified, 1101 tests,
100% over 1659 statements on the host, `make break-check` reddens all five deliberate breaks.
Code review found that an unanchored coverage exclusion had been hiding four function bodies
from the denominator (fixed, ADR-092) and that the break check accepted any non-zero exit as
red (fixed, ADR-093). The first verification found a gap (the permission matrix's mutations
went through `client.request` and sat outside the re-read gate); plan 06-05 closed it
(ADR-096) and re-verification passed 5/5. Seven review warnings remain open as recorded
follow-ups (see 06-REVIEW.md).
- [x] Tests with pytest — 777 unit tests against in-memory fakes, 324 integration tests over
      HTTP against real PostgreSQL, partitioned by marker (`make test-unit` needs no database)
- [x] Unit and integration testing with pytest — totality gates make "every use case, every
      endpoint, every error code, every invalid transition" a build failure rather than a
      claim; an assertion-quality gate requires a body assertion and a re-read after a mutation
- [x] Coverage >= 75%, enforced — `--cov-fail-under=75` in `pytest.ini`, the configuration
      pinned by a test, no pragma and no omit

### Active

**Mandatory — stack (PDF "Requisitos")**
- [ ] Python + FastAPI
- [ ] flake8 as linter, black as formatter

**Mandatory — project structure (PDF 2)**
- [ ] Clean layered structure: Domain, Application/UseCases, Infrastructure
- [ ] Business validations
- [ ] Complete README + DECISION_LOG.md explaining technical decisions

**Mandatory — tooling files (PDF 3-6)**
- [ ] README.md with: project description, local environment setup, running in Docker,
      running the tests

**"Next level" layer (our addition)**
- [ ] `AI_WORKFLOW.md` with Mermaid diagrams showing how AI was directed: spec -> plan ->
      phased execution -> quality gates -> verification; what the human decided vs. what was
      delegated; honest log of AI mistakes and how they were caught
- [ ] Automated quality gates: pre-commit (black, isort, flake8), Makefile, GitHub Actions CI
      running lint + tests + `--cov-fail-under=75`
- [ ] Static typing check (mypy) in CI
- [ ] Public GitHub repository with atomic, phase-scoped commit history and green CI badge

### Out of Scope

- ~~Frontend / UI — the challenge is backend only~~ — reversed by user decision 2026-09-19: Phase 8 adds a small web UI inside the deliverable (UI-01..UI-08); the brief still asks for none
- Real email delivery (SMTP, SendGrid, etc.) — the brief explicitly asks for a simulation
- Refresh tokens, password reset, email verification, OAuth — beyond the "optional JWT" bonus;
  would be documented as future work
- Roles/permissions beyond list ownership and task assignee — not requested
- Production deployment, Kubernetes, observability stack — not requested; keeps the project
  reviewable in minutes
- HTML/visual page for the AI workflow — user decided the Mermaid `.md` is enough
- Pagination/sorting beyond what the brief asks — candidate for "pending work" section only

## Context

- The deliverable will be evaluated by Crehana's talent/engineering team against the PDF
  brief: REST API design, clean code structure, modern Python tooling, technical reasoning,
  and good practices (testing, Docker, linters, validations). Estimated effort in the brief:
  4-6 hours; if something is not covered it must be documented as pending.
- The candidate's differentiator: AI usage is assumed nowadays, so the submission must show
  *how* AI is steered to produce an impeccable product — planning artifacts (`.planning/`),
  decision log, quality gates and verification are part of the deliverable, committed to git.
- Literal file requirements matter: `pytest.ini` and `.flake8` must exist as files (not only
  `pyproject.toml` sections); `DECISION_LOG.md` and `README.md` are explicitly required.
- Ambiguities in the brief to resolve and document in DECISION_LOG.md: whether completion
  percentage is computed over the whole list or the filtered subset; allowed task status
  values and transitions; priority values; who may be assigned to a task; what triggers the
  fake invitation email.
- Local environment: macOS, Docker 29, Python 3.14 on host (project targets Python 3.13 in
  Docker: 3.12 is security-only and all dependencies ship cp313 wheels — verified in research). No uv/poetry installed on host.
- `AI_WORKFLOW.md` must reflect what genuinely happened during development — no fabricated
  narrative.

## Constraints

- **Tech stack**: Python, FastAPI, pytest, flake8, black, Docker — mandated by the brief
- **Database**: PostgreSQL — brief requires "a real database"; removes any doubt SQLite might raise
- **Language**: Everything in English (code, docs, commits, planning artifacts) — user decision
- **Files**: `pytest.ini`, `.flake8`, `Dockerfile`, `docker-compose.yml`, `README.md`,
  `DECISION_LOG.md` must exist literally — brief lists them by name
- **Coverage**: >= 75%, enforced automatically — brief requirement
- **Git**: No Claude/AI co-author attribution lines in commits — user preference; AI usage is
  documented transparently in `AI_WORKFLOW.md` instead
- **Delivery**: Public GitHub repo owned by the candidate; link sent to talento@crehana.com
- **Reviewability**: One-command startup (`docker compose up`) and one-command test run

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PostgreSQL over SQLite | "Real database" requirement; integration tests run against the same engine as production | — Pending |
| Include all three bonus use cases | Maximizes score; JWT enables ownership rules that make business validations meaningful | — Pending |
| Hexagonal-style layers (domain / application / infrastructure / presentation) | Brief asks for Domain, Application/UseCases, Infrastructure; ports as Protocols keep domain framework-free | — Pending |
| Enforce layer boundaries with an automated test | Proves architecture is a rule, not a folder convention | ✓ Good (Phase 2: import-linter + stdlib-only AST test) |
| RFC 9457 (obsoletes 7807) error responses via one exception handler | Custom domain exceptions stay HTTP-agnostic; consistent API contract | ✓ Good (Phase 2: 4 handlers, 1 `problem()` builder, probe-router tests) |
| AI workflow documented as Markdown + Mermaid only | Renders natively on GitHub; user decided HTML is unnecessary | — Pending |
| GSD workflow with `.planning/` committed | Planning/verification artifacts are themselves evidence of AI direction | — Pending |
| Domain entities as stdlib dataclasses; Pydantic at schema/DTO/settings boundaries | Makes "domain imports nothing" provable; pydantic.ValidationError cannot carry the DomainError contract. User-confirmed | ✓ Good (Phase 2; refined by ADR-020: application DTOs are frozen dataclasses, Pydantic stays at HTTP schemas and settings) |
| Python 3.13, psycopg 3, PyJWT + pwdlib[argon2], Alembic | Research-verified current stack; passlib/python-jose are unmaintained or vulnerable | — Pending |
| 404 for invisible resources, 403 for visible-but-forbidden | No existence oracle, while keeping a testable permission matrix | — Pending |
| Completion % computed over the whole list via one SQL aggregate | A filter-scoped percentage is degenerate (`?status=completed` is always 100) | — Pending |
| Everything in English | User decision; standard for code and open repos | — Pending |
| Own git repo inside `crehana/test` | Directory was nested in an unrelated parent repo; challenge needs its own history | ✓ Good |
| The README is executed, not transcribed (`make rehearse`) | A pasted transcript proves one moment; a script that re-types the commands proves the script. Extracting the README's own fenced blocks and running them in a fresh clone can only pass if the document is right | ✓ Good (Phase 7: ADR-103; green twice, 161s then 115s) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-19 during Phase 7 (Documentation & Delivery), plan 07-05*
