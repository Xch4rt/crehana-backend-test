---
phase: 04-task-lists-tasks
fixed_at: 2026-09-19T07:57:36Z
review_path: .planning/phases/04-task-lists-tasks/04-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 6
fixed: 6
skipped: 0
out_of_scope: 6
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-09-19T07:57:36Z
**Source review:** .planning/phases/04-task-lists-tasks/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, WR-01..WR-05)
- Fixed: 6
- Skipped: 0
- Out of scope by `fix_scope: critical_warning`: 6 (IN-01..IN-06, listed at the end)

**Gates on `main` after the last commit (`f4c9a63`):** `make lint` clean (141 files), `make typecheck`
`Success: no issues found in 141 source files`, `make arch` `4 kept, 0 broken`, `make test`
`643 passed`, coverage `100.00%` (baseline was 599 passed / 100.00%). No `# pragma: no cover`, no
coverage `omit`, threshold untouched, no `--no-verify`. No commit carries an AI attribution trailer.

**How the work was isolated.** Every edit and commit happened in a temporary git worktree on a
throwaway branch, which was fast-forwarded into `main` at the end and deleted; `main` has no merge
commit and the branching strategy is still "none". The worktree borrowed the host `.venv` through a
symlink and ran with `PYTHONPATH=<worktree>/src`, verified with `taskmanager.__file__`, because the
editable install would otherwise have pointed every tool at the main checkout. The four gates were
re-run on `main` itself after the fast-forward; that is the run quoted above.

**Status values.** CR-01 and WR-01 change logic, so they are marked
`fixed: requires human verification` per the fixer's own rule: syntax checks and a green suite do
not prove a condition is the right one. Each carries the specific thing to look at.

## Fixed Issues

### CR-01: Read-modify-write without a row lock

**Status:** fixed: requires human verification
**Commit:** `63f6ee4`
**Files modified:** `src/taskmanager/application/ports/repositories.py`,
`src/taskmanager/application/use_cases/access.py`,
`src/taskmanager/application/use_cases/tasks/{change_task_status,update,delete}.py`,
`src/taskmanager/application/use_cases/task_lists/{update,delete}.py`,
`src/taskmanager/infrastructure/db/repositories/{tasks,task_lists}.py`,
`tests/unit/application/fakes.py`, `tests/unit/application/test_ports.py`,
`tests/integration/test_repositories_{tasks,task_lists}.py`, `DECISION_LOG.md` (ADR-058 appended)
**New files:** `tests/integration/test_concurrent_writes.py`,
`tests/unit/application/test_write_paths_hold_what_they_change.py`,
`evidence/04-review-fix-CR-01-red.txt`

**Applied fix:** a locking read on both aggregate ports, stated in domain terms with no SQLAlchemy
type in the signature:

```python
# application/ports/repositories.py
class TaskRepository(Protocol):
    async def get_for_update(self, task_id: UUID) -> Task | None: ...
class TaskListRepository(Protocol):
    async def get_for_update(self, task_list_id: UUID) -> TaskList | None: ...

# application/use_cases/access.py
async def visible_task_list(uow, task_list_id, actor_id, *, for_update: bool = False) -> TaskList
async def visible_task(uow, task_list_id, task_id, actor_id, *, for_update: bool = False) -> Task
```

Contract: the entity returned is the latest committed state, and until the unit of work ends no
other unit of work can obtain it through `get_for_update`. The adapters keep it with
`.with_for_update()` plus `populate_existing=True`, in two module-level statement functions
(`task_for_update_statement`, `task_list_for_update_statement`). The five write paths pass
`for_update=True`; every read path keeps the default and never waits. Lock-ordering rule: only the
*addressed* resource is held - a task's writer holds the task and reads its parent list plainly.
The write path costs no extra statement (`update` finds the row in the identity map);
`tests/integration/api/test_statements.py` covers GET routes only and **no expected count was
edited**.

**Regression tests:**
- `tests/integration/test_concurrent_writes.py::test_a_stale_writer_cannot_persist_a_forbidden_transition`
  - two units of work on two real connections; A is paused after its locking read, B (the real
  `ChangeTaskStatus`) is observed waiting in `pg_stat_activity`, A completes and commits, B is refused
  with `InvalidStatusTransitionError` (`{"from": "completed", "to": "pending"}`), and the row is
  still `completed` with A's `completed_at`.
- `::test_two_list_patches_are_serialised_and_neither_edit_is_lost`,
  `::test_a_read_never_waits_on_a_writer`.
- Bounded three ways (`lock_timeout=8s` on every connection, a 5 s polling deadline,
  `asyncio.wait_for` 15 s) so a broken lock is a red test and never a hung suite. Rows committed
  outside the rollback fixture are deleted from a separate connection in the fixture's `finally`,
  and once more before seeding so a killed run cannot poison the next; `taskmanager_test` was
  verified empty afterwards. Ran 8 times in a row, stable.
- `tests/unit/application/test_write_paths_hold_what_they_change.py` (9 tests): which road each of
  the eight addressed-resource use cases takes, both directions.
