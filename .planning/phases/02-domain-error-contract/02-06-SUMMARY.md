---
phase: 02-domain-error-contract
plan: 06
subsystem: architecture
tags: [python, ast, stdlib, pytest, architecture-test, import-linter, adr, evidence]

# Dependency graph
requires:
  - phase: 01-foundation-quality-gates
    provides: .importlinter with three contracts, tests/architecture/test_layer_boundaries.py, the red/green evidence precedent, pytest/mypy/flake8/black/isort gates
  - plan: 02-03
    provides: the eleven-module domain tree the AST walk scans and whose size the anti-vacuity guard asserts
  - plan: 02-04
    provides: the four exception handlers and STATUS_BY_EXCEPTION, the shipped code ADR-021 describes
  - plan: 02-05
    provides: the frozen-dataclass command and result DTOs, the shipped code ADR-020 describes
provides:
  - tests/architecture/test_domain_is_stdlib_only.py - the AST proof that closes Conflict C-01 and makes roadmap SC-1 mechanically true
  - the anti-vacuity guard pattern for a filesystem-scanning architecture test
  - evidence/domain-stdlib-red-green.txt - the greenlet-vs-lint-imports contrast, the pydantic both-fail run, and the empty-scan appendix
  - ADR-020, ADR-021 and ADR-022, appended without touching a single existing entry
affects: [02-07-phase-close, 03-persistence, 04-crud-endpoints, 05-auth]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "An architecture test that scans the filesystem carries a companion guard asserting the scan matched the real tree, with named files, not only a count"
    - "A violation assertion is made against a list of (module, imported) pairs so the failure names the offender; never against a boolean"
    - "A new check that can ride inside pytest is preferred to a new gate, because a gate must be added to both .pre-commit-config.yaml and ci.yml (ADR-015)"
    - "Evidence files use lint-imports --no-logo instead of Phase 1's [logo elided] marker, so every capture is verbatim with nothing edited out"
    - "DECISION_LOG.md entries refine an earlier ADR by id; the earlier entry is never edited, and git diff proves it (zero removed lines)"

key-files:
  created:
    - tests/architecture/test_domain_is_stdlib_only.py
    - .planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt
  modified:
    - DECISION_LOG.md

key-decisions:
  - "ast + sys.stdlib_module_names over grimp.build_graph: grimp is an undeclared transitive of import-linter, so a future bump would break the suite with a ModuleNotFoundError in an unrelated file"
  - "The enumerated .importlinter contract is kept alongside the new test, not replaced - it names the exact offending import path, which the generic test cannot"
  - "No gate added to .pre-commit-config.yaml or .github/workflows/ci.yml: the check runs inside pytest, which both already invoke, so ADR-015's add-it-in-both-places rule never applies"
  - "greenlet is the planted import because it is real, already installed (3.5.6, transitive of SQLAlchemy[asyncio]) and absent from forbidden_modules - the exact blind spot being closed"
  - "ARC-06 is ticked here: 02-06 is its last claimant across the 02-0* plans; 02-07 claims only ARC-04 and ARC-02"

patterns-established:
  - "The empty-scan failure mode of a filesystem-scanning test is observed and captured, not merely guarded against"
  - "A red/green evidence file closes with an exit-code summary table, so the contrast is readable in four lines"
  - "An ADR that contradicts earlier documents records the contradiction rather than silently reconciling it, and names the plan that will amend the stale text"

requirements-completed: [ARC-06]

# Metrics
duration: 10min
completed: 2026-09-18
---

# Phase 2 Plan 06: The Stdlib-Only Proof and Three Decision Records Summary

**Roadmap success criterion 1 said the import-linter contract proves the domain imports no third-party library; it could not, and now a 15-statement AST test does - every import root under `src/taskmanager/domain/` is checked against `sys.stdlib_module_names`, guarded by an anti-vacuity test that asserts it scanned eleven real modules including four named ones, and observed going red on a planted `import greenlet` that `lint-imports` reported as KEPT in the same tree. 140 passed at 100% coverage on CPython 3.14.3 and 3.13, plus ADR-020, ADR-021 and ADR-022 appended with zero removed lines.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-18T07:34:59Z
- **Completed:** 2026-09-18T07:45:25Z
- **Tasks:** 2
- **Files modified:** 2 created, 1 modified

