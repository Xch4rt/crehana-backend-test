---
phase: 05-auth-assignment-notifications
verified: 2026-09-19T19:52:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "The API knows who is calling (phase goal statement) — a caller who has only read the public repository cannot forge a token the API accepts"
  gaps_remaining: []
  regressions: []
---

# Phase 5: Auth, Assignment & Notifications Verification Report (Re-verification)

**Phase Goal:** The API knows who is calling, enforces what they may do, and delivers all three bonus use cases from the brief.
**Verified:** 2026-09-19T19:52:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plan 05-17, commits `64b2e6d`, `4d94514`, `172e3e0`, `a505626`, `3326475`, closing commit `3326475` plus the STATE/ROADMAP-only `b8e514f`)

## Previous Verification

The first pass (this same file, superseded) found `status: gaps_found`, score 5/6. All five ROADMAP Success Criteria passed on live inspection, but a sixth, goal-derived truth failed: `Settings.jwt_secret` accepted the exact placeholder published in `.env.example` (`replace-me-with-a-generated-secret`, 34 characters, clearing the 32-character floor), and the running container's own `.env` held that value. I forged a JWT for another account offline with that string and `GET /api/v1/auth/me` returned that account's profile with 200 — full impersonation, reproduced live, not inferred from the reviewer's write-up. Four warnings (WR-01..04) from `05-REVIEW.md` were also open. Plan 05-17 was executed to close all five.

## Gap Closure Verification

### Truth #6 (the closed gap): "A caller who has only read the public repository cannot forge a token the API accepts"

✓ **VERIFIED — closed.** Checked at the code, the running container, and by repeating the exact exploit.

- **Code:** `src/taskmanager/infrastructure/config/settings.py` now has `@field_validator("jwt_secret") def _refuse_the_published_placeholder`, raising when `value.casefold().startswith("replace-me")`. `jwt_algorithm: Literal["HS256"]` closes WR-03's free-string set. Read directly, not taken from the summary.
- **Boot-time refusal, re-derived independently:**
  ```
  $ .venv/bin/python3 -c "Settings(_env_file='.env.example', database_url='postgresql+psycopg://x:x@localhost/x')"
  ```
  raises `ValidationError` — confirmed by re-running the equivalent check in this session (previously it booted successfully; now it does not).
- **Live exploit re-run against the rebuilt container:** registered a fresh throwaway account (`verify-phase5-reverify-<ts>@example.com`), took its id from the registration response, forged a token offline with `pyjwt` using the literal string `replace-me-with-a-generated-secret`, and called `GET /api/v1/auth/me` with it.
  - **Before (first verification pass): 200, another account's profile returned.**
  - **After (this pass): 401** `application/problem+json` `authentication_failed` — the exact forged token that worked before is now refused.
- **The running container's effective secret is not the placeholder,** confirmed without printing it: `docker compose ps` shows `api healthy`/`db healthy` (i.e., the container booted, which is only possible if its loaded `JWT_SECRET` is not the refused placeholder — the validator would have refused boot otherwise), and the forged-placeholder-token exploit above independently proves the live signing key differs from `replace-me-with-a-generated-secret`.

### Residual-honesty check (the follow-up question a careful evaluator would ask)

ADR-084 states plainly that the refusal is a **prefix rule** and does not protect an operator who types their own weak 32-character secret. I judged this an honest, correctly-scoped disclosure rather than a new gap, and went further to check whether any *other* value already published in the repository could end up signing tokens on the documented `make env && docker compose up` path:

- `tests/conftest.py:25` — `JWT_SECRET = "b" * 32`, set only via `monkeypatch.setenv` inside the pytest process. It is never written to a `.env` file and pytest does not touch `docker compose`'s environment. **Not reachable from the deployment path.**
- `.github/workflows/ci.yml:54` — `JWT_SECRET: ci-only-secret-not-a-real-credential`, injected as a GitHub Actions runner environment variable for the CI job only. It never reaches a committed file or an evaluator's `.env`. **Not reachable from the deployment path.**
- `docker-compose.yml` — read in full. The `api` service's `environment:` block overrides only `DATABASE_URL`; there is no `JWT_SECRET` default anywhere in the file, and `env_file: .env` has no fallback — Compose refuses to start `api` if `.env` is absent (the file's own comment states, and Compose's documented behavior for a required `env_file` confirms, this is an error, not a silent default).
- `Dockerfile` — grepped for `ENV`/`ARG`; no `JWT_SECRET` of any kind is set at image-build time.
- `scripts/init-env.sh` / `make env` — generates a fresh 64-hex-character secret via `openssl rand -hex 32` (or `/dev/urandom`) and never prints it.

**Conclusion: on the documented `make env && docker compose up` path, no value published anywhere in this repository can become the signing key.** I additionally exercised `init-env.sh` directly (see check 3 below) rather than relying on this reading alone.

### Check 3: `make env` behavior in an isolated temp directory (not the project's real `.env`)

Ran in `/private/tmp/.../scratchpad/envtest`, a scratch copy containing only `.env.example`:

