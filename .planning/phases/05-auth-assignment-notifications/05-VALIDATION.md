---
phase: 5
slug: auth-assignment-notifications
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-19
task_ids_assigned: 2026-09-19
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `05-RESEARCH.md` § "Validation Architecture" and § "Security Domain".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`) + pytest-cov 7.1.0 |
| **Config file** | `pytest.ini` (brief-mandated; `filterwarnings = error`, so an `InsecureKeyLengthWarning` from a short test secret fails the run) |
| **Quick run command** | `.venv/bin/pytest tests/unit tests/architecture -q --no-cov` |
| **Full suite command** | `make test` (`--cov-fail-under=75` from addopts; requires a reachable PostgreSQL, ADR-029) |
| **Containerised run** | `make docker-test` |
| **Baseline** | 643 passed, 100.00% host coverage, 4 import-linter contracts kept |
| **Estimated runtime** | ~2 s quick (no DB) / ~10–60 s full |

`--no-cov` is required on every subset run: `--cov-fail-under=75` rides in `addopts`.
Argon2 must not dominate the suite: use cases and HTTP tests run with a cheap fake hasher; the
real `pwdlib` adapter is exercised in one dedicated unit module.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest tests/unit tests/architecture -q --no-cov`, plus the
  integration module the task touched, then the four-gate set required before any commit
  (`make lint && make typecheck && make arch && make test`)
- **After every plan wave:** `make lint && make typecheck && make arch && make test`
- **Phase gate:** `make test` green, `make docker-test` green, then
  `docker compose down -v && docker compose up -d` reaching `api healthy` with **no seed step**,
  and the scripted walk register → login → create list → create task → assign → the JSON email
  line visible in `docker compose logs api`
- **Before `/gsd:verify-work`:** full suite green
- **Max feedback latency:** 60 seconds (whole-stack evidence captures excepted)

---

## Per-Task Verification Map

