---
phase: 02
slug: domain-error-contract
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-17
updated: 2026-09-18
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` §Validation Architecture. The requirement → test rows were
> fixed at research time; the `Task ID / Plan / Wave / Threat Ref` columns were filled in by
> the planner once the seven PLAN.md files existed.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`) |
| **Config file** | `pytest.ini` (brief-mandated literal file; `[tool.pytest.ini_options]` in `pyproject.toml` is silently ignored) |
| **Coverage config** | `[tool.coverage.run] source = ["taskmanager"], branch = true`; `--cov-fail-under=75` in `pytest.ini` addopts; no `omit`, no `pragma` |
| **Quick run command** | `.venv/bin/pytest tests/unit -q --no-cov` (`--no-cov` suppresses the 75% gate so a subset run does not fail spuriously) |
| **Per-module 100% check** | `.venv/bin/pytest -q && .venv/bin/coverage report --include='*/taskmanager/<subpackage>/*' --fail-under=100` (the CLI `--cov=` flag appends to `pytest.ini`'s source instead of narrowing it, so the targeted check runs through `coverage report` after a full run) |
| **Full suite command** | `make test` (= `.venv/bin/pytest`, coverage gate included) |
| **Full gate** | `make lint && make typecheck && make arch && make test` |
| **Baseline before this phase** | 8 tests, 18 statements, 100% coverage, 0 warnings (`filterwarnings = error`) |
| **Estimated runtime** | ~2 seconds (pure logic, no I/O in this phase) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/unit -q --no-cov`
- **After every plan wave:** Run `make lint && make typecheck && make arch && make test`
- **Before `/gsd:verify-work`:** Full suite green, coverage ≥ 75% (target 100%, matching the Phase 1 baseline), zero warnings
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 02-01 | 1 | ARC-02 | T-02-11, T-02-12 | `TaskStatus`/`TaskPriority` are `StrEnum`, serialize to lowercase strings; `ALLOWED_TRANSITIONS` is exhaustive over `set(TaskStatus)` | unit | `.venv/bin/pytest tests/unit/domain/test_task_status.py tests/unit/domain/test_task_priority.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-01-T2 | 02-01 | 1 | ARC-02 | T-02-13 | `CompletionStats` percentage is `0.0` for an empty list and rounded to two decimals otherwise (ADR-009, user decision C-04) | unit | `.venv/bin/pytest tests/unit/domain/test_completion.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-03-T1, 02-03-T2, 02-03-T3 | 02-03 | 3 | ARC-02 | T-02-20, T-02-23 | `Task`/`TaskList`/`User` are stdlib `slots=True` dataclasses; construction enforces invariants | unit | `.venv/bin/pytest tests/unit/domain/test_task.py tests/unit/domain/test_task_list.py tests/unit/domain/test_user.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-06-T1 | 02-06 | 4 | ARC-02 | T-02-07, T-02-29 | `taskmanager.domain` imports nothing outside the stdlib (closes Conflict C-01), with an anti-vacuity guard and a committed red/green capture | architecture | `.venv/bin/pytest tests/architecture/test_domain_is_stdlib_only.py -q --no-cov` | ❌ W0 | ⬜ pending |
| every plan's closing task (02-01-T2 … 02-07-T2) | all | 1-5 | ARC-02 | T-02-30 | Existing enumerated import-linter contracts still hold with new packages present, and still number exactly three | architecture | `.venv/bin/pytest tests/architecture/test_layer_boundaries.py -q --no-cov` and `make arch` | ✅ | ⬜ pending |
| 02-02-T1, 02-02-T2 | 02-02 | 2 | ARC-06 | T-02-04, T-02-14, T-02-15 | Each error family exists with a stable `code` + structured `details` dict, and every `details` payload is JSON-safe | unit | `.venv/bin/pytest tests/unit/domain/test_exceptions.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-02-T2 | 02-02 | 2 | ARC-06 | T-02-16 | Hierarchy is closed — recursive `__subclasses__()` equals the expected twelve-name set | unit | `.venv/bin/pytest tests/unit/domain/test_exceptions.py::test_hierarchy_is_closed -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-02-T2 | 02-02 | 2 | ARC-06 | T-02-14 | `str(exc) == exc.message`; pickle and `copy.copy` round-trip preserve `details` | unit | `.venv/bin/pytest tests/unit/domain/test_exceptions.py::test_domain_error_survives_pickle_and_copy -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-03-T1, 02-03-T2 | 02-03 | 3 | ARC-06 / D-01 | T-02-18 | Allowed transitions succeed; `completed→pending` raises `InvalidStatusTransitionError` specifically, and the entity is unchanged after the raise | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k transition -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-03-T2 | 02-03 | 3 | ARC-06 / D-02 | — | Same-state `X→X` is a no-op: no field or timestamp changes | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k same_state -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-03-T2 | 02-03 | 3 | ARC-06 / D-03 | — | Entering `completed` sets `completed_at = now`; leaving clears it to `None` | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k completed_at -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-03-T2, 02-03-T3 | 02-03 | 3 | ARC-06 / D-04 | T-02-20, T-02-21 | Blank title, over-length fields, past `due_date` raise `ValidationError`/`BusinessRuleViolationError` | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k validation -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-03-T1, 02-03-T2 | 02-03 | 3 | ARC-06 / D-14 | T-02-19 | A naive `datetime` reaching an entity raises `ValidationError`; an aware non-UTC value is normalised | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k naive -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-05-T1, 02-05-T2 | 02-05 | 4 | ARC-04 | T-02-22, T-02-28 | Each of the eight ports exists as a `Protocol`; an in-memory fake satisfies it (mypy + named test) | unit | `.venv/bin/pytest tests/unit/application/test_ports.py -q --no-cov` and `make typecheck` | ❌ W0 | ⬜ pending |
| 02-05-T3 | 02-05 | 4 | ARC-04 | T-02-25, T-02-26, T-02-27 | Reference use case against fakes: happy path, `TaskNotFoundError` for a missing task, `TaskNotFoundError` (not `AuthorizationError`) for a task the actor cannot see per ADR-008, `InvalidStatusTransitionError` propagated untranslated, commit called exactly once on success and never on failure | unit | `.venv/bin/pytest tests/unit/application/test_change_task_status.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-04-T3 | 02-04 | 3 | ARC-04 / AUTH-06 | T-02-25 | `AuthorizationError` → 403 problem+json end to end (the 403 leg of ADR-008; see the note below this table) | api | `.venv/bin/pytest tests/api/test_error_contract.py -k forbidden -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-05-T1 | 02-05 | 4 | ARC-04 | T-02-28 | `HTTPException` appears nowhere under `domain`/`application` | architecture | `make arch` (`fastapi`/`starlette` in both `forbidden_modules` lists) plus a grep gate over `src/taskmanager/application/` | ✅ | ⬜ pending |
| 02-04-T3 | 02-04 | 3 | ARC-07 | T-02-04, T-02-06 | `DomainError` grandchild raised in a probe route → 409 problem+json with full D-06 member set and `errors: {from,to}`; proves the MRO walk (D-10) | api | `.venv/bin/pytest tests/api/test_error_contract.py -k domain -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-04-T3 | 02-04 | 3 | ARC-07 / D-07 | T-02-02 | Body/query validation failure → 422 with `errors: [{field, message, type}]`, no `loc`/`ctx`/`input` echoed | api | `.venv/bin/pytest tests/api/test_error_contract.py -k validation -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-04-T3 | 02-04 | 3 | ARC-07 / D-08 | T-02-01, T-02-24 | Unexpected `RuntimeError` → 500 with fixed detail; no message/traceback leaked (uses `tolerant_client`); traceback logged server-side | api | `.venv/bin/pytest tests/api/test_error_contract.py -k unexpected -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-04-T3 | 02-04 | 3 | ARC-07 / D-09 | T-02-03, T-02-06 | Unknown route → 404 problem+json; wrong verb → 405 with `Allow` preserved; `HTTPException(401)` → 401 with `WWW-Authenticate` preserved | api | `.venv/bin/pytest tests/api/test_error_contract.py -k http -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-04-T1, 02-04-T3 | 02-04 | 3 | ARC-07 / D-05, D-06 | T-02-06 | Every error response carries `content-type: application/problem+json`; the body key order is exactly `type, title, status, detail, instance, code[, errors]`; `type` is the `urn:taskmanager:problem:{code}` URN | api | `.venv/bin/pytest tests/api/test_error_contract.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 02-04-T2 | 02-04 | 3 | ARC-07 / D-10 | T-02-05 | The production app registers no `/_probe` route | unit | `.venv/bin/pytest tests/unit/test_app_factory.py -k probe -q --no-cov` | ✅ file / ❌ test | ⬜ pending |
| 02-04-T2 | 02-04 | 3 | ARC-07 | — | `create_app()` registers all four handlers, overriding FastAPI's `HTTPException` and `RequestValidationError` defaults | unit | `.venv/bin/pytest tests/unit/test_app_factory.py -k handlers -q --no-cov` | ✅ file / ❌ test | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Planner amendment to the ARC-04 use-case row.** The research-time row asked the reference
use case to demonstrate `AuthorizationError`. `ChangeTaskStatus` has no reachable 403 branch:
ASGN-02 permits both the list owner **and** the assignee to change a task's status, so every
actor who can see the task may also change it, and an actor who cannot see it must receive a
404 (`TaskNotFoundError`) per ADR-008 — a 403 there would confirm the task exists. Inventing a
403 case would have meant inventing a rule. The row was therefore split: the use-case test
covers the happy path, both not-found paths, the invisible-actor 404 and the commit counts,
while `AuthorizationError` is proven structurally in
`tests/unit/domain/test_exceptions.py` (class, `code`, `details`), by status mapping in
`status_for` (02-04-T1), and end to end as a 403 problem+json through the probe router
(02-04-T3, `-k forbidden`). The 403 leg of ADR-008 is exercised by the owner-only operations
in Phases 4 and 5.

---

## Documentation, Evidence and Reconciliation Tasks

Every task in the phase carries an `<automated>` verify. The tasks that produce documents
rather than behaviour are gated on greppable file content plus the unchanged test suite.

| Task ID | Plan | Wave | Owns | Threat Ref | Automated Command |
|---------|------|------|------|------------|-------------------|
| 02-06-T1 | 02-06 | 4 | `evidence/domain-stdlib-red-green.txt` — the planted-`greenlet` red/green capture | T-02-07, T-02-29 | `grep -q greenlet <evidence>` + `test ! -e src/taskmanager/domain/_violation.py` + `.venv/bin/pytest tests/architecture -q --no-cov` |
| 02-06-T2 | 02-06 | 4 | `DECISION_LOG.md` ADR-020 (frozen-dataclass DTOs), ADR-021 (`DomainError` shape, `ValidationError`→422, `ResponseValidationError`→500), ADR-022 (AST stdlib proof) | T-02-31 | `test "$(grep -c '^## ADR-' DECISION_LOG.md)" -eq 22` + `git diff -- DECISION_LOG.md \| grep -c '^-[^-]'` equals 0 |
| 02-07-T1 | 02-07 | 5 | ARC-05 wording, ROADMAP Phase 4 SC-5, the `.importlinter` comment, the `CLAUDE.md` rule | T-02-30, T-02-32, T-02-35 | `test "$(grep -c '^\[importlinter:contract:' .importlinter)" -eq 3` + `.venv/bin/lint-imports` + `.venv/bin/pytest tests/architecture -q --no-cov` |
| 02-07-T2 | 02-07 | 5 | `AI_WORKFLOW.md` Phase 2 section and dated incident entries; the final uninterrupted gate capture | T-02-33, T-02-34 | `test "$(grep -c '^### 20' AI_WORKFLOW.md)" -ge 7` + `make lint && make typecheck && make arch && make test` + `.venv/bin/coverage report --include='*/taskmanager/*' --fail-under=100` |

---

## Wave 0 Requirements

Every Wave 0 item is created by the plan and task that first needs it:

- [ ] `tests/unit/domain/__init__.py` — **02-01-T1** (the first test package this phase adds)
- [ ] `tests/conftest.py` — `app`, `client`, `tolerant_client` fixtures — **02-04-T3**
- [ ] `tests/probe.py` — the test-only probe router (D-10) — **02-04-T3**
- [ ] `tests/api/__init__.py` — **02-04-T3**
- [ ] `tests/unit/application/__init__.py` — **02-05-T2**
- [ ] `tests/unit/application/fakes.py` — `FakeTaskRepository`, `FakeTaskListRepository`, `FakeUserRepository`, `FakeUnitOfWork`, `FrozenClock`, plus `FakePasswordHasher`, `FakeTokenService` and `FakeEmailNotifier` so all eight ports have a conforming double — **02-05-T2**
- [ ] `tests/architecture/test_domain_is_stdlib_only.py` — closes Conflict C-01 — **02-06-T1**
- [x] Framework install — none needed: pytest, pytest-asyncio, pytest-cov and httpx are installed and configured

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Coverage Strategy

Phase 2 adds ~250–300 statements of pure logic. The 75% floor is not the risk; specific uncoverable shapes are:

1. Protocol modules cost nothing — `...` bodies are removed by `exclude_also = ["\\.\\.\\."]`.
2. `assert isinstance` in handlers adds no partial branches; `if not isinstance(): raise` would add four uncoverable ones.
3. The `for`/`return` MRO mapper (use `next(...)`) and `__reduce__`/`_restore`/`__str__` on `DomainError` (needs the pickle test) leak uncovered lines unless handled at write time.

100% is achievable with no `pragma` and no `omit`, as CLAUDE.md §Quality gates demands. Each
plan closes by asserting 100% over the subpackage it added, via
`coverage report --include=... --fail-under=100`, so a shortfall is attributed to the plan
that caused it rather than discovered at the end of the phase.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references, each assigned to the task that creates it
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner, 2026-09-18 (task ids assigned from `02-01-PLAN.md` … `02-07-PLAN.md`)
