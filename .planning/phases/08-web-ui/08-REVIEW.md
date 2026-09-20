---
phase: 08-web-ui
reviewed: 2026-09-19T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - .dockerignore
  - .github/workflows/ci.yml
  - .gitignore
  - .pre-commit-config.yaml
  - Dockerfile
  - Makefile
  - docker-compose.yml
  - frontend/.dockerignore
  - frontend/Dockerfile
  - frontend/eslint.config.js
  - frontend/index.html
  - frontend/nginx.conf
  - frontend/package.json
  - frontend/src/App.test.tsx
  - frontend/src/App.tsx
  - frontend/src/api/client.test.ts
  - frontend/src/api/client.ts
  - frontend/src/api/problem.ts
  - frontend/src/api/types.ts
  - frontend/src/assigned/AssignedScreen.test.tsx
  - frontend/src/assigned/AssignedScreen.tsx
  - frontend/src/auth/LoginScreen.test.tsx
  - frontend/src/auth/LoginScreen.tsx
  - frontend/src/auth/session.test.ts
  - frontend/src/auth/session.ts
  - frontend/src/components/CompletionBar.test.tsx
  - frontend/src/components/CompletionBar.tsx
  - frontend/src/components/ErrorBanner.tsx
  - frontend/src/components/Field.tsx
  - frontend/src/lists/ListsScreen.test.tsx
  - frontend/src/lists/ListsScreen.tsx
  - frontend/src/main.tsx
  - frontend/src/setupTests.ts
  - frontend/src/styles.css
  - frontend/src/tasks/AssigneePicker.test.tsx
  - frontend/src/tasks/AssigneePicker.tsx
  - frontend/src/tasks/TasksScreen.test.tsx
  - frontend/src/tasks/TasksScreen.tsx
  - frontend/src/tasks/transitions.test.ts
  - frontend/src/tasks/transitions.ts
  - frontend/src/testing/http.ts
  - frontend/tsconfig.json
  - frontend/vite.config.ts
  - scripts/clean-clone-rehearsal.sh
  - scripts/ui-gates.sh
  - tests/architecture/test_documentation_claims.py
  - tests/architecture/test_frontend_gates.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 8: Web UI — Code Review Report

**Reviewed:** 2026-09-19
**Depth:** standard
**Files Reviewed:** 33 source/config files (frontend/src, frontend build/proxy config, CI/pre-commit/Make wiring, the two architecture-gate test files)
**Status:** issues_found

## Summary

The frontend is well-disciplined against the properties the phase context calls out: `make ui-lint`,
`make ui-typecheck` and `make ui-test` all ran green (66/66 vitest tests) during this review. The
token-storage rule (D-06) is enforced by eslint and never touched outside `auth/session.ts`; every
render of server-provided text goes through JSX text nodes (no `dangerouslySetInnerHTML`,
`innerHTML` or `eval` anywhere under `frontend/src`); `CompletionBar` is fed the response's own
counters everywhere it is used and never `items.length`; the status control is built from the
transcribed `ALLOWED_TRANSITIONS` table and a 409 is rendered from the API's own `detail`; and the
nginx SPA fallback correctly cannot swallow `/api/` because nginx picks the longest matching prefix.
`scripts/ui-gates.sh` and the `clean-clone-rehearsal.sh` additions are POSIX-sh clean — no bashisms,
consistent quoting, and the pre-commit escape hatch cannot mask a failure once `node_modules`
exists (the three `npm` invocations run under `set -eu` with no `||true` anywhere near them).

Three real correctness/robustness gaps were found (WARNING), none of them a security vulnerability
or a data-loss risk, plus three lower-severity notes (INFO). The most significant is a genuine race
condition on `TasksScreen`'s filter-driven fetch: rapid filter changes have no ordering guard and no
unmount guard, so a stale response can overwrite a newer one.

## Warnings

### WR-01: `TasksScreen`'s task-list fetch has no race guard — rapid filter changes can render stale data

**File:** `frontend/src/tasks/TasksScreen.tsx:90-109`

**Issue:** Every other data-fetching effect in this phase (`ListsScreen.tsx:35-52`,
`AssignedScreen.tsx:27-44`, and even the sibling `listUsers` effect in this same file at
`TasksScreen.tsx:114-130`) guards its `setState` calls with a `let live = true` / cleanup flag so a
response that resolves after the effect was superseded is dropped. The primary `load` effect does
not:

```tsx
const load = useCallback(
  (): Promise<void> =>
    listTasks(list.id, { ...(status === "" ? {} : { status }), ...(priority === "" ? {} : { priority }) })
      .then((loaded) => { setCollection(loaded); })
      .catch((failure: unknown) => { if (failure instanceof ApiError) setError(failure); }),
  [list.id, status, priority],
);

useEffect(() => {
  void load();
}, [load]);
```