Task IDs were assigned by the planner on 2026-09-19 and every row is claimed by at least one task's
`<automated>` verify. `05-NN-TX` reads as plan `05-NN`, task `X`. Where a row is proven at two
levels, both task ids are listed.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-13-T2 | 05-13 | 8 | AUTH-01 | T-5-09 mass assignment | register → 201, profile only, no hash, `extra="forbid"` | integration HTTP | `.venv/bin/pytest tests/integration/api/test_auth.py -k register --no-cov` | ❌ W0 → 05-13 | ⬜ pending |
| 05-13-T2 | 05-13 | 8 | AUTH-01 | T-5-06 (accepted oracle, D-23) | duplicate email → 409 `email_already_registered` | integration HTTP | `.venv/bin/pytest tests/integration/api/test_auth.py -k duplicate --no-cov` | ❌ W0 → 05-13 | ⬜ pending |
| 05-03-T3 | 05-03 | 2 | AUTH-01 | — | `full_name` persists and round-trips; `0002` up/down | integration | `.venv/bin/pytest tests/integration/test_repositories_users.py tests/integration/test_migrations.py --no-cov` | ✅ (cases → 05-03) | ⬜ pending |
| 05-13-T2 | 05-13 | 8 | AUTH-02 | — | login → `access_token`, `token_type == "bearer"` | integration HTTP | `.venv/bin/pytest tests/integration/api/test_auth.py -k login --no-cov` | ❌ W0 → 05-13 | ⬜ pending |
| 05-11-T3 | 05-11 | 6 | AUTH-02 | — | OpenAPI carries `securitySchemes` and per-route `security` (Authorize button) | unit (`app.openapi()`, ADR-057) | `.venv/bin/pytest tests/unit/presentation/test_security_scheme.py --no-cov` | ❌ W0 → 05-11 | ⬜ pending |
| 05-13-T2 | 05-13 | 8 | AUTH-03 | T-5-04 | missing / malformed / bad-signature / expired / unknown-subject → the same 401 problem+json with `WWW-Authenticate: Bearer`; token never echoed | integration HTTP, parametrized, real dependency | `.venv/bin/pytest tests/integration/api/test_auth.py -k unauthenticated --no-cov` | ❌ W0 → 05-13 | ⬜ pending |
| 05-05-T2 | 05-05 | 2 | AUTH-04 | T-5-01 | decode pins `algorithms`; `alg=none` and foreign-secret tokens refused | unit | `.venv/bin/pytest tests/unit/infrastructure/test_tokens.py --no-cov` | ❌ W0 → 05-05 | ⬜ pending |
| 05-01-T3 | 05-01 | 1 | AUTH-04 | T-5-02 | short `JWT_SECRET` rejected at boot; no default; floor raised to 32 (D-26) | unit | `.venv/bin/pytest tests/unit/test_settings.py --no-cov` | ✅ (case → 05-01) | ⬜ pending |
| 05-05-T1 + 05-01-T1 | 05-05, 05-01 | 2, 1 | AUTH-04 | T-5-07 password-length DoS | Argon2 off the event loop; real adapter hash/verify/non-Argon2 → False; 8–128 policy in the domain | unit | `.venv/bin/pytest tests/unit/infrastructure/test_passwords.py tests/unit/domain/test_validation.py --no-cov` | ❌ W0 → 05-05 / ✅ → 05-01 | ⬜ pending |
| 05-05-T2 + 05-13-T2 | 05-05, 05-13 | 2, 8 | AUTH-04 | — | expired token driven by a fake `Clock`, no sleep, no freezegun | unit + integration HTTP | `.venv/bin/pytest -k expired --no-cov` | ❌ W0 → 05-05, 05-13 | ⬜ pending |
| 05-07-T3 + 05-13-T2 | 05-07, 05-13 | 3, 8 | AUTH-04 | T-5-05 | unknown email and wrong password → byte-identical responses; dummy verify performed (D-21) | unit + integration HTTP | `.venv/bin/pytest -k indistinguishable --no-cov` | ❌ W0 → 05-07, 05-13 | ⬜ pending |
| 05-13-T2 | 05-13 | 8 | AUTH-05 | — | `/auth/me` returns the caller's profile, never the hash | integration HTTP | `.venv/bin/pytest tests/integration/api/test_auth.py -k _me --no-cov` | ❌ W0 → 05-13 | ⬜ pending |
| 05-15-T1 | 05-15 | 10 | AUTH-06 | T-5-11 IDOR | the whole route × {owner, assignee, stranger, anonymous} matrix (D-04) over the real dependency | integration HTTP, one parametrized table | `.venv/bin/pytest tests/integration/api/test_permission_matrix.py --no-cov` | ❌ W0 → 05-15 | ⬜ pending |
| 05-04-T1 + 05-04-T2 | 05-04 | 1 | AUTH-06 | T-5-11 IDOR | `access.py` per role: assignee sees, assignee refused with `AuthorizationError`, stranger gets `TaskNotFoundError` | unit with fakes | `.venv/bin/pytest tests/unit/application/test_access.py --no-cov` | ✅ (cases → 05-04) | ⬜ pending |
| 05-08-T2 + 05-08-T3 + 05-14-T1 | 05-08, 05-14 | 4, 9 | ASGN-01 | T-5-12 | owner assigns / unassigns; unknown assignee → 404 `user_not_found`; same-user PUT is a no-op (D-07) | unit + integration HTTP | `.venv/bin/pytest -k assign --no-cov` | ❌ W0 → 05-08, 05-14 | ⬜ pending |
| 05-08-T3 + 05-14-T3 | 05-08, 05-14 | 4, 9 | ASGN-01 | T-5-17 lost update (ADR-058) | owner PATCH vs assignee status change serialise; every new write path holds `get_for_update` | integration, two connections + unit | `.venv/bin/pytest tests/integration/test_concurrent_writes.py tests/unit/application/test_write_paths_hold_what_they_change.py --no-cov` | ✅ (cases → 05-08, 05-14) | ⬜ pending |
| 05-14-T1 | 05-14 | 9 | ASGN-02 | — | `assignee_id` exposed after assign, null after unassign; `GET /api/v1/tasks/assigned-to-me` lists only the caller's tasks | integration HTTP | `.venv/bin/pytest tests/integration/api/test_assignment.py --no-cov` | ❌ W0 → 05-14 | ⬜ pending |
| 05-13-T3 | 05-13 | 8 | ASGN-03 | T-5-06 directory trade-off (D-13) | `GET /users` → id, full_name, email, ordered `created_at, id`; 401 when anonymous | integration HTTP | `.venv/bin/pytest tests/integration/api/test_users.py --no-cov` | ❌ W0 → 05-13 | ⬜ pending |
| 05-08-T2 | 05-08 | 4 | NOTF-01 | — | notifier called exactly once, after the commit; none on re-assign or unassign | unit, in-memory notifier + commit-order recording | `.venv/bin/pytest tests/unit/application/test_assign_task.py --no-cov` | ❌ W0 → 05-08 | ⬜ pending |
| 05-06-T1 + 05-06-T2 | 05-06 | 3 | NOTF-02 | T-5-13 log injection | runtime adapter emits one JSON line at INFO with `event`, `to`, `subject`, `body`, `task_id`; a newline in a title cannot forge a record | unit (`caplog` + `json.loads`) | `.venv/bin/pytest tests/unit/infrastructure/test_notifier.py tests/unit/infrastructure/test_logging.py --no-cov` | ❌ W0 → 05-06 | ⬜ pending |
| 05-08-T2 + 05-14-T2 | 05-08, 05-14 | 4, 9 | NOTF-03 | — | a notifier that raises leaves the assignment committed and the response 200 | unit + integration HTTP | `.venv/bin/pytest -k notifier_failure --no-cov` | ❌ W0 → 05-08, 05-14 | ⬜ pending |
| 05-14-T3 | 05-14 | 9 | D-11 / D-20 | — | statement counts are 2 and 4 under real auth and invariant in row count | integration | `.venv/bin/pytest tests/integration/api/test_statements.py --no-cov` | ✅ (update → 05-14) | ⬜ pending |
| 05-09-T3 + 05-11-T1 + 05-12-T1 + 05-12-T2 | 05-09, 05-11, 05-12 | 5, 6, 7 | ADR-051 | — | no presentation module raises or imports `HTTPException` (new `auth`/`users`/`assignments` routers, the two new schema modules and `actor.py` all named in `REQUIRED_SCANNED_MODULES`) | architecture | `.venv/bin/pytest tests/architecture --no-cov` | ✅ (grow → 05-09, 05-11, 05-12) | ⬜ pending |
| 05-05-T3 + 05-07-T3 | 05-05, 05-07 | 2, 3 | layers | — | `jwt` / `pwdlib` never reach `application` or `domain` | architecture | `make arch` | ✅ | ⬜ pending |
| 05-15-T2 | 05-15 | 10 | D-14 / D-24 | T-5-03 | cold start on an empty volume, no seed; register → Authorize → assign → JSON email line in the logs | evidence capture | scripted walk, output under `evidence/05-15-cold-start.txt` | ❌ W0 → 05-15 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/application/fakes.py` — `FakePasswordHasher`, `FakeTokenService`, `InMemoryEmailNotifier`, a settable fake `Clock`; `FakeUserRepository.list_all` ordering fix (D-25)
- [ ] `tests/integration/conftest.py` — `authenticated_client` and a token helper going through the real `get_current_actor`; `acting_as` kept for existing tests (D-20)
- [ ] `tests/integration/api/test_auth.py`, `test_users.py`, `test_assignment.py`, `test_permission_matrix.py`
- [ ] `tests/unit/infrastructure/test_tokens.py`, `test_passwords.py`, `test_notifier.py`
- [ ] `tests/unit/presentation/test_security_scheme.py`
- [ ] Framework install: none — every dependency is already pinned and installed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Swagger UI "Authorize" button logs in and unlocks the routes | AUTH-02 | Browser interaction; the OpenAPI document that drives it is asserted automatically | `docker compose up`, open `/docs`, register, click Authorize, enter the credentials, call `GET /api/v1/auth/me` → 200 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — every one of the 16 plans' 46 tasks carries an `<automated>` block
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references — each ❌ W0 row above names the plan that creates the missing module
- [x] No watch-mode flags
- [x] Feedback latency < 60s (whole-stack evidence captures excepted, per Sampling Rate)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** task ids assigned by the planner on 2026-09-19; every row is claimed by a task. `Status` stays `⬜ pending` until execution.