- `test_the_write_path_read_locks_the_row`, `test_the_write_path_read_locks_the_list_row` (compiled
  SQL ends in `FOR UPDATE`), `test_get_for_update_never_answers_from_the_identity_map`,
  `test_both_aggregate_ports_declare_the_write_path_read`.

**Red proof:** `evidence/04-review-fix-CR-01-red.txt` - `.with_for_update()` deleted from both
adapters, 2 failed / 1 passed; restored, 3 passed. **Honest limitation, stated in the file:** the
reviewer's exact ordering (B commits *after* A) cannot be constructed once every write path enters
through the locking read, so the red run shows the mirror image - B does not wait, commits
`pending`, is told it succeeded, and A overwrites it.

**For the human verifier:** (1) plain `FOR UPDATE` was chosen over `FOR NO KEY UPDATE`; ADR-058
says why and when to revisit. (2) The reviewer's claim that a concurrent PATCH "writes back its
stale status" did not reproduce at the SQL level: SQLAlchemy emits only changed columns, so the
stale columns were never in the `UPDATE`. The response body *was* stale, and the lock fixes that;
the list-PATCH test therefore goes red on "never waited", not on lost data. (3) CLAUDE.md was
deliberately not edited by this run - consider adding the write-path rule to "Persistence and
transactions".

### WR-01: PATCH re-sending a list's own name with surrounding whitespace is a false 409

**Status:** fixed: requires human verification
**Commit:** `0869013`
**Files modified:** `src/taskmanager/domain/entities/task_list.py`,
`src/taskmanager/application/use_cases/task_lists/update.py`,
`src/taskmanager/application/use_cases/task_lists/create.py`, four test modules
**Applied fix:** `TaskList.normalised_name(name)` is now the one normaliser (`__post_init__` and
`rename` call it). `UpdateTaskList` compares and pre-checks on the normalised name and raises the
conflict with it; `CreateTaskList` builds the entity first and pre-checks/raises with
`task_list.name`, so the 409 has one spelling on both roads.
**Deviation from the review's suggestion, deliberate:** the review proposed calling `rename()`
before the pre-check ("the in-memory mutation is harmless"). That is true for the real adapter and
false for `FakeTaskListRepository`, which returns the stored object itself -
`test_update_task_list_refuses_a_rename_onto_a_name_the_owner_uses` asserts the stored entity is
untouched after a refusal and would have failed. Validating before assigning is also the entity's
own stated rule.
**Regression tests:** `test_resending_the_lists_own_name_padded_is_not_a_conflict`,
`test_a_refused_rename_reports_the_normalised_name`,
`test_a_refused_create_reports_the_normalised_name`,
`test_normalised_name_is_the_name_the_entity_would_store`,
`test_renaming_a_list_to_its_own_name_padded_with_whitespace_succeeds` (HTTP),
`test_a_duplicate_409_reports_the_trimmed_name_on_both_verbs` (HTTP).
**Red proof:** `evidence/04-review-fix-WR-01-red.txt` - 6 failed with `src/` stashed, 6 passed restored.

### WR-02: A `due_date` whose UTC conversion overflows is a 500

**Status:** fixed
**Commit:** `93c4d2c`
**Files modified:** `src/taskmanager/domain/validation.py`, three test modules
**Applied fix:** `require_utc` catches `OverflowError`/`ValueError` from `astimezone(UTC)` and raises
the domain `ValidationError` ("<field> is outside the supported date range.",
`details={"field": field}`), chained with `from error`. The rule is in `domain/validation.py`, not in
Pydantic.
**Regression tests:** `test_require_utc_refuses_a_value_whose_utc_form_is_out_of_range` (both
boundary strings), `test_require_utc_accepts_the_last_representable_instant` (positive control),
`test_task_create_refuses_a_due_date_with_no_utc_form`,
`test_task_reschedule_refuses_a_due_date_with_no_utc_form`,
`test_a_due_date_with_no_utc_form_is_a_domain_validation_error` (HTTP, POST and PATCH, 422
`validation_error`, `errors == {"field": "due_date"}`).
**Red proof:** `evidence/04-review-fix-WR-02-red.txt` - 8 failed / 1 passed (the control), then 9 passed.

### WR-03: A NUL character in any text field is a 500

**Status:** fixed
**Commit:** `5299d7d`
**Files modified:** `src/taskmanager/domain/validation.py`, three test modules
**Applied fix:** `_refuse_nul(text, *, field)` called from both `require_text` and `optional_text`,
before the length check. Not a caught driver error. Only NUL is refused; other control characters
are storable and were left alone on purpose.
**Regression tests:** `test_require_text_refuses_a_nul_character`,
`test_optional_text_refuses_a_nul_character`, `test_a_nul_is_reported_before_the_length`,
`test_a_nul_character_in_a_list_field_is_a_domain_validation_error` and
`test_a_nul_character_in_a_task_field_is_a_domain_validation_error` (HTTP, POST and PATCH, name/title
and description, 422 with the right `field`). Source files were checked to contain no literal NUL byte.
**Red proof:** `evidence/04-review-fix-WR-03-red.txt` - 7 failed, then 7 passed.

