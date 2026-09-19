---
phase: 05-auth-assignment-notifications
verified: 2026-09-19T19:05:00Z
status: gaps_found
score: 5/6 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The API knows who is calling (phase goal statement) — a caller cannot be impersonated by anyone who has only read the published repository"
    status: failed
    reason: >
      `Settings.jwt_secret` only enforces `min_length=32` (src/taskmanager/infrastructure/config/settings.py:51).
      `.env.example:45` ships `JWT_SECRET=replace-me-with-a-generated-secret` (34 chars), which is
      the exact secret currently loaded by the running compose stack's own `.env` (confirmed:
      `.env:42` on disk is the unchanged placeholder). Any caller who reads the public repository
      can therefore mint a JWT for any user id — and `GET /api/v1/users` (ASGN-03, a Phase-5
      endpoint) makes every id discoverable without a credential. This was independently
      reproduced against the live container in this verification: a token was forged offline with
      PyJWT and the placeholder secret for an account ("Verify B") whose password was never
      supplied, and `GET /api/v1/auth/me` returned that account's profile with 200. The
      `settings.py` module docstring explicitly promises the opposite ("rather than starting up on
      a placeholder secret"); the code does not keep that promise. This is not a hypothetical
      production concern — it is true of the exact `cp .env.example .env && docker compose up`
      path the project's own README/CLAUDE.md documents as the one-command reviewer path, and of
      the container running right now.
    artifacts:
      - path: "src/taskmanager/infrastructure/config/settings.py"
        issue: "jwt_secret validator checks only length, not the known placeholder value; docstring claims a guarantee the code doesn't provide"
      - path: ".env.example"
        issue: "ships a 34-character placeholder that clears the 32-character floor, making the documented setup path insecure by default"
    missing:
      - "Reject the specific `.env.example` placeholder (or any value with recognizable placeholder prefixes) in a jwt_secret validator, per the reviewer's proposed fix in 05-REVIEW.md CR-01"
      - "Or: generate a real per-deployment secret in the entrypoint/Makefile when absent, and document that trade-off in an ADR"
      - "Either way, correct the settings.py docstring so it does not assert a guarantee that is not enforced"
---

# Phase 5: Auth, Assignment & Notifications Verification Report

**Phase Goal:** The API knows who is calling, enforces what they may do, and delivers all three bonus use cases from the brief.
**Verified:** 2026-09-19T19:05:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (roadmap Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 (SC-1, amended) | Register (dup email → 409, hash never returned), login via OAuth2 password flow → expiring JWT, `/auth/me` returns own profile; OpenAPI document declares the OAuth2 password scheme with `tokenUrl` resolving to the login route, every op secured or one of 3 named-open ones | ✓ VERIFIED | Live `curl`: register 201 (no hash field), duplicate (case-different) → 409 `email_already_registered`, login → 200 with `access_token`/`expires_in`, `/auth/me` → 200 with own profile. `tests/unit/presentation/test_security_scheme.py` (5 tests) passed; falsification evidence in `evidence/05-11-open-route-falsification.txt` shows a planted unsecured route is caught by name. |
| 2 (SC-2) | Every task-list/task endpoint rejects missing/malformed/expired token with 401 problem+json; wrong password indistinguishable from unknown email | ✓ VERIFIED | Live `curl`: no-auth and garbage-token `/auth/me` both → 401 `application/problem+json` `authentication_failed`. Wrong-password vs unknown-email login bodies are byte-identical (`diff` empty). `tests/integration/api/test_auth.py`, `test_permission_matrix.py` (anonymous legs) passed (201 tests total run). |
| 3 (SC-3) | Invisible resources → 404 on every verb; visible-but-forbidden → 403; assignee can read/change status, cannot edit/delete | ✓ VERIFIED | Live: assignee (B) reading the owner's list → 404; reading/status-changing the assigned task → 200; editing title → 403 "Only the list owner may change this task"; deleting → 403 same body. `tests/unit/application/test_access.py` (22 tests) and `test_permission_matrix.py` (79 tests covering the full matrix) passed. |
| 4 (SC-4) | Owner assigns/unassigns to existing user; non-existent assignee rejected; task response exposes assignee; `GET /users` makes ids discoverable | ✓ VERIFIED | Live: assign to bogus UUID → 404 `user_not_found`; assign to real user → 200 with `assignee_id` set; unassign → 200 with `assignee_id: null`; `GET /api/v1/users` returns `[id, full_name, email]` only (no hash). |
| 5 (SC-5) | Assignment sends invitation through `EmailNotifier` port after commit; runtime adapter only logs; in-memory adapter is mock-free for tests; notifier failure doesn't fail the assignment | ✓ VERIFIED | Live: `docker compose logs api \| grep task_assigned_email` shows a structured JSON line with `to`/`subject`/`body`/`task_id` for the assignment made during this verification. `tests/unit/application/test_assign_task.py -k notifier_failure` and `tests/integration/api/test_assignment.py -k notifier_failure` (both passed) assert the write survives a raising notifier. `tests/unit/infrastructure/test_notifier.py` (7 tests, including "imports no mail library") passed. |
| 6 (derived from phase goal — "the API knows who is calling") | A caller who has only read the public repository cannot mint a valid identity token for an arbitrary user | ✗ FAILED | See gap above. Independently forged a JWT offline using the exact secret shipped in `.env.example` and currently loaded by the running container's `.env`, for an account whose credentials were never used, and `GET /api/v1/auth/me` accepted it (200, correct profile). |

**Score:** 5/6 truths verified

### Required Artifacts (representative sample, not exhaustive across all 47 reviewed files)

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/taskmanager/presentation/api/routers/auth.py` | register/login/me routes, no `HTTPException` | ✓ VERIFIED | Routes exist and work live; `tests/architecture/test_routers_raise_no_http_exception.py` passes (part of the 13 architecture tests re-run). |
| `src/taskmanager/application/use_cases/access.py` | `owned_task`, 404-before-403 ordering | ✓ VERIFIED | Live matrix behavior matches; `test_access.py` (22 tests) green. |
| `src/taskmanager/infrastructure/notifications/logging.py` | Structured log, no real send | ✓ VERIFIED | Live log line captured with all four fields; module imports no mail library (`test_notifier.py`). |
| `src/taskmanager/infrastructure/security/tokens.py` | PyJWT HS256, algorithm pinned, required claims | ✓ VERIFIED (mechanism) / ⚠️ but signing key is compromised by config, see gap | `test_tokens.py` (13 tests) green; decode policy correct. The mechanism is sound — the deployed key is not. |
| `src/taskmanager/infrastructure/config/settings.py` | Secret validated at boot, "fails rather than starts on a placeholder" per its own docstring | ✗ GAP | Boots successfully with the literal `.env.example` placeholder; docstring promise not enforced. Reproduced independently (see gap). |
| `migrations/versions/0002_full_name_and_assignee_index.py` | `full_name`, `ix_tasks_assignee_id` | ✓ VERIFIED | `make test` ran against real Postgres at head; assignment/user endpoints work live, which requires this migration to be applied (confirmed by `docker compose logs api` showing `0001 -> 0002` in the cold-start evidence, consistent with current live behavior). |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `routers/assignments.py` | `AssignTask` use case | direct call, DI via `Depends` | ✓ WIRED | Live PUT/DELETE assignee round-trips correctly. |
| `AssignTask` (post-commit) | `EmailNotifier` port | called after `async with` unit-of-work block | ✓ WIRED | Live log line only appears after the 200 response with the persisted `assignee_id`; matches reviewer's `[verified]` trace of the commit boundary. |
| `presentation/api/actor.py` | `JwtTokenService.decode` | `Depends(get_current_actor)` | ✓ WIRED, but the decode key itself is compromised in the documented deployment (see gap) | Confirmed by both legitimate flows (own token works) and the forged-token exploit (an invalid trust boundary also "works"). |
| `app.openapi()` | OAuth2 password scheme | `SecurityResources` / actor seam | ✓ WIRED | `test_security_scheme.py`, all 5 tests green; falsification evidence on file. |

### Requirements Coverage

All twelve requirement IDs were independently re-run (not trusted from the 05-16 tick table) as part of a single 201-test batch covering the named test files/filters from `05-16-PLAN.md`'s re-verification table, plus live `curl` checks against the running container.

| Requirement | Description (abridged) | Status | Evidence |
|---|---|---|---|
| AUTH-01 | Register, dup → 409, hash never returned | ✓ SATISFIED | Live curl + `test_auth.py -k register/duplicate` |
| AUTH-02 | Login via OAuth2 password flow, expiring JWT; Swagger Authorize contract | ✓ SATISFIED (per amended SC-1, see ruling below) | Live curl + `test_auth.py -k login` + `test_security_scheme.py` |
| AUTH-03 | All task-list/task endpoints require valid token, 401 problem+json | ✓ SATISFIED | Live curl + `test_auth.py -k unauthenticated` + permission matrix (anonymous rows) |
| AUTH-04 | Argon2 hashing off event loop; PyJWT signed with env-provided secret; login failure doesn't reveal which field was wrong | ✓ SATISFIED **as literally worded** — but see the goal-level gap: "env-provided secret" is satisfied mechanically while the provided value is a known public placeholder in the documented deployment. The literal requirement text does not demand secret strength/entropy checking beyond what already exists, so it is not itself BLOCKED, but the goal it serves is undermined (see truth #6). | `test_tokens.py`, `test_passwords.py`, live indistinguishable-login diff |
| AUTH-05 | `/auth/me` returns own profile | ✓ SATISFIED | Live curl |
| AUTH-06 | Invisible → 404, visible-but-forbidden → 403 | ✓ SATISFIED | Live curl (assignee flows) + `test_permission_matrix.py` (79 tests) + `test_access.py` |
| ASGN-01 | Assign/unassign, non-existent assignee rejected | ✓ SATISFIED | Live curl + `test_assignment.py -k assign`, `test_unassign_task.py` |
| ASGN-02 | Assignee exposed on task; assignee can view/change status, not edit/delete | ✓ SATISFIED | Live curl + `test_assignment.py`, `test_permission_matrix.py -k assignee` |
| ASGN-03 | `GET /users` exposes discoverable ids | ✓ SATISFIED | Live curl (`id, full_name, email` only) + `test_users.py` |
| NOTF-01 | Assignment sends invitation via `EmailNotifier` after commit | ✓ SATISFIED | Live log capture + `test_assign_task.py -k notifies`, `test_assignment.py -k notifies` |
| NOTF-02 | Runtime adapter logs only, in-memory adapter mock-free | ✓ SATISFIED | Live log line structure + `test_notifier.py` |
| NOTF-03 | Notifier failure doesn't fail assignment | ✓ SATISFIED | `test_assign_task.py -k notifier_failure`, `test_assignment.py -k notifier_failure` (both re-run, both pass) |

No orphaned requirements found — REQUIREMENTS.md's Phase 5 rows match exactly the twelve IDs declared in the phase plans.

### Anti-Patterns / Additional Findings (from 05-REVIEW.md, independently confirmed where noted)

| Finding | Severity | Confirmed independently? | Blocks a must-have? |
|---|---|---|---|
| CR-01: placeholder JWT secret accepted at boot | Critical (reviewer) → **BLOCKER (this verification)** | Yes — reproduced live forgery against the running container using its actual `.env` | Yes — see truth #6 gap |
| WR-01: NUL byte in login username → unauthenticated 500, value echoed to log | Warning | Read only, not re-executed | No — does not defeat SC-2's literal wording (wrong-password vs unknown-email indistinguishability), but is a real robustness/log-hygiene defect |
| WR-02: Argon2 hash reachable via SQLAlchemy parameter dump on non-IntegrityError DB failures | Warning | Read only | No — narrow trigger (reviewer found no on-demand path); genuine defect, not a phase-goal blocker |
| WR-03: `jwt_algorithm` is an unvalidated free string | Warning | Read only | No — default value (`HS256`) is correct and is what's deployed; a self-inflicted misconfiguration isn't a phase-goal failure the way CR-01 is (CR-01 fires on the *documented, default* path) |
| WR-04: lone surrogate in `full_name` → unauthenticated 500 | Warning | Read only | No — availability/robustness defect, not an authorization/authentication failure |
| IN-01..IN-04 | Info | Read only | No |

No `TBD`/`FIXME`/`XXX` markers found in the Phase 5 files scanned (auth use cases, assign/list_assigned use cases, security infra, notifications infra, routers). No `TODO`/`HACK`/`PLACEHOLDER` string literals found in `src/taskmanager`.

### Quality Gates (re-run, not trusted from SUMMARY)

| Gate | Command | Result |
|---|---|---|
| Lint | `make lint` | ✓ black/isort/flake8 clean |
| Typecheck | `make typecheck` | ✓ mypy: "Success: no issues found in 180 source files" |
| Architecture | `make arch` | ✓ "Contracts: 4 kept, 0 broken" |
| Tests | `make test` | ✓ 998 passed, coverage 100.00%, "Required test coverage of 75% reached" |
| Targeted Phase 5 tests | 11 files covering AUTH/ASGN/NOTF | ✓ 201 passed |
| Architecture unit tests | `tests/architecture` | ✓ 13 passed |

### Human Verification Required

None. Every must-have and every requirement ID was verifiable programmatically or by direct live HTTP interaction with the running container, including the one item that failed (CR-01), which was fully reproduced rather than left as a theoretical concern.

### Ruling: SC-1 Amendment

**Fair restatement, not a weakening.** The original wording ("use Swagger's 'Authorize' button successfully") described an action nobody in this project ever performed: no human clicked through the browser flow, and no automated test drives a browser. Keeping the original wording would have meant the phase's own closing plan (05-16) could never honestly tick it — the criterion as written was unfalsifiable by anything in this project's toolchain. The replacement names exactly the mechanism the button depends on (a declared OAuth2 password scheme, a `tokenUrl` that resolves to a route that exists and accepts a form, and a security partition covering every operation), asserts it against the actual served `app.openapi()` document (not a hand-maintained list), and — the strongest point in its favor — was falsified on purpose: a throwaway unsecured route was added and the test caught it by name (`evidence/05-11-open-route-falsification.txt`). Separately, the underlying end-to-end token path (register → login → bearer-authenticated request) was exercised for real with `curl` against a cold-started container (`evidence/05-15-cold-start.txt`), which I re-derived live myself in this verification. The amendment narrows the *wording* to what is provable, but it does not narrow the *coverage* — if anything the OpenAPI-partition test is a stronger, regression-proof guarantee than a one-time manual click would have been. Verdict: legitimate amendment, following the cited Phase 2/3/4 precedent.

### Ruling: CR-01 and the Warnings

**CR-01 is a genuine phase-goal gap, not a footnote, and I am overriding the reviewer's implicit framing (a fixable code-quality "Critical" finding to close later) upward to a verification BLOCKER.** My reasoning:

1. The phase goal is literally "The API knows who is calling." A caller who can forge a valid, indefinitely-repeatable token for any user — using only a value published in the same public repository and currently loaded, unmodified, in this evaluation's own running `.env` — means the API does *not*, in the deployed configuration, reliably know who is calling. This is not adjacent to the goal; it is the goal's negation.
2. It is not a theoretical or out-of-scope production hardening concern deferred to a later phase. It fires on the exact `cp .env.example .env && docker compose up` path this project's own CLAUDE.md names as its one-command reviewer path, and I confirmed the currently-running container's `.env` still has the unmodified placeholder.
3. I did not stop at reproducing the mechanical half (Settings boots on the placeholder) — I went further than both the orchestrator and the reviewer's own evidence and completed the actual attack chain end-to-end against the live system: registered two throwaway accounts, discovered one's id via the Phase-5 `GET /users` endpoint, forged a token offline with `jwt.encode` and the shipped secret, and received that account's private profile from `GET /auth/me` with 200 — without ever supplying its password. That is full impersonation, demonstrated, not inferred.
4. It contradicts the project's own code: `settings.py`'s docstring promises a process "must fail at boot... rather than starting up on a placeholder secret," and threat T-5-02 / ADR-026 (D-26) frames the 32-character floor as *the* mitigation for weak-secret spoofing — but the floor was sized to a length threshold and never checked against the one placeholder value the project itself publishes, so the stated mitigation does not cover the threat it names.

None of the twelve requirement IDs' literal wording individually demands secret-strength/placeholder-rejection (AUTH-04 only requires "an env-provided secret," which is technically true), so I have left all twelve requirement rows ticked SATISFIED on their literal text — but literal-requirement-text satisfaction is exactly the "task completion" half of this workflow's stated distinction from "goal achievement." I'm holding the phase to the latter, per this workflow's explicit mandate, and recording the gap against the phase goal statement (added as derived truth #6) rather than silently degrading it to a warning that a subsequent phase might never see, since Phase 6 (test hardening) and Phase 7 (documentation/delivery) as scoped in ROADMAP.md do not mention configuration/secret-validation work, so this gap is not deferred to a documented later phase (Step 9b check: no match found in Phase 6 or Phase 7 goals/success criteria).

The four **Warnings** (WR-01..04) are real, independently-plausible defects (I read but did not re-execute them, given the "no source/test modification" and time constraints of this verification), but each is a robustness/log-hygiene issue orthogonal to the five literal Success Criteria and to the phase goal's authentication/authorization claim specifically — none of them lets a caller act as someone else or bypass an ownership check. I classify them as WARNING, matching the reviewer, and do not treat them as blockers.

**Suggested override, if the team disagrees with treating CR-01 as a blocker:**
```yaml
overrides:
  - must_have: "The API knows who is calling (phase goal statement)"
    reason: "CR-01 accepted as a known, documented residual risk to be fixed in a follow-up commit before delivery; not treated as blocking phase closure."
    accepted_by: "<name>"
    accepted_at: "<ISO timestamp>"
```
I did not apply this override myself — no such acceptance exists in the codebase or in any VERIFICATION.md at the time of this run.

### Gaps Summary

One gap: the JWT signing secret accepted at boot includes the exact placeholder value the project publishes in `.env.example` and currently runs with in this evaluation's own container, enabling unauthenticated impersonation of any user via a token forged entirely offline. This is fixable with the one-field validator the reviewer already drafted (CR-01's `_refuse_the_published_placeholder`) plus a docstring correction. Everything else examined — registration, login, `/auth/me`, the 401/403/404 matrix, assignment/unassignment, the user directory, and the post-commit notification with failure resilience — was independently reproduced against the live, running system and is sound.

---

_Verified: 2026-09-19T19:05:00Z_
_Verifier: Claude (gsd-verifier)_

**Test data left behind in the running database (not cleaned up, per environment constraints on destructive operations):**
- `verify-phase5-<ts>-a@example.com` ("Verify A") and `verify-phase5-<ts>-b@example.com` ("Verify B") — two registered users (timestamp embedded in the address, created 2026-09-19 ~18:52 UTC)
- One task list "Verify list" owned by Verify A, containing one task "Verify task" (currently unassigned after an assign/unassign cycle exercised during verification, status `in_progress`)
