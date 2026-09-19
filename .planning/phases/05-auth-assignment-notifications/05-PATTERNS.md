# Phase 5: Auth, Assignment & Notifications - Pattern Map

**Mapped:** 2026-09-19
**Files analyzed:** 74 (24 new source modules, 18 modified source/config files, 15 new test modules,
17 modified test modules — root artifacts counted once)
**Analogs found:** 70 / 74

> **How to read this.** Every excerpt below is copied verbatim from a file that exists in this
> repository today, with its path and line numbers. The planner should reference the analog by
> path+lines in each plan's action section rather than re-deriving conventions. Where no analog
> exists (the JWT adapter, the Argon2 adapter, the JSON logging module, the OAuth2 bearer seam),
> the "No Analog Found" section says so and points at `05-RESEARCH.md` instead.
>
> **The one-sentence version of this phase:** almost everything new is a copy of something that
> already exists — the assignment door is the status door, `AssignTask` is `ChangeTaskStatus`,
> `ListUsers` is `ListTaskLists`, the `0002` revision is the bottom half of `0001` — except four
> things that genuinely have no precedent, listed at the bottom.
>
> **Three corrections to `05-RESEARCH.md` found while reading the code.** They change what the
> planner must schedule. See "Research Corrections" before writing the wave plan.

---

## Research Corrections (read first)

| # | RESEARCH says | The code says | Consequence for the plan |
|---|---------------|---------------|--------------------------|
| RC-1 | Wave 0 gap: "`tests/unit/application/fakes.py` — `FakePasswordHasher`, `FakeTokenService`, `InMemoryEmailNotifier`, `FakeClock`" must be **added** | All four already exist: `FakePasswordHasher` L322-336, `FakeTokenService` L339-346, `FakeEmailNotifier` L349-362, `FrozenClock` L306-319. `tests/unit/application/test_ports.py` L92-104 already asserts all three satisfy their ports. | Do **not** plan to write them. The only `fakes.py` work is: `FakeUserRepository.list_all` ordering (Pitfall 9), a new `FakeTaskRepository.list_for_assignee`, and `FakePasswordHasher.dummy_verify` if D-21's port extension lands. |
| RC-2 | `EmailNotifier` in-memory adapter is called `InMemoryEmailNotifier` | The existing class is `FakeEmailNotifier` and records `list[tuple[str, str, UUID]]` | Keep the existing name and extend it; a second in-memory notifier under a new name would be two doubles for one port. NOTF-02's "assert without mocks" is already satisfied structurally. |
| RC-3 | The planner may want a `get_settings()` call inside each new provider | `dependencies.py` has **no** settings access at all. The established shape is: `main.py` builds a typed container from `Settings` and stores it on `app.state`; `dependencies.py::_resources` (L32-38) narrows it **once**, privately, and every provider reads a field off it. | The token service (which needs `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes`) must arrive through a second typed container built in `create_app`, not through `get_settings()` per request. `DatabaseResources` is the copy-from. Otherwise mypy strict gains a new implicit-`Any` source and the "one narrowing per application" claim in `dependencies.py`'s docstring becomes false. |

---

## File Classification

### Domain — modified (3)

| File | Role | Data Flow | What changes | Closest Analog | Match |
|------|------|-----------|--------------|----------------|-------|
| `domain/entities/user.py` | entity | in-memory validation | `+ full_name`, `+ FULL_NAME_MAX_LENGTH: ClassVar[int] = 100`, `create(full_name=...)` | its own `email` field + `EMAIL_MAX_LENGTH` L31-56 | **exact** |
| `domain/entities/task.py` | entity | in-memory mutation | `+ assign(assignee_id, *, now)`, `+ unassign(*, now)` | its own `reprioritise` L167-177 | **exact** |
| `domain/validation.py` | utility | pure validation | `+ require_password(value, *, field)` (8..128) | its own `require_text` L74-90 | **exact** |

### Application — new (8) and modified (5)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `use_cases/auth/__init__.py` | package init | — | `use_cases/tasks/__init__.py` | exact |
| `use_cases/auth/register.py` (`RegisterUser`) | use case | CRUD write | `use_cases/task_lists/create.py` L49-91 | **exact** |
| `use_cases/auth/login.py` (`Login`) | use case | read + credential check | `use_cases/task_lists/create.py` L58-91 (shape) + `repositories/users.py::get_by_email` | role-match |
| `use_cases/auth/authenticate.py` (`AuthenticateActor`) | use case | read | `use_cases/task_lists/get.py` / `list.py` L42-63 (read, no commit) | role-match |
| `use_cases/users/__init__.py` | package init | — | `use_cases/tasks/__init__.py` | exact |
| `use_cases/users/list.py` (`ListUsers`) | use case | query | `use_cases/task_lists/list.py` L42-63 | **exact** |
| `use_cases/tasks/assign.py` (`AssignTask`, `UnassignTask`) | use case | CRUD write + side effect | `use_cases/tasks/change_task_status.py` L64-101 | **exact** (plus the post-commit leg, no analog) |
| `use_cases/tasks/list_assigned.py` (`ListAssignedTasks`) | use case | query | `use_cases/task_lists/list.py` L42-63 | **exact** |
| `use_cases/access.py` **(M)** | utility (shared guard) | load + authorize | its own `visible_task` L98-129 | **exact** |
| `dto/commands.py` **(M)** | DTO | — | its own `ChangeTaskStatusCommand` L189-205 | **exact** |
| `dto/results.py` **(M)** | DTO | pure transform | its own `TaskResult` + `from_entity` L35-72 | **exact** |
| `ports/repositories.py` **(M)** | port (Protocol) | query | its own `list_for_task_list` L73-79 | **exact** |
| `ports/security.py` **(M)** | port (Protocol) | — | its own `PasswordHasher` L27-31 | **exact** |

### Infrastructure — new (6) and modified (5)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `infrastructure/security/__init__.py` | package init | — | `infrastructure/db/repositories/__init__.py` | exact |
| `infrastructure/security/passwords.py` (`PwdlibPasswordHasher`) | adapter | pure compute (off-loop) | `infrastructure/clock.py` L19-26 (small adapter, no base class) | role-match |
| `infrastructure/security/tokens.py` (`JwtTokenService`) | adapter | pure compute | `infrastructure/clock.py` L19-26 + `db/errors.py` translation idiom | role-match |
| `infrastructure/notifications/__init__.py` | package init | — | `infrastructure/db/repositories/__init__.py` | exact |
| `infrastructure/notifications/logging.py` (`LoggingEmailNotifier`) | adapter | fire-and-forget I/O | `infrastructure/clock.py` L19-26 | partial |
| `infrastructure/logging.py` (`configure_logging`, `JsonFormatter`) | config/bootstrap | — | **none** — see "No Analog Found" | — |
| `db/constraints.py` **(M)** | config constants | — | its own `IX_TASKS_TASK_LIST_ID` L46 | **exact** |
| `db/models.py` **(M)** | ORM model | — | its own `UserRow.email` L54 + `TaskRow.task_list_id` L113-115 (`index=True`) | **exact** |
| `db/mappers.py` **(M)** | mapper | pure transform | its own user trio L78-108 | **exact** |
| `db/repositories/tasks.py` **(M)** | repository adapter | query | its own `list_for_task_list` L179-216 | **exact** |
| `infrastructure/config/settings.py` **(M)** | config | — | its own `jwt_secret` L41 (`min_length=16` → `32`) | **exact** |

### Migration — new (1)

| New File | Role | Data Flow | Closest Analog | Match |
|----------|------|-----------|----------------|-------|
| `migrations/versions/0002_*.py` | migration | schema DDL | `migrations/versions/0001_baseline.py` L39-43, L138-140, L143-153 | **exact** |

### Presentation — new (5) and modified (4)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `presentation/api/routers/auth.py` | router | request-response | `routers/task_lists.py` L94-139 (`create_task_list`, 201 + `Location`) | role-match |
| `presentation/api/routers/users.py` | router | request-response (collection) | `routers/task_lists.py` L142-153 (bare-array collection route) | **exact** |
| `presentation/api/routers/assignments.py` | router | request-response | `routers/tasks.py` L282-331 (the status door + `register_*_routes`) | **exact** |
| `presentation/api/schemas/auth.py` | schema | request/response | `schemas/tasks.py` L144-172 (`TaskStatusChangeRequest`) + L175-210 (`TaskResponse`) | **exact** |
| `presentation/api/schemas/users.py` | schema | response | `schemas/tasks.py` L175-210 | **exact** |
| `presentation/api/actor.py` **(M)** | provider (DI seam) | request-scoped identity | its own L46-59 (signature + alias) — **body has no analog** | partial |
| `presentation/api/dependencies.py` **(M)** | provider | request-scoped construction | its own `_resources` L32-38 + `get_clock` L81-95 + aliases L98-103 | **exact** |
| `presentation/api/schemas/tasks.py` **(M)** | schema | request | its own `TaskStatusChangeRequest` L144-172 | **exact** |
| `main.py` **(M)** | composition root | app construction | its own L53-82 | **exact** |

### Operational / root artifacts — modified (4)

