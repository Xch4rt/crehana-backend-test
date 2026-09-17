# Feature Research

**Domain:** Task list / task management REST API (Crehana Backend Technical Challenge deliverable)
**Researched:** 2026-09-17
**Confidence:** HIGH for HTTP/REST/FastAPI/RFC decisions (Context7 + RFCs + official docs); MEDIUM for "what evaluators expect" (inference from the brief + industry convention); MEDIUM for competitor API details (web sources, not re-verified against live API docs).

> **Framing note.** The "user" of this product is a *Crehana evaluator* skimming the repo for
> 5-15 minutes. Table stakes = things whose absence costs points. Differentiators = things that
> make the submission memorable. Anti-features = things that burn the 4-6h budget without
> earning a single point (and often *lose* points by signalling poor judgement about scope).

---

## Feature Landscape

### Table Stakes (Evaluators Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| CRUD task lists | Literal brief requirement 1.a | LOW | `POST/GET/PATCH/DELETE /api/v1/task-lists[/{list_id}]` |
| CRUD tasks inside a list | Literal brief requirement 1.a | LOW | Fully nested under the list — see "Resource Design" |
| Dedicated change-status endpoint | Brief lists it as a *separate* use case; a generic PATCH does not visibly satisfy it | LOW | `PATCH /task-lists/{list_id}/tasks/{task_id}/status` |
| Filter task listing by `status` and/or `priority` | Literal brief requirement 1.a | LOW | Enum-typed query params → free 422 with allowed values |
| Completion-percentage field on the task listing | Literal brief requirement ("un campo extra") | LOW | Response envelope, computed in SQL, not in Python |
| `status` / `priority` as constrained enums | Untyped free-text status = instant "no domain modelling" verdict | LOW | `str, Enum`; lowercase snake_case wire values |
| Explicit status transition rules in the domain | Brief demands "validaciones de negocio"; status is the only real state machine here | LOW-MED | Allowed-transitions map on the `Task` entity |
| Ownership scoping on every read and write | Without it, JWT is decoration; any user reads any list | MEDIUM | One reusable dependency resolving the list + authorization |
| Unique list name per owner | The most obvious "business validation" an evaluator will probe | LOW-MED | Use-case pre-check **and** DB unique index (race safety) |
| Assignee must be an existing user | Brief bonus 1.b; a dangling FK is the classic miss | LOW | 422 with field pointer, not 500 |
| Cascade delete list → tasks | Orphaned tasks after `DELETE /task-lists/{id}` is a visible bug | LOW | `ON DELETE CASCADE` + an integration test asserting it |
| JWT register + login, protected endpoints | Brief bonus 1.b | MEDIUM | OAuth2 password flow so Swagger "Authorize" works |
| Password hashing (never plaintext, never returned) | Non-negotiable baseline competence signal | LOW | `pwdlib[argon2]` — current FastAPI-docs recommendation |
| `GET /users/me` | Proves the token actually resolves to a principal | LOW | Also the natural smoke test in Swagger |
| Task assignment (assign responsible user) | Brief bonus 1.b | LOW | `assignee_id` field + explicit assign path |
| Simulated email notification on assignment | Brief bonus 1.b ("sin envío real") | LOW | Port + logging adapter + in-memory test adapter |
| Correct status codes (201/204/401/403/404/409/422) | REST design is an explicit evaluation criterion | LOW | See "Status Code Contract" |
| Consistent machine-readable error body | Brief demands "manejo de errores con excepciones personalizadas" | MEDIUM | RFC 9457 `application/problem+json` from one handler |
| Swagger UI that is actually usable end-to-end | `/docs` is the first thing an evaluator opens | LOW-MED | Tags, summaries, examples, working Authorize button |
| `GET /health` returning 200 without touching the DB | Expected of any containerised service | LOW | Liveness; unauthenticated |
| `created_at` / `updated_at` on every resource | Their absence reads as "toy model" | LOW | `TIMESTAMPTZ`, UTC |
| `/api/v1` path prefix | Costs nothing; signals API maturity | LOW | Single `APIRouter(prefix="/api/v1")` |

