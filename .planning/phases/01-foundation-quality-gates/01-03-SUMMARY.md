---
phase: 01-foundation-quality-gates
plan: 03
subsystem: architecture
tags: [import-linter, layers, forbidden-contracts, architecture-test, evidence, mypy-strict]

# Dependency graph
requires:
  - "01-01: installable `taskmanager` src-layout package, `tests/architecture/__init__.py`, import-linter 2.15 pinned in requirements-dev.txt, `.import_linter_cache/` git-ignored"
  - "01-02: every layer module importable with zero environment variables set (`create_app` is a factory, not a module-level `app`), giving the graph a real downward edge to enforce"
provides:
  - "`.importlinter` - root-level INI with `root_package = taskmanager` and three contracts (one layers, two forbidden)"
  - "`tests/architecture/test_layer_boundaries.py` - the contracts executed inside pytest via the import-linter Python API, plus a guard test that the contracts are loaded at all"
  - "`evidence/import-linter-red-green.txt` - the contract observed red on a real forbidden import, green after removal, with the `python -m` no-op contrast"
  - "A verified correction to RESEARCH Pitfall 2 and the real zero-contract typo it should have named"
affects: [01-04, 01-05, 01-06, 01-07, 03-infrastructure, 05-auth]

# Tech tracking
tech-stack:
  added:
    - "import-linter 2.15 (first use; pinned in plan 01-01) - `importlinter.api.read_configuration` and `importlinter.application.use_cases.lint_imports`"
  patterns:
    - "Architecture boundaries are a pytest test, not a separate CLI step: `pytest` alone catches a layer violation"
    - "Every gate ships with a committed observation of it failing; a gate never seen red is indistinguishable from a no-op"
    - "Gate configuration is itself under test - `test_every_contract_is_configured` asserts the contracts are loaded, because import-linter exits 0 on zero contracts"
    - "Never `python -m importlinter.cli`; the `lint-imports` console script for humans and CI, the Python API for tests"

key-files:
  created:
    - .importlinter
    - tests/architecture/test_layer_boundaries.py
    - .planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt
  modified: []

key-decisions:
  - "Root-level `.importlinter` INI rather than `[tool.importlinter]` in `pyproject.toml` (RESEARCH Open Question 1, RESOLVED): functionally identical, but an evaluator finds a file named after the tool in five seconds. Plan 01-06 records the equivalence as an ADR."
  - "The fourth contract (presentation.api.routers/schemas must not import infrastructure) is deliberately absent: those modules do not exist until Phase 3 and import-linter errors on unresolvable `source_modules`."
  - "`pydantic` is forbidden in `domain` but allowed in `application` - domain entities are stdlib dataclasses, application DTOs are pydantic models."
  - "The module docstring describes the forbidden `python -m` form without writing its literal dotted path, so the plan's `! grep -q 'importlinter.cli'` gate stays meaningful as a check on executable code rather than on prose."
  - "RESEARCH Pitfall 2 is wrong about which typo is dangerous, verified by execution; the appendix in the evidence file records the correction and the real trap."

patterns-established:
  - "Evidence files under `.planning/phases/<phase>/evidence/` now hold two gate demonstrations (coverage, architecture) for plan 01-07 to embed"
  - "Tests add no statements to the coverage denominator, so architecture tests are free against the 75% gate - but any new module under `src/` still must be tested"

requirements-completed: [ARC-03, ARC-01]

# Metrics
duration: 8min
completed: 2026-09-17
---

# Phase 01 Plan 03: Architecture Boundaries as a Failing Test Summary

**Three import-linter contracts in a root-level `.importlinter`, executed inside the pytest suite through the supported Python API, observed going red on a real `from fastapi import FastAPI` in the domain and green once removed - and a guard test that survives the config being silently unloaded.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-17T22:50:46Z
- **Completed:** 2026-09-17T22:58:28Z
- **Tasks:** 3
- **Files created:** 3