| File | Role | What changes | Closest Analog | Match |
|------|------|--------------|----------------|-------|
| `docker/entrypoint.sh` | script | delete step `2b` (the demo seed, ~L97-177) and restore the 1/2/3 header | its own pre-Phase-4 shape; the header comment at L10-11 states the deletion contract | **exact** |
| `.env.example` | config doc | `JWT_SECRET` comment if the floor moves to 32 | its own existing entry | exact |
| `CLAUDE.md` § Project Rules | doc | AST gate scope (now all of `presentation/api`) + a write-path locking rule | its own existing rule paragraphs, each naming its gate | exact |
| `DECISION_LOG.md` | doc | ADRs for: `owned_task`, the `/users` directory trade-off (D-13), the `PasswordHasher` port extension (D-21), leeway=0, anyio vs asyncio, package-wide log handler, the register-409 enumeration concession (T-5-06) | its own ADR-058 entry | exact |

### Tests — new (15)

| New File | Role | Closest Analog | Match |
|----------|------|----------------|-------|
| `tests/unit/infrastructure/test_passwords.py` | unit test | `tests/unit/infrastructure/test_clock.py` | role-match |
| `tests/unit/infrastructure/test_tokens.py` | unit test | `tests/unit/infrastructure/test_errors.py` (exception-translation table) | role-match |
| `tests/unit/infrastructure/test_notifier.py` | unit test (`caplog`) | `tests/api/test_error_contract.py`'s `caplog` assertions | partial |
| `tests/unit/infrastructure/test_logging.py` | unit test | none — see "No Analog Found" | — |
| `tests/unit/application/test_register_user.py` | unit test | `tests/unit/application/test_create_task_list.py` | **exact** |
| `tests/unit/application/test_login.py` | unit test | `tests/unit/application/test_change_task_status.py` (refusal-leg style) | **exact** |
| `tests/unit/application/test_authenticate_actor.py` | unit test | `tests/unit/application/test_get_task.py` | **exact** |
| `tests/unit/application/test_assign_task.py` | unit test | `tests/unit/application/test_change_task_status.py` | **exact** |
| `tests/unit/application/test_unassign_task.py` | unit test | same | **exact** |
| `tests/unit/application/test_list_users.py` | unit test | `tests/unit/application/test_list_task_lists.py` | **exact** |
| `tests/unit/application/test_list_assigned_tasks.py` | unit test | `tests/unit/application/test_list_tasks.py` | **exact** |
| `tests/unit/presentation/test_security_scheme.py` | unit test (OpenAPI) | `tests/unit/presentation/test_actor.py` (alias introspection) + ADR-057's `app.openapi()` rule | role-match |
| `tests/integration/api/test_auth.py` | API integration test | `tests/integration/api/test_task_lists.py` L1-150 | **exact** |
| `tests/integration/api/test_users.py` | API integration test | same | **exact** |
| `tests/integration/api/test_assignment.py` | API integration test | `tests/integration/api/test_tasks.py` | **exact** |
| `tests/integration/api/test_permission_matrix.py` | API integration test (parametrized table) | none — see "No Analog Found" | — |

### Tests — modified (17)

| File | What changes | Closest Analog | Match |
|------|--------------|----------------|-------|
| `tests/unit/application/fakes.py` | `list_all` ordering (Pitfall 9); `+ list_for_assignee`; `+ dummy_verify` | its own `list_for_task_list` L79-100 | **exact** |
| `tests/unit/application/test_ports.py` | one test if `dummy_verify` lands | its own L92-104 | **exact** |
| `tests/unit/application/test_access.py` | the 403 leg + mirror-image assertions | its own paired-refusal style L1-80 | **exact** |
| `tests/unit/application/test_change_task_status.py` | un-invert the assignee test (04-03) | itself | — |
| `tests/unit/application/test_write_paths_hold_what_they_change.py` | 3 new cases: assignee status change, `AssignTask`, `UnassignTask` | its own L103-147 | **exact** |
| `tests/unit/presentation/test_actor.py` | delete 4 `DEMO_USER_ID` tests + `test_the_module_says_it_is_not_authentication`; add decode-path tests | its own alias test L64-77 stays verbatim | partial |
| `tests/unit/infrastructure/test_models.py` | 12 constants → 13; `users.full_name` → `FULL_NAME_MAX_LENGTH` | itself | **exact** |
| `tests/unit/infrastructure/test_mappers.py` | `full_name` in the three user functions | itself | **exact** |
| `tests/unit/infrastructure/test_adapter_ports.py` | `PwdlibPasswordHasher`/`JwtTokenService`/`LoggingEmailNotifier` port bindings | its own L73 (`repository: UserRepository = SqlAlchemyUserRepository(...)`) | **exact** |
| `tests/unit/test_settings.py` | `test_short_secret_is_rejected` floor 16 → 32 | itself | **exact** |
| `tests/integration/conftest.py` | `+ authenticated_client`, `+ a token helper`; `api_client` keeps its override; `acting_as` unchanged | its own `api_client` L297-352 | **exact** |
| `tests/integration/api/test_statements.py` | counts 1→2 and 3→4, switch to `authenticated_client`, comment the new first entry | its own L79-93 | **exact** |
| `tests/integration/api/test_task_lists.py` | `DEMO_USER_ID` → a test-local `OWNER_ID` in the same identifier series | its own constants block L53-70 | **exact** |
| `tests/integration/test_concurrent_writes.py` | owner-vs-assignee case | its own L101-175 harness | **exact** |
| `tests/integration/test_migrations.py` | `test_the_migration_directory_holds_exactly_one_revision` (L100) → assert the chain `0001 → 0002`, head == `0002` | itself | partial |
| `tests/integration/test_repositories_users.py` | `full_name` round trip; `list_all` ordering | itself | **exact** |
| `tests/architecture/test_routers_raise_no_http_exception.py` | 5 entries added to `REQUIRED_SCANNED_MODULES` | its own L116-126 | **exact** |

---

## Pattern Assignments

### `application/use_cases/access.py` **(M)** — add `owned_task` (utility, load+authorize)

**Analog:** itself, `visible_task` at L98-129. Copy the shape exactly; only the last branch differs.

**The function to copy** (`access.py` L98-129):

```python
async def visible_task(
    uow: UnitOfWork,
    task_list_id: UUID,
    task_id: UUID,
    actor_id: UUID,
    *,
    for_update: bool = False,
) -> Task:
    if for_update:
        task = await uow.tasks.get_for_update(task_id)
    else:
        task = await uow.tasks.get(task_id)
    # D-14, and it comes first on purpose: a request naming the wrong list must
    # be refused before anything is looked up under that list, so the answer
    # cannot depend on whether the addressed list exists.
    if task is None or task.task_list_id != task_list_id:
        raise TaskNotFoundError(task_id)
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        raise TaskNotFoundError(task_id)
    return task
```

Three properties of this shape are load-bearing and must survive both the assignee short-circuit
in `visible_task` and the new `owned_task`:

1. `if for_update:` is an **explicit two-branch statement**, not a conditional call expression.
   RESEARCH sketches `await (uow.tasks.get_for_update if for_update else uow.tasks.get)(task_id)`
   — that is a different spelling from the file and mypy strict has to infer a union of bound
   methods. Keep the `if`/`else`.
2. The parent-list comparison comes **first**, before any read of the list (ADR-050). The
   assignee short-circuit goes *after* it and *before* the `uow.task_lists.get`.
3. `for_update` is keyword-only with a `False` default, so a read path can never wait by accident.

**The docstring debt (D-22).** `access.py` L25-36 currently states, as a grep-checkable property:

```
**Why nothing here can answer 403.** ... That class is deliberately not
named anywhere in this file, prose included, so "this module cannot produce a
403" is something a grep over it settles rather than something a reader has to
take on trust - the same convention the Makefile follows for the tool
invocations it warns against.
```

The commit that introduces `owned_task` must rewrite that paragraph in the same change, saying why
the claim existed and why it retired. `tests/unit/application/test_access.py` L15-20 documents the
five `assert not isinstance(error, AuthorizationError)` assertions that stay valid for the 404 legs.

---

### `application/use_cases/tasks/assign.py` — `AssignTask` / `UnassignTask` (use case, CRUD write + side effect)

**Analog:** `application/use_cases/tasks/change_task_status.py` L64-101. Copy the whole class shape.

**Constructor + body pattern** (`change_task_status.py` L64-101):

```python
class ChangeTaskStatus:
    """Moves one task to a requested status on behalf of an authenticated actor."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17). Nothing else is injected, because nothing else is
        # touched - which is the whole point of one class per use case.
        self._uow = uow
        self._clock = clock

    async def execute(self, command: ChangeTaskStatusCommand) -> TaskResult:
        """Run the operation, or raise the domain error that describes its refusal."""
        async with self._uow:
            task = await visible_task(
                self._uow,
                command.task_list_id,
                command.task_id,
                command.actor_id,
                for_update=True,
            )
            task.change_status(command.new_status, now=self._clock.now())
            await self._uow.tasks.update(task)
            await self._uow.commit()
        # Mapped outside the block: the result describes a transaction that has
        # already been made durable, never one still in flight.
        return TaskResult.from_entity(task)
```

