---
phase: 04-task-lists-tasks
reviewed: 2026-09-19T07:19:57Z
depth: standard
files_reviewed: 62
files_reviewed_list:
  - .importlinter
  - docker/entrypoint.sh
  - src/taskmanager/application/dto/commands.py
  - src/taskmanager/application/dto/results.py
  - src/taskmanager/application/dto/unset.py
  - src/taskmanager/application/ports/repositories.py
  - src/taskmanager/application/use_cases/access.py
  - src/taskmanager/application/use_cases/task_lists/__init__.py
  - src/taskmanager/application/use_cases/task_lists/create.py
  - src/taskmanager/application/use_cases/task_lists/delete.py
  - src/taskmanager/application/use_cases/task_lists/get.py
  - src/taskmanager/application/use_cases/task_lists/list.py
  - src/taskmanager/application/use_cases/task_lists/update.py
  - src/taskmanager/application/use_cases/tasks/change_task_status.py
  - src/taskmanager/application/use_cases/tasks/create.py
  - src/taskmanager/application/use_cases/tasks/delete.py
  - src/taskmanager/application/use_cases/tasks/get.py
  - src/taskmanager/application/use_cases/tasks/list.py
  - src/taskmanager/application/use_cases/tasks/update.py
  - src/taskmanager/domain/entities/task.py
  - src/taskmanager/domain/entities/task_list.py
  - src/taskmanager/infrastructure/db/repositories/task_lists.py
  - src/taskmanager/main.py
  - src/taskmanager/presentation/api/actor.py
  - src/taskmanager/presentation/api/dependencies.py
  - src/taskmanager/presentation/api/routers/__init__.py
  - src/taskmanager/presentation/api/routers/task_lists.py
  - src/taskmanager/presentation/api/routers/tasks.py
  - src/taskmanager/presentation/api/schemas/__init__.py
  - src/taskmanager/presentation/api/schemas/task_lists.py
  - src/taskmanager/presentation/api/schemas/tasks.py
  - tests/architecture/test_layer_boundaries.py
  - tests/architecture/test_routers_raise_no_http_exception.py
  - tests/integration/api/__init__.py
  - tests/integration/api/test_statements.py
  - tests/integration/api/test_task_lists.py
  - tests/integration/api/test_tasks.py
  - tests/integration/conftest.py
  - tests/integration/test_repositories_task_lists.py
  - tests/unit/application/fakes.py
  - tests/unit/application/test_access.py
  - tests/unit/application/test_change_task_status.py
  - tests/unit/application/test_create_task.py
  - tests/unit/application/test_create_task_list.py
  - tests/unit/application/test_delete_task.py
  - tests/unit/application/test_delete_task_list.py
  - tests/unit/application/test_dtos.py
  - tests/unit/application/test_fakes.py
  - tests/unit/application/test_get_task.py
  - tests/unit/application/test_get_task_list.py
  - tests/unit/application/test_list_task_lists.py
  - tests/unit/application/test_list_tasks.py
  - tests/unit/application/test_ports.py
  - tests/unit/application/test_unset.py
  - tests/unit/application/test_update_task.py
  - tests/unit/application/test_update_task_list.py
  - tests/unit/domain/test_task.py
  - tests/unit/domain/test_task_list.py
  - tests/unit/presentation/test_actor.py
  - tests/unit/presentation/test_schemas.py
  - tests/unit/test_app_factory.py
  - tests/unit/test_settings.py
findings:
  critical: 1
  warning: 5
  info: 6
  total: 12
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-09-19T07:19:57Z
**Depth:** standard
**Files Reviewed:** 62 (the 65-path list minus `AI_WORKFLOW.md`, `CLAUDE.md`, `DECISION_LOG.md`)
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

Scope: the Phase 4 vertical slice - eleven use cases, the `access.py` guard, two routers, the
request/response schemas, the actor seam, the task-list adapter, the entrypoint seed, the
`.importlinter` contract added for D-15, the HTTP integration harness and the unit/integration/
architecture tests.

What held up under adversarial reading (stated so the fixer does not re-audit it):

- **ADR-008 / IDOR.** Every addressed-resource use case enters `visible_task_list` or
  `visible_task`; none skips the guard. The wrong-list leg is checked before the parent list is
  loaded, the four refusal legs raise the same class with only the caller-supplied id, and the
  integration tests compare whole anonymised bodies rather than status codes. `ListTaskLists` is
  scoped in SQL. No 403 path exists. No route leaks existence.
