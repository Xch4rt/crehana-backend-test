# Project Research Summary

**Project:** Task Manager API — Crehana Backend Technical Challenge
**Domain:** Layered/hexagonal REST API (FastAPI + PostgreSQL), delivered as a graded take-home with a documented AI-assisted workflow
**Researched:** 2026-09-17
**Confidence:** HIGH overall (framework mechanics and package versions verified live against PyPI/official docs; architectural and evaluator-behavior judgments are MEDIUM — see Confidence Assessment)

## Executive Summary

This is not a product with users in the conventional sense — it is a REST API for managing task lists and tasks, evaluated by a Crehana reviewer skimming the repo for 5-15 minutes. The four research files agree, in remarkable detail, on how a senior engineer builds this: a four-layer architecture (domain / application / infrastructure / presentation) with the dependency arrow pointing strictly downward and enforced by `import-linter` rather than by folder convention; domain entities as framework-free dataclasses with Pydantic doing its real work at the DTO/schema/settings boundary; ports as `typing.Protocol` so unit tests never touch a database; a Unit-of-Work that commits once, inside the use case, never in a FastAPI dependency's exit code; and a single exception-handling point that turns a closed hierarchy of domain exceptions into RFC 9457 `application/problem+json` responses. The stack is current-dated (Python 3.13, FastAPI 0.141.x, SQLAlchemy 2.0 async, PyJWT + pwdlib[argon2] rather than the stale `python-jose`/`passlib` combo that AI models default to from training data), and the feature research converts the brief's ambiguities (completion-percentage scope, 403-vs-404, PATCH-only, whole-list vs filtered stats) into explicit, defensible design decisions rather than leaving them implicit.

The recommended approach is to build one thin vertical slice first (skeleton + quality gates + one CRUD resource end-to-end) before widening to the rest of the use cases, because retrofitting the error contract, the layer boundaries, or the async session lifecycle across fourteen already-written use cases costs multiples of building them right the first time. PITFALLS.md frames the grading order precisely: a broken `docker compose up` on a clean machine costs more than any amount of architectural elegance, followed by whether tests actually pass and coverage is real (not gamed via `--cov=.` including the test files themselves), followed by whether the layering is real or cosmetic, followed by whether the code reads as owned or as machine-authored, and only then whether `AI_WORKFLOW.md` is credible. The single highest-risk technical pattern across all four files is async SQLAlchemy's implicit lazy-loading (`MissingGreenlet`), caused by handing ORM objects to Pydantic response models outside the session's greenlet context — it must be designed out in the persistence layer (`lazy="raise"`, mapping inside repositories, `expire_on_commit=False`) before any router is written, not fixed after the fact.

Four research files were produced somewhat independently and disagree on several concrete points — Python version, error-contract RFC, package layout, entity typing philosophy, database driver, Postgres image tag, and one pytest-asyncio setting. None of these are project-fatal, but the roadmapper should not silently pick a side: they are enumerated with a recommended resolution in the **Conflicts Between Research Files** section below and should be locked in during Phase 1 planning and recorded in `DECISION_LOG.md`.

## Key Findings

### Recommended Stack