For `AssignTask` the differences are, in order: `owned_task(..., for_update=True)` instead of
`visible_task`; the `uow.users.get(command.assignee_id)` lookup **after** the guard (Pitfall 13);
the D-07 same-assignee early return (mirroring `Task.change_status`'s own no-op at
`task.py` L200-201); capture `assignee.email` and `task.title` into locals **inside** the block;
and the post-commit `try/except` leg, which has no analog in this codebase — see "No Analog Found".

**The constructor grows one argument.** `AssignTask(uow, clock, notifier)`. The docstring rule at
L67-70 above ("nothing else is injected, because nothing else is touched") is the sentence that
justifies the third argument; say so in the new class rather than leaving it unexplained.

**The idempotent no-op is already an established shape** — `domain/entities/task.py` L194-201:

```python
def change_status(self, new_status: TaskStatus, *, now: datetime) -> None:
    """Move the task through the lifecycle, or refuse a forbidden move."""
    # D-02: asking for the status the task already has is an idempotent
    # no-op. No field moves, no timestamp moves, and Phase 4 answers 200
    # with the unchanged task rather than 409 - repeating a request that
    # already succeeded is not a conflict.
    if new_status is self.status:
        return
```

D-07 wants the same behaviour for assignment, but the no-op must live in the **use case**, not in
`Task.assign` — the use case is the layer that also has to skip the commit and the email.

---

### `domain/entities/task.py` **(M)** — `assign` / `unassign` (entity, in-memory mutation)

**Analog:** its own `reprioritise` at L167-177, which is the mutator with no value guard:

```python
def reprioritise(self, priority: TaskPriority, *, now: datetime) -> None:
    """Replace the priority and stamp the change."""
    # There is no value guard here, unlike every sibling mutator, and the
    # absence is deliberate: `TaskPriority` is a StrEnum, so the parameter's
    # own type is the constraint and the enum-typed field at the HTTP
    # boundary refuses anything that is not a member before a command is
    # built. A defensive check would be a branch no test could reach, which
    # this project's coverage norm would then have to excuse with a pragma.
    moment = require_utc(now, field="now")
    self.priority = priority
    self.updated_at = moment
```

`assign(assignee_id: UUID, *, now: datetime)` is this verbatim with `self.assignee_id = assignee_id`,
and the same "no value guard" argument applies (a `UUID` is typed; existence is the use case's
question, not the entity's). `unassign(*, now)` sets `None`.

**The rule the mutator must not break** is stated at `task.py` L143-147, inside `rename`:

```python
# Every guard runs before the first assignment, as in `reschedule` and
# `change_status`. Assigning the title first and validating `now`
# afterwards left a refused call with the new title and the old
# `updated_at`: a half-applied mutation the unit of work cannot undo,
# because the corrupted copy is the in-memory aggregate, not the row.
moment = require_utc(now, field="now")
```

`require_utc(now, field="now")` first, assignment second, `self.updated_at = moment` last.

---

### `domain/entities/user.py` **(M)** — `full_name` (entity)

**Analog:** its own `email` handling, L31-56:

```python
    # The RFC 5321 practical maximum for a full address (64 local + @ + 255).
    EMAIL_MAX_LENGTH: ClassVar[int] = 320
    ...
    def __post_init__(self) -> None:
        """Normalise and validate every field, however the user was built."""
        self.email = require_text(
            self.email, field="email", max_length=self.EMAIL_MAX_LENGTH
        ).lower()
```

`FULL_NAME_MAX_LENGTH: ClassVar[int] = 100` beside `EMAIL_MAX_LENGTH`, and
`self.full_name = require_text(self.full_name, field="full_name", max_length=self.FULL_NAME_MAX_LENGTH)`
in `__post_init__`. `require_text` already trims, refuses blank, refuses NUL (D-18's WR-03 fix at
`validation.py` L49-71) and enforces the cap — no new helper, no second copy of the limit.

`create()` at L57-78 gains `full_name: str` as a keyword-only parameter, in the field order the
dataclass declares.

**Where `full_name` goes in the field order matters** for `tests/unit/infrastructure/test_models.py::
test_string_lengths_match_the_entity_caps`, which reads the ClassVar back out.

---

### `domain/validation.py` **(M)** — `require_password` (utility, pure validation)

**Analog:** its own `require_text` at L74-90:

```python
def require_text(value: str, *, field: str, max_length: int) -> str:
    """Return the trimmed value, refusing a blank or over-long one."""
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field} must not be blank.",
            details={"field": field},
        )
    _refuse_nul(text, field=field)
    if len(text) > max_length:
        # The number comes from the argument, never from a literal repeated
        # here, so the entity ClassVar stays the single source of the limit.
        raise ValidationError(
            f"{field} must be at most {max_length} characters long.",
            details={"field": field},
        )
    return text
```

`require_password` differs in exactly three ways, and each needs a comment saying so:
- it does **not** `.strip()` — leading and trailing spaces are part of a password (NIST 800-63B);
- it therefore does not call `_refuse_nul`… **unless** the planner decides a NUL password is a
  refusal too. It never reaches a text column (only the Argon2 hash is stored), so this is a
  decision to state, not to assume;
- it has a **minimum** as well as a maximum, and the two bounds come from module constants in this
  file (the limits live in the domain per Phase 2 D-04, and `User` never sees plaintext, so they
  cannot be `ClassVar`s on the entity — say this in the docstring, because it looks inconsistent).

The `details={"field": field}` shape is what lands in the problem body's `errors` member; keep it.

---

### `application/dto/commands.py` **(M)** — six new commands (DTO)

**Analog:** its own `ChangeTaskStatusCommand` at L189-205:

```python
@dataclass(frozen=True, slots=True)
class ChangeTaskStatusCommand:
    """Ask for a task to move to `new_status`, on behalf of `actor_id`.

    `task_list_id` is the list the task was addressed *under*, which is not the
    same thing as the task's own parent: the use case compares the two and
    refuses a mismatch with the answer an absent task gets (D-14). ...
    """

    actor_id: UUID
    task_list_id: UUID
    task_id: UUID
    new_status: TaskStatus
```

Every command is `@dataclass(frozen=True, slots=True)` with `actor_id: UUID` **first** — the module
docstring L4-10 states that rule. Two of this phase's commands break it and the plan must say why in
the command's own docstring:

| Command | `actor_id` first? | Note for the planner |
|---|---|---|
| `RegisterUserCommand` | **no** — there is no actor | An unauthenticated operation. State it: "this is one of the two commands with no `actor_id`, because the caller does not exist yet." |
| `LoginCommand` | **no** — same | Same note. |
| `AuthenticateActorCommand` | n/a | Consider passing the raw token as a plain `str` argument to `execute` rather than a one-field command; `ListTaskListsCommand` L66-78 argues the opposite (a one-field command keeps the signature uniform). **Follow `ListTaskListsCommand`** — uniformity is the stated convention. |
| `AssignTaskCommand` | yes | `actor_id, task_list_id, task_id, assignee_id` — mirrors `ChangeTaskStatusCommand` field-for-field. |
| `UnassignTaskCommand` | yes | `actor_id, task_list_id, task_id` — identical to `DeleteTaskCommand` L180-186. |
| `ListUsersCommand`, `ListAssignedTasksCommand` | yes | One field each; copy `ListTaskListsCommand`'s docstring argument at L68-75 verbatim in spirit. |

**Pitfall 7 (Pydantic in the application layer) is a convention, not a gate.** `.importlinter`'s
`application-framework-free` contract deliberately omits `pydantic` (comment at `.importlinter`
L38-44). The password therefore travels as a plain `str`; the `SecretStr` → `.get_secret_value()`
conversion happens in the schema's `to_command()`.

---

### `application/dto/results.py` **(M)** — `UserResult`, `AccessTokenResult` (DTO)

**Analog:** its own `TaskResult` at L35-72:

```python
@dataclass(frozen=True, slots=True)
class TaskResult:
    """One task, flattened out of the aggregate at a single moment in time."""

    id: UUID
    ...

    @classmethod
    def from_entity(cls, task: Task) -> "TaskResult":
        """Copy every field of the entity, naming each one explicitly.

        Written out rather than derived from `dataclasses.asdict` or a
        `**vars(task)` splat: those forms would carry a newly added entity
        field into an API response the moment someone declared it, which is the
        opposite of the boundary this class exists to be.
        """
        return cls(id=task.id, ...)
```

`UserResult.from_entity(user)` copies `id, email, full_name, created_at` **and deliberately not
`password_hash`** — that omission is the field-by-field argument above doing its job, and the
docstring should name it (FEATURES section 8 rule 13, already cited in `user.py` L11-14).

`AccessTokenResult` has no entity to map from; it is constructed by `Login`. It is still a frozen
slotted dataclass. Fields at discretion: `access_token: str`, `token_type: str`, `expires_in: int`.

---

### `application/ports/repositories.py` **(M)** — `TaskRepository.list_for_assignee`

**Analog:** its own `list_for_task_list` at L70-79:

```python
    # TASK-06: filtering by status and by priority is a requirement of the
    # listing endpoint, so it belongs in the query the adapter issues rather
    # than in a comprehension the use case applies to a full table read.
    async def list_for_task_list(
        self,
        task_list_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> Sequence[Task]: ...
```

`async def list_for_assignee(self, assignee_id: UUID) -> Sequence[Task]: ...` with a comment naming
D-02, and the same "belongs in the query, not in a comprehension" argument.

### `application/ports/security.py` **(M)** — the D-21 port extension

**Analog:** its own `PasswordHasher` at L27-31:

```python
class PasswordHasher(Protocol):
    """Turns a plaintext password into a stored hash, and checks one against it."""

    async def hash(self, password: str) -> str: ...
    async def verify(self, password: str, hashed: str) -> bool: ...
```

The module docstring L1-21 is where the *reason* for a port method is argued. D-21's new method
belongs there in the same voice: the dummy hash needs `pwdlib`, `application` may not import it
(`.importlinter` names `pwdlib` in `application-framework-free`), and hard-coding an Argon2 string
in source reads as a credential. **Flag this as a deliberate port change in the plan** — CONTEXT's
carried-forward section says the ports keep their shape "unless research proves a need".

---

### `infrastructure/security/passwords.py`, `tokens.py`, `notifications/logging.py` (adapters)

**Analog:** `infrastructure/clock.py` — the whole file, L1-26. It is the project's smallest adapter
and states the four conventions every new adapter must follow:

```python
"""The runtime adapter for `Clock`, the one port that performs no I/O.

`application/ports/clock.py` explains why that port is not `async`; this is its
production implementation, and it lives in `infrastructure` for the same reason
every other adapter does - the application layer names the capability, the outer
layer supplies it.
...
There is no base class and no ABC: `Clock` is a `typing.Protocol`, so
conformance is structural and mypy strict is the gate that checks it.
"""

from datetime import UTC, datetime


class SystemClock:
    """Reads the real system clock, as an aware UTC `datetime` (D-14)."""

    def now(self) -> datetime:
        return datetime.now(UTC)
```

Conventions to copy: **no base class, no ABC** (structural conformance, mypy is the gate); the
module docstring points back at the port's docstring rather than repeating it; the adapter's
constructor takes its configuration as arguments, never reads `Settings` itself.

**The exception-translation idiom** for `JwtTokenService.decode` has a precedent in
`db/repositories/users.py` L93-104 — translate the one failure you recognise, re-raise anything else:

```python
    def _refused(self, error: IntegrityError) -> NoReturn:
        """Re-raise a refusal as the error it means, or exactly as it arrived.

        `EmailAlreadyRegisteredError` takes no argument, which is the whole point
        of it: there is nothing to pass, so no call site can leak the address by
        being helpful. An unrecognised constraint is re-raised untouched and
        becomes Phase 2's fixed 500, because `violated_constraint` returning
        `None` means *unknowable* rather than *no conflict* (T-3-14).
        """
        if violated_constraint(error) == UQ_USERS_EMAIL_LOWER:
            raise EmailAlreadyRegisteredError() from error
        raise error
```

This is exactly the argument for catching `jwt.exceptions.InvalidTokenError` and **not** widening to
`PyJWTError`: `InvalidKeyError` means the server is misconfigured, so it must reach the fixed 500,
not become a 401. Write that sentence in the adapter, in this voice.

**Constructor-injected clock:** `JwtTokenService(..., clock: Clock)` — the port, never
`SystemClock`. `dependencies.py::get_clock` L81-95 makes the identical argument for its own
annotation ("The annotation is the **port**, never the concrete adapter").

---

### `migrations/versions/0002_*.py` (migration)

**Analog:** `migrations/versions/0001_baseline.py`. Four conventions, all in that file.

**Revision identifiers** (L39-43):

```python
# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Constraint names as literals, never imports** — the docstring at L23-31 is the rule and must be
echoed (ADR-025):

```
The constraint names
are left as literals rather than imported from
`taskmanager.infrastructure.db.constraints`: a revision is a frozen record of
what a database was migrated to, and a name read from a constant would silently
rewrite that record the day the constant is renamed. The agreement is checked
mechanically anyway, in two hops - `tests/unit/infrastructure/test_models.py`
asserts the constants against the DDL the models render, and `alembic check`
asserts this schema against those same models.
```

**`op.f()` for convention-generated names** (L138-140):

```python
    op.create_index(
        op.f("ix_tasks_task_list_id"), "tasks", ["task_list_id"], unique=False
    )
```

**A real downgrade, children before parents, indexes explicit** (L143-153):

```python
def downgrade() -> None:
    """Drop everything upgrade() created, children before parents."""
    # Reverse dependency order: tasks references task_lists and users, and
    # task_lists references users, so dropping users first would fail on the
    # foreign keys. The two indexes are dropped explicitly because both were
    # created as standalone statements rather than inside a CREATE TABLE.
    op.drop_index(op.f("ix_tasks_task_list_id"), table_name="tasks")
    ...
```

`migrated_database` (`tests/integration/conftest.py` L181-207) runs `downgrade base` then
`upgrade head`, so a broken `downgrade()` fails the whole integration suite at the first fixture.

**Also note L18-21 of `0001`** — "A second revision will appear only when a genuine change requires
one." This phase is that genuine change; the `0002` docstring should say so, closing the loop.

---

### `infrastructure/db/models.py` **(M)** — `UserRow.full_name`, indexed `assignee_id`

**Analog for the column:** its own `UserRow.email` at L54 — `email: Mapped[str] = mapped_column(String(320))`.
The `VARCHAR(n)` length **is** the limit enforcement here (no `CHECK`); `models.py` L11-20 argues
that no column delegates a value to a server-side default.

**Analog for the index:** its own `TaskRow.task_list_id` at L113-115:

```python
    task_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("task_lists.id", ondelete="CASCADE"), index=True
    )