1. **No `.env` present:** `sh scripts/init-env.sh` → `Created .env from .env.example with a generated JWT_SECRET.` Resulting `JWT_SECRET` line held a 64-character value, not the placeholder.
2. **Idempotency:** ran again with the generated `.env` present → `Kept the existing .env: its JWT_SECRET is already set.` — `diff` between the two `.env` files was empty.
3. **Never overwrites a real secret:** manually edited `.env` to `JWT_SECRET=my-own-real-secret-abcdefgh12345678`, ran the script again → `Kept the existing .env...`, `diff` empty — the manually-set secret survived untouched.

All three behaviors match the plan's acceptance criteria exactly. The project's real `.env` was never touched by this check.

### Check 4: The four gates, re-run independently in this session

| Gate | Command | Result |
|---|---|---|
| Lint | `make lint` | ✓ black/isort/flake8 clean, 181 files |
| Typecheck | `make typecheck` | ✓ "Success: no issues found in 181 source files" |
| Architecture | `make arch` | ✓ "Contracts: 4 kept, 0 broken" (115 files, 387 dependencies) |
| Tests | `make test` | ✓ **1019 passed**, coverage **100.00%**, "Required test coverage of 75% reached" |

Matches the orchestrator's reported numbers (1019 passed, 100.00% coverage, 4 contracts, mypy clean over 181 files) — independently reproduced, not trusted from the SUMMARY.

### Check 5: Regression — the five original Success Criteria, re-spot-checked live

Registered two new throwaway accounts and repeated the core flow end-to-end against the rebuilt container:

- **Register/login/me:** both registrations → 201 (no password hash in either body); login → 200 with `access_token`; `/auth/me` → 200 with the correct own profile.
- **Assignment + notification:** created a list and task as owner A, assigned to B → 200 with `assignee_id` set to B's id; `docker compose logs api | grep task_assigned_email` shows a fresh structured JSON line for this exact assignment with `to`/`subject`/`body`/`task_id`.
- **403 for the assignee on an owner-only write:** B (the assignee) attempting `PATCH` the task's title → **403** `authorization_failed`, "Only the list owner may change this task."

No regressions found. All five original ROADMAP Success Criteria (SC-1 through SC-5, with SC-1 in its amended form as previously ruled fair) remain independently verified live.

### The two review warnings closed by this plan, re-verified live

- **WR-01** (NUL byte in login username → 500): `POST /auth/login` with `username` containing `\x00` now answers **401**, body byte-identical to the unknown-address refusal (`diff` empty) — confirmed live, not merely by the plan's own test.
- **WR-04** (lone surrogate in `full_name` → 500): `POST /auth/register` with `full_name: "A\ud800B"` now answers **422** `application/problem+json`, `"detail":"full_name must be valid Unicode text."`, `errors: {"field":"full_name"}` — confirmed live with a hand-built UTF-8 JSON body carrying the raw surrogate.
- **WR-02** (Argon2 hash reachable via SQLAlchemy parameter dump): read `src/taskmanager/infrastructure/db/engine.py` — `create_async_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)`. Confirmed by code reading and by the passing `tests/unit/infrastructure/test_engine.py` (part of the 1019); not independently re-triggered live (would require forcing a non-`IntegrityError` DB failure, out of scope for a read-only re-verification against a shared container).
- **WR-03** (free-string `jwt_algorithm`): confirmed by code reading — `Literal["HS256"]` on the `Settings` field.

### Check 6: Every documented occurrence of `cp .env.example .env` stating a present fact

```
$ grep -rn "cp .env.example .env" Makefile docker-compose.yml .env.example src/ CLAUDE.md
(no output)
```
Independently re-run in this session — empty, confirming the plan's own acceptance criterion. Spot-read `Makefile`'s new `env:` target (`sh scripts/init-env.sh`), `docker-compose.yml`'s header and `api.env_file` comments (both now say `make env`), `.env.example`'s header and its `JWT_SECRET`/`JWT_ALGORITHM` key comments (both now state the placeholder is refused and name `make env`), and `CLAUDE.md` § Project Rules → Configuration (two new bullets naming `tests/unit/test_settings.py::test_the_shipped_placeholder_is_refused` and `tests/unit/test_settings.py::test_the_algorithm_is_a_closed_set` as the enforcing gates — both test names exist and were part of the 1019 passing tests). `DECISION_LOG.md` carries `ADR-084` in the house Context/Options/Decision/Consequences format, correctly narrating the exploit found in the first verification pass and the trade-off accepted (prefix rule only). `AI_WORKFLOW.md` carries one dated incident entry, in the existing voice, stating plainly that 998 tests and 100% coverage did not catch this because every test supplied its own secret — the tests measured the code, not the deployment. No self-congratulation, no emoji, matches the project's own house style.

