---
phase: 06-test-hardening-coverage
plan: 04
subsystem: test-gates
tags: [coverage-pin, d-11, d-12, d-13, markers, collection-hook, greenlet-coverage, docker-test, adr, requirement-ticks]

# Dependency graph
requires:
  - phase: 06-test-hardening-coverage
    provides: "06-RESEARCH.md — the eight configuration facts to pin, the measured marker state, and the correction that a unit-only run already clears 75%"
  - phase: 06-test-hardening-coverage
    provides: "06-01, 06-02, 06-03 — the six gates this plan documents, and the two rules they paid for (drive every gate red; never let a gate be satisfied by its own non-vacuity guard)"
  - phase: 01-foundation-quality-gates
    provides: "pytest.ini and pyproject.toml — the coverage configuration this plan turns from prose into a test"
provides:
  - "tests/architecture/test_coverage_configuration.py — nine facts the 75% number rests on, each falsified once"
  - "tests/problem_details.py — PROBLEM_JSON and MEMBERS, importable and never collected"
  - "tests/unit/presentation/test_error_contract.py — the 17 error-contract tests with their siblings; tests/api/ is gone"
  - "tests/conftest.py pytest_collection_modifyitems — an unmarked test fails collection by node id"
  - "make test-unit — the 755-test no-database slice, --no-cov"
  - "concurrency = [thread, greenlet] — the coverage entry that closed an 18-line false negative on Python 3.13"
  - "Dockerfile test stage: scripts/ and git, so make docker-test collects at all"
  - "DECISION_LOG.md ADR-085..091 and the CLAUDE.md Test quality section"