```

`assignee_id` at L121-123 gains `index=True`. **The file already argues against speculative
indexes twice** — L101-104 (no index on `task_lists.owner_id`, it is the leading column of a unique
constraint) and L144-149 (no composite index). The new index must carry the counter-argument
explicitly, in that voice: no unique constraint covers `assignee_id`, it is the whole `WHERE` of
`GET /tasks/assigned-to-me`, and it is the scan every `ON DELETE SET NULL` performs.

### `infrastructure/db/constraints.py` **(M)** — `IX_TASKS_ASSIGNEE_ID`

**Analog:** its own L46, `IX_TASKS_TASK_LIST_ID: Final[str] = "ix_tasks_task_list_id"`.
The module docstring L16-20 says most names are *produced* by the naming convention and this module
is the assertion of what it must render. `tests/unit/infrastructure/test_models.py` must grow from
twelve names to thirteen in the same commit.

### `infrastructure/db/mappers.py` **(M)** — `full_name` in the user trio

**Analog:** the three functions at L78-108, already grouped:

```python
def user_to_row(user: User) -> UserRow:
    """Build the row that persists this user, field by explicit field."""
    return UserRow(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def user_to_entity(row: UserRow) -> User:
    """Rehydrate the user this row stores."""
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        created_at=_aware(row.created_at, column="users.created_at"),
        updated_at=_aware(row.updated_at, column="users.updated_at"),
    )


def apply_user_to_row(user: User, row: UserRow) -> None:
    """Write the user's current values onto the row already in the session."""
    # `row.id` is deliberately not reassigned. ...
    row.email = user.email
    row.password_hash = user.password_hash
    row.created_at = user.created_at
    row.updated_at = user.updated_at
