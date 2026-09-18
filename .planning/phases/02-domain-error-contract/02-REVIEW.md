---
phase: 02-domain-error-contract
reviewed: 2026-09-18T16:10:40Z
depth: standard
files_reviewed: 47
files_reviewed_list:
  - src/taskmanager/application/dto/__init__.py
  - src/taskmanager/application/dto/commands.py
  - src/taskmanager/application/dto/results.py
  - src/taskmanager/application/ports/__init__.py
  - src/taskmanager/application/ports/clock.py
  - src/taskmanager/application/ports/notifications.py
  - src/taskmanager/application/ports/repositories.py
  - src/taskmanager/application/ports/security.py
  - src/taskmanager/application/ports/unit_of_work.py
  - src/taskmanager/application/use_cases/__init__.py
  - src/taskmanager/application/use_cases/tasks/__init__.py
  - src/taskmanager/application/use_cases/tasks/change_task_status.py
  - src/taskmanager/domain/entities/__init__.py
  - src/taskmanager/domain/entities/task.py
  - src/taskmanager/domain/entities/task_list.py
  - src/taskmanager/domain/entities/user.py
  - src/taskmanager/domain/exceptions.py
  - src/taskmanager/domain/validation.py
  - src/taskmanager/domain/value_objects/__init__.py
  - src/taskmanager/domain/value_objects/completion.py
  - src/taskmanager/domain/value_objects/task_priority.py
  - src/taskmanager/domain/value_objects/task_status.py
  - src/taskmanager/main.py
  - src/taskmanager/presentation/api/__init__.py
  - src/taskmanager/presentation/api/errors/__init__.py
  - src/taskmanager/presentation/api/errors/handlers.py
  - src/taskmanager/presentation/api/errors/mapping.py
  - src/taskmanager/presentation/api/errors/problem.py
  - tests/api/__init__.py
  - tests/api/test_error_contract.py
  - tests/architecture/test_domain_is_stdlib_only.py
  - tests/conftest.py
  - tests/probe.py
  - tests/unit/application/__init__.py
  - tests/unit/application/fakes.py
  - tests/unit/application/test_change_task_status.py
  - tests/unit/application/test_ports.py
  - tests/unit/domain/__init__.py
  - tests/unit/domain/test_completion.py
  - tests/unit/domain/test_exceptions.py
  - tests/unit/domain/test_task.py
  - tests/unit/domain/test_task_list.py
  - tests/unit/domain/test_task_priority.py
  - tests/unit/domain/test_task_status.py
  - tests/unit/domain/test_user.py
  - tests/unit/domain/test_validation.py
  - tests/unit/test_app_factory.py
findings:
  critical: 0
  warning: 7
  info: 11
  total: 18
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-09-18T16:10:40Z
**Depth:** standard
**Files Reviewed:** 47
**Status:** issues_found

## Summary

Reviewed the Phase 2 deliverable end to end: the stdlib-only domain (three entities, four value objects, the closed `DomainError` hierarchy and the shared validation guards), the application layer (eight ports, two DTOs and the `ChangeTaskStatus` reference use case), the single RFC 9457 exception-handling point in `presentation`, the composition root, and every test file that pins those contracts.

The layered rules in `CLAUDE.md` are respected everywhere I could check by reading: no third-party import enters `taskmanager.domain`, no `fastapi`/`sqlalchemy` import enters `taskmanager.application`, `HTTPException` is never raised in `src/`, and every error body goes through `problem()`. No hardcoded secrets, no dangerous calls, no debug artifacts. There are no blockers.

What I found are seven warnings, all of them contract-level defects that the current green gates cannot see because they concern behaviour the tests do not exercise or a property the design claims but does not enforce:

1. The "single exception-handling point" produces a 401 that violates RFC 9110 (no `WWW-Authenticate`), which will bite the moment Phase 5 raises `AuthenticationError`.
2. A bare `DomainError` (or any future subclass not in the status table) becomes a 500 whose body is *not* the fixed D-08 body and which is never logged.
3. The reference use case leaks a task's existence and its list id on one branch before authorization runs, contradicting the ADR-008 claim in its own docstring.
4. `rename()` on both entities mutates before it finishes validating, so a failed call leaves a half-modified aggregate.
5. Infrastructure faults (a naive clock reading, a naive timestamp rehydrated from the database) are misclassified as client `422 validation_error` responses.
6. The transactional contract never says who rolls back; the use case never calls `rollback()`, the fake never does either, and no test asserts it.
7. `Task.__post_init__` claims to validate "every field, however the task was built", but does not enforce the `status`/`completed_at` coherence that D-03 establishes.

