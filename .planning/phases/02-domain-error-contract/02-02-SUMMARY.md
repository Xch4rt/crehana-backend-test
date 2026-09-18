---
phase: 02-domain-error-contract
plan: 02
subsystem: domain
tags: [python, stdlib, exceptions, pickle, flake8-bugbear, pytest, mypy]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: src layout, editable install, pytest/mypy/flake8/black/isort gates, import-linter contracts, coverage gate
  - plan: 02-01
    provides: TaskStatus, whose .value is what InvalidStatusTransitionError stores in details
provides:
  - DomainError base with _restore/__reduce__/__str__, the only shape that passes B042, mypy strict and a pickle/copy round trip
  - twelve subclasses covering the seven error families, each with a ClassVar code and title
  - Details = dict[str, str | int | float | bool | None], the static half of the JSON-safety guarantee
  - a closedness test that fails when an error class is added without being mapped
affects: [02-03-entities, 02-04-error-handlers, 02-05-ports, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One __reduce__ on the error base delegating to a module-level _restore, so no subclass ever needs a pickle dunder of its own"
    - "Explicit __str__ on the error base, because B042 forces a 2-tuple args and the inherited __str__ would render the details dict"
    - "details values constrained by a type alias rather than dict[str, Any], so an unserialisable value is a mypy error at the raise site"
    - "A frozenset of expected names as living documentation of a closed hierarchy, guarded against a vacuous empty walk"
    - "Single-parameter exception leaves forward details as a keyword: B042 counts positional arguments, and suppression comments are forbidden"

key-files:
  created:
    - src/taskmanager/domain/exceptions.py
    - tests/unit/domain/test_exceptions.py
    - .planning/phases/02-domain-error-contract/evidence/02-02-tdd-red.txt
    - .planning/phases/02-domain-error-contract/evidence/02-02-b042-leaf-arity.txt
  modified: []

key-decisions:
  - "details is typed Details = dict[str, str | int | float | bool | None], narrower than RESEARCH's dict[str, Any], so the error handler cannot fail on its own input"
  - "Single-argument leaves pass details as a keyword: flake8-bugbear B042 compares positional-argument count with parameter count, a case RESEARCH's two-parameter sample never reached"
  - "EmailAlreadyRegisteredError carries {\"field\": \"email\"} and never the submitted address"
  - "The base class is included in SAMPLE_ERRORS, so the code/title/JSON-safety claims cover all thirteen classes, while closedness counts only the twelve subclasses"

patterns-established:
  - "Module docstring names the rejected alternative and the linter rule that rejects it, without writing the suppression token the plan's grep gate forbids"
  - "A linter finding that contradicts research is captured as an evidence file with the checker's own source quoted, not paraphrased"

requirements-completed: []

# Metrics
duration: 14min
completed: 2026-09-18
---

# Phase 2 Plan 02: Domain Error Contract Summary

**The closed `DomainError` hierarchy - one base carrying `_restore`/`__reduce__`/`__str__` and twelve subclasses covering the seven error families, every one with a stable `ClassVar` code, a human title and a `details` dict whose values cannot be anything but JSON primitives - proven closed, pickle-safe and serialisable by 8 tests at 100% coverage.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-09-18T05:57:46Z
- **Completed:** 2026-09-18T06:11:40Z
- **Tasks:** 2
- **Files modified:** 4 created, 0 modified

## Accomplishments

- `taskmanager.domain.exceptions` exists with thirteen classes and imports nothing but `typing`, `uuid` and `taskmanager.domain.value_objects.task_status` - no `fastapi`, no `starlette`, no `http`, and no status-code literal anywhere in the file (ARC-06, threat T-02-17). The three import-linter contracts stay KEPT.
- One `__reduce__` on the base fixes pickling for **every** subclass, including the five with their own signature: `pickle.loads(pickle.dumps(InvalidStatusTransitionError(COMPLETED, PENDING)))` returns the same leaf class with equal details, as do `copy.copy` and `copy.deepcopy`. Without it the rebuild would call a two-`TaskStatus` signature with the base's `(message, details)` args.
- `str(exc) == exc.message`, asserted - so no log line and no `detail=str(exc)` can ever carry the structured payload (threat T-02-14).
- `Details = dict[str, str | int | float | bool | None]` makes a `UUID` or a `TaskStatus` in `details` a **mypy error at the raise site**; `test_every_error_details_payload_is_json_serialisable` proves the same claim at runtime for one instance of every class (threat T-02-04). This is the deliberate narrowing of RESEARCH's `dict[str, Any]` that Open Question 5 recommended.
- `test_hierarchy_is_closed` walks `__subclasses__()` recursively and compares the result with a twelve-name `frozenset`, with a length guard first so an empty walk cannot pass vacuously. An error class added in Phase 4 or 5 without a status mapping now fails a test instead of reaching the client unmapped (threat T-02-16).
- `EmailAlreadyRegisteredError` names the field and never the address, asserted by a test that also checks no `@` survives into the serialised details (threat T-02-15).
- `exceptions.py` reports **100% coverage** (68 statements, 0 missed) with no `pragma: no cover` and no coverage `omit`; the whole suite is 37 passed, 100% total.
- The suite was additionally run on the target runtime via `make docker-test` (Python 3.13): 37 passed, coverage gate reached - so nothing here depends on the host's 3.14.3.

## Task Commits

Each task was committed atomically:

1. **Task 1: the DomainError base and the twelve subclasses** - `be9e103` (feat)
2. **Task 2: specify the hierarchy with tests** - `a648b83` (test)

**Plan metadata:** see the `docs(02-02)` commit that carries this SUMMARY.

## Files Created/Modified

- `src/taskmanager/domain/exceptions.py` (200 lines) - `DetailValue`/`Details` aliases, the `_restore` helper, `DomainError`, and the twelve subclasses in the taxonomy order the plan fixed
- `tests/unit/domain/test_exceptions.py` (160 lines) - `EXPECTED_SUBCLASS_NAMES`, `SAMPLE_ERRORS` (one instance per class, fixed literals), and 8 tests: closedness, pickle/copy, codes and titles, JSON safety, the D-01 transition details, the not-found identifiers, the email non-echo, and the empty-details default
- `.planning/phases/02-domain-error-contract/evidence/02-02-tdd-red.txt` - the observed RED collection failure and the GREEN run of the same command
- `.planning/phases/02-domain-error-contract/evidence/02-02-b042-leaf-arity.txt` - the four B042 findings research did not predict, plus the checker's own source showing why

## Decisions Made

- **`details` is typed, not `Any`.** RESEARCH's module used `dict[str, Any]`; Open Question 5 flagged the consequence and recommended narrowing. `DetailValue = str | int | float | bool | None` is now the static half of threat T-02-04's mitigation and `test_every_error_details_payload_is_json_serialisable` is the runtime half. The module comment says what the narrowing prevents, so it does not read as a transcription slip.
- **Single-parameter leaves name `details` as a keyword** (see Deviations). `InvalidStatusTransitionError` is the only leaf whose parameter count already matches the two values it forwards, so it stays positional; the module docstring explains the split in three sentences rather than leaving a reader to spot it.
- **The base class is a `SAMPLE_ERRORS` entry.** `DomainError` itself is raisable and carries `domain_error` / "Domain error", so the code, title and JSON-safety claims are made about all thirteen classes. Closedness is a separate count of twelve, because the base is not its own subclass.
- **No `can_raise` helper, no `to_dict()`, no status attribute.** The class-to-status table is plan 02-04's `presentation/api/errors/mapping.py`; putting even a hint of it here would have reintroduced the HTTP knowledge CONTEXT explicitly keeps out of the domain.
- **ARC-06 is not ticked in `REQUIREMENTS.md`.** This plan delivers the hierarchy, but ARC-06 is also claimed by 02-03 (entities raising these errors), 02-04 (the handler that maps them) and 02-07. Plan 02-07, the last claimant, owns the tick - same convention 02-01 set for ARC-02.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] flake8-bugbear B042 fires on every single-argument leaf - a case 02-RESEARCH.md never exercised**