```

All three gain `full_name` in the same position. `_aware()` is only for datetimes.

### `infrastructure/db/repositories/tasks.py` **(M)** — `list_for_assignee`

**Analog:** its own `list_for_task_list` at L179-216. The ordering rationale is at L202-206 and is
the exact argument D-02 and D-25 need:

```python
        The order is `created_at` and then `id`, because `created_at` alone is
        not a total order - two tasks created in the same request share an
        instant, and PostgreSQL may then return them either way round, which is
        how a Phase 4 assertion about the first element passes on one run and
        fails on the next.
        """
        statement = select(TaskRow).where(TaskRow.task_list_id == task_list_id)
        ...
        rows = await self._session.scalars(
            statement.order_by(TaskRow.created_at, TaskRow.id)
        )
        return [task_to_entity(row) for row in rows]
```

`SqlAlchemyUserRepository.list_all` (`users.py` L76-91) is the same `ORDER BY` written for users and
is the one `ListUsers` reuses unchanged — **no adapter change is needed for `GET /users`.**

---

### `presentation/api/routers/assignments.py` (router, request-response)

**Analog:** `presentation/api/routers/tasks.py` L282-331 — the status door, which D-05 says to mirror.

**The route declaration** (`tasks.py` L282-321):

```python
@task_router.patch(
    "/{list_id}/tasks/{task_id}/status",
    response_model=TaskResponse,
    summary="Change a task's status",
    response_description=(
        "The task in full, after the move. Only the transitions the state "
        "machine allows are accepted; a request for the state the task is "
        "already in is a 200 no-op that changes nothing, not an error "
        "(D-11, TASK-05)."
    ),
    responses={
        404: {"description": NOT_FOUND_DESCRIPTION},
        409: {"description": TRANSITION_DESCRIPTION},
        422: {"description": VALIDATION_DESCRIPTION},
        500: {"description": UNEXPECTED_DESCRIPTION},
    },
)
async def change_task_status(
    list_id: UUID,
    task_id: UUID,
    payload: TaskStatusChangeRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
) -> TaskResponse:
    """The one door onto the state machine (D-11).
    ...
    """
    result = await ChangeTaskStatus(uow, clock).execute(
        payload.to_command(actor_id=actor_id, task_list_id=list_id, task_id=task_id)
    )
    return TaskResponse.from_result(result)
```

Copy: the `responses` map with **every** refusal leg declared; an explicit `response_model=` *and*
a return annotation (`task_lists.py` L37-42 says why inference is not enough); the handler is
four lines; `payload.to_command(...)` builds the command, never the handler; the path's parent
segment always travels into the command.

**New legs this phase adds to every `responses` map:**
- `401` on every authenticated route — a new `UNAUTHENTICATED_DESCRIPTION: Final[str]` constant
  alongside the existing ones (`tasks.py` L57-79 shows the constant style).
- `403` on the assignment routes, the generic task `PATCH` and `DELETE` (D-03).

**The refusal-description constants** (`tasks.py` L57-65) are re-declared per module rather than
imported — `schemas/tasks.py` L34-37 states that rule for its own two messages and the reason
(a shared constant makes one endpoint's wording change another's).

**Registration** (`tasks.py` L324-331):

```python
def register_task_routes(app: FastAPI) -> None:
    """Install the task router under `/api/v1`, from create_app().

    A separate registration from the task-list router's, and a separate router,
    even though the two share a URL prefix: the split is what gives `/docs` two
    groups, and it keeps each module readable in one screen.
    """
    app.include_router(task_router, prefix="/api/v1")
```

Every new router module exposes exactly one `register_*_routes(app)`. `GET /api/v1/tasks/assigned-to-me`
needs a **different prefix** (`/tasks`) from the assignee door (`/task-lists`), so it is either a
second `APIRouter` in `assignments.py` with its own registration call, or its own module. Research
Open Question 5 recommends a third OpenAPI tag, `assignments`.

---

### `presentation/api/routers/auth.py` (router)

**Analog for the 201 + `Location` shape:** `routers/task_lists.py` L94-139:

```python
async def create_task_list(
    payload: TaskListCreateRequest,
    actor_id: CurrentActor,
    uow: UnitOfWorkDependency,
    clock: ClockDependency,
    request: Request,
    response: Response,
) -> TaskListResponse:
    """Create a list owned by the caller, and say where it now lives (D-12).

    The owner is never read from the body. `TaskListCreateRequest` declares no
    `owner_id` and forbids extra keys, and the owner reaches the command from
    `CurrentActor` alone - so a client cannot create a list in someone else's
    name by adding a key (T-4-35, T-4-43).
    ...
    """
    result = await CreateTaskList(uow, clock).execute(
        payload.to_command(actor_id=actor_id)
    )
    response.headers["Location"] = str(
        request.url_for("get_task_list", list_id=result.id)
    )
    return TaskListResponse.from_result(result)
```

**D-19 diverges here and the divergence must be commented.** Every existing `Location` is built with
`request.url_for(<handler name>, ...)` — `task_lists.py` L73-74 explicitly says an f-string over
`/api/v1/...` "would not" survive a prefix change. D-19 points `Location` at `/api/v1/auth/me`,
which is a **route with no path parameters**, so `request.url_for("read_current_user")` still works
and must be used rather than a literal. Say in the route docstring that the header names a resource
the caller can read only after logging in.

**`register` and `login` are the two routes with no `CurrentActor` parameter.** Every other handler
in the project takes it. That absence is the openness of the route and should be stated in the
docstring, because it is invisible otherwise — the matrix test (row 2, row 3) is what proves it.

---

### `presentation/api/schemas/auth.py`, `schemas/users.py` (schemas)

**Analog for a request body:** `schemas/tasks.py` L144-172:

```python
class TaskStatusChangeRequest(BaseModel):
    """`PATCH .../tasks/{id}/status`: the one door onto the state machine (D-11).

    One required field, so an empty body is a 422 without needing the patch
    models' at-least-one-field rule. The value is enum-typed, so an unknown
    state is refused before any use case runs and can never reach SQL as free
    text (T-4-39); no membership check is written anywhere.
    """

    model_config = ConfigDict(extra="forbid")

    status: TaskStatus

    def to_command(
        self, *, actor_id: UUID, task_list_id: UUID, task_id: UUID
    ) -> ChangeTaskStatusCommand:
        """Bind the requested state to the task the path addressed. ..."""
        return ChangeTaskStatusCommand(...)
```

`TaskAssigneeRequest` (D-05's `{"assignee_id": "<uuid>"}`) is this file's class with one field
swapped. It belongs in `schemas/tasks.py` beside its sibling, not in a new module — the status
request lives there and the two are the same kind of door.

**Analog for a response body:** `schemas/tasks.py` L175-210:

```python
class TaskResponse(BaseModel):
    """One task on the wire: the eleven members of `TaskResult`, in its order.

    Declaration order is serialisation order, so this list is the contract. It
    mirrors the result DTO exactly, which is what lets `from_result` below be a
    field-for-field copy that a reviewer can check by reading down two columns.
    """

    id: UUID
    ...
    assignee_id: UUID | None

    @classmethod
    def from_result(cls, result: TaskResult) -> "TaskResponse":
        """Copy every field of the result, naming each one explicitly."""
        return cls(id=result.id, ...)
```

**`TaskResponse.assignee_id` already exists at L193 — ASGN-02 needs no schema change.**

`UserResponse` (`{id, email, full_name, created_at}`) and `UserSummaryResponse`
(`{id, full_name, email}` for ASGN-03's literal wording) copy this class field-for-field from
`UserResult`. **Neither declares `password_hash`**, and the "field-for-field, naming each one
explicitly" rule at L197 is what guarantees a later `UserResult` field cannot leak into a response.

**The two boundary rules stated in `schemas/tasks.py` L1-15** apply to every new schema:
no business limit at the boundary (the 8-128 password rule lives in `domain/validation.py`,
per Phase 2 D-04 and CONTEXT D-10), and the `UNSET` marker never in a field annotation.

**Pitfall 6 needs a comment**: `EmailStr` lowercases the **domain half only**; `User.__post_init__`
lowercases the whole address. Both stay. `user.py` L4-9 already argues the complementary split for
format-vs-form; the register schema should point at it rather than look like duplication.

---

### `presentation/api/dependencies.py` **(M)** — new providers

**Analog:** its own three-part structure — the private narrowing L32-38, a stateless provider
L81-95, and the alias block L98-103.

**The one narrowing** (L32-38) — see **RC-3**:

```python
def _resources(request: Request) -> DatabaseResources:
    """The database container the composition root put on `app.state`.

    The single narrowing of this module, deliberately private so it cannot
    acquire a second call site outside this file.
    """
    return cast(DatabaseResources, request.app.state.database)
```

`DatabaseResources` itself (`infrastructure/db/engine.py` L34-50) is the container to copy for a
`SecurityResources` (or similar) holding the token service and the password hasher:

```python
class DatabaseResources:
    """The engine and its session factory, as one typed value.

    This exists so `app.state` carries a single object instead of two loose
    attributes. `starlette.datastructures.State.__getattr__` returns `Any`,
    which mypy strict treats as an implicit-`Any` source, so every read of
    `app.state.engine` would need its own `cast` to stay clean. ...

    Frozen because neither half may be swapped after the application is built ...
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
```

**A stateless provider** (L81-95) is the copy-from for `get_email_notifier`, which needs no config:

```python
def get_clock() -> Clock:
    """The system clock, built fresh for whoever asks (D-14).

    It takes no `Request` because it reads nothing off the application, and it
    is not stored on `app.state` for the same reason: `SystemClock` holds no
    state, opens nothing and costs a single object allocation ...

    The annotation is the **port**, never the concrete adapter, exactly as
    `get_uow`'s is. A use case that wants a frozen instant in a test gets it by
    overriding this provider, which is a line in a fixture rather than a change
    to a signature.
    """
    return SystemClock()