The eleven info items are smaller consistency, typing and test-reliability points.

## Warnings

### WR-01: `AuthenticationError` becomes a 401 without the mandatory `WWW-Authenticate` header

**File:** `src/taskmanager/presentation/api/errors/handlers.py:51-64`, `src/taskmanager/presentation/api/errors/mapping.py:52`
**Issue:** `STATUS_BY_EXCEPTION` maps `AuthenticationError` to 401, and `handle_domain_error` builds the body and returns it with no headers. RFC 9110 section 15.5.2 states that a server generating a 401 response *MUST* send a `WWW-Authenticate` header field. The project already knows this matters: `handle_http_exception` goes out of its way to forward the header for the Starlette path, and `test_http_exception_preserves_the_www_authenticate_header` pins it. But `ports/security.py:39-42` explicitly specifies that Phase 5's `TokenService.decode` raises `AuthenticationError`, which routes through `handle_domain_error`, not `handle_http_exception`. The moment that adapter exists, every bad-token response will be a spec-violating 401. Because this module is by design the *only* place a business failure becomes an HTTP response, the fix belongs here now, not in Phase 5.
**Fix:**
```python
# handlers.py
async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status = status_for(exc)
    response = problem(
        code=exc.code,
        title=exc.title,
        status=status,
        detail=exc.message,
        instance=request.url.path,
        errors=exc.details or None,
    )
    if status == 401:
        # RFC 9110 15.5.2: a 401 MUST carry a challenge.
        response.headers["WWW-Authenticate"] = "Bearer"
    return response
```
Add an API test in `tests/api/test_error_contract.py` with a probe route that raises `AuthenticationError` and asserts `response.headers["www-authenticate"] == "Bearer"`.

### WR-02: A bare `DomainError` answers 500 with a non-fixed, unlogged body, contradicting D-08

**File:** `src/taskmanager/presentation/api/errors/mapping.py:46`, `src/taskmanager/presentation/api/errors/handlers.py:51-64`
**Issue:** `STATUS_BY_EXCEPTION[DomainError] = 500` means any `DomainError` whose family is not in the table (the base class itself, or a future subclass registered directly under `DomainError` without a mapping entry) is answered by `handle_domain_error`, not `handle_unexpected_error`. The result is a 500 with `code: "domain_error"`, `detail: exc.message` and an `errors` member from `exc.details` - three things D-08 says a 500 body never carries - and, unlike the catch-all handler, **nothing is logged**. The docstring of `test_unexpected_error_is_logged_with_its_traceback` says it best: "A blank 500 that logs nothing would be worse than no handler at all". `SAMPLE_ERRORS` in `test_exceptions.py:60` includes a bare `DomainError("A domain rule was broken.")`, so the taxonomy treats it as instantiable, yet no API test covers this path. The `mapping.py` docstring calls the 500 default "unreachable in practice"; it is reachable by construction.
**Fix:** Either make the base non-instantiable in practice and remove it from the table, or treat an unmapped domain error as the server fault it is:
```python
# handlers.py
async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status = status_for(exc)
    if status >= 500:
        # An unmapped domain error is a programming error: same body and
        # same log line as any other unexpected exception (D-08).
        return await handle_unexpected_error(request, exc)
    ...
```
And add an API test that raises a bare `DomainError` from a probe route and asserts the fixed `internal_error` body plus one ERROR log record.

### WR-03: The use case discloses task existence and the task list id before authorization

**File:** `src/taskmanager/application/use_cases/tasks/change_task_status.py:66-75`
**Issue:** The order is load task -> load list -> **raise `TaskListNotFoundError(task.task_list_id)` if the list is missing** -> authorize. On the orphan branch an actor who is neither owner nor assignee receives a `404 task_list_not_found` whose `errors` member carries the task's `task_list_id`. That response (a) confirms the task exists (its code differs from the `task_not_found` an absent task returns), and (b) reveals a foreign identifier. The docstring at lines 25-35 argues at length that "anything that distinguished the two would leak the task's existence" - this branch distinguishes them. The practical exposure is low once Phase 3 adds a foreign key with cascade, but the reference use case is explicitly the template Phase 4 and 5 copy, and the template should not contain a pre-authorization information leak. `test_change_task_status_raises_task_list_not_found_for_an_orphan` currently pins the leaking behaviour, so the test will need to change with the code.
**Fix:**
```python
task = await self._uow.tasks.get(command.task_id)
if task is None:
    raise TaskNotFoundError(command.task_id)
task_list = await self._uow.task_lists.get(task.task_list_id)
# An orphan cannot be authorized, and an unauthorized actor must not learn
# anything an absent task would not tell them: same answer, same details.
if task_list is None or not _may_change_status(task, task_list, command.actor_id):
    raise TaskNotFoundError(command.task_id)
```
If the orphan case must remain distinguishable for operators, log it server-side and still return `TaskNotFoundError` to the caller.

