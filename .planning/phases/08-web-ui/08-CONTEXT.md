# Phase 8: Web UI — Context

**Gathered:** 2026-09-19
**Source:** decisions taken by the user in the execution session that paused 07-05 at its task 4
push checkpoint. No discuss-phase was run; the decisions below were made in conversation and are
recorded here so planning does not re-ask them.

## Phase Boundary

A small web UI **inside the deliverable repository**, so an evaluator who runs
`docker compose up` can drive every brief use case from a browser. The brief asks for no UI: this
phase is beyond the brief, and every document must say so rather than imply otherwise.

It runs **before 07-05 resumes**. 07-05 tasks 4-7 (push approval, push + CI run, badge/diagram
check, delivery email) happen after this phase, so the UI is part of the delivered commit. Nothing
in this phase pushes, and nothing in this phase touches 07-05's plan file.

## Implementation Decisions (locked)

- **D-01 — The UI goes inside the deliverable** (`frontend/`), not on a side branch and not in a
  second repository. The user chose this knowingly over the recommendation to keep it out: it
  reverses the "Frontend / UI" Out of Scope row and `AI_WORKFLOW.md`'s stated rejection of a Node
  toolchain in a Python deliverable. Both reversals must be recorded by id in `DECISION_LOG.md`
  and honestly in `AI_WORKFLOW.md` (the AI recommended against; the human decided).
- **D-02 — React + Vite + TypeScript, a static SPA. Not Next.js.** SSR buys nothing over an
  existing JSON API; a static build served by nginx is a few MB and needs no Node runtime in the
  running stack. ADR owed.
- **D-03 — Same-origin through a reverse proxy; no CORS on the backend.** The UI container's nginx
  proxies `/api/` (and nothing it should not) to the `api` service; the Vite dev server proxies the
  same path in development. `src/taskmanager` is therefore **not modified**. Settings-driven CORS
  (no wildcard, default empty, documented in `.env.example`, tested, ADR) is the fallback only if
  the proxy proves unworkable — and taking the fallback is a deviation to report, not a free choice.
- **D-04 — The backend's kind of rigor, sized to a small UI.** TypeScript `strict`, eslint, vitest
  (component + unit tests with the API client mocked at the fetch boundary), each behind a `make`
  target, a Node job in `.github/workflows/ci.yml`, and the pre-commit side of the two-places rule
  if a new command is introduced. Exact-pinned dependencies with a committed lockfile (`npm ci`),
  versions verified against the npm registry at planning/execution time, no pre-releases — the
  same policy `requirements.txt` follows.
- **D-05 — "Sencillona".** Plain, clean, functional. No design system, no component library, no
  state-management library, no router beyond what two or three screens need (a tiny hand-rolled
  view switch or `react-router` — planner's call, smallest wins). Plain CSS. Accessible basics:
  labels on inputs, buttons that are buttons, visible focus, errors announced in text.
- **D-06 — The token lives in memory, optionally mirrored to `sessionStorage`**; never
  `localStorage`, never a cookie the backend does not set. A 401 clears it and returns to login.
- **D-07 — Errors come from the API's RFC 9457 body.** Show `detail` (fall back to `title`), key
  any special handling on `code`. The UI invents no error text for an API refusal; it may only
  word failures the API never answered (network down).
- **D-08 — One command still starts everything.** `docker compose up` builds and serves the UI
  (multi-stage: Node build stage → `nginx:*-alpine` runtime, pinned tags, non-root where the image
  allows) on a documented host port. `make rehearse` must prove the UI answers in the fresh clone
  and that a proxied API call through it succeeds.
- **D-09 — The documents stay true.** README gains a short UI section (what it is, the URL, that it
  is beyond the brief); the requirement-to-evidence map is not inflated with UI rows presented as
  brief items; pinned counts (`N ADRs`) change in the commit that changes them; the "Pending"
  section says what the UI does not do (no e2e browser tests unless the plan adds them, no i18n,
  no pagination — the API has none).

## Screens (the whole UI contract — no separate UI-SPEC)

1. **Auth** — register and log in (login is an OAuth2 password *form* post: `username` is the
   email). Log out.
2. **Task lists** — the caller's lists, each with `completion_percentage`; create, rename, delete.
3. **One list** — its tasks; create, edit (title/description/priority — read the OpenAPI document
   for the real fields), delete; change status through the dedicated `/status` endpoint, offering
   only moves the transition table allows or rendering the 409 when refused; filter by status and
   by priority; a completion bar fed by the response's whole-list `completion_percentage` (it must
   not be recomputed from the filtered items — ADR-009); assign/unassign from `GET /api/v1/users`
   (a bare JSON array).
4. **Assigned to me** — `GET /api/v1/tasks/assigned-to-me`.

The OpenAPI document (`create_app().openapi()` / `/openapi.json`) is the source of truth for
request and response shapes. Do not guess field names from this file.

## Process constraints (from the user's standing feedback)

- **Compact plans:** 3 plans, 4 at most, each large; behaviour-based acceptance criteria and test
  commands, not grep-count criteria over prose; no evidence/RED transcript files.
- The gsd-sdk state handlers regress `.planning/STATE.md` — hand-edit and diff instead.
- Commits carry no AI attribution trailer. Everything in English.
- All four backend gates stay green on every commit; `make docker-test` before the last commit of
  any plan that touches a file the test image copies.

## Deferred Ideas

- Playwright/browser e2e tests — only if the planner can fit them without a heavy CI cost;
  otherwise named in README "Pending".
- Dark mode, i18n, pagination, optimistic updates, a generated TypeScript client from OpenAPI
  (worth an ADR sentence as "what I'd do next").