## Goal Achievement (full re-statement)

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 (SC-1, amended) | Register/login/me + OpenAPI OAuth2 password-scheme contract | ✓ VERIFIED (regression, unchanged) | Live curl this session; `test_security_scheme.py` unaffected by 05-17. |
| 2 (SC-2) | 401 problem+json for missing/malformed/expired token; indistinguishable login failure | ✓ VERIFIED (regression + strengthened) | Live curl; NUL-username case now also folds into the same indistinguishable-401 bucket (WR-01 closed). |
| 3 (SC-3) | 404 invisible / 403 visible-but-forbidden | ✓ VERIFIED (regression, unchanged) | Live curl: assignee 403 on owner-only PATCH. |
| 4 (SC-4) | Assign/unassign, reject non-existent assignee, assignee exposed, `GET /users` discoverable | ✓ VERIFIED (regression, unchanged) | Live curl this session. |
| 5 (SC-5) | Post-commit notification via `EmailNotifier`, logging adapter, failure-resilient | ✓ VERIFIED (regression, unchanged) | Fresh live log line captured this session for a new assignment. |
| 6 (derived; the closed gap) | A caller who has only read the public repository cannot forge a token the API accepts | ✓ VERIFIED — now TRUE | Repeated the exact forgery that succeeded in the first pass; it is now refused (401). Boot-time refusal, `make env` generation/idempotency/non-destructiveness, and the absence of any other repo-published secret reaching the deployment path were all independently checked (see Checks above). |

**Score:** 6/6 truths verified

### Requirements Coverage

All twelve requirement IDs (AUTH-01..06, ASGN-01..03, NOTF-01..03) remain SATISFIED as established in the first verification pass; AUTH-04 in particular is now satisfied both in literal wording ("tokens are signed... with an env-provided secret") and in the deployment-level sense the first pass found lacking (the env-provided secret can no longer be the one the repository publishes). No count change: still 12/12, matching `.planning/REQUIREMENTS.md`'s 56/69 running total.

### Quality Gates

All four (`make lint`, `make typecheck`, `make arch`, `make test`) re-run independently in this session and green — see Check 4 above.

### Human Verification Required

None.

### What was run versus read in this re-verification

**Ran (live, against the running `test-api-1`/`test-db-1` containers or in an isolated temp directory):**
- The full forged-placeholder-token exploit chain (register → discover id → forge with old secret → `GET /auth/me`) — now 401.
- `Settings(_env_file='.env.example', ...)` boot check — now raises.
- `scripts/init-env.sh` three-scenario check in a scratch temp directory (no `.env`, idempotent re-run, real-secret preservation) — did not touch the project's real `.env`.
- `make lint`, `make typecheck`, `make arch`, `make test`.
- Live regression spot-check of all five original SCs (register/login/me, assignment + notification log, 403 for assignee).
- Live re-check of WR-01 (NUL login → 401, byte-identical to unknown-address) and WR-04 (surrogate `full_name` → 422).
- `grep` checks for residual `cp .env.example .env` occurrences and for any other repo-published `JWT_SECRET` reachable via the documented deployment path.
- `docker compose ps` / `curl /health` to confirm the rebuilt stack is healthy.

**Read only (not re-executed):** `05-17-PLAN.md`, `05-17-SUMMARY.md`, the full diffs of `settings.py`, `validation.py`, `login.py`, `register.py`, `engine.py`, `scripts/init-env.sh`, `Makefile`, `docker-compose.yml`, `.env.example`, `DECISION_LOG.md` (ADR-084), `AI_WORKFLOW.md`, `CLAUDE.md`; `git log` for the five commits. WR-02's log-hiding fix was confirmed by reading `engine.py` and by the passing `test_engine.py` in the full suite run, not by independently forcing a live DBAPIError against the shared container (would require inducing a non-`IntegrityError` write failure, which risks the shared database state and was judged out of proportion for a read-only re-verification).

### Test data left behind in the running database

- `verify-phase5-reverify-<ts>@example.com` ("Reverify User") — one account, used only for the forged-token exploit re-check (never logged in normally).
- `reverify5-a-<ts>@example.com` ("Reverify A") and `reverify5-b-<ts>@example.com` ("Reverify B") — two accounts, one task list ("Reverify list") owned by A containing one task ("Reverify task") assigned to B.
- `surrogate-test-99@example.com` — registration attempt that correctly failed with 422 (no row created).
- (Unchanged from the first verification pass, still present: `verify-phase5-<ts>-a@example.com` / `-b@example.com` and their list/task.)

None of these were cleaned up, per the environment constraints against destructive operations.

## Gaps Summary

None remaining. The single BLOCKER from the first verification pass (forgeable JWT via the published placeholder secret) is closed and independently re-exploited-and-confirmed-refused. All four review warnings addressed by plan 05-17 (WR-01, WR-02, WR-03, WR-04) are closed; WR-02 and WR-03 confirmed by code reading plus the passing suite, WR-01 and WR-04 confirmed live. IN-01..IN-04 remain open by explicit, documented decision (out of scope for this plan) and were not raised as gaps in the first verification pass either — they do not touch a phase Success Criterion or requirement ID.

---

_Verified: 2026-09-19T19:52:00Z_
_Verifier: Claude (gsd-verifier)_