### Differentiators (Competitive Advantage for the Candidate)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Two notification adapters behind one port** (`LoggingEmailNotifier` + `InMemoryEmailNotifier`) | Turns "hexagonal architecture" from a folder claim into a demonstrable fact: tests assert on captured emails with zero mocking | LOW | The single highest value-per-minute item in the whole project |
| **Crisp 403-vs-404 authorization matrix** (invisible → 404, visible-but-not-permitted → 403) | Most candidates use one code for both; a documented matrix shows security reasoning | MEDIUM | Assignee can *see* + *change status*; only owner can edit/delete → 403 |
| **Counts returned alongside the percentage** (`total_tasks`, `completed_tasks`, `returned_count`) | Makes the completion figure self-verifying and kills the "over which set?" ambiguity in the response itself | LOW | Also makes the test assertions trivially readable |
| **Completion % computed in one aggregate query** (including on the list index) | Avoids the N+1 that almost every submission ships | MEDIUM | `GROUP BY` / `FILTER (WHERE status='completed')` |
| **Contract test: every error response is `application/problem+json`** | Proves the error contract is enforced, not aspirational | LOW | Catches stray `raise HTTPException` in routers |
| **`openapi.json` snapshot test** | Turns the API contract into a regression-guarded artifact | LOW | Fails the build on accidental contract drift |
| **RFC 9457 (not 7807) with `errors[]` extension + `trace_id`** | Citing the *current* RFC and mapping Pydantic `loc` to JSON Pointer shows the detail is real | MEDIUM | 9457 obsoletes 7807 (July 2023); wire-compatible |
| **Explicit-null semantics in PATCH** (clear `description` / `due_date` / `assignee_id`) | The single most common REST bug; handling it deliberately is a strong senior signal | MEDIUM | `exclude_unset=True` + sentinel for explicit `null` |
| **`GET /health/ready` wired into `docker-compose` healthcheck** | Makes `docker compose up` deterministic (API waits for a genuinely ready Postgres) | LOW | Directly serves the "reviewable in 5 minutes" core value |
| **Multi-value filters** (`?status=pending&status=in_progress`) | Beyond the brief but one line in FastAPI; documented OR-within-field / AND-across-fields semantics | LOW | `list[TaskStatus] \| None = Query(None)` |
| **`completed_at` set/cleared by the transition** | Gives the state machine an observable side effect worth testing | LOW | Set on entering `completed`, cleared on reopen |
| **UUID primary keys** | No cross-tenant id enumeration; pairs with the 404 policy | LOW | Cast to `str` for the JWT `sub` claim |
| **Request-id middleware feeding the problem `trace_id`** | Connects logs to error responses; cheap observability story | LOW | Echo as `X-Request-ID` response header |
| **Explicit `operation_id` per route** | Clean generated client method names; shows the OpenAPI output was actually inspected | LOW | Otherwise FastAPI emits `read_item_api_v1_items__item_id__get` |
| **Explicit invitation endpoint returning the rendered message** | Makes the "fake email" feature *visible in Swagger* instead of buried in stdout | LOW | `POST /task-lists/{list_id}/invitations` → `202 Accepted` |

### Anti-Features (Seductive, But Wrong Here)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Both `PUT` and `PATCH` for updates | "Complete REST coverage" | Doubles the route, schema, validation and test surface for zero extra points; forces "all fields required" semantics that fight partial updates | `PATCH` only; one `DECISION_LOG.md` paragraph explaining why |
| `status` writable through the generic task `PATCH` | "Consistency" | Two code paths into one state machine → duplicated or (worse) bypassed transition rules | Omit `status` from `TaskUpdate`; the dedicated endpoint is the only door |
| Real SMTP / SendGrid integration | "More impressive" | The brief explicitly says *simulated*; adds secrets, flaky tests, network in CI | Logging adapter + in-memory adapter behind a port |
| Celery / Redis / RabbitMQ for notifications | "Production-grade" | Two more containers, a worker process, async test complexity — for one log line | Synchronous call after commit; note "outbox pattern" as future work |
| Generic filter DSL (`?filter[status][eq]=pending`) | "Flexible API" | Hand-rolled parser, hand-rolled validation, injection surface, no OpenAPI typing | Typed enum query params; FastAPI documents and validates them for free |
| Pagination + sorting + full-text search | "Real APIs have them" | Out of scope per PROJECT.md; triples the listing tests and complicates the completion-% envelope | Document as "pending work" in README with the chosen approach (limit/offset) |
| Refresh tokens, logout/blacklist, password reset, email verification | "Complete auth" | Needs token storage, revocation, clock handling and a mail channel; explicitly Out of Scope | Short-lived access token + a "future work" section |
| Roles / permissions / scopes (`admin`, `member`) | "Enterprise-ready" | Nothing in the brief needs it; invents a domain the evaluator never asked about | Ownership + assignee capabilities only — already enough to justify 403 |
| List membership / sharing model | Implied by the word "invitation" | A whole join table, invite lifecycle, acceptance flow; blows the time budget | Invitation is a *simulated message only*, creates no membership — state this explicitly |
| `cancelled` / `archived` / `blocked` task statuses | "Richer domain" | Makes the completion-% denominator ambiguous (do cancelled tasks count?) and adds transition cases to test | Three statuses; list the extras as documented future work |
| Integer priorities (1-4) | Copying Todoist | Todoist's own API inverts them (API `4` = UI `P1`), a documented, long-lived source of client bugs | String enum `low\|medium\|high`; store an ordinal only if sorting is added |
| Soft delete (`deleted_at`) | "Never lose data" | Every query needs a filter, uniqueness constraints get messy, `DELETE` semantics blur | Hard delete + cascade; mention soft delete as future work |
| Hand-written `API.md` reference | "Better docs" | Duplicates OpenAPI and drifts within a day | README links to `/docs`; commit `openapi.json` only as a snapshot test fixture |
| CORS middleware | Reflex | No frontend exists (explicitly Out of Scope); permissive CORS invites a security comment | Omit; one line in DECISION_LOG saying why |
| Prometheus metrics / uptime / memory in `/health` | "Observability" | Out of scope; a heavy health endpoint slows the container healthcheck | `/health` (liveness) + `/health/ready` (DB ping) only |
| WebSockets / real-time task updates | "Modern" | Nothing in the brief; a second protocol to test and document | Not mentioned at all |

---

## Design Decisions Per Feature

### 1. Resource Design and URL Structure

**Recommendation — full nesting, max two levels:**

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/users/me
GET    /api/v1/users                                   # assignable users (challenge-scope simplification)

GET    /api/v1/task-lists                              # owner's lists + completion stats
POST   /api/v1/task-lists
GET    /api/v1/task-lists/{list_id}
PATCH  /api/v1/task-lists/{list_id}
DELETE /api/v1/task-lists/{list_id}