- **Found during:** Task 1, at the plan's own `flake8 src tests` verification step
- **Issue:** RESEARCH Pattern 6 verified the base plus `InvalidStatusTransitionError`, whose `__init__` takes two parameters and forwards two positional arguments to `super().__init__()`. Every leaf that takes **one** domain object - `TaskNotFoundError`, `TaskListNotFoundError`, `UserNotFoundError`, `DuplicateTaskListNameError` - forwards a message *and* a details dict, i.e. two positional arguments against one declared parameter, and B042 fired four times. Reading `bugbear.check_for_b042` shows why: it computes `expected_arg_count` from the signature and flags `len(call.args) != expected_arg_count`. It counts **positional arguments only**. The plan forbids `# noqa`, and CLAUDE.md forbids `--no-verify`, so neither escape was available.
- **Fix:** every single-parameter leaf (and the zero-parameter `EmailAlreadyRegisteredError`, for consistency) now passes `details=` as a keyword. The stored state is byte-identical; the counts agree; the check stays live. The module docstring gained a paragraph stating the rule and why two call shapes therefore exist in one file.
- **Files modified:** `src/taskmanager/domain/exceptions.py`
- **Verification:** `.venv/bin/flake8 src tests` exits 0 with zero B042 findings; the pickle/copy round trip is unchanged and still asserted.
- **Committed in:** `be9e103` (Task 1 commit), with both the failing output and the checker's source captured in `evidence/02-02-b042-leaf-arity.txt`

