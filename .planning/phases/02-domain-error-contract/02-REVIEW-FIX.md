---
phase: 02-domain-error-contract
fixed_at: 2026-09-18T17:35:00Z
review_path: .planning/phases/02-domain-error-contract/02-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 6
skipped: 1
status: partial
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-09-18T17:35:00Z
**Source review:** `.planning/phases/02-domain-error-contract/02-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (WR-01..WR-07; 0 critical, 11 Info findings out of scope)
- Fixed: 6
- Skipped: 1 (WR-05 — contradicts locked decision D-14)

All six fixes were applied in an isolated git worktree and each was committed only
after `make lint && make typecheck && make arch && make test` came back green.
The suite went from 140 to 151 tests; coverage stayed at 100% over
`src/taskmanager` throughout, with no `pragma: no cover` and no coverage `omit`
entry added — every new branch is exercised by a new test.

## Fixed Issues

### WR-01: `AuthenticationError` became a 401 without `WWW-Authenticate`

**Files modified:** `src/taskmanager/presentation/api/errors/handlers.py`,
`tests/probe.py`, `tests/api/test_error_contract.py`
**Commit:** `cf12361`
**Applied fix:** `handle_domain_error` now resolves the status once, and adds
`WWW-Authenticate: Bearer` to the response when it is 401. The header cannot be
forwarded from the exception the way `handle_http_exception` does it, because a
domain `AuthenticationError` carries no headers. Added a `/_probe/unauthenticated`
route that raises `AuthenticationError`, and
`test_authentication_error_answers_401_with_the_mandatory_challenge`, which pins
the header and the full D-06 body. The route was also added to the media-type
sweep in `test_every_error_response_uses_the_problem_json_media_type`.

### WR-02: A bare `DomainError` answered 500 with a non-fixed, unlogged body

**Files modified:** `src/taskmanager/presentation/api/errors/handlers.py`,
`src/taskmanager/presentation/api/errors/mapping.py`, `tests/probe.py`,
`tests/api/test_error_contract.py`
**Commit:** `62ef9eb`
**Applied fix:** Took the second of the reviewer's two options — treat an
unmapped domain error as the server fault it is, rather than making the base
class non-instantiable. `handle_domain_error` now delegates any resolved status
`>= 500` to `handle_unexpected_error`, so such an error gets the one fixed D-08
body (no message, no `errors` member) and the logged traceback. The
`STATUS_BY_EXCEPTION` comment in `mapping.py` was updated to say what the
`DomainError: 500` entry now means: it is the signal that routes to the
catch-all, not a business answer.

Making the base non-instantiable was rejected because `SAMPLE_ERRORS` in
`tests/unit/domain/test_exceptions.py` instantiates it deliberately as part of
the taxonomy tests, and because `DomainError` must stay the registered handler
key — an `ABCMeta`-based ban would have been a much larger change than the
finding warrants.

New tests: `/_probe/unmapped-domain` raises a bare `DomainError` carrying a
canary message and a details member;
`test_unmapped_domain_error_answers_the_fixed_internal_error_body` asserts the
fixed body and that neither the canary nor `domain_error` appears in the
response text, and `test_unmapped_domain_error_is_logged_like_any_other_server_fault`
asserts the single ERROR record with its `exc_info`.

### WR-03: The use case disclosed task existence and the list id before authorization

**Files modified:**
`src/taskmanager/application/use_cases/tasks/change_task_status.py`,
`tests/unit/application/test_change_task_status.py`
**Commit:** `c192313`
**Applied fix:** The missing-list branch and the failed-authorization branch now
share one condition and one answer — `TaskNotFoundError(command.task_id)` — so an
actor who is neither owner nor assignee learns nothing from the orphan case that
an absent task would not also tell them. `TaskListNotFoundError` is no longer
imported by the module. The module docstring now records why the orphan leg
answers this way even though Phase 3's cascading foreign key makes the branch
unreachable: this module is the template Phases 4 and 5 copy.

The reviewer's alternative — log the orphan server-side and still answer
`TaskNotFoundError` — was not taken, because the application layer has no logging
convention yet and introducing one here would be a design decision outside the
finding's scope. It is worth revisiting in Phase 3 alongside the real adapters.

`test_change_task_status_raises_task_list_not_found_for_an_orphan` pinned the
leaking behaviour and was rewritten as
`test_change_task_status_hides_an_orphaned_task_behind_the_same_404`, which
catches the base `DomainError` and then asserts which leaf came out, asserts the
details carry only the task id, and asserts the list id appears nowhere — the
same falsifiable shape the existing invisible-task test uses.

### WR-04: `rename()` mutated the entity before it finished validating

**Files modified:** `src/taskmanager/domain/entities/task.py`,
`src/taskmanager/domain/entities/task_list.py`,
`tests/unit/domain/test_task.py`, `tests/unit/domain/test_task_list.py`
**Commit:** `5f225a7`
**Applied fix:** Both `rename` methods now call `require_utc(now, field="now")`
first, bind the result, and only then assign the title/name and the timestamp —
matching what `change_status` and `reschedule` already did. Added
`test_task_rename_with_a_naive_now_changes_nothing` and
`test_task_list_rename_with_a_naive_now_changes_nothing`, each passing a valid
title/name with a naive `now` and asserting the pair `(title, updated_at)` is
unchanged after the refusal.

### WR-06: Nobody owned the rollback, and nothing tested that anyone did

**Files modified:** `src/taskmanager/application/ports/unit_of_work.py`,
`tests/unit/application/fakes.py`, `tests/unit/application/test_ports.py`,
`tests/unit/application/test_change_task_status.py`
**Commit:** `bfdda22`
**Applied fix:** The port's permissive "so the adapter *can* roll it back" became
normative: `__aexit__` MUST roll back whatever was not committed, on every exit
path, and the use case never calls `rollback()` itself. The reason is stated in
the module docstring (a pooled session with `expire_on_commit=False` handed back
dirty) and repeated as the first of the two `__aexit__` obligations.

`FakeUnitOfWork` now tracks a `_finished` flag: `commit()` and `rollback()` set
it, and `__aexit__` increments `rollbacks` when it is still unset, so an explicit
rollback is not double-counted. `rollbacks` is therefore a live counter rather
than dead state.

Three new tests in `test_ports.py` pin the fake's behaviour on its own
(uncommitted block rolls back once; committed block does not; explicit rollback
counts once). Every test in `test_change_task_status.py` now asserts the counter
in both directions — `rollbacks == 1` on all four failure paths, `rollbacks == 0`
on all four success paths — and the module docstring records the stronger
property.

### WR-07: `Task.__post_init__` did not enforce the `status`/`completed_at` invariant

**Files modified:** `src/taskmanager/domain/entities/task.py`,
`tests/unit/domain/test_task.py`
**Commit:** `e9af1aa`
**Applied fix:** After the timestamp guards, `__post_init__` now raises
`ValidationError(details={"field": "completed_at"})` when
`(status is COMPLETED) != (completed_at is not None)`, so D-03 is an invariant of
the type rather than a habit of `change_status`. Three tests: both failing halves
(`COMPLETED` with no stamp, `PENDING` with a stamp) and the coherent rehydration
case that Phase 3's mapper will depend on. The existing
`test_task_rejects_a_naive_completed_at` is unaffected — it builds a coherent
pair whose stamp is naive, and the `require_utc` guard still fires first.

The reviewer's parenthetical suggestion to also check `updated_at < created_at`
was deliberately not implemented: it is a separate invariant with its own
edge cases (clock skew across a cluster, backdated migrations) and no decision
record behind it. It belongs in a Phase 3 discussion, not in this fix.

## Skipped Issues

### WR-05: Server-side clock and persistence faults surface as client `422 validation_error`

**File:** `src/taskmanager/domain/validation.py:20-31`,
`src/taskmanager/domain/entities/task.py:58-73,124,128,151`
**Reason:** The proposed fix directly contradicts a locked user decision. The
finding asks for a new `ensure_utc` guard raising `TypeError` for
trust-boundary-internal values (`now`, `created_at`, `updated_at`,
`completed_at`), keeping `require_utc`/`ValidationError` only for genuine input
fields such as `due_date`.

`02-CONTEXT.md` **D-14** states, without qualification:

> Every temporal value — `created_at`, `updated_at`, `completed_at`, `due_date` —
> is a timezone-aware `datetime` in UTC. **A naive `datetime` reaching the domain
> is a `ValidationError` (`DomainError` subclass).**

The `<decisions>` block of `02-CONTEXT.md` is explicitly marked "decisions
already locked (do not reopen)". Splitting the guard in two would change the
error type for four of the five temporal fields, change five existing domain
tests from `ValidationError` to `TypeError`, and — since a `TypeError` escaping
the domain becomes a 500 via the catch-all — change the observable HTTP contract
of the domain layer. That is a decision for the user and an ADR, not for a review
fix.

No smaller change removes the defect either. The defect *is* the classification
(a clock fault answering 4xx with a field name no request schema contains);
renaming the `field` detail or remapping `ValidationError` would either be
cosmetic or would break the genuine `due_date` case that D-14 and D-04 both rely
on.

**Recommended follow-up:** raise this as a Phase 3 decision point, when
`SystemClock` and the SQLAlchemy mappers — the two adapters that can actually
produce a naive value — are written. At that moment the question has a concrete
answer and can be recorded as an ADR that supersedes the relevant half of D-14.

**Original issue:** `require_utc` raises `ValidationError` (mapped to 422) for
`now` and for the rehydration timestamps, which never come from a client. A naive
`SystemClock` reading or a `TIMESTAMP`-instead-of-`TIMESTAMPTZ` column would
therefore tell the client their payload was invalid, name a field that exists in
no request schema, and hide an infrastructure bug behind a 4xx nobody alerts on.

## Notes

- **Info findings (IN-01..IN-11) were out of scope** for this run
  (`fix_scope: critical_warning`). Three of them were incidentally addressed as a
  side effect of the warning fixes: IN-11's missing 401 and 500 probe coverage is
  now in place (WR-01, WR-02), and IN-10's observation about the fake's dead
  `rollbacks` counter is resolved by WR-06. IN-01, IN-02, IN-03, IN-04, IN-05,
  IN-06, IN-07, IN-08 and IN-09 remain open.
- **No `--no-verify` was used.** All twelve pre-commit hooks ran on each of the
  six commits.
- **Commit messages carry no AI attribution trailer**, per `CLAUDE.md`
  §"Language and attribution".

---

_Fixed: 2026-09-18T17:35:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
</content>
</invoke>
