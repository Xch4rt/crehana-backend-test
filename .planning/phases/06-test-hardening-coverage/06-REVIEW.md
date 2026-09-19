---
phase: 06-test-hardening-coverage
reviewed: 2026-09-19T22:20:42Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - scripts/break-check.sh
  - tests/architecture/test_assertion_quality.py
  - tests/architecture/test_use_case_totality.py
  - tests/architecture/test_error_contract_totality.py
  - tests/architecture/test_coverage_configuration.py
  - tests/integration/test_endpoint_totality.py
  - tests/integration/conftest.py
  - tests/conftest.py
  - tests/unit/test_break_check.py
  - tests/integration/test_concurrent_writes.py
  - tests/integration/api/test_auth.py
  - tests/integration/api/test_tasks.py
  - tests/integration/api/test_task_lists.py
  - tests/integration/api/test_assignment.py
  - tests/problem_details.py
  - Dockerfile
  - Makefile
  - pyproject.toml
  - pytest.ini
findings:
  critical: 2
  warning: 11
  info: 6
  total: 19
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-09-19T22:20:42Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 6 added four AST gates, a coverage-configuration pin, a marker-partition guard, an
observed endpoint-totality gate and a `src/`-mutating break script. The engineering is careful
and every gate carries a non-vacuity guard, but the review was asked to find where those gates
can still pass for the wrong reason, and several can. Every finding below that says
"verified" was reproduced, either against planted source through the gate's own functions or
in a throwaway repository under the session scratchpad. No file in the repository was
modified, and the only pytest run was the 51 no-database gate tests (`--no-cov
-p no:cacheprovider`, all green).

The two blockers are both about a tool reporting a stronger result than it measured:

1. The `exclude_also` entry `\.\.\.` removes **whole function bodies** from the coverage
   denominator, including the `execute` methods of three use cases, and the new
   coverage-configuration gate pins that list by value while asserting in its docstring that
   none of the entries excludes executable behaviour. CLAUDE.md forbids reaching the number by
   `omit`; this is an `omit` by regex.
2. `scripts/break-check.sh` treats *any* non-zero pytest exit as RED. A usage error (renamed
   test file), a collection error or an unreachable database all print
   "All 5 breaks turned the suite red", with `red: 0 test(s) failed` beside each break.