GET    /api/v1/task-lists/{list_id}/tasks              # filters + completion percentage
POST   /api/v1/task-lists/{list_id}/tasks
GET    /api/v1/task-lists/{list_id}/tasks/{task_id}
PATCH  /api/v1/task-lists/{list_id}/tasks/{task_id}
DELETE /api/v1/task-lists/{list_id}/tasks/{task_id}
PATCH  /api/v1/task-lists/{list_id}/tasks/{task_id}/status
PUT    /api/v1/task-lists/{list_id}/tasks/{task_id}/assignee     # assign
DELETE /api/v1/task-lists/{list_id}/tasks/{task_id}/assignee     # unassign
POST   /api/v1/task-lists/{list_id}/invitations                  # simulated email

GET    /health
GET    /health/ready
```

**Why full nesting over the hybrid (`/task-lists/{id}/tasks` for the collection, flat
`/tasks/{task_id}` for the item):** the hybrid is arguably the better general-purpose design —
a task has one canonical identity and the nested id is redundant — and the community leans that
way for deep hierarchies. But for *this* deliverable full nesting wins on three counts:

1. It mirrors the brief's wording ("tareas **dentro de** una lista") literally.
2. Every task route then carries the list scope, so authorization is **one** shared dependency
   (`resolve_list_for_user`) reused by seven routes — less code, fewer ways to forget a check.
3. It makes the `list_id`/`task_id` mismatch case explicit and testable (task exists but belongs
   to another list → 404, not a silent cross-list read).

Record the tradeoff in `DECISION_LOG.md`; naming the alternative you rejected is worth more than
the choice itself. Do **not** nest three levels deep.

**Naming:** plural, kebab-case (`task-lists`), lowercase, no trailing slash, no verbs in paths.
`/task-lists` over `/lists` because the URL then maps 1:1 onto the `TaskList` domain entity.
Configure FastAPI consistently so `/task-lists` and `/task-lists/` do not diverge.

**Complexity:** LOW. **Dependencies:** none — this is the first thing to fix, everything else hangs off it.

### 2. Status Code Contract

| Situation | Code | Notes |
|-----------|------|-------|
| Create list / task / user | `201 Created` | + `Location` header pointing at the new resource |
| Read, update, change status, assign | `200 OK` | Return the full updated representation, not `{"ok": true}` |
| Delete list / task / unassign | `204 No Content` | Empty body — assert `response.content == b""` |
| Simulated invitation accepted | `202 Accepted` | Correct semantics for "handed off, not completed" |
| Malformed JSON / bad path param type | `400` / `422` | Framework-level; still must render as problem+json |
| Missing / invalid / expired token | `401 Unauthorized` | **Must** include `WWW-Authenticate: Bearer` |
| Authenticated, resource visible, action not permitted | `403 Forbidden` | e.g. assignee tries to delete the task |
| Resource does not exist **or** is not visible to the caller | `404 Not Found` | Deliberate: no existence disclosure across tenants |
| Duplicate list name for the owner; duplicate email on register | `409 Conflict` | Uniqueness = conflict, not validation |
| Forbidden status transition | `409 Conflict` | State conflict; include `from`/`to` as problem extensions |
| Schema violation, bad enum value, empty title, past due date, unknown assignee | `422 Unprocessable Content` | Field-level `errors[]` in the problem body |
| Readiness probe with DB down | `503 Service Unavailable` | Only on `/health/ready` |
| Unhandled exception | `500` | Logged with traceback + `trace_id`; body leaks nothing |

**The 403-vs-404 decision (make this explicit in `DECISION_LOG.md`).** Sources genuinely
conflict: 403 is semantically honest, while GitHub deliberately returns 404 for private
resources to avoid confirming their existence. Take both, split by *visibility*:

- Not visible to the caller (not owner, not assignee) → **404**, always, for every verb.
- Visible but the action is not permitted (assignee attempting edit/delete) → **403**.

This yields a testable authorization matrix instead of a blanket rule, and gives an honest
answer to the inevitable "why 404 and not 403?" interview question.

**Complexity:** LOW (the table) / MEDIUM (the visibility rule). **Depends on:** JWT auth, assignment.

### 3. PUT vs PATCH

**`PATCH` only**, with `application/json` bodies (not JSON Patch, not JSON Merge Patch — a plain
partial object, which is what every mainstream API means by PATCH).

- `TaskListUpdate` / `TaskUpdate` have **all fields optional**; apply with
  `payload.model_dump(exclude_unset=True)`.
- `TaskUpdate` deliberately **excludes `status`** (dedicated endpoint) and **excludes
  `assignee_id`** if you ship the `/assignee` sub-resource — one writer per field, one rule set.
- **Explicit null:** `{"description": null}` must clear the field, while an absent key must leave
  it untouched. `exclude_unset=True` distinguishes the two; the clean typed form is
  `description: str | None | UnsetType = Unset` (a sentinel) or reading
  `payload.model_fields_set`. Cover it with a test — this is the differentiator, not the plumbing.
- An empty PATCH body (`{}`) → `200` with the resource unchanged (idempotent no-op) rather than
  a 400. Document the choice.

Skipping `PUT` is defensible (`PUT` requires full-replacement semantics and delete-on-omit),
but only if it is *documented*. An undocumented missing `PUT` looks like an oversight; a
documented one looks like a decision.

**Complexity:** LOW (basic PATCH) / MEDIUM (explicit-null handling).

### 4. Dedicated Status-Change Endpoint

```
PATCH /api/v1/task-lists/{list_id}/tasks/{task_id}/status
Body:  {"status": "in_progress"}
200 →  full TaskResponse (with updated status + completed_at)
409 →  problem+json, type ".../invalid-status-transition", extensions {"from": "...", "to": "..."}
```

`PATCH` on a `/status` sub-resource rather than `POST /tasks/{id}/complete`-style action verbs:
the transition here has no side effects beyond the field and a timestamp, so the action-endpoint
pattern (reserved for transitions with real consequences) is not warranted — and one endpoint
covers all transitions instead of three verb routes. Note that Todoist takes the opposite,
action-endpoint route (`/tasks/{id}/close`, `/tasks/{id}/reopen`), so the alternative is
defensible; say so in one line in `DECISION_LOG.md`. *(Todoist detail: MEDIUM confidence.)*

**Complexity:** LOW. **Depends on:** Task CRUD, `TaskStatus` enum, transition rules.

### 5. Status / Priority Enums and Transition Rules

```python
class TaskStatus(str, Enum):      # 3 values, no more
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class TaskPriority(str, Enum):    # default MEDIUM
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