## Accomplishments

- **Conflict C-01 is closed, and roadmap SC-1 is mechanically true.** `tests/architecture/test_domain_is_stdlib_only.py` parses every `.py` file under `src/taskmanager/domain/` with `ast`, collects the root name of every absolute import, and asserts each one is in `sys.stdlib_module_names` or is `taskmanager`. The eleven domain modules import only `dataclasses`, `datetime`, `typing`, `uuid`, `enum`, `collections.abc` and `taskmanager.domain`, and that is now a test rather than a claim.
- **The gap was demonstrated, not argued** (threat T-02-07). With `import greenlet` planted in a domain module, the new test fails naming `('_violation.py', 'greenlet')` while `.venv/bin/lint-imports` exits **0** and reports `Domain is framework-free` **KEPT**. The most useful detail in the whole capture is the file count: 48 files / 79 dependencies clean, **50 / 80** with greenlet present. grimp resolved the import perfectly and added greenlet to the graph as a node; the contract simply had nothing to say about it, because `forbidden_modules` is a list of nine names and greenlet is the tenth.
- **The new test subsumes the old contract rather than replacing it.** With `import pydantic` planted instead, both gates fail. The enumerated contract is kept because its failure message names the exact import path (`taskmanager.domain._violation -> pydantic (l.1)`), which the generic test cannot produce.
- **The test cannot pass vacuously, and that failure mode was observed too** (threat T-02-29). `test_the_domain_package_is_actually_scanned` asserts `len(scanned) >= 10` and that `exceptions.py`, `validation.py`, `value_objects/task_status.py` and `entities/task.py` were all among the scanned files. `MINIMUM_DOMAIN_MODULES` was temporarily raised to 99 to watch the guard fire (`assert 11 >= 99`), the capture is in the evidence file's appendix, and the constant was restored immediately.
- **Relative imports are skipped, not resolved.** `ast.ImportFrom` nodes with `node.level > 0` cannot reach outside the domain, so they are ignored with a comment saying why - reporting them as violations is the obvious bug in a test shaped like this one, and a wrong test here would have been indistinguishable from a real architecture failure.
- **No gate was added to either gate file** (threat T-02-30, PC-8). `git diff --quiet -- .pre-commit-config.yaml .github/workflows/ci.yml` exits 0, and `.importlinter` still declares exactly three contracts, so `test_every_contract_is_configured` and its unchanged `EXPECTED_CONTRACT_NAMES` still pass. The check rides inside `pytest`, which pre-commit, the Docker `test` stage and CI all already invoke.
- **Three decision records appended, nothing edited** (threat T-02-31). `git diff -- DECISION_LOG.md` shows **166 insertions and 0 deletions**; `grep -c '^## ADR-'` returns 22. ADR-004 and ADR-005 are byte-identical to their committed versions.
- **Verified on both runtimes.** `sys.stdlib_module_names` is per-interpreter and the two sets genuinely differ - 297 names on the host's CPython 3.14.3, 290 on `python:3.13-slim-trixie` - so "passes on the host" does not imply "passes in CI" for a check built on this constant. `make docker-test` reports the same 140 passed at 100%, and the seven-name difference is captured in the evidence file rather than assumed away.
- **All four gates green, zero warnings.** `make lint && make typecheck && make arch && make test`: black and isort clean over 59 files, flake8 clean, mypy strict clean over 59 source files, three contracts KEPT, 140 passed, 100% total coverage under `filterwarnings = error`.

## Task Commits

Each task was committed atomically:

1. **Task 1: the AST stdlib-only test and its red/green evidence** - `2443c2c` (test)
2. **Task 2: append ADR-020, ADR-021 and ADR-022 to DECISION_LOG.md** - `d00e4b3` (docs)