`fetch()` responses are not guaranteed to resolve in the order the requests were sent (server load,
proxy buffering, or simply a heavier query on the first filter). Concrete failure scenario: a user
on the tasks screen selects Status=`in_progress`, then a moment later clears it back to Status=`""`.
Two `GET /task-lists/{id}/tasks` requests are in flight. If the *first* (`in_progress`) request's
response arrives *after* the second (`""`) request's response — plausible if the unfiltered query is
cheaper and returns first, or simply due to network jitter — `setCollection` is called last with the
**stale, filtered** result, and the screen silently shows the wrong task list state (including the
wrong `completion_percentage`/`total_tasks`/`completed_tasks`, since those numbers travel with each
response too) until the next state change forces a re-fetch. This is exactly the "stale responses
overwriting newer ones" class of bug the phase's own filtering feature is most exposed to, and it is
not covered by any test in `TasksScreen.test.tsx` (the mocked `serving()` helper always resolves
handlers synchronously in call order, so the suite cannot currently detect out-of-order resolution).

The same effect (and every mutation handler in this file — `add`, `save`, `move`, `remove`, all of
which call `await load()`) also has no unmount guard, so navigating "Back to lists" while a request
from this screen is still in flight calls `setCollection`/`setError`/`setInFlight` on an unmounted
component.

**Fix:** Give `load` the same guard the sibling effects already use, keyed off of a per-effect-run
token rather than a single boolean (a boolean would still let an in-flight *older* request win a
race that finishes after a *newer* request already set `live = false` was itself superseded, but a
monotonically increasing "request id" fixes both problems at once):

```tsx
useEffect(() => {
  let current = true;
  void listTasks(list.id, { ...(status === "" ? {} : { status }), ...(priority === "" ? {} : { priority }) })
    .then((loaded) => { if (current) setCollection(loaded); })
    .catch((failure: unknown) => {
      if (current && failure instanceof ApiError) setError(failure);
    });
  return () => {
    current = false;
  };
}, [list.id, status, priority]);
```

and thread the same `current`-style guard (or an `AbortController` passed into `listTasks`) through
`add`/`save`/`move`/`remove`'s trailing `await load()` calls so a mutation whose screen has since
unmounted does not update state after the fact.

### WR-02: Clearing a task's description in the edit form sends `""`, not `null` — leaves a stray empty paragraph

**File:** `frontend/src/tasks/TasksScreen.tsx:198-210` (assembly) and `frontend/src/tasks/TasksScreen.tsx:348-350` (render)

**Issue:** The create-task path treats an empty description as "omit the field" —
`...(description === "" ? {} : { description })` (`TasksScreen.tsx:164`) — consistent with
`TaskResponse.description: string | null` meaning "no description" is represented as `null`. The
edit path does not apply the same normalization:

```tsx
if (editDescription !== (task.description ?? "")) {
  changes.description = editDescription;   // "" when the user cleared the field
}
```

If a user opens "Edit" on a task that has a description and deletes all the text, `editDescription`
becomes `""`, which is different from `task.description ?? ""` (`"" !== "Semi-skimmed"`), so
`changes.description = ""` is sent verbatim — never `null`. If the API accepts an empty string as a
distinct value from `null` (a reasonable assumption given `description: string | null` is the
documented contract, not `string | null | ""`), the task is left with a non-null, zero-length
description, and:

```tsx
{task.description !== null && (
  <p className="muted">{task.description}</p>
)}
```

renders an empty `<p className="muted"></p>` on every subsequent render of that row instead of no
paragraph at all — the UI now visibly disagrees with "this task has no description" everywhere else
`description !== null` is the check (`AssignedScreen.tsx:66`, `ListsScreen.tsx:177` for lists use the
same pattern for the analogous field).

**Fix:** Normalize the same way the create path already does, sending `null` rather than `""`:

```tsx
if (editDescription !== (task.description ?? "")) {
  changes.description = editDescription === "" ? null : editDescription;
}
```

### WR-03: `frontend/nginx.conf` sets no `X-Content-Type-Options` / `X-Frame-Options` (or CSP `frame-ancestors`)

**File:** `frontend/nginx.conf:49-115`

