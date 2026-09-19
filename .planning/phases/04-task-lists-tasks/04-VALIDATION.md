---
phase: 4
slug: task-lists-tasks
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-18
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`) + pytest-cov 7.1.0 |
| **Config file** | `pytest.ini` (brief-mandated; `[tool.pytest.ini_options]` is ignored when it exists) |
| **Quick run command** | `.venv/bin/pytest tests/unit tests/architecture -q --no-cov` |
| **Full suite command** | `make test` (→ `.venv/bin/pytest`, `--cov-fail-under=75` from addopts; requires a reachable PostgreSQL, ADR-029) |
| **Containerised run** | `make docker-test` (→ `docker compose run --rm --build test`) |
| **CI equivalent** | `.github/workflows/ci.yml` step "Tests with coverage gate", against the `postgres:18-alpine` service on `taskmanager_test` |
| **Estimated runtime** | ~2 s quick (no DB) / ~30–60 s full (real PostgreSQL, migrations once per session) |

`--no-cov` is required on every subset run: `--cov-fail-under=75` rides in `addopts`, so a
partial run would otherwise fail the coverage gate for the wrong reason.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/unit tests/architecture -q --no-cov`, then the four-gate set (`make lint && make typecheck && make arch && make test`) required before any commit (CLAUDE.md Quality gates)
- **After every plan wave:** Run `make lint && make typecheck && make arch && make test`
- **Phase gate:** `make test` green, `make docker-test` green, then `docker compose down -v && docker compose up -d` reaching `api healthy` with the demo-user seed step in place and `POST /api/v1/task-lists` answering 201 on the fresh stack
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Task IDs are filled in by the planner. The rows below are the requirement → test contract from `04-RESEARCH.md` § Validation Architecture; each plan task must cite one of these commands (or add a row).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | ARC-05 | — | Every route declares a Pydantic request/response model; no router returns a dataclass | unit | `pytest tests/unit/presentation/test_schemas.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-05 | — | Commands/results stay frozen slotted dataclasses | unit | `pytest tests/unit/application -k "immutable or undeclared" -q --no-cov` | ✅ pattern exists | ⬜ pending |
| TBD | TBD | TBD | LIST-01 | — | N/A | integration (API) | `pytest tests/integration/api/test_task_lists.py -k create -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | LIST-02 | — | A list the actor does not own answers 404, identical to an absent one | integration (API) | `pytest tests/integration/api/test_task_lists.py -k get -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | LIST-03 / D-17 | — | N/A (one grouped statement, no N+1) | integration (API) | `pytest tests/integration/api/test_statements.py -k lists -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | LIST-04 | — | Unknown keys and `{}` refused with 422, never silently ignored | integration + unit | `pytest tests/integration/api/test_task_lists.py -k patch -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | LIST-05 | — | No orphan tasks after list delete | integration (API) | `pytest tests/integration/api/test_task_lists.py -k delete -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | LIST-06 | — | 409 `duplicate_task_list_name` on create **and** rename | integration (API) | `pytest tests/integration/api/test_task_lists.py -k duplicate -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-01 | — | N/A | integration (API) | `pytest tests/integration/api/test_tasks.py -k create -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-02 / D-14 | — | Task under the wrong list → 404 `task_not_found`, identical to an absent task | integration (API) | `pytest tests/integration/api/test_tasks.py -k wrong_list -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-03 / D-08 | — | `status` in the generic PATCH → 422 | integration (API) | `pytest tests/integration/api/test_tasks.py -k status_is_not_writable -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-04 | — | N/A | integration (API) | `pytest tests/integration/api/test_tasks.py -k delete -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-05 | — | Invalid transition → 409 with `from`/`to`; same-state → 200 | integration + unit | `pytest tests/integration/api/test_tasks.py -k status -x --no-cov` | ⚠️ unit exists, HTTP leg ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-06 | — | Invalid filter value → 422 at `query.status` / `query.priority` | integration (API) | `pytest tests/integration/api/test_tasks.py -k filter -x --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-07 | — | N/A (stats cover the whole list, unchanged by the filter, `0.0` when empty) | integration (API) | `pytest tests/integration/api/test_tasks.py -k statistics -x --no-cov` | ⚠️ repository leg exists, HTTP leg ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TASK-08 | — | Blank title / over-length / past due date → 422 `validation_error` naming the field | integration (API) | `pytest tests/integration/api/test_tasks.py -k rejects -x --no-cov` | ⚠️ entity leg exists, HTTP leg ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-04 (ownership) | — | Not-owned list/task answers 404 on **every** verb | unit | `pytest tests/unit/application -k "not_owned or other_actor" -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-15 gate | — | No module under the routers package raises or imports `HTTPException` | architecture | `pytest tests/architecture/test_routers_raise_no_http_exception.py -q --no-cov` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-15 gate | — | `domain`/`application`/`infrastructure` import no fastapi/starlette | architecture | `pytest tests/architecture/test_layer_boundaries.py -q --no-cov` | ✅ (needs the new contract + `EXPECTED_CONTRACT_NAMES` update) | ⬜ pending |
| TBD | TBD | TBD | D-17 | — | Same statement count for 1 and N lists, and for the task listing | integration (API) | `pytest tests/integration/api/test_statements.py -x --no-cov` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/integration/conftest.py` — `api_client` fixture (real app + `dependency_overrides[get_uow]` over the connection-bound `session_factory`) and an actor-override helper for `get_current_actor`. No HTTP integration fixture exists today; every `tests/integration/api/` module depends on it.
- [ ] `tests/integration/conftest.py` — `statements` fixture (the `before_cursor_execute` recorder) for D-17
- [ ] `tests/integration/api/__init__.py` + `test_task_lists.py`, `test_tasks.py`, `test_statements.py`
- [ ] `tests/unit/presentation/test_schemas.py`
- [ ] `tests/architecture/test_routers_raise_no_http_exception.py`
- [ ] `tests/unit/application/fakes.py` — `list_for_owner_with_stats` and the D-13 ordering on the in-memory fakes
- [ ] **Pre-existing red on the developer host:** `tests/unit/test_settings.py::test_get_settings_is_cached` fails because `get_settings()` reads the host `.env` while `Settings(_env_file=None)` does not (confirmed 2026-09-18; green only where no `.env` exists). `make test` is a commit gate, so the test must be made hermetic before any Phase 4 commit can pass the gate honestly.
- [ ] Framework install: none — pytest, pytest-asyncio, pytest-cov and httpx are already pinned and installed

> **Ordering note.** A seeding session in an HTTP integration test must `commit()` (it releases a
> savepoint inside the connection-bound outer transaction) or its rows are rolled back when the
> session closes, before the request under test runs. `fastapi.testclient.TestClient` must not be
> imported: under `filterwarnings = error` its Starlette deprecation fails at import. Use
> `httpx.AsyncClient(transport=ASGITransport(app=app))`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A fresh stack serves the mandatory use case with zero setup: entrypoint waits, migrates, seeds the demo user idempotently, then starts uvicorn | D-02 / SC-1 | Requires the Docker daemon on the host; runs outside pytest | `docker compose down -v && docker compose up -d`; `docker compose ps --format '{{.Service}} {{.Health}}'` shows `api healthy`; `curl -s -X POST localhost:8000/api/v1/task-lists -H 'content-type: application/json' -d '{"name":"demo"}' -i` returns `201` with a `Location` header; `docker compose restart api` and the seed step logs no error on the second run |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