```

**Return the port, never the adapter** — `-> PasswordHasher`, `-> TokenService`, `-> EmailNotifier`.

**The alias block** (L98-103):

```python
# The two aliases every Phase 4 router shares, declared once here rather than
# re-spelled per router. They are annotations and not argument defaults, for the
# B008 reason `health.py` L47-L54 sets out in full; that argument is not
# repeated here.
UnitOfWorkDependency = Annotated[UnitOfWork, Depends(get_uow)]
ClockDependency = Annotated[Clock, Depends(get_clock)]
```

New aliases go here: `TokenServiceDependency`, `PasswordHasherDependency`, `EmailNotifierDependency`.
The B008 argument is at `health.py` L47-54 and is **not** re-litigated per module — do not repeat it.

**One caveat the analog does not cover.** `PwdlibPasswordHasher` is expensive to construct if it
lazily computes a dummy hash (D-21). A fresh instance per request would recompute it. The
`get_clock` argument ("holds no state, opens nothing, costs a single object allocation") does not
apply — so the hasher belongs in the `app.state` container beside the token service, and the plan
should note that the divergence from `get_clock` is deliberate.

---

### `presentation/api/actor.py` **(M)** — rewritten body

**Analog:** its own L46-59 — the signature and the alias, which do not change:

```python
def get_current_actor() -> UUID:
    """The caller's identity, which in Phase 4 is always the demo user.

    A plain `def` with no parameters: it reads no request, no header and no
    application state, because there is nothing yet to read. Phase 5 gives it
    the token dependency and the decode, and every call site stays as written.
    """
    return DEMO_USER_ID


# Declared as an annotation, never as an argument default - the B008 argument
# `health.py` L47-L54 makes in full, which this module deliberately does not
# re-litigate.
CurrentActor = Annotated[UUID, Depends(get_current_actor)]
```

`CurrentActor` keeps its name, its type (`UUID`) and its target function. That is what makes every
router, schema, command and use case unchanged (ADR-044).

**Four things this module must lose, all named in the file itself:**

| Line(s) | What goes | Why |
|---|---|---|
| L3-4 | `"""...This is **not authentication**, and saying so plainly is the whole point of the module."""` | Phase 5 makes it authentication. `tests/unit/presentation/test_actor.py::test_the_module_says_it_is_not_authentication` asserts the literal phrase `"not authentication"` appears in the source; that test is deleted, and the plan must say so as a deliberate act rather than a quiet drop. |
| L43 | `DEMO_USER_ID: Final[UUID] = UUID("00000000-0000-4000-8000-00000000de00")` | ADR-045. `grep -rn DEMO_USER_ID` returns exactly four files: `actor.py`, `docker/entrypoint.sh` (L154, L170), `tests/unit/presentation/test_actor.py`, `tests/integration/api/test_task_lists.py`. |
| L10-15 | the "it is a module of its own because the seed imports `DEMO_USER_ID`" argument | The seed is gone. |
| L29-31 | `"Nothing here touches the database, and that is load-bearing"` | D-11 makes it touch the database on every request. |

**The body has no analog in this repository** — see "No Analog Found". The two rules it must obey
are stated elsewhere and must be cited in the new docstring:
- It must reach the unit of work **through `Depends(get_uow)`**, never by calling `get_uow(request)`.
  `dependencies.py::get_uow`'s own docstring L51-77 and RESEARCH Pitfall 4 both explain why; the
  harness overrides the *dependency*, and a direct call would dial `tests/conftest.py` L24's
  fictional DSN.
- It must raise `AuthenticationError`, never `HTTPException`. The AST gate at
  `tests/architecture/test_routers_raise_no_http_exception.py` covers all of `presentation/api` now
  (WR-05), including star and aliased imports, so `OAuth2PasswordBearer(auto_error=True)` is not an
  option.

---

### `main.py` **(M)** — composition root

**Analog:** itself, L53-82:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, optionally with explicitly injected settings."""
    resolved = settings or get_settings()
    resources = create_database_resources(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Nothing on the way up; the engine is released on the way down.

        The startup half is empty and must stay empty - that is D-06. ...
        """
        yield
        await resources.engine.dispose()

    app = FastAPI(...)
    app.state.database = resources
    register_exception_handlers(app)
    register_health_routes(app)
    register_task_list_routes(app)
    register_task_routes(app)
    return app
```

Additions: `configure_logging()` near the top, a second `app.state.<container>` assignment, and
three `register_*_routes(app)` calls in the existing block.

**Two gates this function is already held to, both cited in its docstring L10-16:**
- `test_creating_the_app_opens_no_connection` — `configure_logging()` must open nothing. Attaching a
  `StreamHandler(sys.stdout)` satisfies that.
- `test_the_lifespan_disposes_the_engine` — the lifespan's startup half stays empty. Do **not** put
  `configure_logging()` in the lifespan; `tests/integration/conftest.py` L312-320 records that the
  HTTP harness never enters the lifespan at all (ADR-056), so anything placed there is untested.

`configure_logging()` must be **idempotent** — `create_app()` runs hundreds of times across the
suite (RESEARCH Pattern 8, property 3).

---

### `tests/integration/conftest.py` **(M)** — `authenticated_client`

**Analog:** its own `api_client` at L297-352:

```python
@pytest.fixture
async def api_client(
    session_factory: Callable[[], AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    """The real application, over HTTP, over the rolled-back test connection.
    ...
    It yields the application beside the client rather than the client alone.
    Overriding `get_current_actor` is the only way to reach D-04's not-owned
    legs over HTTP, and a test cannot override a provider on an application it
    cannot name.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_uow] = lambda: SqlAlchemyUnitOfWork(session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app
```

`authenticated_client` is this fixture **plus** a real `Authorization` header, and it must yield
`(client, app)` for the same reason. Two details the analog supplies:

- `JWT_SECRET` is `tests/conftest.py` L25's `"b" * 32` — already ≥ 32 bytes, so RESEARCH Pitfall 1's
  `InsecureKeyLengthWarning` under `filterwarnings = error` is not triggered by the existing harness.
- The token has to be minted with the **same** secret/algorithm the app was built with. Building
  `Settings(_env_file=None)` twice is how the fixture already gets a consistent configuration.

**`acting_as` (L355-379) stays verbatim.** Its docstring L367-369 claims "the seam … answers with
one fixed identifier until Phase 5 replaces its body, so a second actor exists in a test and nowhere
else" — that sentence needs rewriting, but the context manager's restore-on-exit behaviour is exactly
what strategy (c) needs and must not be simplified into a one-way setter.

**`seed` (L423-465) is unchanged and its commit rule is mandatory** — L430-440 explains that a
session which does not commit rolls its savepoint back and the seeded rows vanish. Every new
integration module seeds through it.

**`statements` (L382-420)** is the fixture `test_statements.py` reads; no change.

---

### `tests/integration/api/test_auth.py`, `test_users.py`, `test_assignment.py` (API integration tests)

**Analog:** `tests/integration/api/test_task_lists.py` L1-150.

**The two standards every test obeys** (L9-14):

```
Two standards apply to every test below, and both cost nothing now and a great
deal later. Each asserts on the **response body**, never on the status code
alone - a 201 whose body is missing a counter is a broken contract that a status
assertion cannot see. And each mutating test **re-reads through the API**, so
"it was written" is a fact about the database rather than about the return value
of the handler that claimed to write it.
```

**Fixed identifiers in a readable series** (L53-70):

```python
# Fixed identifiers and fixed instants, in the readable series the sibling
# integration modules use. A value generated at run time would make an assertion
# about "the list that was renamed" true of whichever row happened to be there,
# and the ordering tests below are exactly where that stops being noticed.
OTHER_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
LIST_ID = uuid.UUID("00000000-0000-4000-8000-000000000011")
...
NOW = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)
```

`test_statements.py` L64-69 shows how the series is *continued*, not restarted, by a later module.
Phase 5 needs an `ASSIGNEE_ID` and a `STRANGER_ID` in the `…0003`/`…0004` slots and must not reuse
the Phase 4 numbers.

**The member-order contract** (L74-89) is the model for asserting the register/me/users bodies:

```python
# D-10's nine members, in the order `TaskListResponse` declares them. Pydantic
# serialises in declaration order, so the *order* is contract too: a client that
# reads the body as an ordered document should not have it rearranged under
# them, and a member silently added or dropped is what `list(body)` catches and
# a per-key lookup does not.
TASK_LIST_MEMBERS = [...]
```

`list(body) == USER_MEMBERS` is precisely the assertion that proves `password_hash` is absent,
where `"password_hash" not in body` would pass against a body that had renamed it.

**Entity builders with keyword-only overrides** (L92-141), e.g.:

```python
def a_user(
    *,
    user_id: uuid.UUID = DEMO_USER_ID,
    email: str = DEMO_EMAIL,
) -> User:
    """A valid user entity, differing from the demo actor only where asked. ..."""
    return User.create(user_id=user_id, email=email, password_hash=PASSWORD_HASH, now=NOW)
```

`a_user` gains `full_name` and its `user_id` default changes from `DEMO_USER_ID` (deleted) to a
module-local `OWNER_ID`. It is imported by `test_statements.py` L48-58 — a signature change there
ripples.

**The error contract is imported, never re-declared** (L38-44):

```python
# Imported rather than re-declared. The media type and the six-member list
# are the error contract Phase 2 fixed, and `tests/api/test_error_contract.py`
# is where they are stated; a second copy here would be the one that quietly
# disagreed the first time the contract moved.
from tests.api.test_error_contract import MEMBERS, PROBLEM_JSON
```

Every 401/403/404/409 assertion in this phase uses `MEMBERS` and `PROBLEM_JSON`.

---

### `tests/unit/application/test_write_paths_hold_what_they_change.py` **(M)** — three new cases