- **Transactions.** Every mutating use case commits exactly once on the success path; no read
  commits; no repository commits. `IntegrityError` on `uq_task_lists_owner_id_name` is translated
  in the adapter on both `add` and `update` to the same `DuplicateTaskListNameError` the
  pre-check raises, so the pre-check/constraint race converges on one 409.
- **SQL.** No statement is built by string formatting; every value is a bound parameter.
- **Entrypoint.** Both heredocs are quoted (`<<'PY'`), so no environment variable is ever
  interpolated by the shell; `set -eu` aborts before `exec uvicorn` on any failure.
- **Actor seam.** `get_current_actor` reads no request, header or state, so the identity is not
  caller-controllable.
- **Schemas.** `extra="forbid"` everywhere, no `owner_id`/`status`/`assignee_id` mass-assignment
  surface, explicit-null and empty-patch legs behave as documented, response models copy
  field-by-field.
- **Tests.** An AST scan found no assertion-free test in scope; the ownership, wrong-list and
  statement-count tests assert behaviour, not just status codes.

What did not hold up: one concurrency defect that lets the persisted state bypass the state
machine, three client-triggerable wrong answers that were each reproduced against the real stack
(a false 409 and two families of 500 from well-formed JSON), and two gates/tests that cannot
fail for the reason their own docstrings give. All reproductions below were run through the
project's own `api_client` harness (rolled-back transaction on `taskmanager_test`) or, for CR-01,
two real `SqlAlchemyUnitOfWork` instances on `taskmanager_test` with the probe rows deleted
afterwards. No source file was modified.

## Critical Issues

### CR-01: Read-modify-write without a row lock - a concurrent request persists a forbidden status transition and silently discards a committed write

**File:** `src/taskmanager/application/use_cases/access.py:84-93`, consumed by
`src/taskmanager/application/use_cases/tasks/change_task_status.py:81-89`,
`src/taskmanager/application/use_cases/tasks/update.py:60-84`,
`src/taskmanager/application/use_cases/task_lists/update.py:55-79`

**Issue:** Every mutating use case loads a detached entity with a plain `SELECT`, validates the
change against that in-memory copy, then writes the *whole* entity back
(`apply_task_to_row` assigns every column). Nothing locks the row and nothing versions it, so
under READ COMMITTED two overlapping requests both validate against the same stale state and the
second commit wins wholesale.

Reproduced with two real units of work on PostgreSQL, task initially `in_progress`:

1. A loads the task (`in_progress`). B loads the task (`in_progress`).
2. A: `change_status(COMPLETED)` -> update -> commit. Row is `('completed', <ts>)`.
3. B: `change_status(PENDING)` - legal against B's stale `in_progress` copy - update -> commit.

Observed output: `B committed without error` / `final row: ('pending', None)`.

The database went `completed -> pending`, which `ALLOWED_TRANSITIONS` forbids
(`COMPLETED: {IN_PROGRESS}`), and A's completion plus its `completed_at` were erased without
either caller being told. The module docstrings claim the entity is "the only copy of the state
machine" and the status endpoint "the only door" onto it; under concurrency that claim is false.
The CHECK constraint does not help, because B rewrites `status` and `completed_at` together.
The same mechanism makes `PATCH /tasks/{id}` clobber a concurrent status change (B writes back
its stale `status`/`completed_at` along with the new title), and makes two concurrent task-list
PATCHes lose one of the two edits. A client retrying a timed-out request, or two browser tabs,
is enough to trigger it.

**Fix:** Lock the row for the duration of the write transaction. Smallest change that keeps the
layering: add a locking read to the ports and use it from the guard on write paths.

```python
# application/ports/repositories.py
async def get_for_update(self, task_id: UUID) -> Task | None: ...

# infrastructure/db/repositories/tasks.py
async def get_for_update(self, task_id: UUID) -> Task | None:
    row = await self._session.scalar(
        select(TaskRow).where(TaskRow.id == task_id).with_for_update()
    )
    return None if row is None else task_to_entity(row)

# application/use_cases/access.py
async def visible_task(uow, task_list_id, task_id, actor_id, *, for_update: bool = False) -> Task:
    task = await (uow.tasks.get_for_update(task_id) if for_update else uow.tasks.get(task_id))
    ...
```

`ChangeTaskStatus`, `UpdateTask`, `DeleteTask` pass `for_update=True`; mirror it for
`visible_task_list` in `UpdateTaskList`/`DeleteTaskList`. With the lock, B blocks until A
commits, re-reads `completed`, and `change_status(PENDING)` raises
`InvalidStatusTransitionError` -> the documented 409. (Alternative: a `version` column with
`__mapper_args__ = {"version_id_col": ...}` and `StaleDataError` translated to a 409.) Add an
integration test with two units of work on two connections, which the single-connection
`api_client` harness cannot express.

