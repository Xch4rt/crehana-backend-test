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

_Reviewed: 2026-09-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
