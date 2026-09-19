---
phase: 05-auth-assignment-notifications
plan: 06
subsystem: infrastructure-logging-notifications
tags: [logging, json, structured-logs, notifications, adapters, log-injection, tdd]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "The EmailNotifier Protocol port with its keyword-only send_task_assigned, and the no-base-class/no-ABC adapter convention infrastructure/clock.py states"
  - phase: 02-domain-error-contract
    provides: "presentation/api/errors/handlers.py's one logging call - logger.error(..., exc_info=exc) for the fixed 500 - which this plan's handler reformats"
  - phase: 05-auth-assignment-notifications
    provides: "05-05's precedent that a port binding has exactly one home, tests/unit/infrastructure/test_adapter_ports.py"
provides:
  - "configure_logging(level=INFO): idempotent, stdout-bound, propagating, side-effect-free JSON logging setup on the `taskmanager` logger"
  - "JsonFormatter: three base fields plus every extra= field as a top-level key, plus the rendered exception, always one line"
  - "LoggingEmailNotifier: the runtime EmailNotifier emitting D-15's task_assigned_email record and transmitting nothing"
  - "PACKAGE_LOGGER, LOGGER_NAME and ASSIGNED_TASKS_PATH as the named constants 05-11 and 05-15 read instead of re-spelling"
  - "The EmailNotifier adapter port binding in tests/unit/infrastructure/test_adapter_ports.py"