The concurrency test and the signal/trap test were examined specifically for flakiness and
wrong-reason passes: both are sound in their assertions (the deletion case's "answer, not end
state" argument holds, since the repository `delete` is a silent no-op on zero rows), with
only low-risk timing notes recorded under Info. `concurrency = ["thread", "greenlet"]` is a
valid combination for coverage 7.16.1 and is sound; notes under IN-05.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: The `\.\.\.` coverage exclusion silently removes three use-case bodies from the denominator, and the new gate certifies it

**File:** `pyproject.toml:59`, pinned by `tests/architecture/test_coverage_configuration.py:73-78` and `:209-217`

**Issue:** `exclude_also` entries are unanchored regexes, and when the matching line is the
header of a block coverage.py excludes the **entire block**. `\.\.\.` therefore matches every
signature that mentions `tuple[X, ...]`. Verified with `coverage.Coverage(config_file="pyproject.toml").analysis2(...)`:

| File | Lines excluded from measurement |
|---|---|
| `src/taskmanager/application/use_cases/users/list.py` | 52-64 (all of `ListUsers.execute`) |
| `src/taskmanager/application/use_cases/task_lists/list.py` | 48-63 (all of `ListTaskLists.execute`) |
| `src/taskmanager/application/use_cases/tasks/list_assigned.py` | 52-63 (all of `ListAssignedTasks.execute`) |
| `src/taskmanager/domain/exceptions.py` | 70-71 (`DomainError.__reduce__`) |

Any future function whose signature contains `...` (`Callable[..., T]`, `tuple[int, ...]`)
or any executable line containing the three characters in a string (`log.info("loading...")`)
vanishes from the report the same way. The bodies are very likely executed today, so the
reported 100 % is probably still true, but it is unmeasured for those four functions, and the
project rule in CLAUDE.md ("never reached with `# pragma: no cover` or a coverage `omit`
entry") is violated in effect. The new gate makes it worse rather than better:
`test_the_exclusion_list_is_exactly_the_four_known_entries` pins the list by value and its
docstring states "None of the four excludes executable behaviour", which is false, and
`EXPECTED_EXCLUDE_ALSO` now makes removing the entry a red test.

The entry is also redundant: coverage 7.16.1's `DEFAULT_EXCLUDE` already carries an anchored
pattern for ellipsis bodies (`^\s*(((async )?def .*?)?[\])]+(\s*->.*?)?:\s*)?\.\.\.\s*(#|$)`)
and for `if TYPE_CHECKING:`. Verified: with the custom entry dropped, zero `...`-bodied lines
under `src/taskmanager` become measured statements, and `users/list.py` regains lines
52, 58, 62, 64.

**Fix:**
```toml
[tool.coverage.report]
exclude_also = [
    "raise NotImplementedError",
    "@abstractmethod",
]
```
and in `test_coverage_configuration.py`:
```python
EXPECTED_EXCLUDE_ALSO: Final[list[str]] = [
    "raise NotImplementedError",
    "@abstractmethod",
]
```
Add a gate that would have caught this: for every module under `PACKAGE`, assert that no line
in `analysis2(...).excluded` is anything other than a Protocol/overload ellipsis body, a
`TYPE_CHECKING` block or an abstract stub. Then re-run the full suite and confirm the number.

### CR-02: `break-check.sh` reports RED for any non-zero pytest exit, so it can declare all five breaks caught while running zero tests

**File:** `scripts/break-check.sh:148-168`

**Issue:** The verdict is `if [ "$status" -eq 0 ]` survived, else red. pytest exits 2 on a
collection error or interrupt, 3 on an internal error, 4 on a usage error (for example a test
path that no longer exists) and 5 when nothing was collected. All of them count as "the suite
noticed". Verified in a throwaway repository with a stub that prints pytest's
"file or directory not found" and exits 4:

```
    red: 0 test(s) failed

All 5 breaks turned the suite red. src/ is back as it was.
exit=0
```

The same happens when PostgreSQL is down (every integration test errors in `_require_database`,
exit 1, and `grep -c '^FAILED '` does not even count `ERROR` lines), and whenever the selected
tests are already failing before the mutation: there is no baseline run, so a suite that is
red for an unrelated reason "catches" everything. This is the script's only output, it is the
evidence offered for roadmap SC-4, and an evaluator who runs `make break-check` before
`make up` gets a success message that proves nothing. It is exactly the failure mode the file
header says it fears ("the exact inversion of what it exists to say"), reached from the other
side.

**Fix:** Run the selection once unmutated and require exit 0, accept only exit 1 as RED, and
require at least one `FAILED` line:
```sh
# before the mutation, inside check_break
set +e
$PYTEST "$@" --no-cov -p no:cacheprovider >"$LOGDIR/baseline-$number.log" 2>&1
baseline=$?
set -e
if [ "$baseline" -ne 0 ]; then
	echo "    these tests are not green BEFORE the break (pytest exit $baseline);" >&2
	echo "    is PostgreSQL up? see $LOGDIR/baseline-$number.log" >&2
	sed -n '$p' "$LOGDIR/baseline-$number.log" >&2
	exit 2
fi
...
# after the mutated run
case "$status" in
	0) survivors=$((survivors + 1)); ... ;;
	1) red=$(grep -c '^FAILED ' "$log" || true)
	   [ "$red" -gt 0 ] || { echo "    exit 1 with no FAILED test - not a verdict" >&2; exit 2; } ;;
	*) echo "    pytest exit $status is not a test failure (usage/collection error)" >&2
	   sed -n '$p' "$log" >&2; exit 2 ;;
esac
```
(The log directory must then survive an abnormal exit, or its tail must be printed before
`cleanup` removes it.) Add unit tests for stub exit codes 0, 1-without-FAILED, 2 and 4; see WR-09.

## Warnings

### WR-01: SIGHUP and SIGQUIT are not trapped; under dash (the Debian test image, any Linux evaluator) a dropped terminal leaves the defect planted in `src/`

**File:** `scripts/break-check.sh:114-115`

**Issue:** `trap cleanup EXIT` plus `trap on_signal INT TERM`. POSIX does not run the EXIT trap
when the shell dies from an untrapped signal; bash happens to, dash does not. Verified in a
throwaway repository with a stub that sends `kill -HUP "$PPID"`:

```
/bin/dash exit=129
 M src/taskmanager/domain/value_objects/completion.py      <- mutation left behind
/bin/sh   exit=129                                          <- macOS sh is bash: restored
```

A closed terminal tab or a dropped SSH session during the roughly one-minute run leaves, for
example, `"verify_exp": False` in `tokens.py` on disk (and leaks `$LOGDIR`). The header promises
"restores on any exit". The unit test passes on both platforms because it only ever sends TERM.

**Fix:** `trap on_signal HUP INT QUIT TERM`, and parametrize
`test_the_trap_restores_the_file_when_the_script_is_terminated` over `HUP`, `INT`, `TERM`
(run it explicitly under `dash` when `shutil.which("dash")` finds one, so the macOS host
exercises the strict shell too).

### WR-02: Half (b) of the assertion-quality gate cannot see `client.request(...)`, so the permission matrix's destructive rows are ungoverned; subscripted clients and helper-driven requests drop a test out of both halves

**File:** `tests/architecture/test_assertion_quality.py:202-208`, `:324-359`, `:585-597`

**Issue:** `MUTATING_VERBS` is `{"post","put","patch","delete"}`; `"request"` is in
`REQUEST_VERBS` only. `test_the_permission_matrix_answers_what_the_table_promises`
(`tests/integration/api/test_permission_matrix.py:499`) issues every POST/PUT/PATCH/DELETE in
the table through `client.request(cell.row.method, ...)`, never re-reads, carries no
`no_reread` marker and is absent from `REQUIRED_NO_REREAD`, yet the gate is green. Its 2xx
cells assert only `assert_no_challenge_was_issued` (no challenge header, not problem+json), so
a DELETE row that answered 204 and deleted nothing passes. Verified by planted snippets through
the gate's own functions, all reporting no offender in either half:

- `r = await client.request('DELETE', '/x')` with no GET afterwards;
- `client = api_client[0]` followed by `await client.delete(...)` and a status-only assert
  (`client_names` only recognises tuple unpacking, so the test issues "no requests" and leaves
  the scope of both halves);
- a module-level `async def create(client: AsyncClient)` that POSTs, called from a test that
  asserts only `r.status_code == 201` (helpers are not `test_*`, so their requests are invisible).

**Fix:** Treat `request` as mutating unless its first argument is a literal read verb; bind
`name = <client>[0]` in `client_names`; and treat a call that passes a client name to a
same-module function as issuing that function's requests (one hop, the same way
`resolvable_helpers` already resolves `Response` helpers). Then either give the matrix test a
registered `no_reread` exemption with its reason, or add the read-back to its 2xx mutating cells.
Add each planted snippet above as a self-test.

### WR-03: Both halves are satisfied by shapes that assert nothing

**File:** `tests/architecture/test_assertion_quality.py:381-386`, `:483-495`, `:593-595`

**Issue:** Verified by planted snippets, none reported:

- Half (b): `await client.get('/health')` after the mutation, result discarded. Any GET of any
  URL, asserted or not, counts; so does a GET inside `if False:`. The rule as stated ("read the
  resource back") is reduced to "the token `client.get` appears on a later line".
- Half (a): `assert r.headers` (truthiness of a body member);
  `seen = {'s': r.status_code, 'h': r.headers}` then `assert seen['s'] == 200` (the taint is
  per-name, so a status code rides in on a tainted container); and any bare call to a
  `Response`-taking helper with its result discarded satisfies the rule outright
  (`_calls_in(node) & helpers` at line 488), which matters for `anonymised`, the one real
  helper that returns rather than asserts.

**Fix:** For half (b) require the GET's response to reach an `assert` (bind the call's target
name, or accept the inline `(await client.get(...)).json()` form only inside an `assert`), and
ignore GETs nested under a constant-false test. For half (a) require a comparison
(`ast.Compare`) whose subtree reaches a body member or tainted name, exclude `.status_code`
attribute reads from taint sources, and count a helper call only when it is a statement-level
call of an asserting helper or appears inside an `assert`.

### WR-04: The coverage-configuration gate pins one file while coverage.py would read another, and its pragma scan misses every spelling but one

**File:** `tests/architecture/test_coverage_configuration.py:82`, `:116-130`, `:149-206`, `:220-239`

**Issue:** (1) coverage.py searches `.coveragerc`, `setup.cfg`, `tox.ini`, then
`pyproject.toml` and uses the first that has coverage settings. Adding a three-line
`.coveragerc` with `omit = ...` replaces the entire pinned `[tool.coverage.*]` configuration
(including `concurrency`) and every test here stays green. The same goes for `--cov-config=`,
a second `--cov=`, or `--no-cov` in the addopts, none of which is asserted absent.
(2) `FORBIDDEN_PRAGMA in line` is a literal match, but coverage's exclusion regex is
`#\s*(pragma|PRAGMA)[:\s]?\s*(no|NO)\s*(cover|COVER)`. Verified: `#pragma: no cover`,
`# pragma:no cover`, `# PRAGMA: NO COVER`, `# pragma no cover` and `#  pragma: no cover` are all
honoured by coverage and all invisible to the gate. `# pragma: no branch` (partial-branch
exclusion, which matters because `branch = true` is pinned) is not scanned for at all.

**Fix:**
```python
from coverage.config import DEFAULT_EXCLUDE, DEFAULT_PARTIAL
PRAGMAS = [re.compile(p) for p in (DEFAULT_EXCLUDE[0], DEFAULT_PARTIAL[0])]
...
if any(p.search(line) for p in PRAGMAS)
```
and add `test_pyproject_is_the_only_coverage_configuration`: assert `.coveragerc`,
`setup.cfg` and `tox.ini` do not exist at `ROOT` (or carry no coverage section), and that the
addopts contain no `--cov-config`, no `--no-cov` and exactly one `--cov=` token.

### WR-05: The marker guard enforces "at least one", documents "exactly one", and has no test of its own

**File:** `tests/conftest.py:27-29`, `:66-80`

**Issue:** The comment, the docstring and the error message all say every test carries
**exactly one** of `unit` / `integration`; the predicate is
`all(item.get_closest_marker(name) is None ...)`, which only detects *neither*. A module marked
`unit` that gains a class-level or parametrize-level `integration` mark is in both selections,
`make test-unit` silently starts needing PostgreSQL (and running a `downgrade base` against
the test database), and "755 + 323 = 1078" stops being a partition. Separately, the guard was
"driven red by stripping one pytestmark line" by hand; `test_assertion_quality.py`'s own
docstring records the lesson that a gate driven red once by hand is not a tested gate, and this
one has no automated proof.

**Fix:**
```python
def _buckets(item: pytest.Item) -> int:
    return sum(item.get_closest_marker(name) is not None for name in REQUIRED_MARKERS)

wrong = [f"{item.nodeid} ({_buckets(item)})" for item in items if _buckets(item) != 1]
```
and add a `pytester`-based unit test with three planted modules (unmarked, both, one) asserting
exit code 4 for the first two and 0 for the third, including under `-m unit`.

### WR-06: The total half of endpoint totality is skipped, not failed, by innocuous invocation drift, and nothing pins the invocations that count

**File:** `tests/integration/test_endpoint_totality.py:127-137`, `:196-197`

**Issue:** `list(config.args) != list(testpaths)` classifies `pytest tests/`, `pytest .`,
`pytest tests -q` written as `pytest -q tests/` and any `-m "unit or integration"` as partial,
and the TEST-02 half then **skips**. The gate's strength therefore rests entirely on
`Makefile:72`, `Dockerfile:147` and `ci.yml`'s last step staying a bare `pytest`, and no test
asserts that. One edit such as `run: pytest tests/` in CI or a `-m` added to `make test`
disables the gate on every verdict that counts while staying green, with the only trace a
skip line in the `-ra` summary. Conversely `--ignore`, `--ignore-glob` and `-x` are not in
`PARTIAL_SELECTION_OPTIONS`, so those runs fail falsely naming operations that were excluded on
purpose.

**Fix:** Normalise before comparing (`{Path(a).resolve() for a in config.args} ==
{(config.rootpath / t).resolve() for t in testpaths}`); add `ignore`, `ignore_glob` and
`maxfail` to the partial options; and make the skip impossible where it matters:
`if os.environ.get("CI") and partial: pytest.fail(...)`, or a small architecture test that
reads `Makefile`, `Dockerfile` and `ci.yml` and asserts the test invocation is exactly `pytest`.

### WR-07: The error-contract gate resolves raises by spelled name only, so the "tenth leaf" it exists to catch can arrive unseen

**File:** `tests/architecture/test_error_contract_totality.py:148-173`, `:193-202`, `:251-259`, `:276-280`

**Issue:** A class counts as raised only if some `raise` spells its class name. Verified with
the gate's `_raised_name`: `error = TaskNotFoundError(...); raise error` resolves to `error`,
`raise NF(...)` after `import TaskNotFoundError as NF` resolves to `NF`, and
`raise _not_found(list_id)` resolves to `_not_found`. A new leaf raised by any of those shapes
(and `src/` already has three `raise error` sites in the repositories, the natural home for a
translated error built into a variable) is judged "not raised" and its code is never required.
The sibling gate `test_routers_raise_no_http_exception.py` resolves aliases; this one does not.
Two weaker points in the same file: the one-module rule at `:258` only recognises `ast.Name`
bases, so `class X(exceptions.NotFoundError)` or an aliased base in an adapter escapes it, which
re-opens the `__subclasses__()` import-order hole the docstring says is closed; and a code is
"asserted" when the literal appears anywhere under `tests/` (a table, a parametrize id, a
constants module), not in an assertion. Today all nine codes do appear inside `assert`
statements (checked), so this is a future hole, not a present false green.

**Fix:** Invert the rule so it cannot be evaded by spelling: require every **concrete** class
(a `DomainError` subclass with no subclasses of its own) to have its code asserted, whether or
not a `raise` names it, and keep the raised-name scan only for the `REQUIRED_RAISED_CODES`
non-vacuity guard. In the one-module test, flag any `ClassDef` outside `exceptions.py` whose
base's **last dotted segment or import-resolved name** is in `known`. Collect literals from
`ast.Assert` and `ast.Compare` subtrees (plus `Response`-helper bodies) rather than module-wide.

### WR-08: The use-case totality gate matches any attribute call by name and accepts a construction inside code that never runs

**File:** `tests/architecture/test_use_case_totality.py:218-238`

**Issue:** `_called_names` adds `func.attr` for every attribute call in the module, without
looking at the receiver. Verified: `registry.Login()` on an unrelated object covers `Login`; a
`Login(...)` inside a module-level helper that no test calls covers it; and an import under
`if TYPE_CHECKING:` plus `x.Login()` covers it. The docstring states the "reachability, not
exercise" limit honestly and leans on coverage for execution, but CR-01 shows that three
`execute` bodies are currently outside the coverage measurement, so for `ListUsers`,
`ListTaskLists` and `ListAssignedTasks` neither gate proves execution today.

**Fix:** Count `ast.Name` calls of the locally bound name only (drop the `ast.Attribute`
branch, or restrict it to receivers that are themselves a bound use-case module alias), and
require the call to sit inside a `test_*` function or a function some `test_*` in the same
module calls. Fix CR-01 so the stated division of labour with coverage is true.

### WR-09: `test_break_check.py` never exercises the script's verdict

**File:** `tests/unit/test_break_check.py:116-189`

**Issue:** All three tests end before a single `check_break` completes (refused at the
clean-tree check, killed mid-run, failed `assert old in source`), only the first target file is
planted, and every stub exits 1. Nothing covers: a survivor (stub exit 0) producing
`SURVIVED`, the file list and exit 1; five consecutive mutate/restore cycles leaving a clean
tree; the restore-then-`assert_src_is_clean` sequencing between breaks; or the exit-code
handling that CR-02 shows is wrong. The script's safety is tested and its correctness is not,
which is how CR-02 shipped.

**Fix:** Plant all five targets (parse them out of the script the way `first_break_target`
already does for one) and add: `stub exit 0` -> return code 1, "5 of 5 breaks SURVIVED", clean
tree; `stub that prints "FAILED x::y - boom" and exits 1` -> return code 0, "All 5 breaks",
clean tree; and the exit 2/4/5 cases from CR-02 -> non-zero, never the success line.

### WR-10: The derived transition test takes its oracle from the code under test, so it cannot see an over-permissive table

**File:** `tests/integration/api/test_tasks.py:96-101`, `:1047-1108`

**Issue:** `FORBIDDEN_TRANSITIONS` is computed from `ALLOWED_TRANSITIONS`. Under break 2
(`completed -> pending` added to the table) the `completed->pending` case is not refused and
red; it silently leaves the parametrization, and the remaining cases stay green. The test
proves "HTTP honours whatever the table says", never "the table is right", and line 1085
(`assert requested not in ALLOWED_TRANSITIONS[starting]`) is a tautology of the list
comprehension that produced the pair. The break is still caught, but only by the hard-coded
`test_an_invalid_transition_is_409_naming_the_transition` at `:1003` and the unit tests, while
the new docstring disparages exactly that test ("hard-codes the single move an author happened
to think of"), which invites a later tidy-up to delete the only HTTP test that pins the rule.
This is the "mirror of the implementation" the break-check header warns about.

**Fix:** Keep the derivation for totality but pin the rule independently beside it:
```python
# The specification, stated here and nowhere derived: the one cross-move the brief forbids.
assert (TaskStatus.COMPLETED, TaskStatus.PENDING) in FORBIDDEN_TRANSITIONS
assert len([p for p in FORBIDDEN_TRANSITIONS if p[0] is not p[1]]) == 1
```
at module level or in a dedicated test, delete line 1085, and reword the docstring so the
hard-coded test is described as the oracle rather than as the weaker sibling.

### WR-11: Two of the new D-06 assertions cannot fail

**File:** `tests/integration/api/test_task_lists.py:944`, `tests/integration/api/test_tasks.py:1602`

**Issue:** `assert "\x00" not in <response>.text`. The body is JSON, and JSON serialisation
always escapes U+0000 as the six characters ` `, so the raw NUL byte can never appear in
`.text` whether or not the value was stored. The real proof in both tests is
`after == before` on the line above; this line reads as a second check and is none
(`test_task_lists.py:944` also spends an extra GET on it).

**Fix:** Assert on decoded values instead, for example
`assert all("\x00" not in (entry["name"] or "") + (entry["description"] or "") for entry in after)`,
or delete the line and let `after == before` stand alone.

## Info

### IN-01: The `apt-get install git` layer sits after `COPY tests`, so every test edit re-downloads it

**File:** `Dockerfile:116-141`

**Issue:** `make docker-test` always passes `--build`. Because the `RUN apt-get ...` layer comes
after `COPY tests ./tests`, any change under `tests/` invalidates it, and each run then needs
network access to the Debian mirrors and an unpinned `git`. The builder stage's own comment
("dependencies are installed before any source is copied") states the rule this breaks.

**Fix:** Move the `RUN apt-get update && apt-get install ... git` block to directly after
`FROM builder AS test`, before `COPY requirements-dev.txt`.

### IN-02: A mutated `.pyc` can outlive the restore for the one size-preserving break

**File:** `scripts/break-check.sh:135-153`

**Issue:** Python validates a cached `.pyc` by source mtime (whole seconds) and size. Break 3
(`==` to `!=`) preserves size, so if the mutated import and the `git checkout` land in the same
second (a run that aborts immediately), the mutated bytecode stays valid for the restored
source and the next `make test` runs the defect from cache. The Docker image sets
`PYTHONDONTWRITEBYTECODE=1`; the host path does not.

**Fix:** `PYTHONDONTWRITEBYTECODE=1 $PYTEST "$@" ...` for the mutated run.

### IN-03: Small behaviours in `break-check.sh` that mislead

**File:** `scripts/break-check.sh:61-66`, `:102-107`

**Issue:** `on_signal` exits 143 for SIGINT as well (convention is 130, and callers such as
`make` report it differently). Run from any directory but the repository root,
`git status --porcelain -- src/` matches nothing, the tree looks clean, and the failure is the
unrelated "`.venv/bin/pytest` not found - run `make install` first".

**Fix:** Trap each signal with its own code (`trap 'on_signal 130' INT`), and start with
`cd "$(git rev-parse --show-toplevel)"` guarded by the existing override for the unit test, or
fail early with "run from the repository root" when `src/` is not a directory.

### IN-04: `test_break_check.py` inherits the caller's git environment and splits the stub path on whitespace

**File:** `tests/unit/test_break_check.py:36-45`, `:91-95`, `:105-113`

**Issue:** `GIT_ISOLATION` sets identity and signing only; global `core.hooksPath`,
`init.templateDir`, `core.fsmonitor` and any exported `GIT_DIR` / `GIT_INDEX_FILE` /
`GIT_WORK_TREE` (set when pytest is launched from a hook or some `rebase --exec` setups, and
absolute for `git commit -a`) still reach both `git()` and the script, where they would point
the throwaway repository's commands at the real one. pytest is not in the hook set today, so
this is latent. Separately, `f"sh {stub}"` is expanded unquoted by the script, so a `TMPDIR`
containing a space breaks all three tests with a confusing `sh: /path/with: not found`.

**Fix:** Build the subprocess environment as
`{k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}`
and `pytest.skip`/assert early when `" " in str(tmp_path)`.

### IN-05: `concurrency = ["thread", "greenlet"]` is sound; two edges worth a sentence in ADR-089

**File:** `pyproject.toml:50`, `tests/integration/test_concurrent_writes.py:132-139`

**Issue:** coverage 7.16.1 only rejects more than one of `greenlet`/`eventlet`/`gevent`;
`thread` plus `greenlet` is valid and is the documented setting for SQLAlchemy's async bridge.
Two consequences: declaring `greenlet` makes coverage fall back from `sys.monitoring` to the C
tracer on every interpreter (silently, unless `COVERAGE_CORE=sysmon` is exported, in which case
it emits a `CoverageWarning` that `filterwarnings = error` may escalate), and it requires the C
tracer to be importable (true for the cp313/cp314 wheels in use). On the concurrency test:
`WAITING_ON_A_LOCK` counts any backend in the database rather than B's pid, and `waited`
requires B to connect and block within `OBSERVE_FOR = 5.0` s, so a heavily loaded runner can
produce a false red (never a false green). Both are acceptable as they stand.

**Fix:** None required. Optionally filter the observer query by
`pid <> pg_backend_pid() AND query ILIKE '%FOR UPDATE%'` to make `waited` mean "B waited".

### IN-06: Minor redundancy in the gates

**File:** `tests/architecture/test_coverage_configuration.py:242-255`, `tests/architecture/test_assertion_quality.py:718-733`

**Issue:** `test_the_threshold_flag_is_spelled_as_pytest_cov_expects` re-asserts what
`test_the_threshold_is_at_least_the_required_minimum` already guarantees (`int(...)` raises on
anything `\d+` would reject, and `len(thresholds) == 1` is asserted there). `found` is a
`dict[str, str]` mapping each id to itself and is only ever used as a set.

**Fix:** Drop the duplicate test or fold its regex into the threshold test; make `found` a `set[str]`.

---

_Reviewed: 2026-09-19T22:20:42Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
