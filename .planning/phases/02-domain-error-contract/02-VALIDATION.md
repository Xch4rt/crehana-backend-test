---
phase: 02
slug: domain-error-contract
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-17
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` §Validation Architecture. Task IDs in the map are filled in
> by the planner once PLAN.md files exist; the requirement → test rows are fixed now.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`) |
| **Config file** | `pytest.ini` (brief-mandated literal file; `[tool.pytest.ini_options]` in `pyproject.toml` is silently ignored) |
| **Coverage config** | `[tool.coverage.run] source = ["taskmanager"], branch = true`; `--cov-fail-under=75` in `pytest.ini` addopts; no `omit`, no `pragma` |
| **Quick run command** | `.venv/bin/pytest tests/unit -q --no-cov` (`--no-cov` suppresses the 75% gate so a subset run does not fail spuriously) |
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
| TBD | TBD | TBD | ARC-02 | — | `TaskStatus`/`TaskPriority` are `StrEnum`, serialize to lowercase strings | unit | `.venv/bin/pytest tests/unit/domain/test_task_status.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-02 | — | `Task`/`TaskList`/`User` are stdlib `slots=True` dataclasses; construction enforces invariants | unit | `.venv/bin/pytest tests/unit/domain/test_task.py tests/unit/domain/test_task_list.py tests/unit/domain/test_user.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-02 | — | `taskmanager.domain` imports nothing outside the stdlib (closes Conflict C-01) | architecture | `.venv/bin/pytest tests/architecture/test_domain_is_stdlib_only.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-02 | — | Existing enumerated import-linter contracts still hold with new packages present | architecture | `.venv/bin/pytest tests/architecture/test_layer_boundaries.py -q --no-cov` and `make arch` | ✅ | ⬜ pending |
| TBD | TBD | TBD | ARC-06 | — | Each error family exists with a stable `code` + structured `details` dict | unit | `.venv/bin/pytest tests/unit/domain/test_exceptions.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-06 | — | Hierarchy is closed — recursive `__subclasses__()` equals the expected set | unit | `.venv/bin/pytest tests/unit/domain/test_exceptions.py::test_hierarchy_is_closed -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-06 | — | `str(exc) == exc.message`; pickle and `copy.copy` round-trip preserve `details` | unit | `.venv/bin/pytest tests/unit/domain/test_exceptions.py::test_domain_error_survives_pickle_and_copy -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-06 / D-01 | — | Allowed transitions succeed; `completed→pending` raises `InvalidStatusTransitionError` specifically | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k transition -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-06 / D-02 | — | Same-state `X→X` is a no-op: no field or timestamp changes | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k same_state -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-06 / D-03 | — | Entering `completed` sets `completed_at = now`; leaving clears it to `None` | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k completed_at -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-06 / D-04 | — | Blank title, over-length fields, past `due_date` raise `ValidationError`/`BusinessRuleViolationError` | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k validation -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-06 / D-14 | — | A naive `datetime` reaching an entity raises `ValidationError` | unit | `.venv/bin/pytest tests/unit/domain/test_task.py -k naive -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-04 | — | Each of the eight ports exists as a `Protocol`; an in-memory fake satisfies it (mypy + named test) | unit | `.venv/bin/pytest tests/unit/application/test_ports.py -q --no-cov` and `make typecheck` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-04 | — | Reference use case against fakes: happy path, `NotFoundError`, `AuthorizationError`, commit called exactly once | unit | `.venv/bin/pytest tests/unit/application/test_change_task_status.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-04 | — | `HTTPException` appears nowhere under `domain`/`application` | architecture | `make arch` (`fastapi`/`starlette` in both `forbidden_modules` lists) | ✅ | ⬜ pending |
| TBD | TBD | TBD | ARC-07 | T-02-xx | `DomainError` grandchild raised in a probe route → 409 problem+json with full D-06 member set and `errors: {from,to}`; proves MRO walk (D-10) | api | `.venv/bin/pytest tests/api/test_error_contract.py -k domain -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-07 / D-07 | T-02-xx | Body/query validation failure → 422 with `errors: [{field, message, type}]`, no `loc`/`ctx`/`input` echoed | api | `.venv/bin/pytest tests/api/test_error_contract.py -k validation -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-07 / D-08 | T-02-xx | Unexpected `RuntimeError` → 500 with fixed detail; no message/traceback leaked (uses `tolerant_client`) | api | `.venv/bin/pytest tests/api/test_error_contract.py -k unexpected -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-07 / D-09 | T-02-xx | Unknown route → 404 problem+json; wrong verb → 405 with `Allow` preserved; `HTTPException(401)` → 401 with `WWW-Authenticate` preserved | api | `.venv/bin/pytest tests/api/test_error_contract.py -k http -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-07 | — | Every error response carries `content-type: application/problem+json`; no bare `{"detail": …}` | api | `.venv/bin/pytest tests/api/test_error_contract.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-07 / D-10 | — | The production app registers no `/_probe` route | unit | `.venv/bin/pytest tests/unit/test_app_factory.py -k probe -q --no-cov` | ✅ file / ❌ test | ⬜ pending |
| TBD | TBD | TBD | ARC-07 | — | `create_app()` registers all four handlers | unit | `.venv/bin/pytest tests/unit/test_app_factory.py -k handlers -q --no-cov` | ✅ file / ❌ test | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — `app`, `client`, `tolerant_client` fixtures (repo currently has no conftest.py)
- [ ] `tests/probe.py` — the test-only probe router (D-10)
- [ ] `tests/unit/domain/__init__.py`, `tests/unit/application/__init__.py`, `tests/api/__init__.py` — keep the existing `__init__.py` convention
- [ ] `tests/unit/application/fakes.py` — `FakeTaskRepository`, `FakeTaskListRepository`, `FakeUserRepository`, `FakeUnitOfWork`, `FrozenClock`
- [ ] `tests/architecture/test_domain_is_stdlib_only.py` — closes Conflict C-01
- [x] Framework install — none needed: pytest, pytest-asyncio, pytest-cov and httpx are installed and configured

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Coverage Strategy

Phase 2 adds ~200–250 statements of pure logic. The 75% floor is not the risk; specific uncoverable shapes are:

1. Protocol modules cost nothing — `...` bodies are removed by `exclude_also = ["\\.\\.\\."]`.
2. `assert isinstance` in handlers adds no partial branches; `if not isinstance(): raise` would add four uncoverable ones.
3. The `for`/`return` MRO mapper (use `next(...)`) and `__reduce__`/`_restore`/`__str__` on `DomainError` (needs the pickle test) leak uncovered lines unless handled at write time.

100% is achievable with no `pragma` and no `omit`, as CLAUDE.md §Quality gates demands.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
