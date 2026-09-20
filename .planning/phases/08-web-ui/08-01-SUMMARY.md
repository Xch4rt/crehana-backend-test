---
phase: 08-web-ui
plan: 01
subsystem: frontend
tags: [react, vite, typescript, vitest, eslint, nginx, docker, ci, adr]
requires:
  - the running API (Phases 3-5), unmodified
  - docker compose (Phase 3)
  - the RFC 9457 error contract (Phase 2)
provides:
  - a pinned, gated `frontend/` npm package
  - the single fetch boundary every later screen uses (all 18 API operations)
  - the `ui` compose service and its same-origin reverse proxy
  - five `make ui-*` targets, a CI `frontend` job, a pre-commit hook, a pins gate
affects:
  - Makefile, docker-compose.yml, Dockerfile, .pre-commit-config.yaml, ci.yml
  - README.md (ADR count, target table), DECISION_LOG.md (ADR-105..108)
  - scripts/clean-clone-rehearsal.sh (the UI half of the identity check)
tech-stack:
  added: [react 19.3.0, react-dom 19.3.0, vite 8.3.0, typescript 6.0.3, vitest 5.0.1, eslint 10.11.0, typescript-eslint 8.70.0, "@vitejs/plugin-react 6.1.1", jsdom 30.1.0, "@testing-library/react 16.3.3", "node:24-alpine", "nginx:1.30-alpine"]
  patterns: [static SPA behind nginx, same-origin reverse proxy, one fetch boundary, RFC 9457 rendered verbatim, exact pins + committed lockfile]
key-files:
  created:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/tsconfig.json
    - frontend/vite.config.ts
    - frontend/eslint.config.js
    - frontend/index.html
    - frontend/Dockerfile
    - frontend/nginx.conf
    - frontend/.dockerignore
    - frontend/src/main.tsx
    - frontend/src/App.tsx
    - frontend/src/App.test.tsx
    - frontend/src/styles.css
    - frontend/src/setupTests.ts
    - frontend/src/api/types.ts
    - frontend/src/api/problem.ts
    - frontend/src/api/client.ts
    - frontend/src/api/client.test.ts
    - frontend/src/auth/session.ts
    - frontend/src/auth/session.test.ts
    - frontend/src/auth/LoginScreen.tsx
    - frontend/src/auth/LoginScreen.test.tsx
    - frontend/src/components/Field.tsx
    - frontend/src/components/ErrorBanner.tsx
    - scripts/ui-gates.sh
    - tests/architecture/test_frontend_gates.py
  modified:
    - Makefile
    - docker-compose.yml
    - Dockerfile
    - .gitignore
    - .dockerignore
    - .pre-commit-config.yaml
    - .github/workflows/ci.yml
    - scripts/clean-clone-rehearsal.sh
    - README.md
    - DECISION_LOG.md
decisions: [ADR-105, ADR-106, ADR-107, ADR-108]
metrics:
  duration: 35min
  tasks: 4
  files: 36
  completed: 2026-09-19
---

# Phase 8 Plan 01: The frontend scaffold, the fetch boundary, the UI image and its gates — Summary

A React 19 + Vite 8 + TypeScript 6 SPA now lives in `frontend/`, exact-pinned with a committed
lockfile, and `docker compose up` serves it on `http://localhost:8080` through an nginx container
that proxies `/api/` to `api:8000` — so the browser only ever sees one origin, no
`Access-Control-Allow-*` header exists anywhere, and `src/taskmanager` is byte-identical to where
Phase 7 left it.

## What was built

**Task 1 — the scaffold (`be2e35d`).** `frontend/` as an npm package with 18 exact-pinned
dependencies, `tsc --strict`, an eslint flat config, vitest on jsdom, and five `make ui-*` targets
that use `npm --prefix` rather than a `cd` (GNU Make 3.81 runs each recipe line in its own shell).
The eslint config carries D-06 as a **rule**, not a comment: `localStorage` and `document.cookie`
are errors across `src/**`, exempted only in the test files that must name them to assert they
stayed empty.