**Plan metadata:** see the `docs(02-06)` commit that carries this SUMMARY.

## Files Created/Modified

- `tests/architecture/test_domain_is_stdlib_only.py` (92 lines) - a three-paragraph module docstring in the analog's "Deliberately NOT used:" voice (why the `forbidden` contract is not enough, why `grimp` is not imported), `DOMAIN_ROOT` / `MINIMUM_DOMAIN_MODULES` / `REQUIRED_SCANNED_MODULES`, the `_domain_modules()` and `_imported_roots()` helpers, and exactly two `-> None` test functions
- `.planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt` (232 lines) - six verbatim captures with exit codes, a "What this proves" paragraph, the planted-file disclosure, an exit-code summary table, an appendix on the empty-scan failure mode and a second appendix on the 3.13-vs-3.14.3 stdlib-name difference
- `DECISION_LOG.md` (+166 lines, -0) - ADR-020 (frozen-dataclass DTOs refining ADR-004), ADR-021 (the `DomainError` base shape and the four handlers' deliberate gaps), ADR-022 (the AST-over-grimp choice)

## Decisions Made

- **`ast` + `sys.stdlib_module_names`, not `grimp.build_graph`.** Both forms were verified working during research and both report the same violations. `grimp` reaches this environment only as a transitive dependency of `import-linter`, and `requirements-dev.txt` states in a comment that it is intentionally undeclared. Importing it in an architecture test would let a routine `import-linter` bump break the suite with a `ModuleNotFoundError` in a file that has nothing to do with the upgrade. The cost accepted is roughly fifteen statements of hand-rolled import parsing, bounded by skipping relative imports rather than resolving them - the test reads Python's import syntax, it never models the import system.
- **The enumerated contract stays.** Deleting `domain-framework-free` once the general test exists was tempting and would have been wrong: the contract's failure message names the offending module and the imported package and the line number, which is what someone debugging actually needs. The general test answers "is anything wrong"; the contract answers "what, exactly". They are kept for different jobs, and ADR-022 says so.
- **`greenlet` is the planted import, and the choice is load-bearing.** It had to be a package that is genuinely installed (so the demonstration uses an import that would really resolve, not a name invented to fail), genuinely third-party, and genuinely absent from `forbidden_modules`. greenlet 3.5.6 is all three - it arrives as a transitive of `SQLAlchemy[asyncio]` and is exactly the kind of package a later phase could plausibly reach for.
- **`--no-logo` replaces Phase 1's `[logo elided]` marker.** The Phase 1 evidence file had to disclose an edit to its own captures, which slightly weakens a document whose value is that it is verbatim. Suppressing the banner at the source removes the need for the disclosure entirely.
- **The empty-scan failure mode was executed, not just guarded.** The guard test was written first, but writing a guard and *watching it fail* are different claims, and this project's own precedent (Phase 1's `test_every_contract_is_configured` appendix) is to make the second one. `MINIMUM_DOMAIN_MODULES` was raised to 99, the failure captured verbatim, and the file restored from its `.bak` in the same command.
- **ARC-06 is ticked here; ARC-02 is not.** The convention plan 02-01 set gives the tick to the last claimant. Checking every `requirements:` line across `02-0*-PLAN.md`: ARC-06 is claimed by 02-02, 02-03 and 02-06, and **not** by 02-07 - so 02-06 is its last claimant and owns the tick. ARC-02 is claimed by 02-01, 02-03, 02-06 **and 02-07**, so 02-07 still owns that one. Before ticking, both halves of ARC-06 were re-verified: thirteen classes carry a `code: ClassVar`, all five named families exist (`NotFoundError`, `ConflictError`, `BusinessRuleViolationError`, `AuthenticationError`, `AuthorizationError`), and `grep -rn 'HTTPException' src/taskmanager --include='*.py' | grep -v '/presentation/'` returns nothing.
- **A trailing `---` was added after ADR-022.** The observed convention is a separator *between* entries, and the previously-last entry (ADR-019) carried none. The plan asks for every entry to close with one, and adding it is forward-compatible: ADR-023 will simply append after it. A separator was likewise inserted after ADR-019, which is a pure addition and leaves its prose byte-identical.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The evidence file's appendix described an observation that had not been run**