## Accomplishments

- `.importlinter` declares `root_package = taskmanager`, `include_external_packages = True`, and exactly three contracts: the D-10 layers order (`main > presentation > infrastructure > application > domain`) and two `forbidden` contracts keeping frameworks out of `domain` (including `pydantic`) and out of `application` (excluding `pydantic`). `lint-imports` reports **3 kept, 0 broken** while naming each contract (ARC-01, ARC-03, D-10).
- `tests/architecture/test_layer_boundaries.py` runs those contracts as two real tests. `pytest` alone - no separate CLI step, no CI-only check - now fails on a layer violation.
- The gate was **observed failing**: `src/taskmanager/domain/_violation.py` with a single `from fastapi import FastAPI` produced `taskmanager.domain is not allowed to import fastapi`, `Domain is framework-free BROKEN`, `1 failed`, and `lint-imports` exit 1. Deleting the file restored `2 passed` and exit 0. Both runs are committed verbatim (phase success criterion 2).
- The reason the test uses the Python API is now documented with its own evidence: with that identical violation in place, `.venv/bin/python -m importlinter.cli lint-imports` printed **nothing** and exited **0**. The recipe published in `.planning/research/ARCHITECTURE.md` would have shipped an architecture test that can never fail.
- The second, quieter failure mode was closed too: a config that parses but loads zero contracts makes `lint-imports` report `Contracts: 0 kept, 0 broken` and exit 0. `test_every_contract_is_configured` was observed catching exactly that.
- Full suite: **8 passed**, coverage unchanged at **100.00% over 18 statements**, `mypy src tests` clean over 14 files with zero `type: ignore`, flake8 / black / isort clean.

## Task Commits

1. **Task 1: declare the import-linter layer and forbidden contracts** - `ab60d34` (feat)
2. **Task 2: run the contracts inside the pytest suite** - `236acbc` (test)
3. **Task 3: record the contract going red and back to green** - `41b113a` (docs)

## Files Created/Modified

- `.importlinter` - three contracts with English comments explaining *why* each ban exists (a pydantic `ValidationError` cannot carry the domain error contract; the application layer orchestrates through ports)
- `tests/architecture/test_layer_boundaries.py` - two tests, both `-> None`, no `subprocess`, no `importlinter` CLI module; module docstring states the boundary is enforced by the normal test run
- `.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt` - five captured runs plus an appendix on the zero-contract failure mode

## Decisions Made

- **The docstring versus the grep gate.** The plan required `grep -c 'importlinter.cli' tests/architecture/test_layer_boundaries.py` to return 0, and the first draft of the module docstring explained the forbidden form by naming it - which tripped the gate. The docstring was reworded to describe the form ("running import-linter's command-line module through `python -m`") rather than spell it. The alternative, relaxing the grep, would have turned a mechanical check into one that a future contributor could satisfy while still calling the thing. The literal dotted path lives in the evidence file, where grepping for it is harmless.
- **Where the RED observation for Task 2 lives.** Task 2 carried `tdd="true"`, but Task 1 had already committed `.importlinter`, so the test passed the moment it was written - there was no state in which it could fail. Rather than manufacture a RED by hiding the config, the honest RED is Task 3, which is the plan's own design: a real forbidden import, a real failure, captured and committed six minutes later. The commit message of `236acbc` says so explicitly rather than implying a cycle that did not happen.
- **Correcting the research instead of quoting it.** RESEARCH Pitfall 2 names `[importlinter:contracts:...]` (plural) as the typo that silently disables everything. Executed, it changes nothing. The correction and the real trap are recorded in the evidence appendix with the source that explains it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan's stated rationale for the guard test rested on a claim that does not reproduce**