**Task 2 — the fetch boundary, the session, the auth screen (`0ce12d9`).** `src/api/client.ts` is
the single place this UI touches the network. It exports **all eighteen** API operations — not
just the three this screen uses — behind a relative `/api/v1` base path, attaches the bearer token
in one place, parses `application/problem+json` into an `ApiError` carrying
`status/code/title/detail/errors`, resolves a 204 to `undefined` without touching the body, and
calls one registered handler on a 401. `src/api/types.ts` mirrors the live OpenAPI shapes exactly.
The login/register screen renders refusals from the API's own `detail` and finds every control by
accessible name.

**Task 3 — the image, the proxy, the compose service (`aad376f`).** A `node:24-alpine` build stage
(`npm ci`, then `tsc --noEmit && vite build`) into an `nginx:1.30-alpine` runtime that runs as
`nginx` on port 8080 with its pid and all five temp paths under `/tmp`. `location /api/` has no
trailing slash on the upstream, so the prefix and the query string pass through untouched; the SPA
`try_files` fallback cannot swallow it because nginx matches the longest prefix first. The
rehearsal gained `rehearsal_wait_for_a_healthy_ui` and `rehearsal_assert_the_ui_is_ours`, because
8080 is a contended port on a developer machine.

**Task 4 — the gates and the ADRs (`83fecf9`).** `tests/architecture/test_frontend_gates.py` (5
tests) asserts exact pins, a lockfile that exists, belongs to this package and agrees with the
manifest, and `strict` + `noEmit`. Its `COPY` line into the Dockerfile `test` stage landed in the
same commit (ADR-102). A CI `frontend` job, a pre-commit hook scoped `^frontend/`, and ADR-105
through ADR-108 with the README moved to `108 ADRs` in the same commit.

## Verification

| Check | Result |
|-------|--------|
| `make lint` / `make typecheck` / `make arch` | green on every commit |
| `make test` | **1140 passed, 100.00% over 1690 statements** (was 1135) |
| `make docker-test` | **1140 passed, 100.00%** — the ADR-102 verification for task 4 |
| `make ui-lint` / `make ui-typecheck` | exit 0 |
| `make ui-test` | **20 passed** across 4 files |
| `.venv/bin/pre-commit run --all-files` | exit 0, 13 hooks |
| `npm ci && lint && typecheck && test` from a clean slate | exit 0 (the exact four CI steps) |
| `git diff --stat 1dd5af7 -- src/taskmanager` | **empty** |
| `docker compose ps` | db, api, ui all **healthy**; stack left up |

### How the proxy was proved

```
curl -sf http://localhost:8080/ | grep -q 'id="root"'                      -> SPA served
curl -sf -H "Authorization: Bearer $TOKEN" :8080/api/v1/task-lists
  == curl -sf -H "Authorization: Bearer $TOKEN" :8000/api/v1/task-lists    -> IDENTICAL (299 bytes)
curl ... ":8080/api/v1/task-lists/$LIST/tasks?priority=high"
  == the same through :8000                                                -> IDENTICAL
                                                    items: 1, total_tasks: 2, completion_percentage 0.0
curl -s -o /dev/null -w '%{http_code} %{content_type}' :8080/api/v1/task-lists
                                            -> 401 application/problem+json   (NOT 200 text/html)
curl -s http://localhost:8080/anything/deep | grep -q 'id="root"'          -> SPA fallback
docker compose exec ui id -u                                               -> 101 (not root)
```

The `?priority=high` result is the load-bearing one twice over: the query string survived the
proxy, and `items: 1` beside `total_tasks: 2` shows the counters still describe the whole list
(ADR-009).

## Gates driven red before being trusted

| Gate | Planted violation | Observed |
|------|-------------------|----------|
| eslint D-06 rule | `window.localStorage.setItem("x","1")` in `src/App.tsx` | `make ui-lint` exit 2, message names D-06 |
| `client.test.ts` 401 coverage | the `status === 401` branch deleted from `client.ts` | 1 failed, 19 passed |
| exact-pin check | `"react": "^19.3.0"` | `test_every_frontend_dependency_is_an_exact_pin` FAILED, reporting `['react: ^19.3.0']` |
| strict check | `"strict": false` | `test_typescript_is_strict_and_emits_nothing` FAILED |
| non-vacuity | `frontend/package-lock.json` moved aside | 3 failed, message naming the `test` stage |
| the ADR-102 `COPY` line | the `COPY frontend/...` line removed from the Dockerfile | host `make test` **green**, `make docker-test` **5 failed / 1135 passed** |