- **Found during:** Task 1, while writing `evidence/domain-stdlib-red-green.txt`
- **Issue:** The appendix on the empty-scan failure mode was drafted with a *plausible* pytest capture (an abbreviated traceback and `1 failed`) rather than a real one. In a file whose entire value is that it is verbatim, and in a project whose thesis is that AI output must be verified rather than trusted, a reconstructed capture is the single worst defect available - it is indistinguishable from the real thing to a reader and false to anyone who re-runs it.
- **Fix:** `MINIMUM_DOMAIN_MODULES` was actually raised to 99, `.venv/bin/pytest tests/architecture -q --no-cov -k actually_scanned` actually run, and the drafted block replaced with the real output - which differs in several details, including the full docstring echo, the `11 >= 99` values, the enumerated `scanned` set in the `where` clause, the line number `:78` and `1 failed, 3 deselected in 0.05s`. The constant was restored from a `.bak` in the same command and re-checked by grep.
- **Files modified:** `.planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt`
- **Verification:** the appendix capture is now byte-for-byte what the command printed; `grep -n 'MINIMUM_DOMAIN_MODULES = ' tests/architecture/test_domain_is_stdlib_only.py` returns `36:MINIMUM_DOMAIN_MODULES = 10`, and the committed test is the shipped one.
- **Committed in:** `2443c2c` (Task 1 commit)

**2. [Rule 2 - Missing critical] A second appendix proving the test passes on the target runtime**

- **Found during:** Task 1, after `make docker-test`
- **Issue:** The plan's action text does not ask for a Docker run, but this test is built on `sys.stdlib_module_names`, which is *per-interpreter*. The host is CPython 3.14.3 and CI/Docker is 3.13, and the two sets are not the same size. A green host run is therefore not evidence that CI will be green, and shipping the test without checking would have left the phase's central claim resting on an untested assumption.
- **Fix:** Both interpreters were measured (297 names on 3.14.3, 290 on `python:3.13-slim-trixie`), `make docker-test` was run, and Appendix 2 records both counts, both suite results and the one sentence that matters: every module the domain actually imports is in both sets, so the seven-name difference never touches this test.
- **Files modified:** `.planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt`
- **Verification:** `make docker-test` reports 140 passed, 100.00% coverage on CPython 3.13.15.
- **Committed in:** `2443c2c` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** No scope change, no interface change. Both deviations are inside the evidence file; the test module shipped exactly as `<interfaces>` specifies. Plan 02-07 consumes this evidence file for `AI_WORKFLOW.md` and gets a stronger artifact than the plan assumed - the empty-scan appendix and the dual-runtime appendix are both real incidents worth an entry there.

## Issues Encountered

- **The prior-wave handover was wrong about ARC-06.** It stated that ARC-02, ARC-04 and ARC-06 are all claimed by 02-07, so 02-07 owns those ticks. Grepping every `requirements:` line shows 02-07 claims `[ARC-04, ARC-02]` only. ARC-06's last claimant is this plan, so the tick was taken here after re-verifying both halves of the requirement against the code. Worth flagging to 02-07 so it does not look for an ARC-06 tick it never owned.
- **The `roadmap update-plan-progress` handler wrote the malformed progress row again** (`| 6/7 | In Progress|  |` instead of `| 6/7 | In Progress | - |`), for the fifth consecutive plan - 02-02, 02-03, 02-04, 02-05 and now 02-06. Repaired by hand in the same commit as this SUMMARY. This is clearly a handler bug and not a per-plan accident; it is worth reporting upstream rather than repairing a sixth time.
- **`state.record-session` flattened `last_activity` to a bare date again**, dropping the descriptive suffix every other entry carries. Restored by hand, as in 02-04 and 02-05.
- **`state.update-progress` had to be run twice.** It recalculates `completed_plans` from the SUMMARY files present on disk, so the first run (before this file existed) still reported 13. Re-run after writing the SUMMARY.
- Nothing else. Both tasks passed their full `<verify>` chain on the host (CPython 3.14.3) and in Docker (CPython 3.13.15), with zero warnings.