Python 3.13 (`python:3.13-slim-trixie`) with FastAPI 0.141.x, Pydantic 2.13.x, and SQLAlchemy 2.0.x running fully async (`create_async_engine`) is the verified-current core. The single highest-leverage stack decision is the PostgreSQL driver: `psycopg[binary]` 3.3.x is the only DBAPI that gives SQLAlchemy both a sync and an async dialect from the same connection URL, which means Alembic's `env.py` stays a stock synchronous template instead of needing an async rewrite or a second driver — a real simplification for a 4-6h budget. JWT and password hashing must use `PyJWT` and `pwdlib[argon2]` (the current official FastAPI recommendation) rather than `python-jose` and `passlib`, both of which are effectively dead upstream and, in `passlib`'s case, incompatible with Python 3.13 (imports the removed stdlib `crypt` module) and with `bcrypt` ≥ 4.1. Testing runs on `pytest` 9.x + `pytest-asyncio` 1.x + `httpx.AsyncClient(transport=ASGITransport(...))` against a real Postgres (docker-compose or a CI service container, not testcontainers, to keep the evaluator's one-command story intact). `flake8` + `black` + `isort` are brief-mandated; `import-linter` is the tool that turns "layer boundaries" from a claim into an enforced, testable contract; `mypy --strict` is the CI-level static-typing gate.

**Core technologies:**
- **FastAPI 0.141.x + Pydantic 2.13.x**: HTTP framework, OpenAPI, request/response schemas — brief-mandated, current stable versions
- **SQLAlchemy 2.0.x (async) + psycopg[binary] 3.3.x + Alembic 1.20.x**: ORM, single dual-mode driver, migrations — one driver serves both the async app engine and Alembic's sync `env.py`
- **PyJWT 2.14.x + pwdlib[argon2] 0.3.x**: JWT + password hashing — current FastAPI-docs recommendation; `python-jose`/`passlib` are disqualified (CVEs, dead maintenance, Python 3.13 incompatibility)
- **import-linter 2.15 + a pytest wrapper**: automated architecture-boundary enforcement — the specific mechanism the brief's "next level" layer asks for
- **pytest 9.x + pytest-asyncio 1.x + pytest-cov 7.x**: test runner, async support, the `--cov-fail-under=75` gate

### Expected Features

The feature research reframes "user value" as "evaluator points gained or lost," which sharply disambiguates scope. Every mandatory and bonus use case in the brief is P1 (must ship); a small set of cheap, high-signal differentiators (a notification port with two adapters, a documented 403-vs-404 visibility matrix, an aggregate completion-percentage query, explicit-null PATCH semantics) are P2; and a long, well-argued anti-features list (PUT+PATCH both, real SMTP, message queues, pagination/sorting, roles/permissions, soft delete) exists specifically to stop the 4-6h budget from being burned on things that earn zero points or actively signal poor scope judgement.

**Must have (table stakes):**
- CRUD for task lists and nested tasks, a dedicated status-change endpoint, filtering by status/priority, and a completion-percentage field — all literal brief text (1.a)
- JWT register/login with a working Swagger "Authorize" button, task assignment, and a simulated (never real) email notification — all three bonuses (1.b), in scope per PROJECT.md
- Ownership scoping on every read/write, unique list name per owner, assignee-must-exist, cascade delete, consistent RFC 9457 error bodies, and a usable `/docs`

**Should have (differentiators):**
- Notification port + two adapters (logging + in-memory), assertable with zero mocking — the single highest value-per-minute item in the project
- A crisp, documented 403 (visible, not permitted) vs 404 (invisible) authorization matrix
- Completion percentage computed as one SQL aggregate (not Python N+1), with `total_tasks`/`completed_tasks` returned alongside it for self-verification

**Defer (out of scope / "pending work" in README):**
- Pagination/sorting, refresh tokens/logout/password reset, list membership/sharing, roles beyond owner/assignee, soft delete, real email delivery — all explicitly out of scope per PROJECT.md and reconfirmed as anti-features by FEATURES.md

### Architecture Approach

Four layers in a `src/` layout — domain (stdlib only), application (use cases + `Protocol` ports + Pydantic DTOs), infrastructure (SQLAlchemy adapters, JWT/hashing adapters, the logging notifier), and presentation (routers, schemas, the single exception handler) — with the dependency direction enforced by an `import-linter` `layers` contract plus a `forbidden` contract keeping `fastapi`/`sqlalchemy`/`pydantic` out of the domain, wired into pre-commit, CI, and a pytest wrapper so it is a *test*, not a folder convention. One class per use case (`ChangeTaskStatus`, `AssignTask`, ...) follows a fixed shape — load → authorize → invoke domain → persist → commit → map to result — and a Unit-of-Work owns the transaction boundary explicitly, never a FastAPI dependency's exit code (which FastAPI's own docs confirm runs *after* the response is sent).