Wire format: lowercase snake_case strings. String enums over Todoist-style integers — Todoist's
API values are inverted relative to its own UI (API `4` = UI `P1`), a well-documented and
long-lived source of client bugs. Strings are self-describing in Swagger and in logs.

**Persistence:** store as `VARCHAR` with a `CHECK` constraint (or SQLAlchemy
`Enum(..., native_enum=False)`), not a native PostgreSQL `ENUM` type — altering PG enums in
migrations is painful and offers nothing here.

**Allowed transitions (put this map on the `Task` entity, in the domain layer):**

```
pending      → in_progress, completed
in_progress  → pending, completed
completed    → in_progress            # "reopen"
completed    → pending                # FORBIDDEN → 409
X            → X                      # idempotent no-op → 200, no timestamp change
```

Rationale to document: work resumes before it is un-started, so reopening lands in
`in_progress`. Side effect: entering `completed` sets `completed_at = now()`; leaving it clears
`completed_at` back to `NULL`. That observable effect is what makes the state machine worth
testing. Same-status is a **no-op 200**, not a 409 — friendlier and simpler to assert.

**Complexity:** LOW-MED. **Depends on:** Task entity.

### 6. Completion-Percentage Semantics

**Definition:** `completed_tasks / total_tasks * 100`, computed over **all tasks in the list**,
**independent of the active filters**, rounded to 2 decimals. **Empty list → `0.0`** (never
`null`, never a division error, never `100`).

**Why whole-list and not the filtered subset** — this is the ambiguity flagged in PROJECT.md,
and the argument is decisive: a subset-scoped percentage is degenerate, since
`?status=completed` would always return `100.0` and `?status=pending` always `0.0`. The
percentage is a property of the **list**, filters are a property of the **view**. Write exactly
that sentence in `DECISION_LOG.md`.

**Response envelope** for `GET /task-lists/{list_id}/tasks` (the brief's "campo extra" is
naturally an envelope field):

```json
{
  "list_id": "b0e1...",
  "completion_percentage": 33.33,
  "total_tasks": 3,
  "completed_tasks": 1,
  "returned_count": 2,
  "filters": { "status": ["pending", "in_progress"], "priority": null },
  "items": [ /* TaskResponse[] */ ]
}
```

Returning `total_tasks` / `completed_tasks` / `returned_count` makes the number self-verifying
and removes any doubt about which set it covers — cheap, and it reads beautifully in tests.
Echoing `filters` is optional polish.

Also expose `completion_percentage` on `GET /task-lists/{list_id}` and on `GET /task-lists`.
**The index is the trap:** computing it per list in Python is an N+1. Use a single query with
`COUNT(*) FILTER (WHERE status = 'completed')` grouped by list, and cast to avoid integer
division. Return `float` rounded to 2 decimals (not `Decimal`, which drags in serialization
questions for no benefit here).

**Complexity:** LOW (single list) / MEDIUM (aggregate on the index without N+1).
**Depends on:** Task CRUD, `TaskStatus`.

### 7. Filter Query Parameter Design

```
GET /api/v1/task-lists/{list_id}/tasks
      ?status=pending&status=in_progress
      &priority=high
```

- Parameters are **enum-typed** (`list[TaskStatus] | None = Query(None)`), so FastAPI validates
  them, documents the allowed values in Swagger, and returns 422 listing them — for free.
- Semantics: **OR within a field, AND across fields**. Document in the route description.
- Both absent → all tasks in the list. Unknown query params are ignored (FastAPI default);
  do not build strict-unknown-param rejection.
- Canonical values are lowercase; do **not** add case-insensitive coercion — keep the contract
  strict and the error message instructive.
- Single-value (`status=pending`) must keep working if you ship multi-value — `list[...]` handles
  the one-element case naturally.
- Deliberately **not** offered: `assignee_id` filter, text search, date-range filters, sorting,
  pagination. All are scope creep against a brief that names exactly two filters. If you feel
  the pull, put them in the README "pending work" section with the approach you would take.

**Complexity:** LOW. **Depends on:** enums, Task CRUD.

### 8. Business Validations Evaluators Will Probe