## Known Stubs

None. This plan created one test module, which is fully implemented and was observed both passing and failing, and one evidence file, every line of which is a real command's real output.

## TDD Gate Compliance

This plan's Task 1 is `tdd="true"` and, unusually for this repository, its RED phase **is** separable in principle and was genuinely demonstrated - but not as a commit, and for a different reason than plans 02-01 through 02-05 hit.

- **RED:** the test was written first, then run against a tree containing `src/taskmanager/domain/_violation.py` with `import greenlet` in it. It failed, naming the module and the package. The planted import was then changed to `import pydantic` and the run repeated; it failed again, this time alongside `test_import_contracts_hold`. Both captures are verbatim in `evidence/domain-stdlib-red-green.txt` (RUN 1 and RUN 3).
- **GREEN:** `_violation.py` was deleted and the same command re-run - 4 passed, exit 0 (RUN 5). That tree is what `2443c2c` commits.
- **REFACTOR:** not needed. No structural change was made after green.

The RED could not be its own commit because the only way to make this test fail is to commit a deliberate architecture violation into `src/taskmanager/domain/` - which the `import-linter contracts` pre-commit hook rejects for the `pydantic` case, and which would in any event leave a broken domain module in the repository's history for the `greenlet` case. The plan anticipated this and specified the evidence-file form instead. Neither `--no-verify` nor a suppression comment was used anywhere.

Task 2 is not a TDD task and does not claim to be: it appends prose to a Markdown file.

## Threat Flags

None. This plan introduces no network endpoint, no auth path, no schema and no new dependency. Every `mitigate` row of the plan's register is implemented and asserted: T-02-07 (the AST check over `sys.stdlib_module_names`, observed red on a planted `greenlet` that `lint-imports` reported KEPT), T-02-29 (the anti-vacuity guard, itself observed failing), T-02-30 (`.importlinter` still holds exactly three contract headers and `git diff --quiet` over both gate files exits 0), T-02-31 (`git diff -- DECISION_LOG.md` shows zero removed lines). T-02-SC stays not-applicable and is worth one sentence: the plan's central technical choice - `ast` over `grimp` - exists precisely so that no undeclared transitive dependency is taken on, so this plan reduces supply-chain surface rather than merely avoiding adding to it.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Plan 02-07 (phase close) is unblocked and inherits three things.** It owns the `ARC-02` and `ARC-04` ticks (ARC-06 is already done here). It consumes `evidence/domain-stdlib-red-green.txt` for `AI_WORKFLOW.md`, and both deviations above are real, dated incidents of exactly the kind that file records. And ADR-020's consequences name its documentation work explicitly: `REQUIREMENTS.md` ARC-05, `ROADMAP.md` Phase 4 SC-5, the `.importlinter` comment above `application-framework-free`, and the `CLAUDE.md` Project Rules line all still say the application DTOs are Pydantic models, and all four must be amended or Phase 4 verification will fail against its own text.
- **Roadmap SC-1 can now be checked off honestly** when 02-07 verifies the phase - with the caveat that its wording ("the import-linter contract proves...") is itself inaccurate and should be amended to name the test.
- **Phase 3 onward inherits a live constraint.** Any import added to `src/taskmanager/domain/` that is not standard library fails the suite immediately, with no `.importlinter` edit required and no enumerated list to keep current. That is the intended pressure: persistence concerns stay in `infrastructure`.
- No blockers.

## Self-Check: PASSED

Both created files exist on disk (`tests/architecture/test_domain_is_stdlib_only.py`, `.planning/phases/02-domain-error-contract/evidence/domain-stdlib-red-green.txt`), `DECISION_LOG.md` carries 22 ADR headings, and both task commits (`2443c2c`, `d00e4b3`) are present in `git log`.

---
*Phase: 02-domain-error-contract*
*Completed: 2026-09-18*