### WR-04: `rename()` mutates the entity before it finishes validating its inputs

**File:** `src/taskmanager/domain/entities/task.py:119-124`, `src/taskmanager/domain/entities/task_list.py:84-87`
**Issue:** Both `rename` methods assign `self.title`/`self.name` on the first line and only then call `require_utc(now, field="now")`. If `now` is naive, `ValidationError` is raised **after** the title has already been replaced, leaving `updated_at` unchanged: a half-applied mutation. `change_status` (line 151) and `reschedule` (line 128) get this right by validating `now` first, and the test suite pins "a refused operation changes nothing" for `change_status` (`test_task_rejects_the_forbidden_transition_from_completed_to_pending` captures `before` and compares). `rename` has no equivalent test, which is why the inconsistency is invisible today. Under a real unit of work the row is rolled back, but the in-memory aggregate is corrupt for the rest of the request, and Phase 4's PATCH endpoint will call exactly these methods.
**Fix:**
```python
def rename(self, title: str, *, now: datetime) -> None:
    moment = require_utc(now, field="now")
    self.title = require_text(title, field="title", max_length=self.TITLE_MAX_LENGTH)
    self.updated_at = moment
```
Same shape in `TaskList.rename`. Add a test for each that passes a valid title and a naive `now`, and asserts the title is unchanged afterwards.

### WR-05: Server-side clock and persistence faults surface as client `422 validation_error`

**File:** `src/taskmanager/domain/validation.py:20-31`, `src/taskmanager/domain/entities/task.py:58-73,124,128,151`
**Issue:** `require_utc` raises `ValidationError` - the class `mapping.py` maps to 422 and whose `details["field"]` is documented as "the field name that travels into the `errors` member a client actually reads". But `now` is never a client-supplied field: it comes from the `Clock` port. Likewise `created_at`/`updated_at`/`completed_at` on `__post_init__` come from the database on rehydration, never from a request. If Phase 3's `SystemClock` returns a naive datetime, or a column is mapped as `TIMESTAMP` rather than `TIMESTAMPTZ`, every affected request answers `422 {"code": "validation_error", "errors": {"field": "now"}}` - telling the client that *their* payload was semantically invalid, naming a field that does not exist in any request schema, and hiding an infrastructure bug behind a 4xx that nobody alerts on. A contract violation by an adapter is a programming error and should be a 500.
**Fix:** Distinguish the two sources. Keep `require_utc` for genuine input fields (`due_date`) and use a non-domain-error guard for trust-boundary-internal values:
```python
# validation.py
def ensure_utc(value: datetime, *, what: str) -> datetime:
    """For values from the clock or the database: a naive one is a programming error."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise TypeError(f"{what} must be an aware UTC datetime; got a naive one.")
    return value.astimezone(UTC)
```
Then in the entities: `moment = ensure_utc(now, what="now")`, and `ensure_utc(self.created_at, what="created_at")` in `__post_init__`; keep `require_utc(self.due_date, field="due_date")`. Update `test_task_rejects_a_naive_now_argument`, `test_task_rejects_a_naive_created_at`, `test_task_rejects_a_naive_completed_at`, `test_task_list_rejects_a_naive_created_at` and `test_user_rejects_a_naive_created_at` to expect `TypeError`.

### WR-06: The transactional contract never says who rolls back, and nothing tests that anyone does

**File:** `src/taskmanager/application/ports/unit_of_work.py:13-15,59-61`, `src/taskmanager/application/use_cases/tasks/change_task_status.py:65-81`, `tests/unit/application/fakes.py:199-216`
**Issue:** The port declares `rollback()`, but the docstring only says leaving the block without `commit()` "must leave the transaction unfinished *so the adapter can* roll it back" - permissive language for the property the whole design rests on. The use case never calls `rollback()` on any path; it relies on `__aexit__` doing it. `FakeUnitOfWork.__aexit__` does *not* roll back and never increments `rollbacks`, so `rollbacks` is a dead counter (the class docstring at line 165 calls `commits` and `rollbacks` "the point of this class"). Consequently no test in the suite can fail if Phase 3's SQLAlchemy adapter forgets to roll back in `__aexit__`: `commits == 0` proves nothing was committed, not that the connection was returned clean. Given `expire_on_commit=False` and session pooling, an un-rolled-back session after a `DomainError` is a real leak.
**Fix:** Make the contract normative and observable:
```python
# unit_of_work.py docstring / __aexit__ comment
# __aexit__ MUST roll back whatever was not committed, whether the block
# exited normally or by exception. The use case never calls rollback() itself.
```
```python
# fakes.py
async def __aexit__(self, exc_type, exc, tb) -> None:
    if not self._committed:
        self.rollbacks += 1
    self._committed = False
    return None

async def commit(self) -> None:
    self.commits += 1
    self._committed = True
```
Then every failure test in `test_change_task_status.py` should also assert `unit_of_work.rollbacks == 1`, and the happy path `rollbacks == 0`.