## Warnings

### WR-01: PATCH re-sending a list's own name with surrounding whitespace is refused with a false 409

**File:** `src/taskmanager/application/use_cases/task_lists/update.py:65-71`

**Issue:** The "is this my own name?" comparison uses the raw command value, while
`exists_with_name` strips its argument (`task_lists.py:235`, and the fake at `fakes.py:152`) and
`TaskList.rename` strips too. So for a list named `Alpha`, `PATCH {"name": " Alpha "}`:
`" Alpha " != "Alpha"` is true -> `exists_with_name(actor, " Alpha ")` strips, finds the list's
**own** row -> `DuplicateTaskListNameError`. Reproduced over HTTP:

```
PATCH {"name": " Alpha "} -> 409 duplicate_task_list_name
  "detail": "A task list named ' Alpha ' already exists for this owner."
PATCH {"name": "Alpha"}   -> 200
```

This is exactly the failure the module docstring says the conditional exists to prevent ("a
re-send must stay idempotent instead of fatal"); `test_update_task_list.py`'s own-row test only
uses the exact spelling, so it passes by coincidence of its input. Secondary symptom: the 409
`detail` echoes the untrimmed client string here and in `create.py:69`, while the adapter's
constraint path reports the trimmed `task_list.name` - two spellings of one error.

**Fix:** Compare and pre-check on the normalised value, and let the entity be the normaliser so
the rule is not duplicated:

```python
if command.name is not UNSET:
    previous = task_list.name
    task_list.rename(command.name, now=now)          # strips + validates once
    if task_list.name != previous and await self._uow.task_lists.exists_with_name(
        command.actor_id, task_list.name
    ):
        raise DuplicateTaskListNameError(task_list.name)
```

(The in-memory mutation before the raise is harmless: the entity is a detached copy and the
block rolls back.) In `create.py`, build the entity first and pre-check/raise with
`task_list.name`. Add the padded-own-name case to the unit and HTTP tests.

### WR-02: A `due_date` near the datetime range limits with a non-zero offset is an unhandled `OverflowError` -> 500

**File:** `src/taskmanager/domain/validation.py:31` (reached from
`src/taskmanager/domain/entities/task.py:79` on create and `task.py:185` on reschedule; request
field declared at `src/taskmanager/presentation/api/schemas/tasks.py:62,95`)

**Issue:** Pydantic accepts any ISO-8601 datetime in `0001..9999` with any offset, and
`require_utc` calls `value.astimezone(UTC)` unguarded. Converting `9999-12-31T23:59:59-12:00` or
`0001-01-01T00:00:00+14:00` to UTC leaves the representable range and raises `OverflowError`,
which is not a `DomainError`, so the catch-all answers 500. Reproduced:

```
POST  .../tasks  {"title":"t","due_date":"9999-12-31T23:59:59-12:00"} -> 500 internal_error
POST  .../tasks  {"title":"t","due_date":"0001-01-01T00:00:00+14:00"} -> 500 internal_error
PATCH .../tasks/{id} {"due_date":"9999-12-31T23:59:59-12:00"}         -> 500 internal_error
```

The routers' own `VALIDATION_DESCRIPTION` promises a 422 for a value that breaks a domain rule;
a well-formed JSON body must never produce the 500 leg (and each one emits an ERROR log record
with a traceback, which is a cheap log-flooding lever on an unauthenticated API).

**Fix:**

```python
try:
    return value.astimezone(UTC)
except (OverflowError, ValueError) as error:
    raise ValidationError(
        f"{field} is outside the supported date range.", details={"field": field}
    ) from error
```

Add both boundary strings to `tests/unit/domain/test_task.py` and one HTTP test asserting 422.

### WR-03: A NUL character in any text field reaches PostgreSQL and becomes a 500

**File:** `src/taskmanager/domain/validation.py:34-66` (`require_text` / `optional_text`; request
fields at `schemas/task_lists.py:64-65,86-87` and `schemas/tasks.py:56-57,92-93`)

**Issue:** `" "` is valid JSON and a valid Python `str`, passes `strip()`/length checks,
and is then refused by psycopg/PostgreSQL ("text fields cannot contain NUL (0x00) bytes") as a
driver `DataError` that no adapter translates. For `name` it fails even earlier, inside the
`exists_with_name` SELECT. Reproduced:

```
POST /api/v1/task-lists {"name":"a b"}                      -> 500 internal_error
POST /api/v1/task-lists {"name":"ok","description":"x y"}   -> 500 internal_error
```

The same applies to task `title`/`description` on POST and PATCH. Same contract breach and log
amplification as WR-02.

**Fix:** Refuse it where every other text rule lives, once:

```python
def _refuse_nul(text: str, *, field: str) -> None:
    if "\x00" in text:
        raise ValidationError(
            f"{field} must not contain NUL characters.", details={"field": field}
        )
```

called from both `require_text` and `optional_text` before the length check. Add one domain test
per helper and one HTTP test asserting 422.

### WR-04: `test_every_api_route_declares_a_response_model_or_returns_no_content` cannot fail for either case it documents

**File:** `tests/unit/test_app_factory.py:188` (assertion body: the `modelled` computation)

**Issue:** The docstring says the test fails when a handler is "annotated with an application
result dataclass and no explicit model". It does not. FastAPI infers a response model from a
dataclass return annotation and publishes `content` for it, and it also publishes
`"content": {"application/json": {"schema": {}}}` for a handler with **no** annotation and no
`response_model` at all. The test only checks `"content" in responses[code]`, so both are
`modelled = True`. Verified on the pinned stack:

```
/api/v1/dc   (-> dataclass, no response_model)  modelled=True  schema: {"$ref": ".../R"}
/api/v1/bare (no annotation, no response_model) modelled=True  schema: {}
```

So the ARC-05 gate is green by construction; the only thing it can detect is a non-204 route
with `response_class=Response`.

**Fix:** Assert on what distinguishes a declared Pydantic schema: the 2xx schema must be a
non-empty `$ref` (or an array of `$ref`) whose target name is one of the presentation response
models.

```python
ALLOWED = {"TaskListResponse", "TaskResponse", "TaskCollectionResponse"}

def _ref_name(schema: dict[str, Any]) -> str | None:
    target = schema.get("items", schema).get("$ref")
    return None if target is None else target.rsplit("/", 1)[-1]

modelled = any(
    _ref_name(responses[code]["content"]["application/json"]["schema"]) in ALLOWED
    for code in responses
    if code.startswith("2") and code != "204"
)
```

Then prove it red once by temporarily pointing a route at `TaskResult`, as the project does for
its other gates.

### WR-05: The HTTPException AST gate covers `routers/` only, while CLAUDE.md and `.importlinter` describe it as covering the presentation layer; its raise pass does not catch an aliased import as claimed

**File:** `tests/architecture/test_routers_raise_no_http_exception.py:62-69,97-114`;
`.importlinter:77-80`

**Issue:** Three gaps between what is written and what is enforced:

1. `ROUTERS` scans only `presentation/api/routers`. `.importlinter:78-80` says the gate "walks
   the AST of the presentation layer", and CLAUDE.md's rule is that no handler builds an error
   body by hand. `presentation/api/actor.py` and `dependencies.py` are outside the scan - and
   `actor.py` is precisely the file Phase 5 rewrites with JWT decoding, the single most likely
   place for a `raise HTTPException(401)` to appear. Schemas are unscanned too.
2. The docstring (lines 15-16) says the raise pass "catches the direct form, the dotted form and
   an aliased import". `_raised_name` returns the local alias (`HE`), which never equals
   `"HTTPException"`. Only the import pass catches it, so the documented redundancy does not
   exist for that spelling.
3. Neither pass sees `from fastapi import *` (alias name is `"*"`; a later bare-name construct
   bound to a variable is an `ast.Name`, not an `ast.Attribute`), nor a hand-built
   `JSONResponse(status_code=404, ...)`, which violates the same rule by a different route.

**Fix:** Scan `presentation/api` recursively, excluding only `errors/` (the one package allowed
to name the class), and require `actor.py` and `dependencies.py` in
`REQUIRED_SCANNED_MODULES`. Refuse star-imports from `fastapi`/`starlette` in the import pass
(`alias.name == "*" and node.module.split(".")[0] in {"fastapi", "starlette"}`), also flag a
bare `ast.Name` whose `id` is the forbidden class, and correct the docstring sentence about
aliases. Optionally add `JSONResponse`/`PlainTextResponse` construction to the refused names
outside `errors/`.

## Info

### IN-01: `.importlinter` enforces "stdlib-only domain" with a denylist, so it does not enforce it

**File:** `.importlinter:29-43,52-63`
**Issue:** CLAUDE.md states the domain "imports no third-party library at all" and that this is
"enforced automatically". The contract forbids nine named packages; `psycopg`, `uvicorn`,
`email_validator`, `argon2`, `anyio`, `greenlet` and anything added later pass. The application
contract likewise omits `psycopg` (a driver exception type is exactly what the "no SQLAlchemy
exception crosses into application" rule is about), `httpx`, `uvicorn` and `pydantic_settings`.
**Fix:** Add the remaining installed runtime distributions to both lists (at minimum `psycopg`,
`uvicorn`, `httpx`, `pydantic_settings`, `email_validator`, `argon2`, `anyio`), or add a small
AST test asserting every top-level import under `domain/` is in `sys.stdlib_module_names` or
`taskmanager.domain`.

### IN-02: The seed's untargeted `ON CONFLICT DO NOTHING` turns an email collision into a silently broken API

**File:** `docker/entrypoint.sh:156-162`
**Issue:** The comment presents absorbing a `uq_users_email_lower` collision as the safe
outcome. If a row with `demo@taskmanager.local` exists under a different id, the seed writes
nothing, prints nothing, exits 0 - and `DEMO_USER_ID` does not exist, so every
`POST /task-lists` answers 404 `user_not_found` for the rest of the container's life. A restart
that cannot crash is good; one that cannot tell you it did nothing is not.
**Fix:** After the insert, `SELECT 1 FROM users WHERE id = :id` and exit non-zero with a one-line
message if it is absent (or print a warning if aborting on restart is judged worse).

### IN-03: `Location` is built from the request's `Host` header

**File:** `src/taskmanager/presentation/api/routers/task_lists.py:136-138`,
`src/taskmanager/presentation/api/routers/tasks.py:132-134`
**Issue:** `request.url_for` yields an absolute URL from the client-supplied `Host` (and the
internal scheme behind a TLS proxy, since uvicorn is not started with proxy-header trust). A
spoofed `Host` is reflected into the 201's `Location`. Low impact here, but it is a reflected
client value in a response header.
**Fix:** Emit a relative reference: `request.app.url_path_for("get_task_list", list_id=...)`,
which RFC 9110 permits for `Location`.

### IN-04: A repeated filter parameter is silently reduced to its last value

**File:** `src/taskmanager/presentation/api/routers/tasks.py:90-91`
**Issue:** `GET .../tasks?status=pending&status=completed` answers 200 filtered by `completed`
only (reproduced). The route documents "each filter takes a single value; multi-value filters
are deferred to v2", so a client attempting the v2 form gets a plausible wrong answer rather
than the 422 every other malformed filter gets.
**Fix:** Either document last-wins explicitly, or reject duplicates with a small dependency that
checks `len(request.query_params.getlist("status")) > 1` and raises the domain `ValidationError`.

### IN-05: Both collections and every text field are unbounded at the boundary

**File:** `src/taskmanager/presentation/api/routers/task_lists.py:142-169`,
`src/taskmanager/presentation/api/routers/tasks.py:138-179`,
`src/taskmanager/presentation/api/schemas/task_lists.py:64-65`,
`src/taskmanager/presentation/api/schemas/tasks.py:56-57`
**Issue:** ADR-043 deliberately ships no pagination, and D-04 deliberately keeps length limits
out of Pydantic; recorded, not re-litigated. The consequence worth writing next to those ADRs:
on an unauthenticated API one caller can grow a list without limit and every subsequent GET
materialises all of it, and a multi-megabyte `title` is fully parsed, stripped and measured
before the entity refuses it. Neither is bounded by uvicorn.
**Fix:** A hard server-side cap (`LIMIT` with a documented ceiling) keeps ADR-043's "no
parameters" contract while bounding the response; a coarse transport-level
`max_length` far above any domain limit (e.g. 10 000) is a size guard, not a second copy of the
business rule.

### IN-06: Three tests in `test_actor.py` assert prose or tautologies rather than behaviour

**File:** `tests/unit/presentation/test_actor.py:42,78,91`
**Issue:** `test_get_current_actor_is_stable_across_calls` is implied by the test above it
(a constant equals itself). `test_the_module_says_it_is_not_authentication` greps the module's
source for a phrase - it tests a docstring. `test_get_clock_returns_the_clock_port` relies on a
`clock: Clock` annotation that does nothing at runtime and asserts only `tzinfo is not None`,
which a non-UTC aware clock also satisfies while the domain requires UTC.
**Fix:** Drop the first; keep the second only if the project wants prose gated (then say so);
make the third assert `clock.now().utcoffset() == timedelta(0)`.

---

_Reviewed: 2026-09-19T07:19:57Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