**Analog:** its own `test_change_task_status_holds_the_task_it_validates` at L103-122:

```python
async def test_change_task_status_holds_the_task_it_validates() -> None:
    """The use case CR-01 was reproduced against.

    Validating `change_status` against a copy loaded through `get` is what let a
    second writer persist `completed -> pending`. Held exactly once: a second
    hold would be a second statement on the hottest write path in the phase.
    """
    unit_of_work = _uow()

    await ChangeTaskStatus(unit_of_work, FrozenClock(NOW)).execute(
        ChangeTaskStatusCommand(
            actor_id=ACTOR_ID,
            task_list_id=LIST_ID,
            task_id=TASK_ID,
            new_status=TaskStatus.IN_PROGRESS,
        )
    )

    assert unit_of_work.task_repository.held_for_update == [TASK_ID]
    assert unit_of_work.task_list_repository.held_for_update == []
```

Three new tests in this exact shape: `AssignTask`, `UnassignTask`, and the **assignee's** status
change (a second actor against the same task). The second assertion — the parent list is *not* held
— is the lock-ordering rule from `access.py` L62-66 and must appear in every one.

`test_no_read_use_case_ever_holds_anything` (L174-193) says in its docstring "a fourth read added
later belongs here" — `ListAssignedTasks` is that read and goes in the same test.

---

### `tests/integration/test_concurrent_writes.py` **(M)** — owner vs assignee

**Analog:** the module's own harness, L101-175. Three pieces to reuse verbatim:

```python
class _Clock:
    """The `Clock` port, stopped at `LATER`, local so this module imports no fake."""

    def now(self) -> datetime:
        return LATER
```

```python
LOCK_TIMEOUT_MS = 8_000
OBSERVE_FOR = 5.0
AWAIT_WRITER_FOR = 15.0

WAITING_ON_A_LOCK = text(
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
)
```

```python
async def _remove_what_was_committed(engine: AsyncEngine) -> None:
    """Both foreign keys cascade from `users`, so one row takes the rest along."""
    async with engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM users WHERE id = :id"), {"id": OWNER_ID}
        )
```

**The new case needs a second user row**, so `_remove_what_was_committed` must delete both, or the
assignee row must be created as a child of nothing that cascades from `OWNER_ID`. The docstring at
L18-22 records why cleanup is legitimate here and not the housekeeping the integration conftest
forbids; the extension should keep that argument true.

The module docstring L24-38 is the template for describing the new interleaving and what goes red
without the lock — write the equivalent paragraph for owner-PATCH vs assignee-PATCH-status.

---

### `tests/architecture/test_routers_raise_no_http_exception.py` **(M)**

**Analog:** its own L116-126:

```python
REQUIRED_SCANNED_MODULES: Final[frozenset[str]] = frozenset(
    {
        "actor.py",
        "dependencies.py",
        "health.py",
        "routers/task_lists.py",
        "routers/tasks.py",
        "schemas/task_lists.py",
        "schemas/tasks.py",
    }
)
```

Add, in the same commit that creates each file: `routers/auth.py`, `routers/users.py`,
`routers/assignments.py`, `schemas/auth.py`, `schemas/users.py`. RESEARCH Pitfall 14 explains why
the non-vacuity guard (L236-237, `assert REQUIRED_SCANNED_MODULES <= scanned`) still passes without
them: the file is scanned incidentally, but nothing asserts it *must* be.

---

### `tests/unit/application/fakes.py` **(M)** — three edits

**Analog for the ordering fix:** its own `list_for_task_list` at L93-100:

```python
        # Ordered by `(created_at, id)`, exactly as the SQLAlchemy adapter's
        # `ORDER BY` is, and for the reason `list_for_owner` below gives at
        # length: the fake used to return insertion order, which is a divergence
        # with teeth - a D-13 assertion about the first element would pass here
        # and fail over HTTP, where PostgreSQL is free to answer in whatever
        # order the plan produced. `created_at` alone is not a total order
        # either, since the clock is read once per request.
        return sorted(tasks, key=lambda entry: (entry.created_at, entry.id))
```

`FakeUserRepository.list_all` (L223-224) is today `return list(self.stored.values())` — the exact
divergence that comment describes, missed when `FakeTaskRepository` and `FakeTaskListRepository`
were both fixed. Apply the same `sorted(..., key=lambda entry: (entry.created_at, entry.id))`
**and the same comment** (D-25 asks for it to be falsified the way 04-06 did).

`FakeTaskRepository.list_for_assignee` copies L86-100 with a different predicate.

**The `held_for_update` recorder** (L58, L63-65) exists already and is what the write-path tests read:

```python
    async def get_for_update(self, task_id: UUID) -> Task | None:
        self.held_for_update.append(task_id)
        return self.stored.get(task_id)
```

Nothing to add there.

**`FakePasswordHasher`** (L322-336) gains `dummy_verify` if D-21 lands:

```python
class FakePasswordHasher:
    """A reversible prefix in place of Argon2id: deterministic and instant.

    Real hashing is intentionally expensive, which is a property no unit test
    wants to pay for on every run. The prefix keeps `verify` honest - a wrong
    password still fails - without any of the cost.
    """

    PREFIX = "fake-hash:"

    async def hash(self, password: str) -> str:
        return f"{self.PREFIX}{password}"

    async def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"{self.PREFIX}{password}"
```

---

## Shared Patterns

### 1. Errors: no router answers a business failure

**Source:** `presentation/api/errors/mapping.py` (`STATUS_BY_EXCEPTION`) + `errors/handlers.py` L74-83
**Apply to:** every new router, every new use case, `actor.py`

The whole 401/403/404/409 contract this phase needs **already exists and needs no code change**:

```python
STATUS_BY_EXCEPTION: Final[dict[type[DomainError], int]] = {
    DomainError: 500,
    ValidationError: 422,
    BusinessRuleViolationError: 422,
    InvalidStatusTransitionError: 409,
    NotFoundError: 404,
    ConflictError: 409,
    AuthenticationError: 401,
    AuthorizationError: 403,
}
```

The table is keyed by class and resolved by an MRO walk (docstring L3-11), so `UserNotFoundError`
resolves through `NotFoundError` to 404 and `EmailAlreadyRegisteredError` through `ConflictError` to
409 with no new entry. **Do not add leaf classes to this table** — the docstring L36-44 names that
as a deliberate omission.

The 401 challenge is already wired (`handlers.py` L74-83):

```python
    # RFC 9110 section 15.5.2: a server generating a 401 MUST send a challenge.
    # `handle_http_exception` gets this for free by forwarding `exc.headers`,
    # but a domain `AuthenticationError` carries no headers of its own, and
    # `ports/security.py` already specifies that Phase 5's `TokenService.decode`
    # raises exactly that. The challenge therefore belongs here, at the one
    # place a business failure becomes an HTTP response, rather than in the
    # adapter that has not been written yet.
    if status == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
```

### 2. Layer boundaries: what each new module may import

**Source:** `.importlinter`
**Apply to:** every new module

| New module | May import | Enforced by |
|---|---|---|
| `domain/validation.py` | stdlib only | `domain-framework-free` (lists `jwt`, `pwdlib`, `pydantic`) + `test_domain_is_stdlib_only.py` |
| `application/use_cases/auth/*.py`, `tasks/assign.py` | ports, DTOs, domain, **`logging` (stdlib, permitted)** | `application-framework-free` forbids `fastapi`, `starlette`, `sqlalchemy`, `alembic`, `jwt`, `pwdlib` |
| `infrastructure/security/*.py` | `jwt`, `pwdlib`, `anyio`, ports, domain | `no-http-below-presentation` forbids only `fastapi`/`starlette` here |
| `presentation/api/**` | everything below + FastAPI, **never `HTTPException`** | `test_routers_raise_no_http_exception.py` (AST, two passes, star-import aware) |

`.importlinter` L38-44 records that `pydantic` is deliberately **not** forbidden in `application` —
it is a convention stated in `dto/commands.py`, not a gate. Do not rely on a build failure for it.

### 3. Transactions: the use case owns the boundary, the repository never commits

**Source:** `application/ports/repositories.py` L22-41 + `use_cases/tasks/change_task_status.py` L76-101
**Apply to:** `RegisterUser`, `Login`, `AuthenticateActor`, `AssignTask`, `UnassignTask`, `ListUsers`, `ListAssignedTasks`

- `async with self._uow:` opens; `await self._uow.commit()` on the success path **only**; the result
  is mapped **outside** the block (`change_task_status.py` L99-101).