**Major components:**
1. **Domain entities & exceptions** — `@dataclass` entities carrying real invariants (`Task.change_status` enforces the transition map, raises `DomainError` subclasses), zero imports outside stdlib
2. **Application use cases + ports** — one class per brief use case; ports as `typing.Protocol` (`TaskRepository`, `UnitOfWork`, `PasswordHasher`, `TokenService`, `EmailNotifier`, `Clock`); Pydantic command/result DTOs decouple HTTP shape from domain shape
3. **Infrastructure adapters** — SQLAlchemy 2.0 `Mapped[...]` ORM models + explicit mappers (never returned directly to routers), `SqlAlchemyUnitOfWork`, JWT/hasher adapters, `LoggingEmailNotifier`/`InMemoryEmailNotifier`
4. **Presentation (composition root)** — routers with no `try/except` and no SQLAlchemy import, `dependencies.py` as the only module wiring infra into use cases, one `@app.exception_handler(DomainError)` producing RFC 9457 bodies

### Critical Pitfalls

1. **`MissingGreenlet` from implicit async lazy-loading** — set `lazy="raise"` on every relationship, map ORM rows to domain objects inside the repository (never hand an ORM instance to a router/Pydantic schema), and use `expire_on_commit=False` on the session factory. Fix this before the first repository ships, not after.
2. **Session/transaction lifecycle drift** — one session per request via a UoW; repositories `add()`/`flush()` but never `commit()`; the use case commits exactly once on success. `grep -rn "\.commit()" infrastructure/repositories/` must return nothing.
3. **Coverage that looks like ≥75% but isn't** — set `source = app` (or the real package) explicitly so unimported files show as 0% instead of vanishing from the denominator, and never `--cov=.` (which counts the test files themselves toward the number).
4. **Docker startup race on a clean volume** — `depends_on: condition: service_healthy` plus a `pg_isready -h 127.0.0.1 ...` healthcheck (without `-h`, the official Postgres image's temporary init-time Unix-socket server reports "ready" before TCP is actually listening — invisible on a warm volume, guaranteed on the evaluator's first `docker compose up`).
5. **Layers that are folders, not enforced boundaries, and `HTTPException` raised inside use cases** — both are "one `grep` away from being caught" and both directly undercut the project's stated architectural differentiator; write the `import-linter` contract and the domain-exception hierarchy in the same phase the domain is written, not after.

## Conflicts Between Research Files

The four researchers worked independently and disagree on the following points. Do not resolve these silently — lock in a choice during Phase 1 planning and record it in `DECISION_LOG.md`.