| # | Rule | Response | Notes |
|---|------|----------|-------|
| 1 | List `name`: required, trimmed, 1-120 chars, not blank | 422 | Strip before validating; `"   "` must fail |
| 2 | List `name` unique per owner, case-insensitive | 409 | Use case pre-check **+** unique index on `(owner_id, lower(name))`; catch `IntegrityError` → 409 |
| 3 | Task `title`: required, trimmed, 1-200 chars | 422 | |
| 4 | Task `description`: optional, ≤ 2000 chars | 422 | Nullable; clearable via explicit `null` |
| 5 | `due_date`: optional; if present on create, must be ≥ today | 422 | Use `date` (calendar day), not `datetime` — sidesteps timezone ambiguity entirely; document it |
| 6 | `due_date` on update: rejected if in the past; **never** retro-invalidates existing rows | 422 | Validation is on input, not an invariant sweep |
| 7 | `assignee_id` must reference an existing user | 422 | Field-level pointer; not a 404 (the task URL *does* exist), not a 500 from an FK violation |
| 8 | Task must be created inside an existing, visible list | 404 | Nonexistent **or** other user's list → same 404 |
| 9 | `task_id` must belong to `list_id` | 404 | Guards the nested-URL mismatch case |
| 10 | Every read/write scoped to the authenticated principal | 404 / 403 | Per the visibility matrix in §2 |
| 11 | Deleting a list deletes its tasks | 204 | `ON DELETE CASCADE` + an explicit integration test |
| 12 | Register email: valid format, unique | 409 on duplicate | `EmailStr`; store lowercased |
| 13 | Register password: min length (≥ 8), never echoed | 422 | Never return the hash in any response model |
| 14 | Status transitions per §5 | 409 | Enforced in the domain entity, not the router |
| 15 | Duplicate task titles within a list are **allowed** | — | A deliberate *non*-validation; say so in DECISION_LOG. Over-validating is as wrong as under-validating |

Validations belong in two places with different jobs: **Pydantic** for shape/format
(422, automatic), **domain entities / use cases** for business rules (custom exceptions, mapped
to 409/422 by the single handler). Do not raise `HTTPException` from the domain — that is the
exact coupling the brief's layered-architecture requirement is testing for.

**Complexity:** MEDIUM overall. **Depends on:** JWT auth (for anything ownership-related).

### 9. JWT Register / Login Flow

```
POST /api/v1/auth/register   JSON {email, password, full_name?}  → 201 UserResponse
POST /api/v1/auth/login      form-encoded {username, password}   → 200 {access_token, token_type, expires_in}
GET  /api/v1/users/me        Bearer token                        → 200 UserResponse
```

**Use the OAuth2 password flow so the Swagger "Authorize" button works.** This is the detail
that makes the whole API demoable in 60 seconds, and it is non-obvious. Verified against the
FastAPI docs (HIGH confidence):

- Login must depend on `OAuth2PasswordRequestForm` → the body is **form-encoded** with fields
  literally named `username` and `password` (the `username` field carries the email; document
  this, it surprises people).
- Declare `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`. `tokenUrl` does
  *not* create the endpoint; it tells the OpenAPI schema where Swagger should post credentials.
  A wrong `tokenUrl` is the #1 reason the Authorize button silently fails.
- Response must be `{"access_token": "...", "token_type": "bearer"}` — Swagger parses exactly
  those keys.

**Implementation choices (all verified from current FastAPI docs):**

- **Hashing:** `pwdlib` with Argon2 (`PasswordHash.recommended()`) — this is what the FastAPI
  docs now use, and it dodges the well-known `passlib` + `bcrypt 4.x` breakage that still bites
  tutorials. Using it is itself a small currency signal.
- **JWT:** `PyJWT` (`import jwt`), HS256. Claims: `sub` (user id **cast to `str`** — recent PyJWT
  validates `sub` as a string; *MEDIUM confidence, verify against the installed version*), `exp`,
  `iat`. Expiry 30-60 minutes.
- **Timing safety:** on unknown username, still verify against a dummy hash before returning —
  the FastAPI docs example does this to avoid a user-enumeration timing oracle. Cheap, and worth
  a comment in the code.
- **Errors:** wrong credentials → `401` with `WWW-Authenticate: Bearer` and a message that does
  **not** distinguish "no such user" from "wrong password". Expired token → `401` with a distinct
  problem `type` so clients can tell it apart.
- **Secret** from an env var, with `.env.example` committed and the real value never in git.
  A fixed test secret in `pytest` fixtures.
- **Public routes:** `/auth/register`, `/auth/login`, `/health*`, `/docs`, `/redoc`,
  `/openapi.json`. Everything else requires the token. Prefer a router-level
  `dependencies=[Depends(get_current_user)]` over per-route decoration — one place to forget
  instead of fifteen.
- **`GET /api/v1/users`** (authenticated, id + email + name only): without it, nobody can
  discover a valid `assignee_id` and the assignment feature is undemoable in Swagger. Flag it in
  the README as a challenge-scope simplification that a real product would scope to collaborators.

**Complexity:** MEDIUM. **Blocks:** ownership rules, assignment, notifications.

### 10. Simulated Email Invitation

**Shape — port + two adapters (this is the architectural showpiece):**

```
application/ports/notification.py      NotificationPort (Protocol)
                                       send(message: EmailMessage) -> None
infrastructure/notifications/logging_notifier.py     LoggingEmailNotifier   # app runtime
infrastructure/notifications/in_memory_notifier.py   InMemoryEmailNotifier  # tests, .sent[]
```

`EmailMessage` is a domain-level value object: `to`, `subject`, `body`, `template`, `sent_at`.
The use case depends only on the `Protocol`; the adapter is injected via FastAPI
`dependency_overrides` in tests. Tests then assert `notifier.sent[0].to == "..."` with **no
mocking or patching** — which is precisely how you prove the hexagonal claim instead of asserting
it in a README.

**Triggers:**

1. **Primary (implicit):** whenever a task acquires a *new* assignee — on create with
   `assignee_id`, and on assign/re-assign. Re-assigning to the *same* user sends nothing
   (assert this; it is the kind of edge case that reads as care).