### WR-07: `Task.__post_init__` does not enforce the `status`/`completed_at` invariant it documents

**File:** `src/taskmanager/domain/entities/task.py:58-73,154-156`
**Issue:** The docstring says the constructor validates "every field, however the task was built", and D-03 establishes that `completed_at` is set exactly when `status is COMPLETED` and cleared otherwise ("a reopened task is never reported as finished"). But the constructor accepts `status=COMPLETED, completed_at=None` and `status=PENDING, completed_at=<datetime>` without complaint. The invariant only holds if every task in existence was mutated through `change_status`; a row written by a migration, a hand-edited fixture, or a Phase 3 mapper bug rehydrates into an entity that violates D-03 and then serialises straight into `TaskResult`. Since the entity is the single copy of the state machine, it should refuse the incoherent combination the same way it refuses a naive timestamp. (The same check should arguably cover `updated_at < created_at`.)
**Fix:**
```python
def __post_init__(self) -> None:
    ...
    if (self.status is TaskStatus.COMPLETED) != (self.completed_at is not None):
        raise ValidationError(
            "completed_at must be set exactly when status is completed.",
            details={"field": "completed_at"},
        )
```
Add two constructor tests (`status=COMPLETED, completed_at=None` and `status=PENDING, completed_at=NOW`) expecting `ValidationError`.

## Info

### IN-01: `problem(errors: Any)` throws away the JSON-safety guarantee the domain paid for

**File:** `src/taskmanager/presentation/api/errors/problem.py:31`
**Issue:** `exceptions.py:31-39` narrows `Details` to `dict[str, str | int | float | bool | None]` precisely so a `UUID` in `details` is a mypy error rather than a serialisation crash inside the error handler. The single body builder then declares `errors: Any`, so the presentation layer accepts anything - the exact failure mode the domain comment calls "the worst failure mode available here" is unguarded at the one place it would actually crash.
**Fix:** `errors: Details | Sequence[Mapping[str, DetailValue]] | None = None`, importing the aliases from `taskmanager.domain.exceptions` (a downward import, allowed).

### IN-02: `settings or get_settings()` should be an identity check

**File:** `src/taskmanager/main.py:18`
**Issue:** `or` on an object relies on truthiness. A `BaseSettings` instance happens to be truthy today, but the idiom silently replaces any falsy-but-valid value and reads as a bug to a reviewer.
**Fix:** `resolved = settings if settings is not None else get_settings()`.

### IN-03: `ALLOWED_TRANSITIONS` is a mutable `dict` behind a `Mapping`/`Final` annotation

**File:** `src/taskmanager/domain/value_objects/task_status.py:30-34`
**Issue:** `Final` only prevents rebinding the name; the object is a plain `dict` and can be mutated at runtime (`ALLOWED_TRANSITIONS[TaskStatus.COMPLETED] = frozenset(TaskStatus)`). The module docstring describes the table as the single source of truth for the state machine; it should be as immutable as the `frozenset` values it holds.
**Fix:** Wrap in `types.MappingProxyType({...})` (stdlib, so the domain rule holds).

### IN-04: `DomainError` stores the caller's `details` dict by reference

**File:** `src/taskmanager/domain/exceptions.py:65-68`
**Issue:** `self.details = details` aliases the argument. A caller that reuses or later mutates the dict changes what the error reports. All current leaves build a fresh literal so it is harmless today.
**Fix:** `self.details = dict(details) if details is not None else {}`.

### IN-05: Test bootstrap constants and env setup duplicated in three places

**File:** `tests/conftest.py:24-25,33-34`, `tests/unit/test_app_factory.py:18-19,24-25,38-39,60-61`
**Issue:** `DATABASE_URL`, `JWT_SECRET` and the two `monkeypatch.setenv` calls are copied into every test in `test_app_factory.py` and again into `conftest.py`. When the settings surface grows (Phase 3 adds more required env), four sites drift.
**Fix:** Add a `settings` fixture in `conftest.py` that performs the env injection and returns `Settings(_env_file=None)`; have both `app` and the three factory tests depend on it.