- A read-only use case never commits — `use_cases/task_lists/list.py` L27-28 says why ("the
  transaction wrote nothing, and `__aexit__` closing it is the port's documented obligation").
- `tests/architecture/test_no_commit_in_repositories.py` scans
  `src/taskmanager/infrastructure/db/repositories/` for any transaction-ending call.
- The unit of work is **single-entry but re-openable** — `actor.py`'s new body enters and exits
  within itself, and the use case's later `async with` is a re-open, pinned by
  `test_a_unit_of_work_can_be_reopened_after_its_block_ended`.

### 4. Row locking: every new write path goes through the `for_update` door

**Source:** ADR-058, `access.py` L49-66 + `repositories/tasks.py` L78-104
**Apply to:** the assignee's status change, `AssignTask`, `UnassignTask`

```python
def task_for_update_statement(task_id: UUID) -> Select[tuple[TaskRow]]:
    """The write-path read: one task row, locked until the transaction ends.
    ...
    `populate_existing` is the other half of "latest committed state". A session
    that already held this row in its identity map would otherwise be handed that
    cached object back with its old attribute values, lock or no lock, which is
    the defect again by a quieter road.
    """
    return (
        select(TaskRow)
        .where(TaskRow.id == task_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
```

Nothing new is needed in the adapter — `get_for_update` already exists on both task repositories.
The three rules from `access.py` L49-66: read paths never lock; only the **addressed** resource is
held (a task's writer never holds its list); `for_update` is keyword-only so a write path names it
at the call site.

### 5. Ordering: `created_at`, then `id`, no pagination

**Source:** `repositories/users.py` L76-91, `repositories/tasks.py` L202-216 (ADR-043)
**Apply to:** `GET /users`, `GET /tasks/assigned-to-me`, and their fakes

```python
        rows = await self._session.scalars(
            select(UserRow).order_by(UserRow.created_at, UserRow.id)
        )
        return [user_to_entity(row) for row in rows]
```

The `id` tie-break is not decoration — `users.py` L82-86 records it as review fix WR-03. Both the
adapter **and** the fake must sort (Pitfall 9).

### 6. Dependency injection: `Annotated[T, Depends(provider)]`, never an argument default

**Source:** `health.py` L47-54 (the full argument), `dependencies.py` L98-103 (the aliases)
**Apply to:** every new provider and every new route parameter

flake8-bugbear B008 in `make lint` is the gate; `.flake8`'s `extend-immutable-calls` whitelists the
dotted spelling `fastapi.Depends`, and this project imports by name, so the default-argument form
fails. The argument lives in `health.py` and is **not** repeated per module.

### 7. OpenAPI: assert through `app.openapi()`, never `app.routes` (ADR-057)

**Source:** `tests/unit/presentation/test_actor.py` L64-77 (alias introspection) + ADR-057
**Apply to:** `tests/unit/presentation/test_security_scheme.py`

The existing alias test is the closest shape for pinning that a dependency still points where it
should:

```python
def test_current_actor_depends_on_this_module_s_provider() -> None:
    """The alias routers will use resolves to `get_current_actor`, still. ..."""
    assert get_origin(CurrentActor) is Annotated

    annotated_type, marker = get_args(CurrentActor)

    assert annotated_type is UUID
    assert marker.dependency is get_current_actor
```

This test survives the rewrite verbatim and is worth keeping as the one positive assertion that
replaces the deleted `test_the_module_says_it_is_not_authentication`.

### 8. Port conformance: a typed assignment, checked by mypy strict

**Source:** `tests/unit/application/test_ports.py` L92-104 + `tests/unit/infrastructure/test_adapter_ports.py` L73
**Apply to:** the three new adapters

```python
def test_fake_password_hasher_satisfies_the_password_hasher_port() -> None:
    hasher: PasswordHasher = FakePasswordHasher()
    assert hasher is not None
```

```python
    repository: UserRepository = SqlAlchemyUserRepository(a_session_factory()())
```

The assignment **is** the test; `mypy --strict` is the gate. No ABC, no `isinstance`.

### 9. Test doubles live under `tests/`, never under `src/`

**Source:** `tests/unit/application/fakes.py` L1-16
**Apply to:** the in-memory notifier, hasher and token service (all three already exist)

```
They live under `tests/` on purpose. A fake under `src/` would be shipped code
with no caller, and it would drag the ports into the coverage report as
*implemented* rather than declared ...
```

This rules out an `InMemoryEmailNotifier` in `infrastructure/notifications/` for test use. The
runtime `LoggingEmailNotifier` is the only notifier that ships.

### 10. Documentation as a checkable contract

**Source:** `access.py` L32-36, `tests/unit/presentation/test_actor.py` L78-89, `test_no_commit_in_repositories.py`
**Apply to:** `access.py`'s docstring (D-22), `actor.py`'s docstring, `CLAUDE.md`'s Project Rules

This project repeatedly asserts prose and relies on a *name not being spelled* so a grep stays
meaningful (`conftest.py` L20-23, `.importlinter` comments, `routers/task_lists.py` L22-26). Phase 5
falsifies two such claims and must rewrite both in the commit that falsifies them — not later, and
not silently.

---

## No Analog Found

Five things in this phase have no close match in the codebase. The planner should take the shape
from `05-RESEARCH.md` (which verified each by execution) rather than looking for a precedent.

| File / concern | Role | Data Flow | Why there is no analog | Where to get the shape |
|---|---|---|---|---|
| `infrastructure/logging.py` (`JsonFormatter`, `configure_logging`) | config/bootstrap | — | The project has never configured logging. uvicorn configures only `uvicorn*`; root stays at WARNING, so today's INFO line is dropped entirely (verified). | RESEARCH Pattern 8, including the four executed properties: `propagate` stays `True` (`caplog` in `tests/api/test_error_contract.py` depends on it), no double printing, idempotence via a handler marker, and `caplog.at_level(INFO, logger=...)` in the test. |
| `presentation/api/actor.py` body (`OAuth2PasswordBearer(auto_error=False)` → `AuthenticateActor`) | provider | request-scoped identity | Nothing in the project extracts a credential from a request. `health.py` is the only other module reading the framework's request surface, and it reads none. | RESEARCH Pattern 1, with the four-row behaviour table (missing header, non-bearer scheme, empty param, lowercase `bearer`) and the verified `securitySchemes` emission through a nested dependency. |
| The post-commit notification leg in `AssignTask` | use case | side effect after transaction | No use case in the project does anything after `commit()` except map a result. `except Exception` in application code has one precedent, in `docker/entrypoint.sh`, not in `src/`. | RESEARCH Pattern 7: capture `recipient_email` and `task_title` **inside** the block (the uow unbinds its repositories on exit), `try/except Exception` outside it, `logger.warning(..., exc_info=True)`, swallow (NOTF-03). Verify the flake8 code with `make lint` rather than pre-committing a `noqa` (Assumption A2). |
| `tests/integration/api/test_permission_matrix.py` | API integration test | parametrized table | No parametrized cross-product test exists. The closest is `test_access.py`'s paired-refusal style, which is per-case, not tabular. | RESEARCH "The full permission matrix" — 19 rows × 4 columns, lifted verbatim. It must run on the **unoverridden** client with three real tokens plus no header. A missing cell must be visible in the table. |
| `Login`'s timing equalisation (dummy-verify) | use case | credential check | Nothing in the project has a timing-side-channel concern. | RESEARCH Pattern 4 + Open Question 3: the port gains one method; the fake follows; the observable status and body are locked by D-12 and asserted byte-for-byte. |

---

## Open Decisions the Planner Must Resolve Before Writing Plans

These come from RESEARCH's Open Questions and are all **answered by CONTEXT** except the last two.
Listed here so a plan does not silently pick one.

| # | Question | CONTEXT's answer | Status |
|---|---|---|---|
| 1 | Where does `Location` on register point? | **D-19: `/api/v1/auth/me`** | Resolved — use `request.url_for(<me handler>)`, not a literal. |
| 2 | Does `PasswordHasher` gain a dummy-verify? | **D-21: yes, deliberately recorded as a port extension** | Resolved — needs an ADR. |
| 3 | Which harness strategy? | **D-20: strategy (c)** — `api_client` keeps its override, `authenticated_client` is added; 401 legs, the anonymous column and `test_statements.py` go through the real dependency; counts become 2 and 4 | Resolved. |
| 4 | Does `Settings.jwt_secret`'s `min_length` move 16 → 32? | **Not stated in CONTEXT.** RESEARCH recommends 32 (RFC 7518 §3.2; PyJWT warns below 32 and `filterwarnings = error` makes that fatal). Every value in the repo is already ≥ 32. | **Unresolved** — a change to an existing validated setting. It touches `settings.py` L41, `tests/unit/test_settings.py::test_short_secret_is_rejected`, `.env.example`'s comment, and `test_env_example_documents_every_field`. Surface it, do not slip it in. |
| 5 | Which OpenAPI tag for `assigned-to-me`? | Not stated. RESEARCH recommends a third tag, `assignments`. | **Unresolved, cosmetic** — pick one and record it in the router docstring. |

---

## Metadata

**Analog search scope:** `src/taskmanager/**` (all 48 modules), `migrations/versions/`, `tests/**`
(all 46 test modules), `.importlinter`, `docker/entrypoint.sh`, `.planning/phases/04-task-lists-tasks/04-PATTERNS.md`
**Files read in full:** 24 source modules, 8 test modules, 1 migration, 1 config file
**Files read by targeted range:** 6 (`repositories/tasks.py`, `mappers.py`, `entities/task.py`,
`test_task_lists.py`, `test_statements.py`, `test_concurrent_writes.py`)
**Pattern extraction date:** 2026-09-19