- **Found during:** Task 3
- **Issue:** Both the plan (Task 1 action, Task 2 action) and RESEARCH Pitfall 2 assert that writing `[importlinter:contracts:layers]` instead of `[importlinter:contract:layers]` yields zero contracts and a vacuous green. Applied to all three headers on import-linter 2.15, `lint-imports` still reported **3 kept, 0 broken** and the guard test still passed. `importlinter/adapters/user_options.py` keeps every section whose name starts with `importlinter:` and uses `section_name.split(":")[-1]` as the contract id - the middle word is never inspected. The plan's `! grep -q '\[importlinter:contracts:'` acceptance check is therefore guarding against a harmless string.
- **Fix:** Found and verified the failure mode that is real - getting the *prefix* wrong. `[import-linter:contract:...]` (the hyphenated spelling used by PyPI, the docs and the console script) produces `Contracts: 0 kept, 0 broken`, exit 0, and zero enforcement. Confirmed `test_every_contract_is_configured` fails on it (`assert set() == {...}`), then restored `.importlinter` with `git checkout --` and confirmed `git diff HEAD -- .importlinter` is empty. Both the correction and the observation are in the evidence appendix. The shipped file still satisfies every one of the plan's acceptance criteria, including the plural-header check.
- **Files modified:** `.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt` (appendix section)
- **Commit:** `41b113a`

**2. [Rule 2 - Missing critical functionality] The guard test's discriminating power was asserted but never observed**

- **Found during:** Task 3
- **Issue:** `must_haves` D-10 #4 requires that "a typo producing zero contracts cannot report green". Task 3 as written only demonstrates the forbidden-import failure mode; the guard test would have shipped having never been seen to fail - the exact condition the phase's own thesis calls indistinguishable from a no-op.
- **Fix:** Added the appendix demonstration above, so both of this gate's failure modes now have a captured observation of the test that catches them. Cost: about a minute, no production file touched.
- **Files modified:** `.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt`
- **Commit:** `41b113a`

### Process Deviations

**3. Task 2's `tdd="true"` cycle ran GREEN-only, with the RED in Task 3**

- **Found during:** Task 2
- **Reason:** The plan ordered `.importlinter` (Task 1) before the test (Task 2), so at the moment the test was written the contracts already held and no failing state existed. Reordering was not possible without abandoning Task 1's own verification, which requires `lint-imports` to pass.
- **Impact:** None on the artifacts. The RED observation the TDD cycle exists to produce is Task 3's, is stronger (a real forbidden import rather than a missing file), and is committed as evidence rather than living only in a commit message.

## Issues Encountered

None blocking. Two observations worth carrying forward:

- The evidence file elides import-linter's nine-line ASCII logo from the `lint-imports` captures, marked `[logo elided]` and disclosed in the file header. Everything else, exit codes included, is verbatim. Consider `--no-logo` in the Makefile and CI recipes (plans 01-04 and 01-05) to keep job logs readable.
- `lint-imports` analysed 13 files / 6 dependencies with the violation present and 12 / 5 without, confirming the graph is rebuilt per run and `.import_linter_cache/` is not masking anything. That cache directory stayed out of `git status` throughout.

## Verification Results

| Check | Result |
|-------|--------|
| `.venv/bin/lint-imports` | exit 0, **3 kept, 0 broken**, all three contract names printed |
| `.venv/bin/pytest tests/architecture -q --no-cov` | `2 passed` |
| `.venv/bin/pytest` | exit 0, **8 passed**, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| `grep -c 'importlinter.cli' tests/architecture/test_layer_boundaries.py` | 0 |
| `grep -c 'subprocess' tests/architecture/test_layer_boundaries.py` | 0 |
| `grep -c '^\[importlinter:contract:' .importlinter` | 3 |
| `grep -c '\[importlinter:contracts:' .importlinter` | 0 |
| `grep -c 'presentation.api' .importlinter` | 0 |
| `root_package = taskmanager`, `include_external_packages = True` | both present |
| Evidence contains `not allowed to import` + `fastapi` | pass (2 occurrences) |
| Evidence shows `Domain is framework-free BROKEN` and `lint-imports` exit 1 | pass |
| Evidence records `python -m importlinter.cli` exit 0 with the violation present | pass |
| Evidence contains post-removal `2 passed` and exit 0 | pass |
| `src/taskmanager/domain/_violation.py` exists | no - deleted |
| `git status --porcelain \| grep -c '_violation'` | 0 |
| `git diff HEAD -- .importlinter` after the appendix experiment | empty |
| `.venv/bin/mypy src tests` | `Success: no issues found in 14 source files` |
| `.venv/bin/flake8 src tests` | pass (no output) |
| `.venv/bin/black --check src tests` | pass (14 files unchanged) |
| `.venv/bin/isort --check-only src tests` | pass |
| `AI_WORKFLOW.md` not created or modified | pass (does not exist) |

## Self-Check: PASSED

All 3 created files verified present on disk; commits `ab60d34`, `236acbc`, `41b113a` verified in `git log`.

## Known Stubs

None. The one intentionally deferred item is the fourth contract (`presentation.api.routers` / `.schemas` must not import `infrastructure`), which cannot be written before Phase 3 creates those modules - import-linter errors on unresolvable `source_modules`. Plan 03 owns it.

## Threat Flags

None. No network surface, auth path, file access or schema was introduced; the plan's own register (T-01-12 through T-01-16) is fully addressed, with T-01-13 strengthened beyond the plan by the appendix demonstration.

## User Setup Required

None.

## Next Phase Readiness

Ready for plan 01-04 (pre-commit + Makefile) and 01-05 (Dockerfile + CI). Notes for the next executors:

- **Use the `lint-imports` console script, never `python -m importlinter.cli`.** The Makefile `arch` target, the pre-commit hook and the CI step must all call `lint-imports` (add `--no-logo` to keep logs clean). The `python -m` form exits 0 unconditionally; this is now documented with evidence, so shipping it would be a knowing error.
- **`pytest` already covers the architecture gate**, so a `make test` that runs pytest is sufficient for correctness. Keeping a separate `make arch` / CI step is still worth it for a readable failure in a job log - that was the design intent, not redundancy.
- **pre-commit hook shape:** import-linter needs the `taskmanager` package importable and its third-party dependencies present (`include_external_packages = True` resolves `fastapi`, `sqlalchemy`, etc.). A `repo: local` hook with `language: system` running `.venv/bin/lint-imports` works; an isolated `language: python` hook would need the full runtime requirements declared as `additional_dependencies` and would not see the editable install. Prefer the local/system form.
- **`.import_linter_cache/` is git-ignored** and must also be in `.dockerignore` (RESEARCH Pitfall 11) alongside `src/*.egg-info`.
- **Coverage headroom is unchanged.** 18 statements at 100%; tests do not enter the denominator. Any new module under `src/` still needs its own test - a single untested 7-statement module drops the total to 72%.
- **Docker note:** the image runs `uvicorn --factory taskmanager.main:create_app`; there is still no module-level `app`, and adding one would break both the settings-free import property and the layers contract's premise.
- **Plan 01-06 (DECISION_LOG.md) owes two ADRs from this plan:** `.importlinter` over `[tool.importlinter]` (equivalent alternative, discoverability decided it) and import-linter over a hand-rolled AST check (grimp sees the transitive graph).
- **Plan 01-07 (AI_WORKFLOW.md) now has two evidence files** in `.planning/phases/01-foundation-quality-gates/evidence/`: `coverage-gate-red.txt` and `import-linter-red-green.txt`. The latter carries the third real incident for the honest incident log - a recipe from this project's own research (`ARCHITECTURE.md:786-796`) that would have shipped an architecture test incapable of failing, caught by executing it rather than trusting it - plus a fourth, smaller one: a research pitfall that did not reproduce and whose real version was found by reading the tool's source.

---
*Phase: 01-foundation-quality-gates*
*Completed: 2026-09-17*