### IN-06: Fake `exists_with_name` folds differently from the index it claims to mirror

**File:** `tests/unit/application/fakes.py:124-132`, `src/taskmanager/application/ports/repositories.py:69-72`
**Issue:** The comment says the fake matches the `(owner_id, lower(name))` unique index, but it uses `str.casefold()`, which is broader than SQL `lower()` (e.g. `"straße".casefold() == "strasse"`, `lower()` does not). A use-case test can therefore pass on a collision the database will not detect, or vice versa. Separately, the port offers no way to exclude the list being renamed, so Phase 4's rename-to-same-name will trip its own pre-check.
**Fix:** Use `.lower()` in the fake; consider `exists_with_name(owner_id, name, *, exclude_id: UUID | None = None)` on the port before Phase 4 builds on it.

### IN-07: The `handlers.py` docstring overstates the `assert` constraint

**File:** `src/taskmanager/presentation/api/errors/handlers.py:15-19`
**Issue:** The docstring says the `assert isinstance(...)` lines are "load-bearing, so nothing may run this application with assertions disabled". They are load-bearing for mypy narrowing only. Under `python -O` the asserts vanish and every handler still works, because Starlette only dispatches an exception to the handler registered for its class. The stated operational constraint (no `-O`, no `PYTHONOPTIMIZE`) is therefore not real and an evaluator can disprove it in one command.
**Fix:** Reword to "the asserts exist for mypy narrowing; at runtime Starlette's dispatch already guarantees the type", and drop the operational prohibition.

### IN-08: `handle_http_exception` renders a non-string `detail` as a Python repr

**File:** `src/taskmanager/presentation/api/errors/handlers.py:99`
**Issue:** `StarletteHTTPException.detail` is typed `Any`; FastAPI code commonly passes dicts or lists. `str(exc.detail)` turns `{"reason": "x"}` into the Python literal `"{'reason': 'x'}"` in the `detail` member. Nothing in `src/` raises one today, but the handler is the shared translator for all future presentation-layer raises.
**Fix:** `detail=exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)` or, better, route a non-string detail into `errors` and use the reason phrase as `detail`.

### IN-09: Test-shape nits: `async def` tests that await nothing, and a local import

**File:** `tests/unit/application/test_ports.py:87-91`, `tests/api/test_error_contract.py:48`
**Issue:** `test_frozen_clock_returns_the_same_instant_on_every_call` is `async` with no `await`, which puts it on the event loop for no reason; and `test_domain_error_handler_catches_a_grandchild_through_the_mro` imports `InvalidStatusTransitionError` inside the function body while the module already imports from the same package at the top.
**Fix:** Make the clock test a plain `def`; hoist the import.

### IN-10: The fake repositories hand out live references, so a mutate-then-raise use case leaves the fake store dirty

**File:** `tests/unit/application/fakes.py:51,58,102`
**Issue:** `get()` returns the stored instance and `update()` stores the same object. A use case that mutates the entity and then raises before `update()` still leaves the mutated object in `stored`, and a use case that forgets `update()` still "persists" in the fake. The suite compensates by asserting on `updated` and `commits`, so current tests are sound, but `stored[...]` assertions (e.g. `test_change_task_status_is_idempotent_for_the_status_already_held:283`) prove less than they appear to.
**Fix:** Return `copy.replace(task)` (3.13+) / `dataclasses.replace(task)` from `get()` so a write is only visible after `update()`, and pair that with the rollback modelling from WR-06.

### IN-11: Two mapped status codes have no end-to-end test through the handler

**File:** `tests/api/test_error_contract.py`, `tests/probe.py`
**Issue:** The status table maps `AuthenticationError -> 401`, `ValidationError -> 422`, `ConflictError -> 409` and `DomainError -> 500`, but the API suite only drives `InvalidStatusTransitionError`, `TaskNotFoundError` and `AuthorizationError` through `handle_domain_error`. The 401 (WR-01) and 500 (WR-02) paths are exactly the ones with defects, and the domain 422 path is never distinguished from the request-validation 422.
**Fix:** Add probe routes for `AuthenticationError`, a domain `ValidationError`, `DuplicateTaskListNameError` and a bare `DomainError`, and extend `test_every_error_response_uses_the_problem_json_media_type` with them.

---

_Reviewed: 2026-09-18T16:10:40Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