**2. [Rule 3 - Blocking] The module docstring tripped the plan's own "no suppression comment" grep gate**

- **Found during:** Task 1 verification
- **Issue:** the docstring paragraph that explains *why* B042 is not silenced spelled the suppression token out. The plan's acceptance criterion is `grep -c 'noqa' … returns 0`, so prose about the forbidden form failed the gate that exists to ban the form itself.
- **Fix:** the paragraph now says "an inline suppression comment on that line - the obvious way out, deliberately absent from this file". Same convention as Phase 1 plan 01-04's Makefile comments: describe the forbidden form without writing it.
- **Files modified:** `src/taskmanager/domain/exceptions.py`
- **Verification:** `grep -c 'noqa' src/taskmanager/domain/exceptions.py` returns 0.
- **Committed in:** `be9e103` (Task 1 commit)

**3. [Rule 3 - Blocking] The same collision in the test file, for the determinism gate**

- **Found during:** Task 2 verification
- **Issue:** the comment justifying the fixed `UUID` literals named the two generators it was avoiding, and the plan's acceptance criterion is `grep -c 'uuid4()\|datetime.now(' … returns 0`.
- **Fix:** reworded to "a freshly generated identifier or a clock reading".
- **Files modified:** `tests/unit/domain/test_exceptions.py`
- **Verification:** the grep returns 0; all 8 tests still pass.
- **Committed in:** `a648b83` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking, 0 bugs)
**Impact on plan:** No scope change, no interface change. Deviation 1 is the substantive one: it corrects a gap in 02-RESEARCH.md Pattern 6 that plans 02-03 and 02-05 would otherwise have walked into the moment they wrote a single-argument exception leaf.

## Issues Encountered

- **02-RESEARCH.md Pattern 6 is incomplete, not wrong.** Its four-shape table is accurate for the base and for a two-parameter leaf; it does not cover the one-parameter leaf, which is the majority shape in this taxonomy. The evidence file records the correction so plans 02-03 and 02-05 do not rediscover it.
- **TDD gate commits again not separable** - same wall plan 02-01 hit. See TDD Gate Compliance below.
- Nothing else. Both tasks passed their full `<verify>` chain after the three fixes above, on the host (CPython 3.14.3) and in Docker (CPython 3.13).

## Known Stubs

None. Every class in the hierarchy is fully implemented and exercised; `exceptions.py` is at 100% statement and branch coverage with no escape hatch.

## TDD Gate Compliance

Both tasks are `tdd="true"` and the cycle was executed in order, but the gate commits are **not** separable in this repository - the convention plan 02-01 established applies unchanged:

- **RED:** the eight specification tests were written first and run against a tree with no `exceptions.py`. The `ModuleNotFoundError` collection failure was observed and captured verbatim in `evidence/02-02-tdd-red.txt`, together with the GREEN run of the identical command. It is not a commit of its own, because the `mypy (strict)` pre-commit hook rejects a test importing a module that does not exist and `--no-verify` is forbidden by CLAUDE.md.
- **GREEN:** `be9e103` (the module, with the RED capture alongside it) and `a648b83` (the tests).
- **REFACTOR:** not needed. The B042 fix happened before green was reached, not after it.

Commit-type note: `be9e103` is a `feat` and `a648b83` a `test`, so the pair reads as GREEN-then-specification in `git log`. The honest ordering is recorded here and in the evidence file rather than faked by a commit sequence the hooks would reject.

## Threat Flags

None. This plan introduces no network endpoint, no auth path, no file access and no schema. Every threat in the plan's register that is dispositioned `mitigate` (T-02-04, T-02-14, T-02-15, T-02-16, T-02-17) is implemented and asserted by a named test or a grep gate; T-02-SC stays not-applicable, since nothing was installed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-03 (entities) can import `ValidationError`, `BusinessRuleViolationError` and `InvalidStatusTransitionError` immediately. Before writing a new single-argument exception leaf, read `evidence/02-02-b042-leaf-arity.txt`.
- Plan 02-04 (the RFC 9457 handler) has the exact contract it was written against: `exc.code`, `exc.title`, `exc.message`, `exc.details`, and one handler registered on `DomainError` catching every leaf through the MRO. Its `mapping.py` must cover all twelve subclass names - `EXPECTED_SUBCLASS_NAMES` in the test module is the list to check against.
- Plan 02-05 (ports) can reference `NotFoundError` and `ConflictError` in Protocol docstrings without importing anything framework-shaped.
- No blockers.

## Self-Check: PASSED

All four created files exist on disk, and both task commits (`be9e103`, `a648b83`) are present in `git log`.

---
*Phase: 02-domain-error-contract*
*Completed: 2026-09-18*