| # | Conflict | Positions | Recommended Resolution |
|---|----------|-----------|-------------------------|
| 1 | **Ownership-violation status code** | PITFALLS' Security Mistakes table reads as "always 404 for others' resources"; FEATURES gives an explicit matrix (invisible to caller → 404 always; visible but action not permitted, e.g. assignee tries to delete → 403). Note PITFALLS' own Pitfall-13 prose actually already states the same nuance ("403 is correct only when the user can legitimately see the resource but lacks permission for this action") — the conflict is really the compressed Security Mistakes table row reading as blunter than the detailed guidance. | Adopt FEATURES' explicit visibility matrix (it is the differentiator-grade version of the same rule PITFALLS' detailed text already supports): **invisible → 404 for every verb; visible-but-forbidden → 403.** Write four cross-user negative tests per PITFALLS' checklist. If time runs short, PITFALLS explicitly sanctions falling back to 404-everywhere — cut order confirms this is acceptable, but the docs and an unreachable status code must then be updated together. |
| 2 | **`asyncio_default_fixture_loop_scope`** | STACK's `pytest.ini` sets `session` (to support a shared async engine fixture with less boilerplate); PITFALLS sets `function` (to avoid `RuntimeError: attached to a different loop` / `Event loop is closed`, which it documents as a common, hard-to-reproduce-locally, CI-only failure mode). | Default to **`function`** — PITFALLS' failure mode is a suite-level correctness risk, STACK's is a convenience optimization. Keep the shared engine fixture where wanted by giving it its own explicit `@pytest_asyncio.fixture(loop_scope="session", scope="session")` (both parameters, matched) rather than changing the global default — this gets STACK's performance benefit without PITFALLS' fragility. |
| 3 | **Python version in Docker** | PROJECT.md says 3.12 (rationale: "wheel stability" on the host); STACK says 3.13, verified live that 3.12 is now security-only status (bugfixes stopped) while every dependency in this stack ships `cp313` wheels — the wheel-stability rationale for 3.12 is stale as of the research date. | **3.13** (`python:3.13-slim-trixie`). Update PROJECT.md's stated rationale; this is a documentation update, not a design tradeoff — STACK's evidence is dated and verifiable. |
| 4 | **Error contract RFC** | PROJECT.md says RFC 7807; FEATURES and ARCHITECTURE say RFC 9457 (which obsoletes 7807, July 2023, with a wire-compatible, non-breaking format). | **RFC 9457.** Same `application/problem+json` media type and core members as 7807, so this is a citation upgrade with no rework — cite both in `DECISION_LOG.md` and update PROJECT.md's wording. |
| 5 | **Layer naming / import-linter contract, and package layout** | ARCHITECTURE recommends a `src/taskmanager/` layout with `root_package = "taskmanager"` and a `layers` contract `taskmanager.main > taskmanager.presentation > taskmanager.infrastructure > taskmanager.application > taskmanager.domain`. STACK's illustrative sample uses a flat `app` package with `root_package = app` and layers `app.api > app.infrastructure > app.application > app.domain` (no `main`, "presentation" renamed "api"). This propagates into `.flake8` excludes, `pytest.ini`'s `--cov=app` vs `--cov=src/taskmanager`, and every code sample's import paths. | Adopt **ARCHITECTURE's `src/taskmanager/` layout** — it is the more deeply justified choice (a missing `__init__.py` or packaging bug then fails in CI instead of at `docker build`, and it gives import-linter one unambiguous root). Rename the top layer package to match whatever the project's package name ends up being; treat STACK's `app`/`api` naming as illustrative shorthand, not a competing structural recommendation. Update `pytest.ini`'s `--cov=` target and `.flake8`'s excludes to match once the package name is fixed. |
| 6 | **Domain entity typing: dataclasses vs Pydantic** | ARCHITECTURE recommends stdlib `@dataclass` entities with Pydantic confined to the application DTO/schema/settings boundary, arguing this is what makes "domain imports nothing" a provable claim. PROJECT.md's brief says "strong typing with Pydantic," which a literal reading could take as applying to entities too. | **User decision, not resolvable by research alone.** ARCHITECTURE's position is well-argued (Pydantic validation errors leak a foreign type into the domain and can't carry `code`/`details`; `pydantic.dataclasses.dataclass` exists as a documented escape hatch that keeps dataclass ergonomics but weakens the framework-free claim). Recommend dataclasses-in-domain + Pydantic-everywhere-else as the default, but flag explicitly for the user/roadmapper to confirm before Phase 2, since it is a visible, literal-compliance judgement call worth one sentence in `DECISION_LOG.md` either way. |
| 7 | **Alembic vs `Base.metadata.create_all()` given the 4-6h budget** | PITFALLS treats `create_all` as an acceptable shortcut *if explicitly declared as scoped-out in `DECISION_LOG.md`*, reflecting real time pressure; STACK and ARCHITECTURE both assume Alembic is in scope and build significant tooling around it (async `env.py` template, CI migration step, "never `create_all`" as an anti-pattern). | **Alembic**, per STACK/ARCHITECTURE's converging recommendation — psycopg3 (conflict #8 below) keeps `env.py` a stock sync template, which materially lowers the cost PITFALLS is worried about. Budget it explicitly (~30-45 min) in the Persistence phase; keep `create_all()` as a named, documented fallback only if that phase overruns, never as a silent substitute. |
| 8 | **PostgreSQL driver: psycopg3 vs asyncpg** | STACK gives a detailed, well-sourced argument for `psycopg[binary]` 3.x as the single dual sync/async driver (simplifies Alembic to a sync `env.py`, one dependency, one `DATABASE_URL` everywhere). PITFALLS' generic "Integration Gotchas" table illustrates the async-driver-URL pitfall using `postgresql+asyncpg://` and implies a second sync URL for Alembic — consistent with an asyncpg-first assumption, not with STACK's single-driver simplification. | **psycopg3**, per STACK's decision detail (§3) — it is the more specific, more deeply reasoned analysis for this exact scope. Read PITFALLS' asyncpg example as illustrating the general "driver suffix must match sync/async engine" principle, not as a competing driver recommendation; the same principle holds for `postgresql+psycopg://` used consistently. |
| 9 | **PostgreSQL Docker image tag** | STACK recommends `postgres:18-alpine` (GA Sept 2025, ~1 year in the field, EOL 2030-11). ARCHITECTURE's and PITFALLS' `docker-compose.yml` examples both use `postgres:16-alpine`. | Low-stakes either way — **`postgres:18-alpine`** per STACK's freshness argument is the slightly better choice for a 2026 submission, but `16-alpine` is a defensible, more conservative fallback. What matters more than the exact number is STACK's actual rule: **never `postgres:latest`**; pin the major version explicitly in `docker-compose.yml`. |

## Implications for Roadmap

Based on combined research — ARCHITECTURE's "Suggested Build Order" (its natural phase seams: `{0}`, `{1,2}`, `{3,4}`, `{5}`, `{6,7}`, `{8}`) and PITFALLS' "Pitfall-to-Phase Mapping" (P1 Foundation through P7 Delivery) converge almost exactly on the same shape — the roadmap should follow seven phases, each ending on a green test suite and a demonstrable capability:

### Phase 1: Foundation & Quality Gates
**Rationale:** Every later pitfall in this research (coverage gaming, flake8/black wars, pytest-asyncio loop chaos, deprecated-idiom drift, Docker startup races) is cheapest to prevent before any app code exists, and most expensive to retrofit. ARCHITECTURE's own build order puts this at step 0 with the explicit note: "writing the contract before the code is the whole trick — boundaries can never be violated because they were never unenforced."
**Delivers:** `src/` skeleton, `pyproject.toml`/`pytest.ini`/`.flake8` (all three literal files the brief names), black/isort/mypy/pre-commit, `import-linter` contracts against still-empty packages, Makefile, GitHub Actions CI, multistage Dockerfile + `docker-compose.yml` with a correct Postgres healthcheck, `GET /health`.
**Addresses:** the brief's tooling-file requirements (PDF 3-6); the "next level" quality-gate layer from PROJECT.md.
**Avoids:** Pitfalls 4 (loop-scope), 6 (fake coverage), 7 (Postgres readiness race), 15 (deprecated idioms — `filterwarnings = error` from commit one), 16 (flake8/black/isort fights), 17 (Docker review failures).

### Phase 2: Domain & Architecture Boundaries
**Rationale:** The domain and the `DomainError` hierarchy must exist before any use case or router does, or every subsequent file gets written against an unstable contract; the boundary test must be written in the same phase as the domain, per PITFALLS, "not bolted on later, or the violations accumulate faster than they can be fixed."
**Delivers:** `TaskList`/`Task`/`User` entities with real invariants (status transition map, `completed_at` side effect), `TaskStatus`/`TaskPriority` enums, the closed `DomainError` hierarchy, `application/ports/` Protocols, the naming glossary, and `tests/architecture/test_layer_boundaries.py` using `ast`-based import inspection (verified by temporarily adding a forbidden import and confirming it fails).
**Implements:** ARCHITECTURE Patterns 1, 2, 6 (dataclass entities, `Protocol` ports, domain-exception hierarchy).
**Avoids:** Pitfalls 9 (layers-as-folders), 10 (`HTTPException` in use cases), and lays groundwork against 18 (AI-code tells — naming glossary).

### Phase 3: Persistence
**Rationale:** ARCHITECTURE explicitly flags this as the step needing deeper research during planning — "async session + transactional test fixtures is the single most error-prone area in this stack." The router in Phase 4 needs something real to call, so this must precede it.
**Delivers:** SQLAlchemy 2.0 `Mapped[...]` ORM models, explicit ORM↔domain mappers, `SqlAlchemyUnitOfWork`, repository implementations satisfying the Phase 2 ports, Alembic baseline migration (async `env.py` template, run via container entrypoint before `exec uvicorn`), and the transactional-rollback integration-test fixture (`join_transaction_mode="create_savepoint"`).
**Uses:** psycopg3 + SQLAlchemy 2.0 async + Alembic from STACK.md (see Conflicts #7, #8 for the two decisions this phase must lock in first).
**Avoids:** Pitfalls 1 (`MissingGreenlet`), 2 (`expire_on_commit`), 3 (session lifecycle), 5 (test-DB isolation), 8 (migration race/absence).

### Phase 4: Core API — Task Lists & Tasks
**Rationale:** This is the first end-to-end vertical slice (router + schemas + composition root + the RFC 9457 error handler wired for real) and proves the whole pattern before it is repeated across the remaining use cases; everything after this phase is repetition of a proven shape, not new risk.
**Delivers:** Full CRUD for task lists and nested tasks, cascade delete, the dedicated status-change endpoint, filtered listing, and the completion-percentage envelope computed as a single SQL aggregate (never Python-side N+1).
**Addresses:** all of brief use-case 1.a; FEATURES' P1 table-stakes list for lists/tasks/status/filters/percentage.
**Avoids:** Pitfall 11 (N+1 completion percentage) — the one place PITFALLS says an evaluator can directly see whether the candidate "thinks in SQL."

### Phase 5: Auth & Bonus Features
**Rationale:** Ownership scoping (needed from Phase 3's repository signatures onward) only becomes testable once a `User` and JWT principal exist; assignment and the fake-notification bonus both depend on users existing and being discoverable.
**Delivers:** User registration/login (OAuth2 password flow so Swagger's "Authorize" button works), PyJWT + pwdlib[argon2], `GET /users/me` + `GET /users`, ownership-scoped queries on every list/task route, task assignment with the `EmailNotifier` port (`LoggingEmailNotifier` + `InMemoryEmailNotifier`), and the 403-vs-404 visibility matrix (see Conflict #1).
**Addresses:** brief use-case 1.b, all three bonuses.
**Avoids:** Pitfall 12 (JWT implemented from stale training data — hard-coded secrets, missing `algorithms=`, `python-jose`/`passlib`), Pitfall 13 (IDOR/ownership leakage).

### Phase 6: Test Hardening & Coverage
**Rationale:** By this point the app is feature-complete; this phase exists specifically to catch the failure mode PITFALLS calls the most damaging to the project's own thesis — tests that assert nothing and inflate coverage without proving anything, which directly contradicts a submission whose differentiator is "directed, verified AI use."
**Delivers:** An assertion audit (every test checks the response body, not just the status code; every mutating test re-reads through the API to confirm persistence), coverage pushed to ≥75% via `--cov-fail-under=75` in CI, and a deliberate-break spot check (invert the completion-percentage formula, confirm a test goes red).
**Avoids:** Pitfall 18 (AI-generated-code tells — the assertion half), reinforces Pitfall 6 (coverage that looks real but isn't).

### Phase 7: Docs & Delivery
**Rationale:** README failures on a clean machine are the #1 reviewer-rejection cause per PITFALLS' sourced claim, and there is no recovery from discovering it post-submission — this must be a blocking, rehearsed acceptance criterion, not a final glance.
**Delivers:** `README.md` (quickstart-first structure), `DECISION_LOG.md` (every brief ambiguity resolved and every conflict in this document recorded), `AI_WORKFLOW.md` (finalized against actual git history — at least three real, falsifiable AI mistakes, zero superlatives), a fresh-clone-and-`docker compose down -v && up --build` rehearsal, and a green CI badge on a public repo.
**Avoids:** Pitfall 14 (README fails on a clean machine), Pitfall 19 (`AI_WORKFLOW.md` reads as marketing).

### Phase Ordering Rationale

- **Gates before code (Phase 1 first, always):** every pitfall that is cheap to prevent and expensive to retrofit (coverage config, lint config, Docker healthchecks) lives in tooling files that exist before app logic does.
- **Domain before application before persistence before presentation:** this is both the brief's literal grading axis and the dependency order ARCHITECTURE's ports require (application's `Protocol` ports reference domain types, so domain must exist first; persistence implements those ports, so it comes after; presentation calls use cases, so it comes last of the four).
- **One proven vertical slice (Phase 4) before widening to auth/bonus (Phase 5):** avoids repeating an unproven wiring pattern across fourteen use cases, per ARCHITECTURE's explicit ordering rule ("4 before 5/6/7 — never repeat an unproven pattern fourteen times").
- **Auth before assignment/notifications:** assignment needs a `User` to assign to; the fake-notification trigger is the assignment event.
- **Hardening and delivery last, but logging starts early:** `AI_WORKFLOW.md` must be written incrementally (PITFALLS is explicit that retroactive reconstruction is where fabrication creeps in), so a running log should start in Phase 1 even though the document is only finalized in Phase 7.

### Research Flags

Needs deeper research during phase planning:
- **Phase 3 (Persistence):** ARCHITECTURE names this explicitly as the highest-risk area — async session lifecycle, transactional test fixtures (`join_transaction_mode="create_savepoint"`), and the Alembic async `env.py` template are all easy to get subtly wrong and hard to debug once wrong (`/gsd:plan-phase --research-phase 3`).
- **Phase 5 (Auth & Bonus):** JWT/password-hashing library choice has real moving parts and stale-training-data traps (PyJWT vs `python-jose`, `pwdlib` vs `passlib`), and the 403-vs-404 visibility matrix touches every route — worth a focused research pass to confirm the negative-test matrix is complete (`/gsd:plan-phase --research-phase 5`).

Standard patterns (well-documented in this research, skip `--research-phase`):
- **Phase 1 (Foundation):** tooling configs are fully specified, byte-for-byte, in STACK.md and PITFALLS.md.
- **Phase 2 (Domain):** the dataclass-entity + Protocol-port pattern is fully worked with code samples in ARCHITECTURE.md.
- **Phase 4 (Core API):** CRUD + filtering + the completion-percentage aggregate query are fully specified with exact SQL and response-envelope shapes in FEATURES.md and ARCHITECTURE.md.
- **Phase 6/7 (Hardening, Delivery):** checklists exist verbatim in PITFALLS.md ("Looks Done But Isn't" and "Recovery Strategies" tables).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every version, release date, and dependency constraint was read live from the PyPI JSON API and GitHub Releases API on the research date, not from training data. |
| Features | MEDIUM-HIGH | HTTP/REST/FastAPI/RFC mechanics are HIGH (Context7 + RFC text + official docs); "what evaluators expect" and competitor-API details are MEDIUM (inference from the brief plus web sources, not re-verified against live competitor API docs). |
| Architecture | MEDIUM-HIGH | Framework mechanics (FastAPI dependency-exit-code timing, SQLAlchemy session-transaction recipes, import-linter contract syntax, RFC 9457 supersession) are HIGH, verified against official docs. Layer decomposition, port placement, and the dataclass-vs-Pydantic call are explicitly labeled MEDIUM by the research itself — design judgment, not fact. |
| Pitfalls | HIGH for library/tooling pitfalls (verified against Context7 + official docs — e.g. `MissingGreenlet`, `expire_on_commit`, pytest-asyncio loop scope, coverage.py `source` behavior, Postgres init-race). MEDIUM for evaluator-behavior and AI-disclosure claims (multiple credible web sources agree, but not independently measured). |

**Overall confidence:** HIGH — the four files converge strongly on architecture, stack, and risk areas, and disagree only on a bounded, enumerated set of concrete parameters (see Conflicts section) rather than on strategy.

### Gaps to Address

- **All nine items in the Conflicts table above** need an explicit decision during Phase 1 planning, recorded in `DECISION_LOG.md` — most are cheap documentation updates (Python version, RFC citation, Postgres image tag), but package layout (#5) and entity typing (#6) shape many other files' exact contents and should be settled before Phase 2 starts.
- **Domain entity typing (Conflict #6)** is flagged by ARCHITECTURE itself as needing an explicit human decision, not a research-derived answer — surface it to the user before Phase 2.
- **PostgreSQL driver and Alembic scope (Conflicts #7, #8)** are linked: choosing psycopg3 (recommended) is what makes committing to Alembic over `create_all()` cheap within the 4-6h budget; if the roadmap later needs to drop to asyncpg for a stated reason, re-open the Alembic-scope question too.
- **`AI_WORKFLOW.md` credibility** is not a technical gap but a process one: PITFALLS is explicit that it must be logged incrementally starting in Phase 1, not reconstructed at the end — the roadmap should include a lightweight "log an AI_WORKFLOW entry" step at the end of each phase, not just in Phase 7.
- **Competitor-API details in FEATURES.md** (Todoist action-endpoint pattern, Google Tasks nesting) are explicitly flagged LOW confidence (training data, not re-verified) — fine to cite in `DECISION_LOG.md` as color, not to be treated as verified fact if precision matters.

## Sources

### Primary (HIGH confidence)
- PyPI JSON API and GitHub Releases/Tags API, queried live 2026-09-17 — every package version, release date, and wheel-platform constraint in STACK.md
- FastAPI official docs (via Context7 and direct URLs) — OAuth2/JWT tutorial (PyJWT + pwdlib), dependencies-with-yield timing, async-tests pattern, handling-errors — https://fastapi.tiangolo.com/
- SQLAlchemy 2.0 official docs — asyncio extension, session-transaction / external-transaction test recipe — https://docs.sqlalchemy.org/en/20/
- RFC 9457, *Problem Details for HTTP APIs* (obsoletes RFC 7807) — https://www.rfc-editor.org/rfc/rfc9457.html
- import-linter official docs (via Context7) — layers/forbidden contract syntax — https://import-linter.readthedocs.io/en/stable/
- pytest-asyncio official docs — `asyncio_mode`, `asyncio_default_fixture_loop_scope`, loop-scope migration guidance — https://pytest-asyncio.readthedocs.io/
- coverage.py official docs — `source` option and its effect on unexecuted-file reporting — https://coverage.readthedocs.io/
- python.org devguide — Python version status/EOL table — https://devguide.python.org/versions/

### Secondary (MEDIUM confidence)
- GitHub docs / community write-ups on 403-vs-404 information-disclosure tradeoffs
- Docker Postgres image init-race issue threads (`docker-library/postgres#1237`) corroborating the `pg_isready -h` fix
- `pyca/bcrypt` issue threads corroborating `passlib` + `bcrypt` ≥ 4.1 breakage
- Take-home-interview reviewer-behavior write-ups (README-first-run failure as dominant rejection cause; "polished but unowned" as the 2026 AI-disclosure red flag)

### Tertiary (LOW confidence, flagged inline in source files)
- Todoist `/tasks/{id}/close`/`/reopen` action-endpoint pattern and Google Tasks' nested URL shape (training data, not re-verified against live API docs)
- PyJWT's handling of non-string `sub` claims for the exact pinned version (flagged "verify against the installed version" in STACK.md)

---
*Research completed: 2026-09-17*
*Ready for roadmap: yes*