### WR-04: The response-model test could not fail

**Status:** fixed
**Commit:** `b68686c`
**Files modified:** `tests/unit/test_app_factory.py`
**Applied fix:** `test_every_api_route_declares_a_response_model_or_returns_no_content` now compares
each route's published 2xx schema - a `$ref`, or an array of one - against a hand-written
`EXPECTED_RESPONSE_MODELS` table, and asserts that every name in the table is a `BaseModel` defined
under `presentation/api/schemas/` and that the table covers `EXPECTED_API_ENDPOINTS` exactly. An
inline or empty schema is reported as `<inline>`.
**Red proof:** `evidence/04-review-fix-WR-04-red.txt` - two plants on `get_task` (returns the
`TaskResult` dataclass; no annotation at all). Under **both**, the old test passes and the new test
fails naming the route and what it found (`TaskResult`, `<inline>`); shipped tree green. This test
had never been driven red before.

### WR-05: The HTTPException AST gate covered `routers/` only and did not catch an aliased import

**Status:** fixed
**Commit:** `6f30d07`
**Files modified:** `tests/architecture/test_routers_raise_no_http_exception.py`, `.importlinter`
**Applied fix:** the gate walks all of `presentation/api` except the single module
`errors/handlers.py` - checked: it is the only module that names the class, because it registers a
handler for `starlette.exceptions.HTTPException`; `errors/mapping.py` and `errors/problem.py` are
scanned. `REQUIRED_SCANNED_MODULES` now names `actor.py`, `dependencies.py`, `health.py`, both routers
and both schema modules. The raise pass resolves aliased imports (the docstring's claim is now
true); the import pass also refuses `from fastapi|starlette... import *` and a bare `ast.Name`.
`test_the_exempt_module_still_needs_its_exemption` fails if the exemption outlives its reason. Three
snippet tests keep each spelling honest on every run. The overclaiming `.importlinter` comment was
corrected. File name kept, because CLAUDE.md and other documents point at it.
**Not done (the review's "optionally"):** detecting a hand-built `JSONResponse(status_code=404, ...)`.
`health.py` legitimately sets a status on a response, so a syntactic rule needs more design; the
gap is stated in the gate's docstring.
**Red proof:** `evidence/04-review-fix-WR-05-red.txt` - aliased import + raise planted in `actor.py`:
old gate green (3 passed), new gate both passes red (`actor.py:55`, `actor.py:38`); star-import
only: import pass red alone; shipped tree 7 passed.

## Additional commit

`f4c9a63` `docs(04)` - the dated incident entry in `AI_WORKFLOW.md` ("599 green tests and 100%
coverage sat on top of a lost update, and only the code review found it"), citing the real hashes
and test names. It is a separate commit because it has to cite `63f6ee4`, which cannot name itself.
ADR-058 went into the CR-01 commit; `DECISION_LOG.md` was appended to, never edited.

## Out of Scope (fix_scope: critical_warning)

Not attempted. Listed so they are not mistaken for fixed.

| ID | Title | File |
|----|-------|------|
| IN-01 | `.importlinter` enforces "stdlib-only domain" with a denylist | `.importlinter:29-43,52-63` |
| IN-02 | The seed's untargeted `ON CONFLICT DO NOTHING` hides an email collision | `docker/entrypoint.sh:156-162` |
| IN-03 | `Location` is built from the request's `Host` header | `routers/task_lists.py:136-138`, `routers/tasks.py:132-134` |
| IN-04 | A repeated filter parameter is silently reduced to its last value | `routers/tasks.py:90-91` |
| IN-05 | Both collections and every text field are unbounded at the boundary | routers and schemas |
| IN-06 | Three tests in `test_actor.py` assert prose or tautologies | `tests/unit/presentation/test_actor.py:42,78,91` |

## Notes for the Phase 5 planner

- The assignee who may change a task's status concurrently with the owner, and the new `AssignTask`
  write path, are further writers of the same task row. They must load through
  `uow.tasks.get_for_update(task_id)` - via `visible_task(..., for_update=True)` or whatever guard
  Phase 5 introduces for the assignee - and must not put a plain `get` on a write path.
- Keep the lock-ordering rule: hold only the addressed resource; a task's writer never holds a list.
- A new write use case adds a test to `test_write_paths_hold_what_they_change.py`; a new read adds
  itself to `test_no_read_use_case_ever_holds_anything`.
- `actor.py` and `dependencies.py` are now inside the HTTPException gate. An authentication failure
  is a `DomainError` translated by the single handler, never a raised `HTTPException(401)`. A new
  module under `presentation/api` adds its name to `REQUIRED_SCANNED_MODULES`.
- A new route adds a row to `EXPECTED_RESPONSE_MODELS` beside `EXPECTED_API_ENDPOINTS`.

---

_Fixed: 2026-09-19T07:57:36Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
