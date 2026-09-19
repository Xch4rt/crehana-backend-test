---
phase: 4
slug: task-lists-tasks
status: draft
nyquist_compliant: true
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
- **Max feedback latency:** 60 seconds (two documented whole-stack exceptions, see Sign-Off)

---

## Per-Task Verification Map

> Task IDs use the format `4-PP-TT` (phase 4, plan `PP`, task `TT`) and name the plan task that
> owns the verification. Block A is the requirement → test contract from `04-RESEARCH.md`
> § Validation Architecture, now bound to the task that proves it. Block B covers every remaining
> plan task, so all 33 tasks of the phase appear with an automated command.

### Block A — requirement contracts

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-07-02 | 04-07 | 3 | ARC-05 | T-4-35, T-4-40 | Every route declares a Pydantic request/response model; no router returns a dataclass | unit | `pytest tests/unit/presentation/test_schemas.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04-04 | 2 | ARC-05 | T-4-17, T-4-20 | Commands/results stay frozen slotted dataclasses | unit | `pytest tests/unit/application -k "immutable or undeclared" -q --no-cov` | ✅ pattern exists | ⬜ pending |
| 4-09-02 | 04-09 | 5 | LIST-01 | — | N/A | integration (API) | `pytest tests/integration/api/test_task_lists.py -k create -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-09-03 | 04-09 | 5 | LIST-02 | T-4-51, T-4-52 | A list the actor does not own answers 404, identical to an absent one | integration (API) | `pytest tests/integration/api/test_task_lists.py -k get -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-10-03 | 04-10 | 6 | LIST-03 / D-17 | T-4-62 | N/A (one grouped statement, no N+1) | integration (API) | `pytest tests/integration/api/test_statements.py -k lists -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-09-03 | 04-09 | 5 | LIST-04 | T-4-54 | Unknown keys and `{}` refused with 422, never silently ignored | integration + unit | `pytest tests/integration/api/test_task_lists.py -k patch -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-09-02 | 04-09 | 5 | LIST-05 | — | No orphan tasks after list delete | integration (API) | `pytest tests/integration/api/test_task_lists.py -k delete -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-09-03 | 04-09 | 5 | LIST-06 | T-4-25 | 409 `duplicate_task_list_name` on create **and** rename | integration (API) | `pytest tests/integration/api/test_task_lists.py -k duplicate -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-10-01 | 04-10 | 6 | TASK-01 | T-4-58 | N/A | integration (API) | `pytest tests/integration/api/test_tasks.py -k create -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-10-01 | 04-10 | 6 | TASK-02 / D-14 | T-4-57 | Task under the wrong list → 404 `task_not_found`, identical to an absent task | integration (API) | `pytest tests/integration/api/test_tasks.py -k wrong_list -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-10-02 | 04-10 | 6 | TASK-03 / D-08 | T-4-59 | `status` in the generic PATCH → 422 | integration (API) | `pytest tests/integration/api/test_tasks.py -k status_is_not_writable -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-10-01 | 04-10 | 6 | TASK-04 | T-4-58 | N/A | integration (API) | `pytest tests/integration/api/test_tasks.py -k delete -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-10-02 | 04-10 | 6 | TASK-05 | — | Invalid transition → 409 with `from`/`to`; same-state → 200 | integration + unit | `pytest tests/integration/api/test_tasks.py -k status -x --no-cov` | ⚠️ unit exists, HTTP leg ❌ W0 | ⬜ pending |
| 4-10-02 | 04-10 | 6 | TASK-06 | T-4-60 | Invalid filter value → 422 at `query.status` / `query.priority` | integration (API) | `pytest tests/integration/api/test_tasks.py -k filter -x --no-cov` | ❌ W0 | ⬜ pending |
| 4-10-02 | 04-10 | 6 | TASK-07 | T-4-61 | N/A (stats cover the whole list, unchanged by the filter, `0.0` when empty) | integration (API) | `pytest tests/integration/api/test_tasks.py -k statistics -x --no-cov` | ⚠️ repository leg exists, HTTP leg ❌ W0 | ⬜ pending |
| 4-10-02 | 04-10 | 6 | TASK-08 | T-4-63 | Blank title / over-length / past due date → 422 `validation_error` naming the field | integration (API) | `pytest tests/integration/api/test_tasks.py -k rejects -x --no-cov` | ⚠️ entity leg exists, HTTP leg ❌ W0 | ⬜ pending |
| 4-03-01 | 04-03 | 1 | D-04 (ownership) | T-4-13, T-4-15 | Not-owned list/task answers 404 on **every** verb | unit | `pytest tests/unit/application -k "not_owned or other_actor" -q --no-cov` | ❌ W0 | ⬜ pending |
| 4-08-03 | 04-08 | 4 | D-15 gate | T-4-49 | No module under the routers package raises or imports `HTTPException` | architecture | `pytest tests/architecture/test_routers_raise_no_http_exception.py -q --no-cov` | ❌ W0 | ⬜ pending |
| 4-02-03 | 04-02 | 1 | D-15 gate | T-4-09, T-4-10 | `domain`/`application`/`infrastructure` import no fastapi/starlette | architecture | `pytest tests/architecture/test_layer_boundaries.py -q --no-cov` | ✅ (needs the new contract + `EXPECTED_CONTRACT_NAMES` update) | ⬜ pending |
| 4-10-03 | 04-10 | 6 | D-17 | T-4-62 | Same statement count for 1 and N lists, and for the task listing | integration (API) | `pytest tests/integration/api/test_statements.py -x --no-cov` | ❌ W0 | ⬜ pending |

### Block B — remaining plan tasks

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 04-01 | 1 | gate hygiene | T-4-01 | A commit gate must not depend on an untracked host `.env` | unit | `.venv/bin/pytest tests/unit/test_settings.py -q --no-cov && .venv/bin/pytest tests/unit tests/architecture -q --no-cov` | ✅ exists (red on host today) | ⬜ pending |
| 4-01-02 | 04-01 | 1 | LIST-04, TASK-03, TASK-08 (domain leg) | T-4-02, T-4-03, T-4-04 | Mutators re-validate; invariants stay in the entity, never in the schema | unit | `.venv/bin/pytest tests/unit/domain/test_task.py tests/unit/domain/test_task_list.py -q --no-cov && .venv/bin/mypy src tests && .venv/bin/pytest tests/unit tests/architecture -q --no-cov` | ✅ exists | ⬜ pending |
| 4-01-03 | 04-01 | 1 | ARC-05 | T-4-05 | "Field absent" is a typed sentinel that mypy narrows, never `None` | unit | `.venv/bin/pytest tests/unit/application/test_unset.py -q --no-cov && .venv/bin/mypy src tests && make lint && make arch` | ❌ W0 | ⬜ pending |
| 4-02-01 | 04-02 | 1 | LIST-03 | T-4-06 | The fake answers the same port contract as the adapter, D-13 ordering included | unit | `.venv/bin/pytest tests/unit/application -q --no-cov` | ⚠️ files exist, method ❌ W0 | ⬜ pending |
| 4-02-02 | 04-02 | 1 | LIST-03 / D-17 | T-4-07, T-4-08, T-4-11 | One grouped statement, asserted against real PostgreSQL | integration (repository) | `docker compose up -d db && sleep 5 && .venv/bin/pytest tests/integration/test_repositories_task_lists.py tests/unit/infrastructure/test_adapter_ports.py -x --no-cov -q && .venv/bin/mypy src tests` | ✅ exists | ⬜ pending |
| 4-03-02 | 04-03 | 1 | TASK-02, TASK-05 / D-14 | T-4-12, T-4-16 | `ChangeTaskStatusCommand` carries `task_list_id`; a wrong parent is a 404, not a silent success | unit | `.venv/bin/pytest tests/unit/application -q --no-cov && .venv/bin/mypy src tests && make lint && make typecheck && make arch` | ✅ exists | ⬜ pending |
| 4-04-02 | 04-04 | 2 | ARC-05, LIST-03, TASK-07 | T-4-19, T-4-20, T-4-21 | Results are explicit mappings; no ORM row or entity leaks into a result DTO | unit | `.venv/bin/pytest tests/unit/application -q --no-cov && .venv/bin/mypy src tests && make lint && make typecheck && make arch` | ✅ exists | ⬜ pending |
| 4-05-01 | 04-05 | 3 | LIST-01, LIST-06 | T-4-25, T-4-27 | Duplicate name is refused by a pre-check **and** by the adapter's `IntegrityError` translation | unit | `.venv/bin/pytest tests/unit/application/test_create_task_list.py -q --no-cov && .venv/bin/mypy src tests && make arch` | ❌ W0 | ⬜ pending |
| 4-05-02 | 04-05 | 3 | LIST-02, LIST-03 | T-4-22, T-4-23 | Reads never commit, and a not-owned list is indistinguishable from an absent one | unit | `.venv/bin/pytest tests/unit/application/test_get_task_list.py tests/unit/application/test_list_task_lists.py -q --no-cov && .venv/bin/mypy src tests` | ❌ W0 | ⬜ pending |
| 4-05-03 | 04-05 | 3 | LIST-04, LIST-05, LIST-06 | T-4-26 | Rename conflict is a 409; delete cascades to tasks | unit | `.venv/bin/pytest tests/unit/application -q --no-cov && .venv/bin/mypy src tests && make lint && make typecheck && make arch` | ❌ W0 | ⬜ pending |
| 4-06-01 | 04-06 | 3 | TASK-01, TASK-04 | T-4-28, T-4-34 | Create and delete both authorize the parent list first | unit | `.venv/bin/pytest tests/unit/application/test_create_task.py tests/unit/application/test_delete_task.py -q --no-cov && .venv/bin/mypy src tests` | ❌ W0 | ⬜ pending |
| 4-06-02 | 04-06 | 3 | TASK-02, TASK-06, TASK-07 | T-4-29, T-4-31, T-4-32 | The filter narrows the returned rows and never moves the statistics | unit | `.venv/bin/pytest tests/unit/application/test_get_task.py tests/unit/application/test_list_tasks.py -q --no-cov && .venv/bin/mypy src tests` | ❌ W0 | ⬜ pending |
| 4-06-03 | 04-06 | 3 | TASK-03, TASK-08 | T-4-30, T-4-33 | `status` is not an `UpdateTask` field at all, so it cannot be written through PATCH | unit | `.venv/bin/pytest tests/unit/application -q --no-cov && .venv/bin/mypy src tests && make lint && make typecheck && make arch` | ❌ W0 | ⬜ pending |
| 4-07-01 | 04-07 | 3 | ARC-05, D-01, D-03 | T-4-36, T-4-37, T-4-38 | One dependency is the only source of caller identity, and its docstring says it is not authentication | unit | `.venv/bin/pytest tests/unit/presentation -q --no-cov && .venv/bin/mypy src tests && make arch` | ❌ W0 | ⬜ pending |
| 4-07-03 | 04-07 | 3 | ARC-05, TASK-01, TASK-03, TASK-06 | T-4-35, T-4-39, T-4-40, T-4-42 | PATCH schemas are `extra="forbid"`; `status` is absent from the generic PATCH schema | unit | `.venv/bin/pytest tests/unit/presentation -q --no-cov && .venv/bin/mypy src tests && make lint && make typecheck && make arch && .venv/bin/pytest tests/unit tests/architecture -q --no-cov` | ❌ W0 | ⬜ pending |
| 4-08-01 | 04-08 | 4 | LIST-01 … LIST-06 | T-4-43, T-4-44, T-4-45 | The router raises no `HTTPException`; every failure is a `DomainError` translated once | unit + architecture | `.venv/bin/mypy src tests && make lint && .venv/bin/pytest tests/unit tests/architecture -q --no-cov` | ✅ exists | ⬜ pending |
| 4-08-02 | 04-08 | 4 | TASK-01 … TASK-08 | T-4-46, T-4-47, T-4-48 | Same for the task router, status endpoint included | unit + architecture | `.venv/bin/mypy src tests && make lint && .venv/bin/pytest tests/unit tests/architecture -q --no-cov` | ✅ exists | ⬜ pending |
| 4-09-01 | 04-09 | 5 | ARC-05 (harness) | T-4-55, T-4-56 | The harness drives the real app over ASGITransport; `TestClient` is never imported | integration (API) | `docker compose up -d db && sleep 5 && .venv/bin/pytest tests/integration/api -x --no-cov -q && .venv/bin/mypy src tests` | ❌ W0 | ⬜ pending |
| 4-11-01 | 04-11 | 5 | D-02 / SC-1 | T-4-64, T-4-66, T-4-67, T-4-68 | The demo-user seed is idempotent (`ON CONFLICT DO NOTHING`), so a restart cannot fail the boot | script gate | `bash -n docker/entrypoint.sh && make arch && make lint && make typecheck && grep -q "DEMO_USER_ID" docker/entrypoint.sh && grep -q "ON CONFLICT" docker/entrypoint.sh` | ✅ exists | ⬜ pending |
| 4-11-02 | 04-11 | 5 | D-02 / SC-1 | T-4-69 | A cold stack on an empty volume migrates, seeds and serves 201 with no manual step | manual-equivalent (scripted) | `docker compose down -v && docker compose up -d --build && sleep 30 && docker compose ps --format '{{.Service}} {{.Health}}' \| grep -q 'api healthy' && curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8000/api/v1/task-lists -H 'content-type: application/json' -d '{"name":"cold-start-check"}' \| grep -q 201` | n/a (Docker) | ⬜ pending |
| 4-12-01 | 04-12 | 7 | DOC (ADRs) | T-4-72 | Decisions are append-only; no prior ADR is rewritten | doc gate | `git diff DECISION_LOG.md \| grep -c '^-' \| grep -qx 1 && grep -c "^## ADR-" DECISION_LOG.md` | ✅ exists | ⬜ pending |
| 4-12-02 | 04-12 | 7 | LIST-01 … TASK-08 (tick-off) | T-4-70, T-4-73 | A requirement is ticked only with a green test behind it | doc gate + tests | `grep -c "LIST-01" .planning/REQUIREMENTS.md && .venv/bin/pytest tests/integration/api tests/unit/presentation -q --no-cov` | ✅ exists | ⬜ pending |
| 4-12-03 | 04-12 | 7 | phase gate | T-4-71, T-4-75 | Every gate green in one uninterrupted run on a clean tree | full gate | `git status --porcelain \| wc -l \| grep -qx 0 && make lint && make typecheck && make arch && docker compose up -d db && sleep 5 && make test && make docker-test` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Every item below is created by a named plan task; none is left to improvisation at execution time.

- [ ] `tests/integration/conftest.py` — `api_client` fixture (real app + `dependency_overrides[get_uow]` over the connection-bound `session_factory`) and an actor-override helper for `get_current_actor`. **Checked by 4-09-01** (plan 04-09, Task 1, wave 5). No HTTP integration fixture exists today; every `tests/integration/api/` module depends on it.
- [ ] `tests/integration/conftest.py` — `statements` fixture (the `before_cursor_execute` recorder) for D-17. **Checked by 4-09-01** (plan 04-09, Task 1, wave 5); first consumed by 4-10-03.
- [ ] `tests/integration/api/__init__.py` and `test_task_lists.py` — **checked by 4-09-01** (package + smoke test) and filled by 4-09-02 / 4-09-03. `test_tasks.py` — **checked by 4-10-01**, extended by 4-10-02. `test_statements.py` — **checked by 4-10-03**.
- [ ] `tests/unit/presentation/test_schemas.py` — **checked by 4-07-02** (plan 04-07, Task 2, wave 3), extended by 4-07-03. `tests/unit/presentation/test_actor.py` — **checked by 4-07-01**.
- [ ] `tests/architecture/test_routers_raise_no_http_exception.py` — **checked by 4-08-03** (plan 04-08, Task 3, wave 4), with the planted-violation red capture under `evidence/04-08-ast-gate-red.txt`.
- [ ] `tests/unit/application/fakes.py` — `list_for_owner_with_stats` and the D-13 ordering on the in-memory fakes. **Checked by 4-02-01** (plan 04-02, Task 1, wave 1), with its adapter conformance leg in 4-02-02.
- [ ] `src/taskmanager/application/dto/unset.py` — the typed PATCH sentinel every command in 04-04 and every schema in 04-07 depends on. **Checked by 4-01-03** (plan 04-01, Task 3, wave 1).
- [ ] `src/taskmanager/application/use_cases/access.py` — the shared ADR-008 ownership guard. **Checked by 4-03-01** (plan 04-03, Task 1, wave 1).
- [ ] The new `.importlinter` contract and its `EXPECTED_CONTRACT_NAMES` registration (3 kept → 4 kept). **Checked by 4-02-03** (plan 04-02, Task 3, wave 1), with the red capture under `evidence/04-02-importlinter-red.txt`. Wave-1 plans that do not own this change must assert `0 broken` only, never a kept count.
- [ ] **Pre-existing red on the developer host:** `tests/unit/test_settings.py::test_get_settings_is_cached` fails because `get_settings()` reads the host `.env` while `Settings(_env_file=None)` does not (confirmed 2026-09-18; green only where no `.env` exists). `make test` is a commit gate, so the test must be made hermetic before any Phase 4 commit can pass the gate honestly. **Checked by 4-01-01** (plan 04-01, Task 1, wave 1) — fixed unconditionally, not made conditional on a CI run.
- [ ] Framework install: none — pytest, pytest-asyncio, pytest-cov and httpx are already pinned and installed. No task required.

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

Scripted as far as it can be by 4-11-02, which runs the same sequence as a single automated
command; only the "read the logs" judgement remains human.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — all 33 tasks across plans 04-01 … 04-12 carry an `<automated>` command; none is `MISSING`
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — the gap is zero, every task is sampled
- [x] Wave 0 covers all MISSING references — every Wave 0 item above names the plan task that creates it
- [x] No watch-mode flags — no `--watch`/`--watchAll` appears in any plan command
- [x] Feedback latency < 60 s for every task-level gate, with two documented whole-stack exceptions accepted at review: 4-11-02 (cold-start rehearsal, ~60–90 s) and 4-12-03 (phase gate, ~3–5 min). Both are deliberate end-of-chain verifications, not inner-loop feedback.
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-18 (plan-time)