Every revert was the exact inverse of the plant, verified with `diff`/`git status`. No `git stash`,
no blanket `git checkout`, no `git reset --hard`. No transcript files written.

## Deviations from Plan

**1. [Rule 3 - Blocking] `eslint-plugin-react-hooks` flat config lives under `configs.flat`**
- **Found during:** Task 1
- **Issue:** `reactHooks.configs["recommended-latest"]` is still the legacy eslintrc object whose
  `plugins` is an array of strings. eslint 10 refuses it outright with a migration error.
- **Fix:** `reactHooks.configs.flat["recommended-latest"]`, with a comment saying why.
- **Commit:** `be2e35d`

**2. [Rule 3 - Blocking] `"types": ["vite/client"]` added to `tsconfig.json`**
- **Issue:** `import "./styles.css"` is `TS2882: Cannot find module or type declarations for
  side-effect import`. The plan's compiler-option list did not include it.
- **Fix:** one `types` entry rather than a `vite-env.d.ts` file. The gate in task 4 reads `strict`
  and `noEmit` and is unaffected.
- **Commit:** `be2e35d`

**3. [Rule 3 - Blocking] `frontend/src/App.test.tsx` added in task 1**
- **Issue:** the plan expects `make ui-test` to exit 0 with zero tests. `vitest run` exits **1**
  when it finds no test file, and the standard escape — `--passWithNoTests` in the npm script —
  would be a permanent hole that kept the gate green the day somebody deleted the suite.
- **Fix:** one real smoke test asserting the product heading renders. It survives task 2's rewrite
  of `App.tsx`.
- **Commit:** `be2e35d`

**4. [Rule 1 - Bug] `setupTests.ts` wires Testing Library's `cleanup()` by hand**
- **Found during:** Task 2, as three failures reporting "found multiple elements".
- **Issue:** `@testing-library/react` registers its auto-cleanup only when it can see a **global**
  `afterEach`. With `globals: false` — which the plan mandates — it silently does not, and every
  render accumulates in the same document.
- **Fix:** an explicit `afterEach(cleanup)` in `setupTests.ts`, with a comment, instead of the
  plan's "one import and nothing else".
- **Commit:** `0ce12d9`

**5. [Process] The RED phase was observed but not committed separately**
- The plan marks task 2 `tdd="true"`. The three test files were written first and run against no
  implementation — 3 files failed with unresolved imports, 1 passed. That RED state was **not**
  committed, because this repository's standing rule is that all four backend gates *and* the
  frontend gates are green on **every** commit, and a committed RED test contradicts it. The
  tests-first order is real; the separate `test(...)` commit is not. Recorded here rather than
  claimed in a commit message.

**6. [Scope] UI-05 marked Partial, not Complete**
- The plan's frontmatter claims `UI-01, UI-05, UI-06, UI-07`. UI-05 reads "**every** API refusal is
  rendered from its RFC 9457 body". The mechanism (`problem.ts`, `ErrorBanner`, the global 401
  handler) exists and is exercised on the auth screen, but only three endpoints are reachable from
  the UI today. `REQUIREMENTS.md` records it as `Partial (08-01) ... completed by 08-02's screens`
  rather than overstating it. UI-01, UI-06 and UI-07 are ticked.

### Not a deviation, but worth recording

- **No extra pin was needed.** `@vitejs/plugin-react@6.1.1` did not ask for any of its three
  optional peers. The dependency set is exactly the 18 the plan's table names, and every one
  resolved at the version it names.
- **`check-added-large-files` needed no `--maxkb`.** The committed lockfile is **132 kB**, well
  under the hook's 500 kB default.
- **The `grep -nE '"[^"]+": *"[\^~><*]' frontend/package.json` acceptance criterion prints one
  line** — `"node": ">=24"` in `engines`, which is legitimately a range. The real gate scans only
  `dependencies` and `devDependencies`, and excludes `engines` with a comment saying why.
