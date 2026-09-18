---
phase: 3
slug: persistence-runnable-stack
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-18
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`) |
| **Config file** | `pytest.ini` (brief-mandated; `[tool.pytest.ini_options]` is ignored when it exists) |
| **Quick run command** | `.venv/bin/pytest -m "not integration" -q` |
| **Full suite command** | `make test` (→ `.venv/bin/pytest`, `--cov-fail-under=75` from addopts) |
| **Containerised run** | `make docker-test` (→ `docker compose run --rm --build test`) |
| **CI equivalent** | `.github/workflows/ci.yml` step "Tests with coverage gate", against the `postgres:18-alpine` service on `taskmanager_test` |
| **Estimated runtime** | ~1 s quick (no DB) / ~20–40 s full (real PostgreSQL, migrations once per session) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest -m "not integration" -q`, then the four-gate set (`make lint && make typecheck && make arch && make test`) required before any commit (CLAUDE.md Quality gates)
- **After every plan wave:** Run `make lint && make typecheck && make arch && make test`
- **Phase gate:** `make test` green **twice in a row**, then `docker compose down -v && docker compose up -d` reaching `api healthy`, then `make docker-test` green
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Task IDs are filled in by the planner. The rows below are the success-criteria → test contract from `03-RESEARCH.md` § Validation Architecture; each plan task must cite one of these commands (or add a row).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 0 | DOCK-02 / SC-1 | — | N/A | smoke | `docker compose down -v && docker compose up -d && docker compose ps --format '{{.Service}} {{.Health}}'` → `api healthy` | ❌ W0 (compose changes) | ⬜ pending |
| TBD | TBD | TBD | DOCK-03 / SC-1 | — | `/health` never leaks DB error text | integration (API) | `pytest tests/integration/test_health.py::test_health_reports_ok_against_a_reachable_database -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DOCK-03 / SC-1 | — | 503 body has same shape, no stack trace | unit (API) | `pytest tests/unit/presentation/test_health.py::test_health_reports_503_when_the_database_probe_fails -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-03 / SC-1 | — | N/A | integration | `pytest tests/integration/test_migrations.py::test_alembic_upgrade_creates_every_table -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-01 / SC-2 | — | N/A | unit | `pytest tests/unit/infrastructure/test_mappers.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-01 / SC-2 | — | N/A | unit (introspection) | `pytest tests/unit/infrastructure/test_models.py::test_every_relationship_raises_on_lazy_load -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-02 / SC-2 | — | N/A | integration | `pytest tests/integration/test_repositories_task_lists.py::test_a_returned_entity_is_readable_after_the_session_is_gone -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-03 / SC-3 | — | N/A | integration | `pytest tests/integration/test_schema.py::test_task_lists_has_an_owner_id_foreign_key -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-04 / SC-3 | — | Invalid status/priority refused at the DB | integration | `pytest tests/integration/test_constraints.py -k "check" -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-03 / SC-3 | — | N/A | integration | `pytest tests/integration/test_schema.py::test_timestamps_round_trip_as_aware_utc -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-05 / SC-3 | — | No orphan tasks after list delete | integration | `pytest tests/integration/test_constraints.py::test_deleting_a_task_list_cascades_to_its_tasks -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-03 / SC-3 | — | N/A | integration | `pytest tests/integration/test_migrations.py::test_the_models_and_the_migrations_do_not_disagree -x` (`alembic check`) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-03 / SC-3 | — | N/A | integration | `pytest tests/integration/test_migrations.py::test_downgrade_base_removes_every_table -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-08 / SC-4 | — | N/A | integration | `pytest tests/integration/test_unit_of_work.py::test_a_successful_block_commits_once -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-08 / SC-4 | — | Partial writes never persist on DomainError | integration | `pytest tests/integration/test_unit_of_work.py::test_a_domain_error_leaves_nothing_written -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-08 / SC-4 | — | N/A | integration | `pytest tests/integration/test_unit_of_work.py::test_an_uncommitted_block_is_rolled_back -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | ARC-08 / SC-4 | — | N/A | architecture | `pytest tests/architecture/test_no_commit_in_repositories.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ARC-08 / SC-4 | — | N/A | typecheck + unit | `make typecheck && pytest tests/unit/infrastructure/test_adapter_ports.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DB-02 / SC-5 | — | N/A | integration | `pytest tests/integration/test_unit_of_work.py::test_a_committed_write_is_invisible_outside_the_test_transaction -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SC-5 | — | N/A | integration | `make test && make test` (identical result twice) | ✅ | ⬜ pending |
| TBD | TBD | TBD | SC-5 | — | N/A | all | `make lint && make typecheck && make arch && make test` | ✅ | ⬜ pending |
| TBD | TBD | TBD | D-03 | — | N/A | integration (negative) | `TEST_DATABASE_URL=postgresql+psycopg://x:x@127.0.0.1:1/x .venv/bin/pytest tests/integration -x` → exactly one failure naming `make up` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-04 | — | Password containing `taskmanager` is not rewritten | unit | `pytest tests/unit/infrastructure/test_database_url.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-13 | — | Constraint violation → typed `DomainError`, not 500 | integration | `pytest tests/integration/test_repositories_*.py -k "conflict or duplicate" -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-13 | — | Unknown constraint is re-raised, not swallowed | unit | `pytest tests/unit/infrastructure/test_errors.py::test_an_unknown_constraint_is_not_swallowed -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `alembic.ini` + `migrations/env.py` + `migrations/versions/0001_baseline.py` — the `migrated_database` fixture cannot run without them; these precede every integration test
- [ ] `docker/initdb/01-create-test-database.sql` — without it there is no `taskmanager_test` and every integration test fails at collection
- [ ] `tests/integration/__init__.py` + `tests/integration/conftest.py` — fixtures `database_url`, `_require_database`, `migrated_database`, `connection`, `session_factory`, `uow` (D-01/D-02/D-03/D-04)
- [ ] `tests/unit/infrastructure/__init__.py` — new package for mapper/clock/URL/error tests
- [ ] `tests/unit/presentation/__init__.py` — new package for the `/health` 503 unit test
- [ ] `tests/architecture/test_no_commit_in_repositories.py` — SC-4 gate
- [ ] Framework install: none — pytest, pytest-asyncio and pytest-cov are already pinned and installed

> **Ordering note.** Nothing in `tests/integration/` can be collected before `alembic.ini`, `migrations/env.py`, `0001_baseline.py` and the initdb script exist. The first plan must establish models → baseline migration → fixtures before any repository TDD cycle, otherwise the RED is a collection error rather than an assertion failure.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cold start on an empty volume reaches `api healthy` and the entrypoint waited for a genuinely ready DB and ran `alembic upgrade head` | DOCK-02 / SC-1 | Requires the Docker daemon on the host; runs outside pytest | `docker compose down -v && docker compose up -d`; `docker compose ps --format '{{.Service}} {{.Health}}'` shows `db healthy` and `api healthy`; `docker compose logs api` shows the migration run before uvicorn starts; `curl -s localhost:8000/health` returns `database: ok` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
