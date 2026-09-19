# Phase 5: Auth, Assignment & Notifications - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-19
**Phase:** 05-auth-assignment-notifications
**Areas discussed:** Assignee visibility matrix, Assignment API shape, Auth surface & account rules, Evaluator's first 5 minutes

---

## Assignee visibility matrix

### What can an assignee who does not own the list read?

| Option | Description | Selected |
|--------|-------------|----------|
| Only their tasks | GET on the task works; the parent list and its other tasks stay 404. Smallest surface, literal ASGN-02. | ✓ |
| Task + parent list header | Also GET the list (name, description, stats); the nested collection shows only their tasks. Stats would reveal counts of unseen tasks. | |
| Whole list read-only | One assignment makes the entire list readable. Discloses every other task. | |

**User's choice:** Only their tasks

### How does an assignee find the tasks assigned to them?

| Option | Description | Selected |
|--------|-------------|----------|
| `GET /api/v1/tasks/assigned-to-me` | One new flat read-only collection; `GET /task-lists` stays "lists I own" with its one-statement guarantee. | ✓ |
| No discovery route | The URL is learned from the invitation email only. | |
| Nested collection filters itself | `GET /task-lists/{id}/tasks` answers an assignee with only their tasks; same URL, different meaning per caller. | |

**User's choice:** `GET /api/v1/tasks/assigned-to-me`

### Which verbs answer 403 for an assignee on their task?

| Option | Description | Selected |
|--------|-------------|----------|
| PATCH, DELETE and assignee change | GET 200, status 200; generic PATCH 403, DELETE 403, assign/unassign 403; POST into the invisible list stays 404. | ✓ |
| Same, but the assignee may unassign themselves | Adds a "decline" rule not asked for by ASGN-01. | |

**User's choice:** PATCH, DELETE and assignee change

### How is the permission matrix proven?

| Option | Description | Selected |
|--------|-------------|----------|
| One parametrized matrix test over HTTP | Rows = routes, columns = owner / assignee / stranger / anonymous; doubles as documentation. | ✓ |
| Per-route tests, like Phase 4 | Consistent with existing tests; the matrix exists only implicitly. | |
| Both | Matrix plus unit-level per-role tests. | |

**User's choice:** One parametrized matrix test over HTTP
**Notes:** CONTEXT.md D-04 still expects per-role unit tests of `access.py` as the development path; the HTTP table is the contract.

---

## Assignment API shape

### How does an owner assign and unassign?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `PUT`/`DELETE .../assignee` | Mirrors ADR-048; the notification hangs off exactly one use case; generic PATCH stays side-effect-free. | ✓ |
| `assignee_id` in the generic PATCH | Fewer routes; UpdateTask would sometimes send email and the 403 rule becomes per-field. | |
| Single `PATCH .../assignee` with null | One route; a nullable body field does double duty. | |

**User's choice:** Dedicated `PUT`/`DELETE .../assignee`

### May a task be created already assigned?

| Option | Description | Selected |
|--------|-------------|----------|
| No — only through the dedicated route | POST keeps its Phase 4 schema; one place that notifies. | ✓ |
| Yes — optional `assignee_id` on create | Convenient; the side effect then lives in two use cases. | |

**User's choice:** No

### PUT with the user who is already the assignee?

| Option | Description | Selected |
|--------|-------------|----------|
| 200 no-op, no second email | Idempotent like the same-state status request; retries do not spam. | ✓ |
| 200 and notify again | Simplest rule; retries duplicate emails. | |

**User's choice:** 200 no-op, no second email

### Self-assignment and a non-existent assignee?

| Option | Description | Selected |
|--------|-------------|----------|
| Self-assign allowed + emailed; unknown user → 404 `user_not_found` | One rule; reuses `UserNotFoundError`; discloses nothing `GET /users` does not. | ✓ |
| Self-assign allowed, not emailed; unknown → 404 | One extra branch and test. | |
| Self-assign allowed + emailed; unknown → 422 | Treats it as invalid input; needs a new error path. | |

**User's choice:** Self-assign allowed + emailed; unknown user → 404

---

## Auth surface & account rules

### What does register return?

