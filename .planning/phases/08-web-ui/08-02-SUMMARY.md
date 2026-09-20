---
phase: 08-web-ui
plan: 02
subsystem: frontend
tags: [react, vitest, ui, adr-009, adr-097, rfc9457, accessibility]
requires:
  - 08-01's fetch boundary (`frontend/src/api/client.ts`, all 18 operations)
  - the running API (Phases 3-5), unmodified
provides:
  - the four screens the phase contract names, all drivable in a browser
  - a filtered task view whose completion bar still reports the whole list
  - a status control that offers only the moves ADR-097 allows
  - assignment from the user directory, and the caller's assigned tasks
affects:
  - frontend/src/** only; no document, no Makefile, no compose file
tech-stack:
  added: []
  patterns:
    [
      hand-rolled view switch,
      response-driven rows (never optimistic),
      counters rendered as given,
      fetch routed by URL in tests,
    ]
key-files:
  created:
    - frontend/src/components/CompletionBar.tsx
    - frontend/src/components/CompletionBar.test.tsx
    - frontend/src/lists/ListsScreen.tsx
    - frontend/src/lists/ListsScreen.test.tsx
    - frontend/src/tasks/transitions.ts
    - frontend/src/tasks/transitions.test.ts
    - frontend/src/tasks/TasksScreen.tsx
    - frontend/src/tasks/TasksScreen.test.tsx
    - frontend/src/tasks/AssigneePicker.tsx
    - frontend/src/tasks/AssigneePicker.test.tsx
    - frontend/src/assigned/AssignedScreen.tsx
    - frontend/src/assigned/AssignedScreen.test.tsx
    - frontend/src/testing/http.ts
  modified:
    - frontend/src/App.tsx
    - frontend/src/App.test.tsx
    - frontend/src/styles.css
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
decisions: []
metrics:
  duration: 25min
  tasks: 3
  files: 16
  completed: 2026-09-19
---

# Phase 8 Plan 02: The four screens — lists, tasks, status, filters, assignment Summary

Every brief use case is now drivable from `http://localhost:8080`, and the property the phase
exists for holds in three independent places: a task list filtered to `priority=high` shows **one
row** while its completion bar still reads **50% (1 / 2)**, because the bar renders the response's
own whole-list counters and derives nothing (ADR-009).

## What was built

**Task 1 — the list index and the bar (`82e68c5`).** `CompletionBar` takes three required numbers
and computes none of them. `ListsScreen` reads on mount, creates from the response the API
answered (not from the form it submitted), renames with a `{name}`-only PATCH, and deletes behind
a `window.confirm` that names the list. `App` became a discriminated-union view switch — no
router, per ADR-106 — keeping 08-01's global 401 handler exactly as it was.

**Task 2 — one list (`fbf2482`).** `transitions.ts` orders the move table; `TasksScreen` renders
the rows, the two filters, the create form and the edit form. A status change goes only through
`PATCH .../tasks/{id}/status`; the general PATCH sends **only the fields that changed** and never
`status`, and an edit that changed nothing makes no request at all (an empty body is a 422).

**Task 3 — assignment (`ebb6139`).** `AssigneePicker` takes the directory as a prop —
`TasksScreen` reads `GET /api/v1/users` **once per screen**, because that endpoint has no
pagination and a fetch inside the row component would multiply it by the row count. Unassigning
uses the **200 body** it answers rather than assuming the 204 the two deletes answer. An assignee
missing from the directory renders as the raw id, never as "Unassigned". `AssignedScreen` renders
no completion bar: that response carries no counters, and inventing one is ADR-009's mistake
pointing the other way.

## Verification

| Check | Result |
|-------|--------|
| `make ui-test` | **66 passed** across **10 files** (was 20 / 4) |
| `make ui-lint` / `make ui-typecheck` / `npm run build` | exit 0 (bundle 236.91 kB, 73.02 kB gzip) |
| `make lint` / `make typecheck` / `make arch` | green on every commit |
| `make test` | **1140 passed, 100.00%** — unchanged, no Python file touched |
| `make docker-test` | **1140 passed, 100.00%** |
| `git diff --stat 1dd5af7 -- src/taskmanager` | **empty** |
| `grep -rn "dangerouslySetInnerHTML" frontend/src` | nothing (T-08-07) |
| `grep -rnE "https?://" frontend/src` outside tests | nothing — the client stays relative |
| `docker compose ps` | db, api, ui all **healthy**; only `ui` was rebuilt, `test_pgdata` untouched |

### The end-to-end proof through the proxy on :8080

Every call below went through nginx on `:8080`, never to `:8000`:

```
1  GET  /                                     -> the SPA (id="root")
2  POST /api/v1/auth/register  x2             -> two accounts
3  POST /api/v1/auth/login     (form post)    -> 188-char bearer token
4  POST /api/v1/task-lists                    -> a list
5  POST .../tasks x2                          -> "Buy milk" high, "Buy bread" medium
6  PATCH .../tasks/{id}/status {"completed"}  -> status completed, completed_at set
7  GET  .../tasks?priority=high               -> items 1 | total_tasks 2 completed_tasks 1
                                                 completion_percentage 50.0     <-- ADR-009
8  PATCH .../status {"pending"}               -> 409 invalid_status_transition
                                                 "A task cannot move from completed to pending."
                                                 errors {'from': 'completed', 'to': 'pending'}
9  PUT  .../assignee                          -> assignee_id set; GET /users -> 7 users
10 GET  /api/v1/tasks/assigned-to-me (acct B) -> ['Buy milk']
11 DELETE .../assignee                        -> http 200 application/json, body carries the task
12 GET  /api/v1/task-lists (no token)         -> 401 application/problem+json
13 docker compose logs api | grep -c task_assigned_email -> 1
```

### A browser run DID happen

No browser-driver package is installed and none was added. A Playwright chromium cache from an
unrelated project exists on this host, so the **binary** was driven directly over the DevTools
Protocol from a throwaway script using **Node 24's built-in `WebSocket` and `fetch`** — zero npm
dependencies, nothing committed, the script lives in the session scratch directory. Every step
below ran against the **built** bundle served by nginx:

```
PASS  the SPA renders its login screen in Chromium
PASS  registering signs the account in and lands on the list index
PASS  a list is created and appears without a reload
PASS  a duplicate name renders the API's RFC 9457 detail
      "A task list named 'Browser walkthrough' already exists for this owner. (duplicate_task_list_name)"
PASS  renaming a list works from the browser
PASS  clicking a list opens its tasks screen
PASS  two tasks are created, one high and one medium
PASS  completing one of two moves the bar -- "50% 1 / 2"
PASS  ONE row is visible and the bar still reads the whole list
      {"rows":["Buy milk"],"bar":"50% 1 / 2","valuenow":"50"}
PASS  a completed task is offered only the reopening move -- ["Completed","In progress"]
PASS  a task is assigned and the row shows the assignee -- "Ada Lovelace (ada@example.com)"
PASS  a task is edited in place
PASS  deleting asks first and then removes the row -- confirm() called 1x
PASS  assigned-to-me renders, with no invented completion bar
PASS  a forged token gets a 401 on the first call, and the browser is returned to
      the login screen with sessionStorage cleared
```

The forced-401 step is worth its own sentence, because the first attempt at it was **wrong and
said so**: clearing `sessionStorage` in a live tab proves nothing, since the token lives in memory
and storage is only its mirror (D-06). Writing an unusable token and **reloading** is what
actually puts a bad credential in the client's hand — and that is what produced the 401.

This is a one-off spot check, not a gate: it adds no dependency, no `make` target and no CI step,
and it is not repeatable on a machine without that cached binary. The suite is the proof that
survives.

## The three falsifications, each driven red and reverted

| Gate | Planted defect | Observed |
|------|----------------|----------|
| ADR-009, the component | `CompletionBar` recomputing `Math.round((completed / total) * 100)` | 1 failed / 4 passed — exactly the "derives nothing" test |
| ADR-097, the move table | `"pending"` added to `ALLOWED_TRANSITIONS.completed` | 1 failed / 4 passed — the "single forbidden move" test |
| the 200-vs-204 body | `unassignTask`'s response ignored, a local `{...task, assignee_id: null}` used | 1 failed / 5 passed — the "rather than assuming a 204" test |

Each revert was a byte-for-byte restore verified with `git diff` / a re-read of the line, followed
by a full green run. No `git stash`, no blanket `git checkout`, no `git reset --hard`. The
ADR-009 plant is the phase's most important one and it failed the single test written to catch it,
not a neighbour.

## Deviations from Plan

**1. [Rule 3 - Blocking] `react-hooks/set-state-in-effect` refused the plan's effect shape**
- **Found during:** Task 2, at `make ui-lint`.
- **Issue:** eslint-plugin-react-hooks 7 reads `useEffect(() => { void load(); })` where `load` is
  an `async` function containing `setState` **after an `await`** as a synchronous setState inside
  an effect, and errors. The rule is not wrong about the shape it can see — it cannot see the
  `await`.
- **Fix:** `load` returns a promise chain, so every `setState` sits inside a `.then` callback —
  which is what the rule documents as correct, and what `ListsScreen` already did. A comment says
  why, so the next reader does not "simplify" it back.
- **Commit:** `fbf2482`

**2. [Design] `transitions.ts` orders the existing table instead of transcribing it a second time**
- The plan said to transcribe `ALLOWED_TRANSITIONS` from `task_status.py`. That table was already
  transcribed once, by 08-01, into `frontend/src/api/types.ts`. A second copy would be a second
  thing to keep true. `transitions.ts` imports it and adds the one thing it lacks: deterministic
  **order** (the Python side is a `frozenset`). The honest limit the plan asked to state is stated
  in the file — it is still a copy, nothing compares it with Python, and the server stays the
  authority via the tested 409 path. The falsification above was planted in `types.ts` and went
  red through `transitions.test.ts`, which is the proof the indirection costs nothing.
- **Commit:** `fbf2482`

**3. [Design] `AssigneePicker` renders its own refusal instead of taking an `onError` prop**
- The plan's props list had `onError`, but its behaviour list required the picker's own test to
  find `role="alert"`. Both cannot be true at once. The picker owns a small `ErrorBanner`, which
  also puts the refusal next to the control that caused it. The plan's "it fetches `GET /users`
  once" test moved to `TasksScreen.test.tsx`, where the fetch actually lives — the picker is
  *given* the directory, exactly as the plan's own action paragraph specifies.
- **Commit:** `ebb6139`

**4. [Rule 3 - Blocking] The tasks tests were re-based on URL routing**
- Adding the directory read gave `TasksScreen` **two** mount requests with no order between them,
  and a `mockResolvedValueOnce` queue hands whichever effect runs first the other's body. A
  `serving([...])` helper in `frontend/src/testing/http.ts` answers by method + URL fragment and
  builds a fresh `Response` per call (a `Response` body can only be read once).
- **Commit:** `ebb6139`

**5. [Process] The RED phase was observed but not committed separately**
- Same as 08-01. Each task's tests were written first and run against no implementation: task 1
  gave 2 files unresolved + 2 failures, task 2 gave 2 files unresolved, task 3 gave 3 files
  failing. Those states were **not** committed, because every commit in this repository must be
  green on all six gates. The tests-first order is real; the `test(...)` commit is not.

**6. [Scope] Editing a task's due date is displayed, not offered**
- `TaskUpdateRequest` accepts `due_date` and a row shows it when the API sends one, but no control
  edits it. The phase contract's screen list names title/description/priority for editing, and a
  date control that must serialise to the API's datetime shape is a guess this plan did not need
  to make. Named below for the README.

## Threat Flags

None. The register is unchanged: **T-08-07** mitigated — every value is a React child, and
`dangerouslySetInnerHTML` appears nowhere under `frontend/src`. **T-08-08** stays *accepted*: the
directory is shown exactly as `GET /api/v1/users` publishes it and the UI claims no restriction the
API does not have. **T-08-09** mitigated — every row is replaced from a response body, the assigned
screen renders no derived counter, and the simulated invitation is deliberately **not** surfaced
(see below). **T-08-10** mitigated — `allowedMovesFrom` mirrors the table, the copy is documented
as a copy, and the 409 path is tested and was observed live.

## Known Stubs

None. Every screen the plan names is wired to the real API; no component receives placeholder data.

## Deliberate omissions (each a fact the UI refuses to invent)

- **The simulated invitation is not surfaced.** It is a log line the backend emits after the
  transaction commits (ADR-070); the API returns nothing about it, so a UI saying "invitation sent"
  would be asserting something it was never told. `docker compose logs api | grep
  task_assigned_email` is how it is observed, and it printed 1 in the walkthrough above.
- **`AssignedScreen` shows `task_list_id`, not a list name.** That response carries no list name,
  and looking one up would be a request the screen has no reason to make.
- **No completion bar on the assigned screen**, for the same reason.

## For 08-03 — what the documents must say truthfully

**README "Pending" owes these, and none of them is a hedge:**
- **No deep links and no browser Back between screens** — navigation is a hand-rolled view switch
  (ADR-106). A refresh returns to the list index, signed in.
- **No end-to-end browser tests in the suite or in CI.** The screens are gated by 66 vitest
  component tests that mock at the fetch boundary. A browser walkthrough *was* performed once, by
  hand, over the DevTools Protocol with no dependency added — it is a spot check like
  `make break-check`, not a gate, and it is not reproducible on a machine without a cached
  chromium binary. Say exactly that; "tested in a browser" without the qualifier would overclaim.
- **No generated TypeScript client from OpenAPI** — `api/types.ts` is a hand transcription, and so
  is the status-transition table. Nothing compares either with the Python source; the server stays
  the authority and refuses with a 409 the UI renders.
- **No i18n, no pagination** (the API has none), **no optimistic updates** (deliberate: every row
  comes from a response body), **no dark mode**, **no due-date editing** (displayed only).
- **The user directory is unrestricted** (ADR-068) — already a README item; the UI shows it as the
  API publishes it.

**`AI_WORKFLOW.md` should record, from this plan:** the three falsifications above as the evidence
that the UI's gates are real; that the phase's single most important property (ADR-009) is asserted
by a test whose fixture deliberately contains *inconsistent* numbers, which is what makes a later
"tidy-up" fail; and the honest note that the browser walkthrough was a one-off spot check driven
with the runtime's built-in WebSocket rather than an added test dependency.

**Counts 08-03 must not break:** `DECISION_LOG.md` is still at **108** ADRs and the README still
says `108 ADRs` — this plan added none. The next free id is **ADR-109**.

## Self-Check: PASSED

All 13 created files exist on disk; the three commit hashes (`82e68c5`, `fbf2482`, `ebb6139`)
resolve in `git log`; `docker compose ps` shows db, api and ui healthy; the working tree carries
only this SUMMARY and the three planning files.