affects: [07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pin the configuration a number depends on, not the number: the threshold is a parsed floor, so raising it is legal and lowering it is not"
    - "An exact-set comparison with its cost stated in the docstring, the test_layer_boundaries.py convention, applied to exclude_also"
    - "A collection-time hook as the gate for a rule about the suite's own shape, reporting node ids rather than a count"
    - "A false negative in a measurement is the one error nobody investigates, so the thing that prevents it gets pinned too"

key-files:
  created:
    - tests/architecture/test_coverage_configuration.py
    - tests/problem_details.py
  modified:
    - tests/unit/presentation/test_error_contract.py
    - tests/conftest.py
    - Makefile
    - Dockerfile
    - pyproject.toml
    - DECISION_LOG.md
    - CLAUDE.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "`concurrency = [\"thread\", \"greenlet\"]` was added to the coverage configuration because `make docker-test` — run here for the first time since routers existed — reported 99.08% on Python 3.13, with 18 lines missing that the passing tests demonstrably execute: every `return XResponse.from_result(...)` and every Location header in presentation/api/routers/, i.e. the lines after a handler's first await into SQLAlchemy's greenlet bridge. A coverage error that makes the number too LOW is the one kind nobody goes looking for"
  - "The Docker test stage never received `scripts/`, so tests/unit/test_break_check.py (06-03) and tests/unit/test_env_bootstrap.py (05-17) were collection errors there; git was missing too. Both fixed in the test stage only. A skip was rejected on the D-03 argument: a skipped test in a container is a green run that exercised none of it"
  - "The threshold is asserted as a parsed floor (>= 75), never as the literal `--cov-fail-under=75`: the string form would be red on 80, which is the one change nobody needs to prevent"
  - "The coverage NUMBER is deliberately not asserted. 100% is a norm, not a requirement (D-12); a test pinning it would go red on an honest refactor and the only way back to green would be to test something the code does not do"
  - "`exclude_also` is compared by exact value with the cost written into the docstring, because a fifth entry is how a real exclusion would be smuggled in and every weaker comparison waves it through"
  - "`tryfirst=True` on the collection hook pins an ordering that happens to hold anyway: the claim that running after pytest's mark plugin would miss an unmarked item under `-m unit` was FALSIFIED by removing the decorator (the guard still fired). The docstring says so rather than shipping prose the tree disagrees with; the decorator stays because registration order is not a documented promise"
  - "Every prose reference to the old `tests/api/test_error_contract.py` path was repointed — eight files, including two src/ docstrings and migrations/env.py — not only the plan's six import sites and the alembic_config docstring. DECISION_LOG.md line 3025 is left stale on purpose: the log is append-only (the 01-08 precedent)"
  - "make test-unit is documented in the Makefile as a convenience subset, not a gate: it runs a strict subset of make test, so ADR-015's two-places rule does not apply and neither pre-commit nor CI learns about it"

patterns-established:
  - "When a measured claim in a plan or a docstring turns out to be false, correct the claim rather than keeping the prose and hoping: the tryfirst paragraph now records what was observed, decorator removed"
  - "Run every delivery command the plan names, not only the ones that were green last time: make docker-test had been broken for two phases and no gate could see it"

requirements-completed: [TEST-01, TEST-02, TEST-03, TEST-04, TEST-05]

# Metrics
duration: 48min
completed: 2026-09-19
---

# Phase 6 Plan 04: The Coverage Pin, the Marker Partition and the Phase Close Summary

**The coverage number is now defended by a test rather than by prose — and the first thing that
test's neighbourhood turned up was that the number had been too low in Docker, not too high.**

## What Was Built

### Task 1 — the coverage configuration pin (`03e8c3a`)

`tests/architecture/test_coverage_configuration.py`, nine tests over `pytest.ini` (via
`configparser`) and `pyproject.toml` (via `tomllib`):

- `--cov=taskmanager` present, so the denominator is the package and not a directory one flag away
  from containing `tests/`.
- `--cov-fail-under=N` with `N >= 75`, **parsed as a number**, appearing exactly once.
- `[tool.coverage.run]`: `source == ["taskmanager"]`, `branch` true, `concurrency` exactly
  `["thread", "greenlet"]`, **no** `omit` key.
- `[tool.coverage.report]`: **no** `fail_under` key, so the threshold has exactly one home;
  `exclude_also` equal to the exact four-entry `EXPECTED_EXCLUDE_ALSO`.
- Zero `# pragma: no cover` under `src/taskmanager/`, reported by `file:line`.
- Two non-vacuity tests: both configuration files are required by name and parsed, and the `src/`
  glob is required to have matched `__init__.py` and `main.py`.

Every one of the six ways to weaken the number was planted and observed:

| Planted | Result |
|---|---|
| `--cov-fail-under=70` | 1 failed |
| `--cov-fail-under=80` | 9 passed (a raise stays legal) |
| `omit = ["*/main.py"]` under `[tool.coverage.run]` | 1 failed |
| a fifth `exclude_also` entry (`if not TYPE_CHECKING:`) | 1 failed |
| `fail_under = 75` under `[tool.coverage.report]` | 1 failed |
| `# pragma: no cover` on `main.py:79` | 1 failed, naming `main.py:79` |
| `concurrency` removed (added in task 4) | 1 failed |

`git status --porcelain -- src/` was empty after the pragma falsification. Nothing was reverted
with a blanket checkout; each planted edit was written back byte for byte and the equality
asserted.

### Task 2 — `tests/api/` folded in (`f63658e`)

- `tests/problem_details.py` holds `PROBLEM_JSON` and `MEMBERS` with a `probe.py`-style docstring:
  why it lives under `tests/`, that it is never collected, and why a constant imported *out of a
  test module* was the wrong arrangement — it tied six integration modules to a test file's
  location.
- `git mv tests/api/test_error_contract.py tests/unit/presentation/test_error_contract.py`
  (git records it as a 96% rename), plus `pytestmark = pytest.mark.unit` and a paragraph saying
  why it belongs there. All 17 tests unchanged.
- `tests/api/` including its `__init__.py` is gone.
- Eight files had their prose repointed, not the plan's two: the six import-site comments, the
  `alembic_config` docstring, `migrations/env.py`, `tests/unit/test_app_factory.py`,
  `tests/unit/infrastructure/test_logging.py`, `tests/integration/test_endpoint_totality.py`, and
  two `src/` docstrings (`application/use_cases/access.py`,
  `application/use_cases/tasks/change_task_status.py`, `infrastructure/logging.py`). Three of them
  needed rewrapping, because the new path is longer than 88 columns allows.

`pytest --collect-only | grep -c problem_details` → 0. The collected total did not move.

### Task 3 — the marker partition and its guard (`52ed708`)

- `pytestmark = pytest.mark.unit` added as a module-level line to the **60** collected modules that
  carried neither marker, inserted immediately after each module's import block — where the
  integration modules place theirs — with `import pytest` added where it was absent. No test body
  changed. (The plan said 58; 06-01/06-02/06-04 had since added modules, and two already carried
  the marker.)
- `pytest_collection_modifyitems(config, items)` in `tests/conftest.py` raises `pytest.UsageError`
  listing the offending node ids when a collected item carries neither marker. `--strict-markers`
  refuses an *unregistered* marker; nothing in pytest refuses a *missing* one.
- `make test-unit` → `$(VENV)/bin/pytest -m unit --no-cov`, in `.PHONY`, with the comment block the
  file's convention requires.

| Check | Result |
|---|---|
| `-m unit` collected | 755 |
| `-m integration` collected | 323 |
| total collected | **1078 = 755 + 323** |
| `make test-unit` | 755 passed, 323 deselected, 2.9 s |
| `make test-unit` with `docker compose stop db` | 755 passed, exit 0 |
| `coverage.xml` sha1 + mtime across `make test-unit` | **unchanged** |
| one `pytestmark` line deleted | exit 4 under both `pytest` and `pytest -m unit`, node ids named |

### Task 4 — the documentation, the agreement and the ticks (`bf55419`, `6cda302`)

Seven ADRs, **085–091**, contiguous, in the order the plan enumerates: use-case totality, observed
endpoint totality, error-leaf totality, assertion quality with the `no_reread` exemption, the
coverage configuration pin, the marker partition with its collection guard, and the
deliberate-break spot check. `git diff DECISION_LOG.md | grep -c '^-'` → **1**, the diff header
alone, so the log stayed append-only mechanically rather than by intention.

`CLAUDE.md` gained a new **Test quality** section (six bullets, one of them the
drive-every-gate-red / never-satisfiable-by-its-own-guard rule that 06-01 and 06-03 both handed
forward) and three bullets under **Quality gates** — the configuration pin, the marker partition
with `make test-unit`, and the statement, made once, that none of these gates adds a pre-commit
hook or a CI step because each rides inside `pytest` or `lint-imports`, with `make break-check`
deliberately in neither.

TEST-01..TEST-05 ticked — checkboxes and traceability rows — with the evidence for each written
into the traceability notes against a named test or command.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `make docker-test` could not collect at all**

- **Found during:** Task 4, at the first `make docker-test` of the plan.
- **Issue:** `FileNotFoundError: '/app/scripts/break-check.sh'` during collection — the Dockerfile
  `test` stage never received `scripts/`, and it has no `git`, which
  `tests/unit/test_break_check.py` needs to build its throwaway repository. This had been broken
  since 05-17 for `tests/unit/test_env_bootstrap.py` and since 06-03 for the break-check tests;
  no host gate could see it, because every host gate has both.
- **Fix:** `COPY scripts ./scripts` plus an apt install of `git` in the **test stage only** — the
  runtime image receives nothing from there, so the delivered container still carries no
  version-control tooling. A conditional skip was rejected on D-03's own argument: a skipped test
  in a container is a green run that exercised none of it.
- **Commit:** `bf55419`

**2. [Rule 1 - Bug] coverage under-reported 18 executed lines on Python 3.13**

- **Found during:** Task 4, immediately after fix 1 made the container run at all.
- **Issue:** `make docker-test` reported **99.08%**, 18 lines missing, against the host's 100%. The
  18 are every `return XResponse.from_result(...)` and every `Location` header in
  `presentation/api/routers/` — the lines that run *after* a handler's first `await` into
  SQLAlchemy's greenlet bridge. The tests asserting those very response bodies were passing, and
  the bytecode line tables for the handlers are identical on both interpreters (checked with
  `code.co_lines()`), so the lines demonstrably execute. `COVERAGE_CORE=ctrace` made no
  difference, which ruled out the tracer core.
- **Fix:** `concurrency = ["thread", "greenlet"]` under `[tool.coverage.run]`, with the whole
  finding written into the comment above it. Both interpreters now report 100.00%. The gate from
  task 1 pins the value, falsified by removing it.
- **Why it matters more than the percentage:** this is a false negative. The number was too *low*,
  which is the one direction nobody audits — an honest 100% was being reported as 99% in the only
  environment an evaluator runs.
- **Commit:** `bf55419`

**3. [Rule 2 - Missing] every stale reference to the moved path, not only the plan's two**

- **Found during:** Task 2.
- **Issue:** the plan names six import sites and the `alembic_config` docstring. A repository-wide
  grep found eight more prose references, including two `src/` docstrings and
  `migrations/env.py` — all of which would have pointed an evaluator at a file that no longer
  exists.
- **Fix:** all repointed in the same commit; three lines rewrapped to stay under 88 columns.
  `DECISION_LOG.md` line 3025 is deliberately left stale — the log is append-only, and this is the
  same call 01-08 made about ADR-019.
- **Commit:** `f63658e`

### Corrections to this plan's own prose

**`tryfirst=True` is not what makes the collection guard work.** The docstring first claimed that
without it, pytest's mark plugin would have removed an unmarked item before the guard looked, so a
`-m unit` run would report nothing. That was falsified by deleting the decorator: the guard still
fired, because on pytest 9 a conftest implementation is called before the builtin plugin's. The
docstring now records the measurement and keeps the decorator for the reason that survives —
registration order is not a documented promise, and the failure it would produce is a silent hole
rather than an error.

## The three-way agreement (D-11)

| Leg | Pass count | Coverage | Statements |
|---|---|---|---|
| `make test` (host, CPython 3.14.3) | 1078 | **100.00%** | 1643, 0 miss, 154 branches, 0 partial |
| `make docker-test` (container, CPython 3.13.15) | 1078 | **100.00%** | 1796, 0 miss, 154 branches, 0 partial |
| CI | — | — | **manual verification, taken at phase verification** per `06-VALIDATION.md` |

The percentages and the pass counts agree exactly. The denominators do not, for a reason that is
not a defect: Python 3.14 evaluates annotations lazily (PEP 649/749), so the annotation lines in
the Pydantic schemas and the router signatures are not executable statements there, while 3.13
evaluates them at definition time. Both legs are at 100% with zero missed statements and zero
partial branches, which is what D-11's agreement is about. The CI leg is the phase's one
manual-only verification and was deliberately not chased here.

## Verification Results

```
make lint       -> black 187 files unchanged, isort clean, flake8 clean
make typecheck  -> Success: no issues found in 187 source files
make arch       -> Contracts: 4 kept, 0 broken.
make test       -> 1078 passed, TOTAL 1643 stmts / 154 branches, 100.00%
make test-unit  -> 755 passed, 323 deselected, 3.1s
make break-check-> All 5 breaks turned the suite red. src/ is back as it was. (exit 0)
make docker-test-> 1078 passed, TOTAL 1796 stmts / 154 branches, 100.00%
```

- `test -d tests/api` → false.
- `grep -rn "tests.api.test_error_contract\|tests/api/test_error_contract" tests/` → nothing.
- `pytest --collect-only -q | grep -c problem_details` → 0.
- `grep -c "^## ADR-0" DECISION_LOG.md` → 91, up 7, contiguous 085–091 with no gap or duplicate.
- `grep -n "TEST-0" .planning/REQUIREMENTS.md` → all five `[x]`, all five rows `Complete`.
- `git status --porcelain -- src/` → empty.
- No commit in this plan carries a `Co-Authored-By` or a `Generated with` line.

## Ceremony

Minimal, per the user's standing preference: one SUMMARY, no evidence files, no falsification
transcripts. Every falsification above was run and its result is recorded in the tables rather
than in a separate file.

## For Phase 7

- **`DECISION_LOG.md` line 3025 names `tests/api/test_error_contract.py`**, a path that no longer
  exists. The log is append-only, so it was not edited; Phase 7 owns the refresh, exactly as
  01-08 handed over ADR-019.
- **The CI leg of D-11's agreement is unrecorded.** After the next push, read the coverage total
  out of the run log and compare with the two numbers above. CI runs CPython 3.13, so expect
  1796 statements at 100.00%.
- **`make docker-test` had been broken for two phases and nothing noticed.** Worth an
  `AI_WORKFLOW.md` entry of its own: the one gate no host command can stand in for is the one that
  runs on the interpreter the deliverable ships.

## Self-Check: PASSED

- `tests/architecture/test_coverage_configuration.py` — FOUND
- `tests/problem_details.py` — FOUND
- `tests/unit/presentation/test_error_contract.py` — FOUND
- `tests/api/` — CONFIRMED ABSENT
- `tests/conftest.py` `pytest_collection_modifyitems` — FOUND
- `Makefile` `test-unit` target and `.PHONY` entry — FOUND
- `DECISION_LOG.md` ADR-085..091 — FOUND (91 total)
- commits `03e8c3a`, `f63658e`, `52ed708`, `bf55419`, `6cda302` — all FOUND in `git log`