**Issue:** The `server` block is otherwise careful (unprivileged port, `server_tokens off`, correct
`try_files` fallback that cannot swallow `/api/`, correct immutable/no-store cache split) but adds no
`X-Content-Type-Options: nosniff` and no clickjacking defense (`X-Frame-Options: DENY` or a CSP
`frame-ancestors 'none'`). This is a UI that holds a bearer token in memory and offers one-click
destructive actions (`Delete` on a list or task, `Log out`) behind plain `<button>` elements with no
re-confirmation beyond `window.confirm`. Without a frame-ancestors/X-Frame-Options defense, a
third-party page could iframe the running UI and use a transparent-overlay clickjacking technique to
get an authenticated user to click "Delete" on a list they can see but did not intend to act on. Not
classified CRITICAL because it requires the victim to already be an authenticated user visiting a
malicious page and to be lured into a plausible-looking click sequence, and because the brief does
not ask for a hardened UI — but it's a cheap, standard line worth adding to a container that already
goes to the trouble of running unprivileged.

**Fix:**

```nginx
server {
    ...
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Content-Security-Policy "frame-ancestors 'none'" always;
    ...
}
```

## Info

### IN-01: The global 401 → logout handler fires for anonymous endpoints too (login/register), not just for an authenticated session going stale

**File:** `frontend/src/api/client.ts:120-122`, `frontend/src/App.tsx:28-37`

**Issue:** `request()` calls the module-level `onUnauthorized()` handler on *any* 401 response,
including one from `POST /auth/login` with a merely-wrong password (no session existed yet). `App`
registers this handler unconditionally on mount, before the user has ever authenticated
(`App.tsx:28-37`), so a failed login attempt today harmlessly re-runs `clearToken()` (already empty)
and `setView({ name: "lists" })` (irrelevant while `token === null`, since `App` renders
`LoginScreen` whenever `token === null` regardless of `view`). There is no visible bug today, and
`client.test.ts` even asserts the current (fire-on-any-401) behavior. But the handler's name and
comment ("registered once by App... a 401 raised by ANY call ends the session and returns to the
login screen") describe session-expiry semantics, not login-attempt semantics, and the two are
conflated. The first future change that makes `onUnauthorized` do something user-visible (e.g., a
"your session expired" banner) will incorrectly show that banner after a plain wrong-password login
attempt.

**Fix:** Either scope `setUnauthorizedHandler`'s callback to fire only for requests made with a
token attached (check `getToken() !== null` before calling `onUnauthorized()` inside `request()`),
or rename/re-document the callback so a future reader does not assume it only ever fires for a
previously-authenticated session.

### IN-02: No CSP `<meta>` tag in `frontend/index.html` to back up the missing nginx CSP header

**File:** `frontend/index.html:1-12`

**Issue:** Companion to WR-03 — there is also no document-level Content-Security-Policy meta tag as
a defense-in-depth fallback for any static-file serving path that bypasses the nginx `add_header`
directives (e.g., a future change to serve the SPA from a CDN or a different static host without
carrying `nginx.conf` along). Low priority since the current deployment shape always goes through
the pinned nginx config.

**Fix:** Optional; if added, a `<meta http-equiv="Content-Security-Policy" content="default-src
'self'; connect-src 'self'">` line is consistent with the same-origin-only design (D-03) and costs
nothing since the app makes no cross-origin requests.

### IN-03: `gzip_types` omits `text/javascript`, the MIME type `mime.types` may assign to `.js` on newer nginx/mime-db pairings

**File:** `frontend/nginx.conf:45-47`

**Issue:** `gzip_types text/css application/javascript application/json image/svg+xml;` covers
`application/javascript`. Recent `mime.types` tables (and the WHATWG MIME spec) increasingly favor
`text/javascript` for `.js`; if the bundled `nginx:1.30-alpine` image's `mime.types` maps `.js` to
`text/javascript`, Vite's JS bundles would silently stop being gzip-compressed (not a correctness
bug — `Content-Type` would still be correct — purely a lost-compression regression to watch for).
Out of v1 scope as a performance concern, noted only because it is a one-line, zero-risk addition.

**Fix:** `gzip_types text/css text/javascript application/javascript application/json image/svg+xml;`

---

## Resolution

All three WARNING findings are fixed, one atomic commit each, every commit green on all seven
gates (`make lint`, `make typecheck`, `make arch`, `make test` — 1140 — and `make ui-lint`,
`make ui-typecheck`, `make ui-test`). The UI test count went 66 → 68. `src/taskmanager` was not
touched; `git diff d48e20b~1..0f3e364 -- src/taskmanager` is empty.

| Finding | Commit | How it was proven |
|---|---|---|
| WR-01 | `d48e20b` | A new vitest test drives `fetch` by hand (the shared `serving()` helper answers synchronously in call order and cannot express the race): the filtered read is held open and released only after the later unfiltered read has rendered. **Observed red first** — the stale row appeared, `Buy bread` vanished and the bar read 99%. Green after the fix. |
| WR-02 | `20b6b44` | A new test pins the PATCH body to exactly `{"description": null}`, and was driven red against the old line (`expected { description: '' } to deeply equal { description: null }`). The backend contract was confirmed first, in source and live through the UI proxy. |
| WR-03 | `0f3e364` | `docker compose up -d --build ui`, then `curl` on all four served shapes. Plus the README's rehearsal region gained a third command, and `make rehearse` was run on a clean clone of `0f3e364`: exit 0, 152s. |

