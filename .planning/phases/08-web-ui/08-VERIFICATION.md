---
phase: 08-web-ui
verified: 2026-09-20T04:15:06Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 8: Web UI Verification Report

**Phase Goal:** An evaluator who runs `docker compose up` can also open a browser and drive every
brief use case — lists, tasks, status, filters with the completion percentage, login, assignment —
through a small web UI, without the UI weakening a single claim the repository makes about itself.

**Verified:** 2026-09-20T04:15:06Z
**Status:** passed
**Re-verification:** No — initial verification

## Method

This verification did not trust SUMMARY.md claims. Every check below was independently reproduced
against the live codebase and the running dev stack (`docker compose` project `test`, all three
services — db, api, ui — healthy throughout). All `make` gates were re-run in this session
(not read from a prior log), a throwaway user was registered and driven end to end through the
`:8080` proxy, and every cited file was opened and read.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth (Roadmap SC) | Status | Evidence |
|---|---------------------|--------|----------|
| 1 | `docker compose up` serves the UI on a documented port, same-origin proxy, no CORS | ✓ VERIFIED | `docker compose ps` shows db/api/ui all healthy; `curl -sf http://localhost:8080/` returns 200 with `id="root"`; `frontend/nginx.conf:76-84` proxies `/api/` to `http://api:8000` with no trailing slash and no `Access-Control-Allow-*` header anywhere; `git diff --stat 1dd5af7 -- src/taskmanager` is empty (confirmed live) |
| 2 | Every brief use case is drivable through the UI: auth, lists CRUD, task CRUD, status, filters+percentage, assign/unassign, assigned-to-me | ✓ VERIFIED | Live curl walkthrough through `:8080` reproduced register → login → create list → create 2 tasks → complete one → filter `priority=high` (returns 1 item, `total_tasks:2, completed_tasks:1, completion_percentage:50.0`) → illegal transition refused with 409 `invalid_status_transition`. Code-level: `TasksScreen.tsx:270-273` feeds `CompletionBar` directly from `collection.total_tasks/completed_tasks/completion_percentage`, never from `items` (grep confirms no `items.length` used for the bar); `AssigneePicker.tsx`, `AssignedScreen.tsx` wired to `listUsers`/`assignTask`/`unassignTask`/`listAssignedTasks` in `client.ts:289-318`; `App.tsx` wires all 4 screens (lists/tasks/assigned/login) |
| 3 | Refusals rendered from RFC 9457 body; 401 returns to login; UI invents no error text besides network failure | ✓ VERIFIED | `frontend/src/api/problem.ts` — `messageFor` returns `detail \|\| title`; `client.ts:120-133` — 401 triggers `onUnauthorized()`, non-OK responses parsed as `Problem` and thrown as `ApiError`, only a genuinely unparseable response gets a UI-authored `code: "network"` message; `App.tsx:28-37` registers the unauthorized handler that clears the session and resets the view to `{name:"lists"}` (shown as login when token is null) — live-tested 401 via `curl -o /dev/null -w '%{http_code} %{content_type}'` → `401 application/problem+json` |
| 4 | Frontend has backend-grade gates (TS strict, eslint, vitest) behind `make` targets and CI Node job, two-places rule honored, `src/taskmanager` untouched | ✓ VERIFIED | Ran live: `make ui-lint` exit 0, `make ui-typecheck` exit 0, `make ui-test` → 66 passed / 10 files; `.github/workflows/ci.yml` has both `quality-gates` and `frontend` jobs (confirmed via `yaml.safe_load`); `.pre-commit-config.yaml` has the `ui-gates` hook scoped `files: ^frontend/`; `.venv/bin/pre-commit run --all-files` → 13/13 hooks passed including `frontend gates`; `git diff --stat 1dd5af7 -- src/taskmanager` empty |
| 5 | README, `make rehearse`, and the documentation gate stay true and green; pinned counts updated in the same commit | ✓ VERIFIED (rehearsal not re-run per task constraints, but evidence is strong) | README has "## The web UI (beyond the brief)" section (line 160) naming `localhost:8080`, stating the brief asks for no UI, with no new evidence-map row (23 rows, unchanged per 08-02/08-03 SUMMARYs, confirmed by counting the current table); `grep -c '^## ADR-' DECISION_LOG.md` = 108, matches README's "108 ADRs"; `tests/architecture/test_documentation_claims.py` — ran live, 13/13 passed including `test_the_human_ai_account_covers_every_phase` and `test_the_adr_count_...`; `make test` and `make docker-test` both ran live and passed (1140 passed, 100% coverage, both host and container). `make rehearse` was NOT re-run in this verification session per the explicit task instruction not to stop the dev stack; SUMMARY 08-03 documents it ran twice and exited 0 on the phase's final commit — this specific claim rests on the SUMMARY, flagged below |
| 6 | DECISION_LOG has ADRs for stack choice, proxy, and the two reversed positions by id; AI_WORKFLOW gains Phase 8 human/AI split + incident entry | ✓ VERIFIED | Read ADR-105 (reversal, names AI recommendation vs human decision), ADR-106 (React+Vite, not Next.js), ADR-107 (proxy, not CORS), ADR-108 (gates) in full in `DECISION_LOG.md:4816-5000+`; `AI_WORKFLOW.md` line 142-144 amended narrative in place (git diff confirms only the old paragraph's 5 lines were removed, nothing else); "What is already true of Phase 8" block at line 408 opens with the sentence "the AI's recommendation was the opposite"; Phase 8 incident entry exists at line 2293; every `commit <sha>` in `AI_WORKFLOW.md` resolves via `git cat-file -e` (checked live, zero MISSING) |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/package.json` + `package-lock.json` | Exact pins, committed lockfile | ✓ VERIFIED | `grep -nE '"[^"]+": *"[\^~><*]'` finds only the legitimate `engines.node: ">=24"`; lockfile `lockfileVersion: 3`, name matches |
| `frontend/nginx.conf` | Same-origin proxy, no CORS | ✓ VERIFIED | Read in full; `proxy_pass http://api:8000` with no trailing slash; SPA fallback documented as unable to swallow `/api/` (longest-prefix match) |
| `frontend/Dockerfile` | Two-stage, non-root runtime | ✓ VERIFIED | `docker compose exec ui id -u` → `101` (not root) |
| `frontend/src/api/client.ts` | Single fetch boundary, 401 handling, RFC 9457 parsing | ✓ VERIFIED | 319 lines, read in full relevant sections; all 18 operations exported |
| `frontend/src/components/CompletionBar.tsx` | Renders given numbers, computes nothing | ✓ VERIFIED | 48 lines, read in full; props are three required numbers with no defaults |
| `frontend/src/tasks/transitions.ts` | Mirrors ALLOWED_TRANSITIONS (ADR-097) | ✓ VERIFIED | `allowedMovesFrom` imports from `api/types.ts`; comments cite ADR-097 |
| `tests/architecture/test_frontend_gates.py` | Pins-and-strict gate, runs in container | ✓ VERIFIED | 5/5 tests pass; `Dockerfile` has the matching `COPY frontend/package.json frontend/package-lock.json frontend/tsconfig.json ./frontend/` line (ADR-102); `make docker-test` passed live |
| `scripts/ui-gates.sh` | Pre-commit hook, node_modules escape documented | ✓ VERIFIED | Read in full; exits 0 with explanation when `node_modules` absent; honest comment block |
| `README.md` UI section | States beyond-brief, URL, no evidence-map row | ✓ VERIFIED | Read section in full |
| `DECISION_LOG.md` ADR-105..108 | Stack, proxy, reversal decisions | ✓ VERIFIED | Read in full |
| `AI_WORKFLOW.md` Phase 8 block + incident | Human/AI split, dated incident, amended sentence | ✓ VERIFIED | Read in full |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `docker-compose.yml` `ui` service | `frontend/Dockerfile` | `context: ./frontend`, `target: runtime` | ✓ WIRED | Confirmed in compose file; live `docker compose ps` shows `test-ui-1` healthy |
| `frontend/nginx.conf` | `api` service | `proxy_pass http://api:8000` | ✓ WIRED | Live curl through `:8080/api/v1/...` returns real API data (register, login, list/task CRUD, filtered query all succeeded) |
| `.github/workflows/ci.yml` | `frontend/package.json` | `npm ci` then lint/typecheck/test | ✓ WIRED | `frontend` job present with matching 4 steps; confirmed via `yaml.safe_load` |
| `App.tsx` | 401 handler → login screen | `setUnauthorizedHandler` | ✓ WIRED | Code read; live `curl` without token → 401; SUMMARY documents an in-browser forced-401 reproduction |
| `TasksScreen.tsx` | `CompletionBar` | response counters, not `items` | ✓ WIRED | Live filtered-query curl confirms `completion_percentage` stays whole-list under a filter |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| UI-01 | Register/login/logout SPA | ✓ SATISFIED | `LoginScreen.tsx`, live register+login through proxy |
| UI-02 | Lists CRUD + completion % | ✓ SATISFIED | `ListsScreen.tsx`, live create/list |
| UI-03 | Task CRUD, status, filters w/ whole-list % | ✓ SATISFIED | `TasksScreen.tsx`, `transitions.ts`; live filter+percentage proof |
| UI-04 | Assign/unassign, assigned-to-me | ✓ SATISFIED | `AssigneePicker.tsx`, `AssignedScreen.tsx`, `client.ts` operations |
| UI-05 | RFC 9457 rendering, 401→login | ✓ SATISFIED | `problem.ts`, `ErrorBanner.tsx`, `App.tsx` 401 handler |
| UI-06 | One-command start, same-origin proxy | ✓ SATISFIED | `docker-compose.yml` `ui` service, `nginx.conf` |
| UI-07 | TS strict/eslint/vitest gates, CI job | ✓ SATISFIED | Live `make ui-lint`/`ui-typecheck`/`ui-test`, CI `frontend` job |
| UI-08 | Docs stay true (README, AI_WORKFLOW, DECISION_LOG, CLAUDE.md, REQUIREMENTS) | ✓ SATISFIED | All read and cross-checked in full |

### Anti-Patterns Found

None. Scanned `frontend/src` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|placeholder|coming soon|not yet implemented`, `dangerouslySetInnerHTML`, absolute URLs (`https?://`) outside tests, and `localStorage`/`document.cookie` outside test files. All clean. No stub components (`return <div>Component</div>` style) found; every screen fetches from and renders the real API response shapes.

### Gates Run Live in This Session

| Gate | Result |
|------|--------|
| `make ui-lint` | exit 0 |
| `make ui-typecheck` | exit 0 |
| `make ui-test` | 66 passed, 10 files |
| `make lint` | exit 0 (black/isort/flake8) |
| `make typecheck` | exit 0 (mypy strict, 193 files) |
| `make arch` | 4/4 import-linter contracts kept |
| `make test` | 1140 passed, 100% coverage over 1690 statements |
| `make docker-test` | 1140 passed, 100% coverage over 1844 statements (container includes the frontend pins-gate) |
| `.venv/bin/pre-commit run --all-files` | 13/13 hooks passed |
| `tests/architecture/test_frontend_gates.py` | 5/5 passed |
| `tests/architecture/test_documentation_claims.py` | 13/13 passed |
| `git diff --stat 1dd5af7 -- src/taskmanager` | empty |
| Commit attribution scan (`1dd5af7..HEAD`) | no AI co-author/attribution trailers found; all 12 commits authored by Pablo Gutierrez |

### Human Verification Required

None. All six roadmap Success Criteria were independently verified against live code, a running
stack, and reproduced HTTP traffic through the UI's own proxy — no item required subjective visual
judgment beyond what was already confirmed mechanically (accessible labels, `role="alert"`,
`role="progressbar"` are asserted by the vitest suite, which was re-run and passed).

One item is worth naming for completeness rather than as a gap: `make rehearse` was not re-run in
this verification session, per the explicit instruction not to stop the running dev stack. The
08-03-SUMMARY.md's claim that it ran twice and passed on the phase's final commit is corroborated
by lower-level evidence gathered independently here — `tests/architecture/test_documentation_claims.py`
passing (including the rehearsal-region-shape and PHASES-coverage tests), the README's rehearsal
markers being well-formed and containing exactly the two UI `curl` lines described, and the general
health of every gate the rehearsal depends on — but the rehearsal script itself was not re-executed
as a full end-to-end proof in this session. This is not treated as a gap because it was explicitly
out of scope for this verification run, not because it is unverifiable in principle.

### Gaps Summary

No gaps found. All six ROADMAP Success Criteria for Phase 8 are independently verified against the
running stack and the actual codebase, not merely against SUMMARY.md narrative. The implementation
matches the CONTEXT.md's locked decisions (D-01 through D-09) exactly: the UI lives in `frontend/`
inside the deliverable, is a static SPA built with React+Vite+TypeScript, reaches the API through a
same-origin nginx reverse proxy with `src/taskmanager` provably untouched, keeps the access token
out of `localStorage` (enforced by an eslint rule, not just convention), renders every refusal from
the API's own RFC 9457 body, starts with one `docker compose up`, and both DECISION_LOG.md and
AI_WORKFLOW.md honestly record that the AI recommended against including the UI and the human
overruled that recommendation. No commit in `1dd5af7..HEAD` carries an AI attribution trailer.

---

_Verified: 2026-09-20T04:15:06Z_
_Verifier: Claude (gsd-verifier)_