2. **Secondary (explicit, differentiator):** `POST /api/v1/task-lists/{list_id}/invitations`
   with `{"email": "..."}` → `202 Accepted`, returning the rendered message so the simulation is
   visible directly in Swagger rather than buried in container logs. Be explicit in the docs that
   it creates **no** membership and grants **no** access — it is a message, nothing else.
   This keeps the word "invitación" from dragging a whole sharing model into scope.

**Rules:**

- Fire **after** the DB transaction commits, and **never** let a notification failure roll back
  or fail the request — wrap in try/except, log the error. A 500 on "task assigned successfully
  but the fake email logged badly" is an own goal.
- Keep it **synchronous inside the use case**. Do not reach for `BackgroundTasks` (that would
  leak a FastAPI type into the application layer) and do not add a queue. One line in
  `DECISION_LOG.md`: "a production implementation would persist to an outbox and dispatch
  asynchronously".
- Log as a single structured line (`event=email.simulated to=... template=task_assigned`) so it
  is greppable during the demo.
- Message content: recipient, task title, list name, who assigned it, due date.

**Complexity:** LOW. **Depends on:** assignment, user lookup. **Highest value per minute in the project.**

### 11. RFC 9457 Error Contract

Cite **RFC 9457** (July 2023), noting it **obsoletes RFC 7807** — PROJECT.md currently says 7807;
update the wording. The wire format is compatible, so this is a citation upgrade, not rework, and
it reads as genuine currency. Verified HIGH against the RFC.

- Media type: `application/problem+json` on **every** error response.
- Members: `type` (URI), `title`, `status`, `detail`, `instance`. RFC 9457 explicitly allows
  **non-dereferenceable** `type` URIs, so stable identifiers such as
  `urn:crehana:task-api:error:list-name-conflict` are compliant — no need to host a docs page.
  Reserve `about:blank` for plain status-code-only errors.
- Extensions to add: `errors: [{pointer, detail, type}]` for field-level validation (map Pydantic
  `loc` → a JSON Pointer such as `/body/title`), and `trace_id` correlating to the request-id
  middleware and the logs.
- RFC 9457 guidance: when several things are wrong, surface the **most relevant/urgent** problem
  at the top level and put the rest in the extension.

**Single registration point** — `register_exception_handlers(app)` covering:

| Handler | Produces |
|---------|----------|
| `DomainError` subclasses (`ListNameAlreadyExists`, `InvalidStatusTransition`, `TaskNotFound`, `NotListOwner`, `UnknownAssignee`, …) | Mapped status + stable `type` URI |
| `RequestValidationError` | 422 problem with `errors[]` (override FastAPI's default `{"detail":[...]}`) |
| `StarletteHTTPException` | Covers 404-on-unknown-route and 405 so *those* are problem+json too |
| `Exception` (catch-all) | 500, traceback logged server-side, body exposes only `trace_id` |

Domain exceptions must carry **zero** HTTP knowledge — no status codes in the domain layer. The
mapping table lives in the presentation layer, which is exactly the boundary the automated
architecture test should be protecting.

**Declare the problem schema in OpenAPI** (`responses={409: {"model": Problem, ...}}` or a
`responses` default on the router) so `/docs` shows error shapes. Most submissions document only
happy paths.

**Contract test:** parametrize over a list of (request, expected status) error cases and assert
`content-type == "application/problem+json"` plus the presence of `type`/`title`/`status`. This
catches the classic regression where somebody leaves a `raise HTTPException(404, "not found")`
in a router and quietly breaks the contract.

**Complexity:** MEDIUM. **Build it in the first implementation phase** — retrofitting an error
contract over finished routers costs multiples of building it first.

### 12. OpenAPI / Swagger Quality

`/docs` is the evaluator's first impression. Table stakes:

- `FastAPI(title=..., description=..., version=..., openapi_tags=[...])` with a description that
  explains auth in two lines ("register → login → Authorize").
- Tags per router (`auth`, `users`, `task-lists`, `tasks`, `health`) with descriptions.
- `summary` + `description` on every route (the docstring becomes the description — write real
  ones, including filter and transition semantics).
- `response_model` everywhere; explicit `status_code=201` / `204`; `response_description`.
- Request/response **examples** via `Field(examples=[...])` / `model_config["json_schema_extra"]`
  — a Swagger "Try it out" that is pre-filled with valid data is dramatically more demoable.
- Working `Authorize` button (see §9).
- Separate `Create` / `Update` / `Response` schemas. Never expose the ORM model or `password_hash`.

Differentiators: explicit `operation_id`s; documented error responses per route; an
`openapi.json` snapshot test; `servers` metadata.

**Complexity:** LOW-MED, spread across the endpoint work. **Enhances:** every feature.

### 13. Health Endpoints

```
GET /health        → 200 {"status":"ok","version":"1.0.0"}        # liveness, no DB, unauthenticated
GET /health/ready  → 200 {"status":"ready","checks":{"database":"ok"}}
                   → 503 problem+json when SELECT 1 fails         # readiness
```

Separating liveness from readiness is the standard recommendation, and here it has a concrete
payoff rather than being ceremony: point the `docker-compose` API healthcheck at `/health/ready`
so `depends_on: condition: service_healthy` actually gates on a reachable database. That is what
makes the PROJECT.md promise of a working one-command `docker compose up` true on a cold machine.

Keep both unauthenticated, exclude them from the versioned prefix (`/health`, not
`/api/v1/health`) so probes are stable across API versions, and keep the readiness check to a
single cheap `SELECT 1` with a short timeout. No metrics, no uptime, no memory stats.

**Complexity:** LOW. **Enhances:** Docker startup reliability.

---

## Feature Dependencies

```
[User entity + password hashing]
    └──requires──> nothing
        └──enables──> [JWT register/login]
                          └──enables──> [Ownership scoping (404 policy)]
                          │                 └──enables──> [Task list CRUD]
                          │                                   └──enables──> [Task CRUD]
                          │                                        ├──enables──> [Status enum + transitions]
                          │                                        │                 └──enables──> [Status endpoint]
                          │                                        ├──enables──> [Priority enum]
                          │                                        ├──enables──> [Filters]  (needs both enums)
                          │                                        └──enables──> [Completion percentage]
                          └──enables──> [GET /users/me] + [GET /users]
                                            └──enables──> [Task assignment]
                                                              └──enables──> [Simulated email notification]
                                                              └──enables──> [403 assignee-capability rule]

[RFC 9457 error contract] ──enhances──> every endpoint      (build FIRST)
[OpenAPI polish]          ──enhances──> every endpoint      (build alongside)
[Health endpoints]        ──independent──> (consumed by docker-compose healthcheck)

[PUT full replacement]        ──conflicts──> [PATCH partial update]
[status writable via PATCH]   ──conflicts──> [dedicated status endpoint as single source of truth]
[completion % over filtered subset] ──conflicts──> [completion % as a list property]
[list membership model]       ──conflicts──> [invitation as a stateless simulated message]
```

### Dependency Notes

- **Ownership scoping requires JWT auth:** there is no `owner_id` to compare against until a
  principal exists. Corollary: the `task_lists.owner_id` FK must exist from the first migration —
  bolting it on later means rewriting every repository method and every fixture.
- **Completion percentage requires the status enum, not just Task CRUD:** the definition of
  "completed" is the enum member. Ship the enum before the aggregate query.
- **Filters require both enums:** shipping filters before `TaskPriority` exists means writing the
  query-param layer twice.
- **Notifications require assignment:** the trigger is the assignment event. Without assignment
  the only remaining trigger is the explicit invitation endpoint, which is the weaker demo.
- **The 403 rule requires assignment:** with owner-only access, every denial is a 404 and `403`
  never appears in the API. If assignment is cut, the 403 branch must be cut too — do not ship a
  status code that no test can reach.
- **The error contract enhances everything and must come first:** every router written before the
  handler exists will contain `raise HTTPException`, and retrofitting means touching every file.
- **Health is independent but gates Docker:** build it in the infrastructure phase, before
  compose orchestration, or the healthcheck has nothing to call.

---

## MVP Definition

### Launch With (the submission itself)

Everything the brief names, mandatory and bonus, since PROJECT.md scopes all three bonuses in.

- [ ] RFC 9457 error contract + custom domain exceptions — every later endpoint depends on it
- [ ] User + JWT register/login (OAuth2 password flow, Argon2 hashing) — gates ownership
- [ ] Task list CRUD with ownership scoping and unique-name-per-owner — brief 1.a
- [ ] Task CRUD nested in a list, cascade delete — brief 1.a
- [ ] `TaskStatus` / `TaskPriority` enums + transition rules + `completed_at` — makes "business validations" real
- [ ] Dedicated status-change endpoint — brief 1.a names it separately
- [ ] Filtered task listing + completion percentage envelope with counts — brief 1.a
- [ ] Task assignment (assignee must exist) + `GET /users` for discoverability — brief 1.b
- [ ] Simulated email via port + logging adapter + in-memory test adapter — brief 1.b
- [ ] `/health` + `/health/ready` wired into compose — makes the one-command demo reliable
- [ ] Swagger with working Authorize, tags, summaries, examples — the first impression

### Add After Validation (documented as "pending work" in the README)

- [ ] Pagination + sorting on the task listing — trigger: any list exceeding ~100 tasks
- [ ] `assignee_id` and `due_date` range filters — trigger: real multi-user usage
- [ ] Refresh tokens + logout/revocation — trigger: a real client with sessions
- [ ] List sharing / membership model — trigger: invitations needing to actually grant access
- [ ] Transactional outbox for notifications — trigger: replacing the fake sender with real email

### Future Consideration

- [ ] Real email delivery (SMTP/SendGrid) — explicitly Out of Scope per the brief
- [ ] Roles and permissions beyond owner/assignee — not requested; invents domain
- [ ] Soft delete / audit trail — no requirement; complicates every query
- [ ] Recurring tasks, subtasks, labels, comments, attachments — full product scope, not a challenge
- [ ] WebSocket / webhook notifications — a second protocol to test and document

---

## Feature Prioritization Matrix

*"User value" read as "evaluator value" — points gained or lost in review.*

| Feature | Evaluator Value | Implementation Cost | Priority |
|---------|-----------------|---------------------|----------|
| Task list CRUD + ownership | HIGH | LOW | P1 |
| Task CRUD nested in a list | HIGH | LOW | P1 |
| Status enum + transition rules | HIGH | LOW | P1 |
| Dedicated status endpoint | HIGH | LOW | P1 |
| Filters by status/priority | HIGH | LOW | P1 |
| Completion percentage (+ counts, whole-list semantics) | HIGH | LOW | P1 |
| JWT register/login with working Swagger Authorize | HIGH | MEDIUM | P1 |
| RFC 9457 error contract from one handler | HIGH | MEDIUM | P1 |
| Notification port + 2 adapters | HIGH | LOW | P1 |
| Task assignment + assignee existence check | HIGH | LOW | P1 |
| Business validations (unique name, due date, cascade) | HIGH | MEDIUM | P1 |
| Swagger polish (tags, summaries, examples) | HIGH | LOW | P1 |
| `/health` + `/health/ready` + compose healthcheck | MEDIUM | LOW | P1 |
| `GET /users/me` + `GET /users` | MEDIUM | LOW | P1 |
| 403-vs-404 visibility matrix | HIGH | MEDIUM | P2 |
| Explicit-null PATCH semantics | MEDIUM | MEDIUM | P2 |
| Aggregate completion % on the list index (no N+1) | MEDIUM | MEDIUM | P2 |
| problem+json contract test | MEDIUM | LOW | P2 |
| `openapi.json` snapshot test | MEDIUM | LOW | P2 |
| Explicit invitation endpoint (202) | MEDIUM | LOW | P2 |
| Multi-value filters | LOW | LOW | P2 |
| Request-id middleware + `trace_id` | LOW | LOW | P3 |
| Explicit `operation_id`s | LOW | LOW | P3 |
| Pagination / sorting | LOW | MEDIUM | P3 (documented only) |

**Priority key:** P1 = must ship. P2 = ship if the P1 set is green. P3 = document as pending work.

**Cut order if time runs short:** P3 first, then multi-value filters, then the invitation
endpoint, then the 403 matrix (fall back to 404 everywhere — and update the docs, do not leave an
unreachable status code documented). Never cut: tests, the error contract, or the README, since
they are explicit brief requirements.

---

## Competitor Feature Analysis

*Reference points for defending design choices in the DECISION_LOG. Details from web sources;
MEDIUM confidence, not re-verified against live API docs.*

| Feature | Todoist | Asana | Google Tasks | Our Approach |
|---------|---------|-------|--------------|--------------|
| Status model | Action endpoints `/tasks/{id}/close` and `/reopen` | Boolean `completed` + `completed_at` | `status` enum: `needsAction` \| `completed` | 3-value enum + `completed_at`, one `PATCH .../status` endpoint |
| Priority model | Integer 1-4, **inverted** vs the UI (API `4` = UI `P1`) | Custom-field enums keyed by gid | None | String enum `low\|medium\|high`, default `medium` — no inversion trap possible |
| Nesting | Flat `/tasks?project_id=` | Flat `/tasks?project=` | Nested `/lists/{tasklist}/tasks/{task}` | Full nesting, matching the brief's wording and unifying the auth dependency |
| Completion % | Not exposed | Not exposed | Not exposed | Explicit envelope field + counts — the brief's differentiating ask |
| Update verb | `POST` on the item | `PUT` | `PATCH` / `PUT` | `PATCH` only, documented |
| Assignment | `assignee_id` | `assignee` gid | Not supported | `assignee_id` via `PUT`/`DELETE` on an `/assignee` sub-resource |

**Takeaway:** no mainstream task API exposes a completion percentage, so there is no convention to
copy — which makes the whole-list-vs-filtered-subset choice a genuine design call and therefore
worth a paragraph of reasoning in `DECISION_LOG.md`. Meanwhile Todoist's inverted integer
priorities are a concrete, citable argument for string enums, and Google Tasks is a precedent for
full nesting.

---

## Sources

**HIGH confidence**
- FastAPI official docs via Context7 (`/websites/fastapi_tiangolo`): OAuth2 password flow,
  `OAuth2PasswordBearer(tokenUrl=...)`, `OAuth2PasswordRequestForm`, PyJWT + `pwdlib`/Argon2,
  dummy-hash timing defence, `RequestValidationError` handler override, `exclude_unset=True`
  partial updates — https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt,
  https://fastapi.tiangolo.com/tutorial/handling-errors,
  https://fastapi.tiangolo.com/tutorial/body-updates
- RFC 9457 *Problem Details for HTTP APIs* (July 2023, obsoletes RFC 7807): members, media type,
  problem-type registry, non-dereferenceable `type` URIs, most-relevant-problem guidance —
  https://www.rfc-editor.org/rfc/rfc9457.html

**MEDIUM confidence**
- 403-vs-404 information-disclosure tradeoff, incl. GitHub's deliberate 404 for private
  resources — https://docs.github.com/en/rest (troubleshooting), plus corroborating community
  write-ups
- Nested vs flat sub-resource design tradeoffs —
  https://www.moesif.com/blog/technical/api-design/REST-API-Design-Best-Practices-for-Sub-and-Nested-Resources/
- State-transition endpoint design (`PATCH /x/status` vs `POST /x/actions/y`) —
  https://restful-api-design.readthedocs.io/en/latest/methods.html,
  https://blog.postman.com/http-patch-method/
- Liveness vs readiness separation for FastAPI/Docker —
  https://patrykgolabek.dev/guides/fastapi-production/health-checks/
- Todoist inverted priority integers —
  https://www.todoist.com/help/articles/introduction-to-priorities-Wy82Jp,
  https://github.com/Doist/todoist-python/issues/18
- Asana boolean `completed` + `completed_at` — https://developers.asana.com/reference/tasks
- RFC 9457 adoption commentary —
  https://swagger.io/blog/problem-details-rfc9457-doing-api-errors-well/

**LOW confidence (flagged inline, verify before relying on)**
- Todoist's `/tasks/{id}/close` + `/reopen` action endpoints (training data; not re-verified)
- Google Tasks' nested `/lists/{tasklist}/tasks/{task}` URL shape (training data)
- PyJWT ≥ 2.10 validating `sub` as a string — verify against the version you pin

---
*Feature research for: task list / task management REST API (Crehana Backend Technical Challenge)*
*Researched: 2026-09-17*