**WR-01 — the guard is a token, not a boolean.** A `let live = true` flag answers "is the effect
run that issued you gone?", which covers an unmount and not a race. Up to three collection reads
can be outstanding on this screen, because every mutation handler ends in `await load()`. A
monotonic request token in a ref answers the question that decides whether a body may render — "are
you still the newest read?" — and the effect cleanup bumps it past every token handed out so far,
which makes *superseded* and *unmounted* one case. A second ref tracks mount state and guards the
post-await `setState` calls that have no ordering question but must not fire after "Back to lists":
the form resets, `setInFlight`, `setError`, and the row replacement the assignee picker triggers.

**WR-02 — it went the `null` way, and the review's predicted symptom was not real.** Checked
before fixing rather than assumed. `TaskPatchRequest.description` is `str | None` and `to_command`
reads the key out of `model_fields_set`, so an explicit null is "clear" and not "absent"; and
`Task.describe` runs the value through the domain's `optional_text`, which *folds `""` to `None`*.
Verified live against the running stack through the UI's own `/api/` proxy with a throwaway user:
`{"description": null}` answers 200 with `"description":null`, and so does `{"description": ""}`.
So nothing was ever stored wrong and no stray empty `<p class="muted">` was ever rendered — the
review's stated consequence does not hold against this backend. The request was still wrong:
`TaskResponse.description` is `string | null`, so `""` was a third spelling of a two-valued field,
correct only because of a fold the UI cannot see. `frontend/src/api/types.ts` needed no change —
`TaskUpdateRequest.description` was already `string | null`.

**WR-03 — the four curl proofs.** `add_header` is replaced, not extended, by any `location` that
declares one of its own, and two locations set a `Cache-Control`; `= /index.html` also serves every
deep path, because `try_files ... /index.html` is an internal redirect that re-runs location
matching. So the three headers are written three times on purpose — server block (inherited by
`/api/` and `/`), `= /index.html`, and `/assets/`. All four shapes on the rebuilt image:

```
GET /                      200 text/html                  nosniff + DENY + frame-ancestors 'none'
GET /assets/index-*.js     200 application/javascript     nosniff + DENY + frame-ancestors 'none'
GET /lists/deep/path       200 text/html (SPA fallback)   nosniff + DENY + frame-ancestors 'none'
GET /api/v1/task-lists     401 application/problem+json   nosniff + DENY + frame-ancestors 'none'
```

The 401 is the `always` proof: without it nginx attaches headers only to 200/201/204/301/302/304,
and the proxied 401 an unauthenticated SPA call receives is one of the most common responses this
origin serves. (`curl -I` sends HEAD, which the API answers 405; the row above is a real `GET`.)

**The rehearsal region changed, and `make rehearse` was run.** One line was added inside the
markers — `curl -sfI $UI | grep -q 'X-Frame-Options: DENY'` — so a fresh clone re-proves the header
on the entry document, which is the location where the repetition is load-bearing. Both gates that
read the region count commands as a **floor** (`MINIMUM_REHEARSAL_COMMANDS = 3` in
`tests/architecture/test_documentation_claims.py`, `MINIMUM_COMMANDS=3` in
`scripts/clean-clone-rehearsal.sh`), so nothing was pinned to two; the region's other gate only
restricts `make` targets, and a `curl` line names none. The README prose that said "Two commands"
was corrected in the same commit. `make docker-test` was run before that commit, per CLAUDE.md.

**`DECISION_LOG.md` is untouched.** ADR-107 is the nginx/proxy entry (id verified) and it states
what the proxy *does* — the upstream, the missing trailing slash, the longest-prefix argument, the
DNS-caching cost — not what the server block sets. Nothing in it became false, and three headers do
not earn an entry in an append-only log. The reasoning is in the commit message and in
`frontend/nginx.conf`'s own comments.

### Info findings

**IN-03 was checked and deliberately not taken.** Its premise does not hold for the pinned image:
`nginx:1.30-alpine` (1.30.5) maps `js` to `application/javascript` in its own
`/etc/nginx/mime.types`, and the served bundle answers `Content-Type: application/javascript` with
`Content-Encoding: gzip` today. Adding a MIME type this image never emits would be a line nothing
can verify. **IN-01 and IN-02 are open**, untouched and out of scope for this pass.

---

_Reviewed: 2026-09-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Resolved: 2026-09-19 — WR-01 `d48e20b`, WR-02 `20b6b44`, WR-03 `0f3e364`_