affects: [05-08, 05-11, 05-15, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A formatter's reserved-attribute set computed from a throwaway logging.LogRecord at import time, never typed out, because a hard-coded list drifts silently with the standard library (taskName arrived in 3.12)"
    - "Log-injection mitigated by construction rather than by sanitising: every value goes through json.dumps, and the test asserts one parseable line with the injected text as a value"
    - "Process-wide logging state isolated by an autouse fixture that both clears the handler list before a test and restores exactly what pytest left after it"
    - "A no-I/O promise made falsifiable the way test_security_resources.py does it: socket and open replaced with objects that raise, the function called between them"

key-files:
  created:
    - src/taskmanager/infrastructure/logging.py
    - src/taskmanager/infrastructure/notifications/__init__.py
    - src/taskmanager/infrastructure/notifications/logging.py
    - tests/unit/infrastructure/test_logging.py
    - tests/unit/infrastructure/test_notifier.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-06-tdd-red.txt
  modified:
    - tests/unit/infrastructure/test_adapter_ports.py

key-decisions:
  - "JsonFormatter renders record.exc_info into an `exception` field, which the plan and 05-RESEARCH Pattern 8 both omit. Without it this change would have silently thrown every traceback in the application away: handlers.py logs the fixed 500 with exc_info=exc and its docstring promises the traceback reaches the log, exc_info is a reserved LogRecord attribute so the extras merge skips it, and the two existing caplog assertions read record.exc_info rather than formatted output, so nothing in the suite would have failed"
  - "The notifier's logger is named with the literal `taskmanager.notifications`, not the plan's logging.getLogger(__name__). __name__ here is taskmanager.infrastructure.notifications.logging, which propagates to `taskmanager` but never to `taskmanager.notifications` - so the plan's own <behavior> line, its acceptance snippet and D-15 would all have been false"
  - "stack_info is deliberately not rendered: nothing in this project passes it, so the branch would be one no test could reach, and the no-pragma coverage rule has no way to excuse an unreachable line"
  - "json.dumps is called with no `default=` fallback. The one caller stringifies its UUID at the call site, which is the discipline the plan asks for in a comment; a silent coercion would turn a call-site bug into a line whose shape nobody chose"
  - "The handler is attached to the package logger rather than to taskmanager.notifications alone, following 05-RESEARCH's recommendation, and the consequence is named in the module docstring rather than in a changelog: the fixed 500's ERROR record is JSON from now on"
  - "The EmailNotifier port binding went to test_adapter_ports.py alone, even though this plan's Task 2 <behavior> lists it - the 05-05 call, for the reason that module's own docstring gives about Clock"
  - "No requirement tick taken. NOTF-02 is named in this plan's frontmatter and 05-16 is its last claimant; what ships here is an adapter and a logging setup with no use case and no route above them - nothing calls configure_logging() and nothing constructs LoggingEmailNotifier in production yet"

patterns-established:
  - "The autouse logging-isolation fixture: snapshot handlers/level/propagate, clear, yield, restore - the only way a suite can assert on global logging state without the assertion depending on test order"
  - "A source scan for forbidden library names via inspect.getsource, asserting a property about what the file contains rather than about what it did at runtime (the 03-06 SC-4 precedent applied to a mail library)"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-09-19
---

# Phase 5 Plan 06: Structured Logging and the Simulated Invitation Summary

The runtime `EmailNotifier` writes one greppable JSON line, and the application now has a logging
setup that actually emits it — which, verified by execution before this plan, it did not.

## Performance

- **Duration:** ~5 min
- **Started:** 2026-09-19T15:41Z
- **Completed:** 2026-09-19T15:46Z
- **Tasks:** 2 of 2
- **Files modified:** 7 (6 created, 1 modified)

## Accomplishments

- `configure_logging()` attaches exactly one `StreamHandler(sys.stdout)` carrying `JsonFormatter`
  to the `taskmanager` logger at INFO, and a second call returns early because the handler carries
  a private marker attribute. `create_app()` runs hundreds of times across this suite and will
  reach this function once 05-11 wires it in; without the marker every line would be printed once
  per call.
- `propagate` is left true and both halves are asserted — the flag itself, *and* a record reaching
  `caplog`, which attaches to the **root** logger. The flag alone would pass against a handler that
  swallowed the record some other way. The two pre-existing `caplog` assertions in
  `tests/api/test_error_contract.py` still pass.
- `JsonFormatter` emits `level`, `logger` and `message`, then merges every non-reserved record
  attribute — exactly the set a caller passed through `extra=`. The reserved set is computed at
  import from a throwaway `logging.LogRecord` rather than typed out, because a hard-coded list
  drifts silently with the standard library.
- **T-5-13 is mitigated by construction.** Every value goes through `json.dumps`, so a newline
  inside a task title is escaped. The formatter test builds a message containing `\n` and a
  complete `{"level": "ERROR", ...}` object and asserts one parseable line with the injected text
  as the `message` *value*; the notifier test does the same end to end through a task title.
- **A regression the plan would have shipped was caught and closed.** `handlers.py` logs the fixed
  500 with `exc_info=exc` and its docstring promises the traceback goes to the log and nowhere
  else. `exc_info` is a reserved `LogRecord` attribute, so a formatter merging only the extras
  drops it — and the existing assertions read `record.exc_info`, not the formatted output, so the
  suite would have stayed green while every traceback in the application vanished. The formatter
  now renders it into an `exception` field, on one line, with a test for each leg.
- `configure_logging()` performs no I/O, falsifiably: `socket.socket` and `builtins.open` are
  replaced with objects that raise and the function is called between them — the same shape
  `test_security_resources.py` uses, and the property `main.py` depends on when 05-11 calls this
  from `create_app`.
- `LoggingEmailNotifier` emits D-15's exact field set — `event=task_assigned_email`, `to`,
  `subject`, `body`, `task_id` — as one INFO record on `taskmanager.notifications`, so
  `docker compose logs api | grep task_assigned_email` finds it (NOTF-02).
- `task_id` is stringified at the call site with the reason in a comment: a `UUID` is not
  JSON-serialisable and `json.dumps` would raise *inside the formatter*, turning a notification
  into a logging failure. The test asserts the attribute's **type**, not just its rendered value,
  because the rendered value looks identical either way right up until the formatter raises.
- The body names the flat discovery route `/api/v1/tasks/assigned-to-me` (D-02), and the reason is
  a comment rather than an omission: the port carries `task_id` but no `task_list_id`, so the
  nested URL cannot be built from what the method is given, and widening the port for a log line
  is not a trade worth making.
- **Nothing is transmitted, and that is checked two ways.** A source scan asserts `smtplib`,
  `aiosmtplib`, `email.message` and `SMTP(` are absent from the module, and a runtime test replaces
  `socket.socket` with an object that raises and sends anyway. The module docstring records that
  **T-5-14 (email header injection) is not applicable only because nothing is transmitted**, names
  the address and the title as the two caller-supplied values that would become header material,
  and says it must be re-raised by whoever writes a real SMTP adapter.
- `FakeEmailNotifier` under `tests/` remains the only in-memory double (RC-2):
  `grep -rc InMemoryEmailNotifier src/ tests/` matches nothing.
- Coverage over both new modules is **100% with no missing lines and no partial branches**
  (`logging.py` 23 statements / 4 branches, `notifications/logging.py` 10 statements). The suite
  went from 725 to **744** passing at **100.00%** over 1306 statements, with no `pragma: no cover`
  and no coverage `omit` anywhere under `src/taskmanager/`. `tests/unit` plus `tests/architecture`
  went from 523 to **542**.

## Task Commits

1. **Task 1: `JsonFormatter` and the idempotent `configure_logging()`** — `1866b49` (feat)
2. **Task 2: `LoggingEmailNotifier` — the invitation that is only logged** — `1daed85` (feat)

## Files Created/Modified

- `src/taskmanager/infrastructure/logging.py` — **created.** 23 statements, 4 branches.
  `PACKAGE_LOGGER`, the private marker, the computed reserved set, `JsonFormatter` and
  `configure_logging`. The docstring argues four decisions as decisions: propagation stays on,
  the marker makes the call idempotent, the handler is package-wide (and the 500 record is JSON
  from now on as a result), and the stream is `sys.stdout` because that is what
  `docker compose logs api` reads.
- `src/taskmanager/infrastructure/notifications/__init__.py` — **created**, empty, like
  `infrastructure/security/__init__.py`.
- `src/taskmanager/infrastructure/notifications/logging.py` — **created.** 10 statements, no
  branches. `LOGGER_NAME`, `ASSIGNED_TASKS_PATH` and `LoggingEmailNotifier`.
- `tests/unit/infrastructure/test_logging.py` — **created.** 11 tests over the seven behaviours
  the plan lists plus the exception-rendering pair, with the autouse isolation fixture.
- `tests/unit/infrastructure/test_notifier.py` — **created.** 7 tests: one record at INFO, the
  D-15 field set, the stringified id, the body's title and route, the newline case, the
  no-connection case and the source scan.
- `tests/unit/infrastructure/test_adapter_ports.py` — **modified.** One import, one binding test,
  and one sentence added to the module docstring extending its existing one-binding-one-home
  argument to the notifier.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-06-tdd-red.txt` — **created.**
  Both RED runs, appended after each was observed: collection errors and exit status 2, twice.

## Decisions Made

1. **The formatter renders `exc_info`.** Neither the plan nor 05-RESEARCH Pattern 8 does, and the
   omission is not cosmetic — it would have silently discarded every traceback the application
   logs. Rendered through `self.formatException(...)` into an `exception` key, escaped onto one
   line by `json.dumps` like everything else.
2. **`stack_info` is deliberately *not* rendered.** Nothing passes it, so the branch would be
   unreachable, and the project forbids the `pragma` that would excuse it. Stated in the docstring
   so the absence reads as a choice.
3. **No `default=` fallback on `json.dumps`.** The single caller stringifies at the call site,
   which the plan asks for explicitly; a coercion here would hide that call-site bug and pick a
   shape nobody chose.
4. **The notifier names its logger literally.** See the deviation below — `__name__` would have
   made D-15 and the plan's own acceptance snippet false.
5. **Package-wide handler over a notifications-only one**, as 05-RESEARCH recommends, with the
   blast radius named in the module docstring: the fixed 500's ERROR record is machine-readable
   from now on, its content unchanged. 05-16 owns the ADR.
6. **The port binding has one home.** `test_adapter_ports.py`, not the behaviour suite — the 05-05
   call, for the reason that module's docstring gives about `Clock`.
7. **No requirement tick.** NOTF-02 is in this plan's frontmatter and 05-16 is its last claimant.
   This plan ships an adapter and a logging setup with no use case and no route above them:
   nothing calls `configure_logging()` and nothing constructs `LoggingEmailNotifier` in
   production yet. The eighth consecutive Phase 5 plan to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The notifier's logger name: `__name__` contradicts D-15 and the plan's own
acceptance criteria**

- **Found during:** Task 2
- **Issue:** The plan's `<action>` says the notifier calls `logger.info(...)` on a module-level
  `logging.getLogger(__name__)`. In `src/taskmanager/infrastructure/notifications/logging.py`,
  `__name__` is `taskmanager.infrastructure.notifications.logging`. Records on that logger
  propagate to `taskmanager.infrastructure.notifications`, `taskmanager.infrastructure`,
  `taskmanager` and root — **never** to `taskmanager.notifications`, which is a sibling branch.
  The plan's own `<behavior>` ("emits exactly one record on `taskmanager.notifications`"), its
  `caplog.at_level(..., logger="taskmanager.notifications")` instruction, its acceptance snippet
  (which attaches a handler to `taskmanager.notifications` and asserts `len(records) == 1`) and
  D-15 itself would all have been false. Only the plan's parenthetical — "which resolves under the
  `taskmanager` tree" — would have held.
- **Fix:** The logger is named with the literal `taskmanager.notifications`, exported as
  `LOGGER_NAME` so the tests and 05-15's grep read one constant. A comment in the module says why
  `__name__` was rejected, adding the second reason: a path-derived name would change the day the
  file moved, and the operator's filter would break with it.
- **Files modified:** `src/taskmanager/infrastructure/notifications/logging.py`
- **Commit:** `1daed85`

**2. [Rule 2 — Missing critical functionality] The JSON formatter dropped every traceback**

- **Found during:** Task 1
- **Issue:** The formatter specified by the plan and by 05-RESEARCH Pattern 8 serialises three base
  fields plus the non-reserved record attributes. `exc_info` **is** a reserved attribute, so it is
  excluded from the merge and never rendered. `presentation/api/errors/handlers.py` logs the fixed
  500 with `exc_info=exc` and its docstring states "The traceback goes to the log and nowhere
  else" — so attaching this handler to the package logger would have made the traceback go
  nowhere at all. Nothing would have caught it: the two existing assertions read
  `record.exc_info`, an attribute of the record object, not the handler's output.
- **Fix:** `if record.exc_info is not None: payload["exception"] = self.formatException(...)`.
  `json.dumps` escapes the newlines, so a traceback is still one line. Two tests, one per leg, and
  the docstring records why the branch exists.
- **Files modified:** `src/taskmanager/infrastructure/logging.py`,
  `tests/unit/infrastructure/test_logging.py`
- **Commit:** `1866b49`

### Criteria met in substance rather than literally

- **Task 2's `<behavior>` lists the port binding**, but its `<action>` assigns that binding to
  `test_adapter_ports.py`. It lives there only, so `test_notifier.py` collects **7** tests rather
  than the 6 the acceptance criterion names as a floor — the floor is met, and the binding is not
  duplicated. This is exactly the call 05-05 recorded for `PasswordHasher`.
- **Task 1's acceptance criterion asks for "at least 7 tests collected"** in
  `test_logging.py`; it collects **11**, the extra four being the marker-identity test, the level
  test, the reserved-attribute test and the exception pair.

## Threat Flags

None. No network endpoint, no auth path, no file access and no schema change is introduced. The
plan's register is satisfied as written: T-5-13 mitigated by `json.dumps` (two tests, formatter
and end to end), T-5-14 accepted-not-applicable with the deferral written into the adapter
docstring and a grep gate proving no mail library is imported, T-5-04 mitigated by the notifier
logging exactly the three values its port hands it and nothing else, T-5-03 accepted with the
package-wide blast radius named in the module docstring (ADR owed by 05-16), T-4-xx addressed by
`configure_logging()` itself, and T-5-SC trivially satisfied — this plan installs no package and
imports only `json`, `logging` and `sys`.

## Quality Gates

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | black 153 files unchanged, isort clean, flake8 clean |
| Types | `make typecheck` | Success: no issues found in 153 source files |
| Architecture | `make arch` | 101 files, 299 dependencies — Contracts: **4 kept, 0 broken** |
| Tests | `make test` | **744 passed**, coverage **100.00%** over 1306 statements / 128 branches (gate 75%) |

`grep -rn "pragma: no cover" src/taskmanager/` prints nothing.

## Handoff Notes

- **Plan 05-11 owns the `configure_logging()` call.** Nothing calls it today, so the line is still
  invisible in a running container — that is deliberate and matches how 05-05 left
  `create_security_resources`. It must be called from `create_app()`, and it is safe there: the
  no-I/O test exists precisely so `test_creating_the_app_opens_no_connection` keeps holding.
- **Plan 05-10 owns constructing `LoggingEmailNotifier`** and handing it to the assignment use
  case. It is stateless and cheap, so unlike `PwdlibPasswordHasher` it needs no per-application
  caching decision.
- **Plan 05-08 should import `LOGGER_NAME`, not re-spell it.** A warning logged when a notifier
  fails (D-16/NOTF-03) belongs under the same tree so the JSON handler formats it too.
- **Plan 05-15's cold-start capture** can grep for `task_assigned_email` in
  `docker compose logs api`; the field is a top-level JSON key, so
  `| grep task_assigned_email | python -m json.tool` is a clean way to show the whole record. Note
  that the fixed-500 record now appears as JSON too if one is provoked.
- **05-16 owes two ADRs from this plan:** the package-wide handler and its named blast radius
  (05-RESEARCH's own recommendation, T-5-03 accepted), and the formatter's exception rendering —
  the second because the decision was made *against* both the plan and the research document, and
  the reason (a silently-discarded traceback that no existing test could see) is the kind of thing
  the append-only log exists for.
- **Do not set `propagate = False` on the `taskmanager` logger.** Two assertions in
  `tests/api/test_error_contract.py` and one in `test_logging.py` depend on records reaching root.
- The Phase 6 coverage divergence (host 3.14 vs container 3.13, PEP 649) was not re-measured here;
  `make docker-test` was not run for this plan, and the existing blocker in `STATE.md` still owns
  it.

## Self-Check: PASSED

All three created source modules, both created test modules, the evidence file and this summary
exist on disk; the two task commits `1866b49` and `1daed85` are both in `git log`.