- **Host Node is 24.13.0 and `jsdom@30.1.0` wants `>=24.15.0`**, so `npm ci` prints an
  `EBADENGINE` **warning** on this machine. It is a warning, not an error; the tests run. The
  container (`node:24-alpine`, 24.21.0) and CI (`node-version: '24'`) both satisfy it.

## Threat Flags

None. The register in the plan is unchanged: T-08-01 through T-08-05 are all mitigated and
asserted (the `401` curl, the eslint rule, `id -u` = 101, the pins gate, the rehearsal's `:8080`
identity check), and T-08-06 stays *not taken* — no CORS surface was added.

## Known Stubs

- `App.tsx` renders `<p>Signed in.</p>` plus a **Log out** button once a token exists. Intentional
  and named in the plan: **plan 08-02 replaces it** with the three real screens. The session, the
  401 handler and the log-out path around it are real and tested.
- `src/api/client.ts` exports fifteen operations no screen calls yet. Deliberate (interface first);
  08-02 consumes them.

## For the next plans

**08-02 (the four screens, all under `frontend/src/`)**
- Import everything from `./api/client`. Do **not** write `fetch` anywhere else, and do not add an
  absolute URL — `grep -rnE "https?://" frontend/src` must keep finding nothing.
- The client's operation names: `listTaskLists`, `createTaskList`, `getTaskList`,
  `updateTaskList`, `deleteTaskList`, `createTask`, `listTasks(listId, {status?, priority?})`,
  `getTask`, `updateTask`, `deleteTask`, `changeTaskStatus`, `listUsers`, `assignTask`,
  `unassignTask`, `listAssignedToMe`, plus `register`, `login`, `me`.
- `ALLOWED_TRANSITIONS` is exported from `./api/types` — use it to offer only legal status moves,
  and render the 409 when the API refuses anyway.
- Never recompute `completion_percentage` from `items` (ADR-009). `.completion-bar > .fill` in
  `styles.css` takes an inline width.
- Errors go through `<ErrorBanner error={apiError} />`; catch with `if (e instanceof ApiError)`.
- `App.tsx` already owns the token and the 401 handler — replace only the signed-in branch.
- Tests: `globals: false`, so import `describe`/`it`/`expect` from `vitest`. Cleanup is already
  wired. Find controls by label text, never a test id. Assert the API's own `detail`, never a
  string the component invented.

**08-03 (README / AI_WORKFLOW / CLAUDE.md / rehearsal)**
- `DECISION_LOG.md` is at **108** ADRs and the README says `108 ADRs`. The next free id is
  **ADR-109**. Any append must move that number in the same commit.
- The README target table already has the five `make ui-*` rows; the ADR count is already moved.
  **No UI section exists yet** — 08-03 owns it, plus the Pending entries this plan owes: **no deep
  links / no browser Back** (ADR-106), **no generated TypeScript client from OpenAPI**, no e2e
  browser tests, no i18n, no pagination.
- `AI_WORKFLOW.md` line ~141 still reads "adding a Node toolchain to a Python deliverable was
  judged the wrong trade". ADR-105 says that sentence is amended **in place** by 08-03.
- The rehearsal's `PREAMBLE` already carries `rehearsal_wait_for_a_healthy_ui` and
  `rehearsal_assert_the_ui_is_ours`, and the awk branch emits **five** generated lines (the report
  line says five). 08-03 adds the UI's own commands **inside** the README markers using `curl` and
  POSIX tools only — `test_the_rehearsal_region_needs_no_virtualenv` allows only
  `make env|up|down|docker-test` in there, so **no `make ui-*` target may go inside the markers**.
- `make rehearse` stops the developer's stack and needs a clean tree; bring it back with
  `docker compose up -d`.
- CLAUDE.md's hand-maintained "Project Rules" has no frontend section yet — 08-03 owns it.

## Self-Check: PASSED

All 26 created files exist on disk; all four commit hashes resolve in `git log`; the working tree
is clean; `docker compose ps` shows db, api and ui healthy.
