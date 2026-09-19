# Phase 4: Task Lists & Tasks - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-18
**Phase:** 04-task-lists-tasks
**Areas discussed:** Actor before auth, PATCH semantics, Response shapes, Proof & gates

---

## Actor before auth

| Option | Description | Selected |
|--------|-------------|----------|
| Seam dependency | `get_current_actor()` returns a fixed demo user; Phase 5 swaps only its body | ✓ |
| Temporary X-User-Id header | Caller supplies a UUID header; an impersonation door to remove later | |
| Pull minimal auth into Phase 4 | Register and login now; blurs the roadmap boundary | |

| Option | Description | Selected |
|--------|-------------|----------|
| Idempotent startup seed | Entrypoint seeds after `alembic upgrade head`, `ON CONFLICT DO NOTHING` | ✓ |
| Alembic data migration | Revision 0002 inserts the demo user (a fake revision, needs undoing) | |
| Get-or-create in the dependency | A hidden write inside a read-path dependency | |

| Option | Description | Selected |
|--------|-------------|----------|
| Enforce now | owner_id == actor_id from day one; not owned → 404 | ✓ |
| Defer to Phase 5 | Retrofit ownership into every use case later | |

| Option | Description | Selected |
|--------|-------------|----------|
| Constant in presentation | `Final` UUID beside the seam, shared with the seed | ✓ |
| Setting DEMO_ACTOR_ID | An env key that exists for one phase | |
| You decide | | |

**User's choice:** All recommended options.

---

## PATCH semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Omitted vs explicit null | JSON Merge Patch semantics via `model_fields_set` | ✓ |
| Null means unchanged | Nullable fields can never be cleared | |

| Option | Description | Selected |
|--------|-------------|----------|
| 422 validation_error | At least one known field, `extra="forbid"` | ✓ |
| 200 no-op | Unknown fields silently swallowed | |

| Option | Description | Selected |
|--------|-------------|----------|
| Refuse, as the entity does | `reschedule()` refuses a past date; checked only when sent | ✓ |
| Allow on PATCH | Weakens a Phase 2 invariant | |

**User's choice:** All recommended options.

---

## Response shapes

| Option | Description | Selected |
|--------|-------------|----------|
| Flat envelope | items + total_tasks + completed_tasks + completion_percentage | ✓ |
| Nested stats object | `{items, stats: {...}}` | |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, on every list response | One TaskListResponse with stats; one grouped query for the collection | ✓ |
| Only on the collection | Two shapes | |

| Option | Description | Selected |
|--------|-------------|----------|
| PATCH .../status {status} | 200 with the full task | ✓ |
| POST .../transitions | RPC-style command resource | |

| Option | Description | Selected |
|--------|-------------|----------|
| 201 + Location + body | Textbook REST | ✓ |
| 201 + body only | | |

| Option | Description | Selected |
|--------|-------------|----------|
| created_at, then id | Deterministic total order, no sort params | ✓ |
| You decide | | |

**User's choice:** All recommended options.

---

## Proof & gates

| Option | Description | Selected |
|--------|-------------|----------|
| Add HTTPException gate in Phase 4 | import-linter forbidden contract + AST test, proven red | ✓ |
| Leave to review | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Every route, happy + key refusals | Integration tests per route now; Phase 6 audits | ✓ |
| Smoke per route, depth in Phase 6 | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Statement-count test | Constant statement count regardless of N lists/tasks | ✓ |
| Compiled-SQL tests are enough | | |

**User's choice:** All recommended options.

---

## Claude's Discretion

- How commands represent "not provided" versus `None` for PATCH
- Whether `updated_at` moves on a value-identical PATCH
- Router and schema module layout, and the names of the `Annotated` aliases
- The exact seed mechanism in the entrypoint
- The exact grouped-statistics SQL shape
- The OpenAPI polish level in this phase

## Deferred Ideas

- JWT swap of the seam, removing the seed, and the assignee 403 leg: Phase 5
- Pagination, sorting and multi-value filters: v2
