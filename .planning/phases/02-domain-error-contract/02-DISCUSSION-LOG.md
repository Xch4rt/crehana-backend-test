# Phase 2: Domain & Error Contract - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-18
**Phase:** 02-domain-error-contract
**Areas discussed:** Task state machine, problem+json shape, Identity and time in the domain, Use case and DTO shape

---

## Task state machine

### Which transitions does a Task accept?

| Option | Description | Selected |
|--------|-------------|----------|
| Research matrix | pending→in_progress\|completed; in_progress→pending\|completed; completed→in_progress (reopen); completed→pending forbidden → 409 | ✓ |
| Strict linear | pending→in_progress→completed only; any step back is 409 | |
| Any to any | Only the enum value is validated; no transition rule | |

**User's choice:** Research matrix (recommended)

### Same-state request (X→X)?

| Option | Description | Selected |
|--------|-------------|----------|
| Idempotent no-op, 200 | Task returned unchanged, no timestamp touched | ✓ |
| 409 as an invalid transition | X→X treated like any forbidden move | |

**User's choice:** Idempotent no-op

### Observable `completed_at` side effect?

| Option | Description | Selected |
|--------|-------------|----------|
| Set on enter, clear on leave | completed_at = now via Clock on entering completed; None on reopen | ✓ |
| No completed_at | Only status and updated_at | |

**User's choice:** Set/clear

### Where do business validations live (TASK-08)?

| Option | Description | Selected |
|--------|-------------|----------|
| Entity, raising DomainError | `__post_init__` and mutating methods validate; Pydantic validates shape only | ✓ |
| Pydantic schemas at the boundary | Field constraints in presentation; entity trusts input | |
| Both, duplicated | Pydantic early 422 plus entity re-check | |

**User's choice:** Entity + DomainError

---

## problem+json shape

### How is the `type` member built?

| Option | Description | Selected |
|--------|-------------|----------|
| Stable URN per code | `urn:taskmanager:problem:{code}`; RFC 9457 allows non-dereferenceable URIs | ✓ |
| URL under a fictional domain | `https://taskmanager.example/problems/{code}` (research sketch) | |
| about:blank + code | RFC default type; code only in the extension member | |

**User's choice:** URN per code

### Request-validation errors (422) inside problem+json?

| Option | Description | Selected |
|--------|-------------|----------|
| `errors` list of {field, message, type} | Translate RequestValidationError; hide Pydantic internals | ✓ |
| Raw `exc.errors()` | Native Pydantic list with loc/ctx/input | |

**User's choice:** Translated errors list

### What does an unexpected error (500) expose?

| Option | Description | Selected |
|--------|-------------|----------|
| Generic body + server-side log | Fixed detail, no traceback, same shape in every environment | ✓ |
| Exception detail outside production | `str(exc)` in detail when environment != production | |

**User's choice:** Generic body everywhere

### How is the handler tested before real routers exist?

| Option | Description | Selected |
|--------|-------------|----------|
| Test-only probe router | `/_probe/...` included by tests on top of create_app(); never in production | ✓ |
| Real `/health` as probe | Pull `/health` forward from Phase 3 and force errors from it | |
| Handler as a pure function | Call the handler directly; skips Starlette MRO routing | |

**User's choice:** Test-only probe router

---

## Identity and time in the domain

### Who generates entity ids?

| Option | Description | Selected |
|--------|-------------|----------|
| Application-generated UUID | uuid4 before persistence; DB stores as PK; non-enumerable | ✓ |
| DB autoincrement integer | id None until flush; enumerable ids | |

**User's choice:** Application-generated UUID

### IdGenerator port or direct uuid4()?

| Option | Description | Selected |
|--------|-------------|----------|
| uuid4() direct in the use case | No ninth port; tests assert on the returned id | ✓ |
| IdGenerator port | Deterministic ids in fixtures at the cost of one more abstraction | |

**User's choice:** uuid4() direct

### How does current time reach entities?

| Option | Description | Selected |
|--------|-------------|----------|
| Clock port; `now` as argument | Use case calls clock.now() and passes it to entity methods | ✓ |
| Clock port injected into the entity | Domain depends on an application interface | |
| datetime.now() in the domain | No port; temporal rules tested by patching | |

**User's choice:** Clock port, now as argument

### Date types and timezone?

| Option | Description | Selected |
|--------|-------------|----------|
| Aware UTC datetime everywhere | Timestamps and due_date; naive → DomainError; timestamptz in Phase 3 | ✓ |
| due_date as `date`, timestamps UTC | Two temporal types; "in the past" compared against UTC today | |

**User's choice:** Aware UTC datetime everywhere

---

## Use case and DTO shape

### Use case shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Class per case, `async def execute(command) -> Result` | Ports via __init__, single explicit method | ✓ |
| Class per case, `async def __call__` | Invocable as a function | |
| Service per aggregate | `TaskService` with several methods (god-object; violates ARC-04) | |

**User's choice:** Class + execute

### Commands and results made of?

| Option | Description | Selected |
|--------|-------------|----------|
| Frozen dataclasses | `@dataclass(frozen=True, slots=True)`; application stays framework-free | ✓ |
| Pydantic models | model_validate / model_dump convenience; application depends on Pydantic | |

**User's choice:** Frozen dataclasses

### How do repositories reach the use case?

| Option | Description | Selected |
|--------|-------------|----------|
| Through the UnitOfWork | uow.tasks / uow.task_lists / uow.users bound to one transaction | ✓ |
| Separate repos + UoW for commit | Explicit signatures; transactional coherence by discipline | |

**User's choice:** Through the UnitOfWork

### How does the acting user reach the use case?

| Option | Description | Selected |
|--------|-------------|----------|
| `actor_id: UUID` in every command | Presentation fills it from the JWT; use case decides 404 vs 403 | ✓ |
| CurrentUser context object | Second input to execute or constructor | |
| Defer to Phase 4 | Leave the signature open | |

**User's choice:** actor_id in every command

---

## Claude's Discretion

- Module layout inside `domain/` and `application/` (follow ARCHITECTURE.md unless a reason to deviate appears)
- Exact `DomainError` class names and `code` strings within the seven families
- Whether Phase 2 ships one real reference use case or a typed skeleton plus docstring/ADR
- Packaging of the probe router (tests fixture vs test-only presentation helper)
- Structural conformance tests for the Protocols via in-memory fakes under `tests/`

## Deferred Ideas

- Multi-value status filters — Phase 4
- Extra task statuses (`cancelled`, `archived`, `blocked`) — documented future work, Phase 7
- Targeted import-linter contract for `HTTPException` outside `presentation` — Phase 4
