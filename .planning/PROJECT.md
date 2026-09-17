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

(None yet — ship to validate)

### Active

**Mandatory — stack (PDF "Requisitos")**
- [ ] Python + FastAPI
- [ ] A real database (PostgreSQL)
- [ ] Tests with pytest
- [ ] flake8 as linter, black as formatter
- [ ] Docker container that runs the application

**Mandatory — use cases (PDF 1.a)**
- [ ] Create, get, update and delete task lists
- [ ] Create, get, update and delete tasks inside a list
- [ ] Change the status of a task
- [ ] List all tasks of a list with filters by status or priority, plus an extra field with
      the completion percentage

**Bonus — use cases (PDF 1.b), all in scope**
- [ ] Login and authentication with JWT protecting endpoints
- [ ] Task assignment: assign a responsible user to each task
- [ ] Fake notification: simulated email invitation to users (no real sending)

**Mandatory — project structure (PDF 2)**
- [ ] Clean layered structure: Domain, Application/UseCases, Infrastructure
- [ ] Strong typing with Pydantic
- [ ] Error handling with custom exceptions
- [ ] Business validations
- [ ] Unit and integration testing with pytest
- [ ] Linters (flake8) and formatting (black, isort)
- [ ] Dockerfile (multistage) and docker-compose
- [ ] Complete README + DECISION_LOG.md explaining technical decisions

**Mandatory — tooling files (PDF 3-6)**
- [ ] Test coverage >= 75% of the project
- [ ] `pytest.ini` file configuring pytest
- [ ] `.flake8` file with configuration
- [ ] black configured
- [ ] `Dockerfile` + `docker-compose.yml`
- [ ] README.md with: project description, local environment setup, running in Docker,
      running the tests

**"Next level" layer (our addition)**
- [ ] `AI_WORKFLOW.md` with Mermaid diagrams showing how AI was directed: spec -> plan ->
      phased execution -> quality gates -> verification; what the human decided vs. what was
      delegated; honest log of AI mistakes and how they were caught
- [ ] Automated quality gates: pre-commit (black, isort, flake8), Makefile, GitHub Actions CI
      running lint + tests + `--cov-fail-under=75`
- [ ] Architecture boundaries enforced by an automated test (domain must not import
      infrastructure/frameworks), not just by folder names
- [ ] Static typing check (mypy) in CI
- [ ] Consistent error contract (RFC 9457 Problem Details, which obsoletes RFC 7807) from a single exception-handling
      point
- [ ] Public GitHub repository with atomic, phase-scoped commit history and green CI badge

### Out of Scope

- Frontend / UI — the challenge is backend only
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
| Enforce layer boundaries with an automated test | Proves architecture is a rule, not a folder convention | — Pending |
| RFC 9457 (obsoletes 7807) error responses via one exception handler | Custom domain exceptions stay HTTP-agnostic; consistent API contract | — Pending |
| AI workflow documented as Markdown + Mermaid only | Renders natively on GitHub; user decided HTML is unnecessary | — Pending |
| GSD workflow with `.planning/` committed | Planning/verification artifacts are themselves evidence of AI direction | — Pending |
| Domain entities as stdlib dataclasses; Pydantic at schema/DTO/settings boundaries | Makes "domain imports nothing" provable; pydantic.ValidationError cannot carry the DomainError contract. User-confirmed | — Pending |
| Python 3.13, psycopg 3, PyJWT + pwdlib[argon2], Alembic | Research-verified current stack; passlib/python-jose are unmaintained or vulnerable | — Pending |
| 404 for invisible resources, 403 for visible-but-forbidden | No existence oracle, while keeping a testable permission matrix | — Pending |
| Completion % computed over the whole list via one SQL aggregate | A filter-scoped percentage is degenerate (`?status=completed` is always 100) | — Pending |
| Everything in English | User decision; standard for code and open repos | — Pending |
| Own git repo inside `crehana/test` | Directory was nested in an unrelated parent repo; challenge needs its own history | ✓ Good |

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
*Last updated: 2026-09-17 after research and requirements definition*