| Option | Description | Selected |
|--------|-------------|----------|
| 201 + the profile, no token | Login is a separate explicit step through the OAuth2 form. | ✓ |
| 201 + profile + access token | Auto-login; two routes issue tokens. | |

**User's choice:** 201 + the profile, no token

### Password policy and email identity?

| Option | Description | Selected |
|--------|-------------|----------|
| Length-only (8–128), email lower-cased | NIST 800-63B style; matches `uq_users_email_lower`; `full_name` trimmed 1–100. | ✓ |
| Composition rules too | Letter + digit; NIST advises against. | |
| You decide | Leave limits to planning. | |

**User's choice:** Length-only (8–128), email lower-cased

### A valid token whose user no longer exists?

| Option | Description | Selected |
|--------|-------------|----------|
| 401 — load the user on every request | One extra indexed SELECT; all 401 causes share one generic body. | ✓ |
| Trust the token, no lookup | Stateless; a deleted user's token works until expiry (cannot occur today). | |

**User's choice:** 401 — load the user on every request
**Notes:** Consequence recorded in CONTEXT.md D-11: the measured statement counts of ADR-054 move by one.

### `GET /api/v1/users`: who may call it and what does it return?

| Option | Description | Selected |
|--------|-------------|----------|
| Any authenticated user; id, full_name, email | Literal ASGN-03; the directory trade-off goes in an ADR. | ✓ |
| Authenticated; id and full_name only | Hides emails; deviates from ASGN-03. | |
| Authenticated; lookup by exact email | Strongest privacy; not "list users". | |

**User's choice:** Any authenticated user; id, full_name, email

---

## Evaluator's first 5 minutes

### How does an evaluator get a session once the seed is deleted?

| Option | Description | Selected |
|--------|-------------|----------|
| No seeded account; documented register → Authorize flow | Ships empty, no known credential, entrypoint back to its Phase 3 shape. | ✓ |
| Opt-in demo data via `make demo` | A script walks the assignment story through the real API. | |
| Seed demo accounts with a documented password | Fastest; ships a known password and contradicts Phase 4 D-02. | |

**User's choice:** No seeded account; documented register → Authorize flow

### What does the simulated invitation look like in the logs?

| Option | Description | Selected |
|--------|-------------|----------|
| One structured JSON log line | Dedicated logger; `event`, `to`, `subject`, `body`, `task_id`; greppable. | ✓ |
| Human-readable multi-line block | Easier on the eye; hard to grep; interleaves under uvicorn. | |
| You decide | Any format with to/subject/body. | |

**User's choice:** One structured JSON log line

### Where does the send happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in the use case, after commit, inside try/except | Deterministic; testable without sleeps or mocks; application layer owns the side effect. | ✓ |
| FastAPI BackgroundTasks | Faster response; side effect moves into presentation. | |

**User's choice:** Inline in the use case, after commit, inside try/except

### When is the Phase 4 review debt (CR-01, WR-01..03) fixed?

| Option | Description | Selected |
|--------|-------------|----------|
| Before Phase 5, via `/gsd-code-review 4 --fix` | Phase 5 plans are written against write paths that already serialise writers. | ✓ |
| Fold into Phase 5 as its first plan | One flow; the phase grows beyond its requirements. | |
| Leave for Phase 6 | The assignee as a second writer makes CR-01 easier to hit meanwhile. | |

**User's choice:** Before Phase 5, via `/gsd-code-review 4 --fix`

---

## Claude's Discretion

- JWT claims beyond `sub`/`exp`, clock-skew leeway, token response shape
- How login equalises unknown-email and wrong-password timing
- Route, schema and module layout; OpenAPI security-scheme wiring
- Shape of the `0002` revision and any `full_name` backfill
- How the HTTP harness authenticates (override vs real tokens), provided 401 legs use the real dependency
- Names of `Task` assignment mutators and of the new use cases
- Whether `TaskResponse` embeds an assignee summary beyond `assignee_id`

## Deferred Ideas

- Assignee self-unassign ("decline")
- `make demo` walkthrough script (possible Phase 7 revisit)
- Scoping `GET /users` to a team / lookup-by-email
- Login throttling, refresh tokens, revocation, password reset, email verification (v2)
- Assignee summary in `TaskResponse`; filters on `assigned-to-me`
