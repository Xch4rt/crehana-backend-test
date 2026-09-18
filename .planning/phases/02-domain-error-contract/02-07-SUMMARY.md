---
phase: 02-domain-error-contract
plan: 07
subsystem: documentation
tags: [documentation, adr, requirements, roadmap, import-linter, ai-workflow, evidence]

# Dependency graph
requires:
  - plan: 02-05
    provides: the frozen-dataclass command and result DTOs the four amendments now describe, and the eight Protocol ports that satisfy ARC-04
  - plan: 02-06
    provides: ADR-020 (whose Consequences name the four stale texts), the AST stdlib-only test that makes roadmap SC-1 true, and evidence/domain-stdlib-red-green.txt
provides:
  - ARC-05 and ROADMAP Phase 4 SC-5 reworded so Phase 4 can be verified against its own text
  - ROADMAP Phase 2 SC-1 naming the test that actually proves the domain is stdlib-only
  - an .importlinter comment recording that the permissive application contract is deliberate
  - a CLAUDE.md application-layer rule that matches the shipped code
  - the Phase 2 AI_WORKFLOW.md record - human/AI split, one verification bullet, nine dated incidents
  - ARC-02 and ARC-04 ticked after re-verification against the code
affects: [03-persistence, 04-crud-endpoints, 05-auth, 07-documentation-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A wording amendment that propagates an ADR is gated by a positive grep for the new text and a negative grep for the old, so a partial reconciliation fails"
    - "A permissive enforcement rule is documented as a decision in the config file itself, or the next reader tightens it"
    - "AI_WORKFLOW.md is appended to at the end of every phase while the captures are fresh; insertion-only, asserted by zero removed lines in git diff"

key-files:
  created:
    - .planning/phases/02-domain-error-contract/02-07-SUMMARY.md
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .importlinter
    - CLAUDE.md
    - AI_WORKFLOW.md

key-decisions:
  - "ROADMAP Phase 2 SC-1 was amended too, beyond the plan's four artifacts: it claimed the import-linter contract proves the domain is stdlib-only, which 02-06 demonstrated it cannot"
  - "pydantic is still absent from application-framework-free's forbidden_modules, and the comment above the contract now says that is a decision rather than an oversight"
  - "Nine incident entries rather than the three the plan owes: every one is traceable to a summary, an evidence file or a commit, and the phase genuinely produced them"
  - "ARC-02 and ARC-04 were re-verified against the code before being ticked, not inherited from the plan's requirements list"

patterns-established:
  - "An amendment task touches only comment and prose lines when the file is read by a tool; contract names, section headers and enumerated values stay byte-identical"
  - "The incident log records a process compromise (the uncommittable TDD red step) as a compromise, with its cost, rather than omitting it"

requirements-completed: [ARC-04, ARC-02]

# Metrics
duration: 19min
completed: 2026-09-18
---

# Phase 2 Plan 07: Documentation Reconciliation and the Phase 2 Record Summary

**The four artifacts that still claimed application DTOs are Pydantic models now say what the code does and cite ADR-020, a fifth (roadmap SC-1) stops crediting the import-linter contract with a proof it cannot produce, and `AI_WORKFLOW.md` gains the Phase 2 human/AI split plus nine dated incident entries quoting real captures - appended with zero removed lines, with the three import-linter contracts byte-identical and the whole gate observed green in one uninterrupted run at 140 passed and 100% coverage.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-09-18T15:46Z
- **Completed:** 2026-09-18T16:05Z
- **Tasks:** 2
- **Files modified:** 1 created, 5 modified

## Accomplishments

- **Phase 4 can now be verified against its own text.** ARC-05 read "Pydantic v2 models type every boundary: HTTP request/response schemas, application command/result DTOs, settings"; the code ships frozen slotted dataclasses for those DTOs. The requirement now reads "Pydantic v2 models type every HTTP boundary: request/response schemas and settings; application command/result DTOs are frozen dataclasses (ADR-020)", still prefixed `- [ ] **ARC-05**:`, still unticked, still citing `[PDF 2.b]`. ROADMAP Phase 4 success criterion 5 was amended to match.
- **The stale `.importlinter` comment is gone and the permissive contract is documented as deliberate.** The two lines claiming "DTOs are pydantic models" are replaced by a comment that says pydantic is left out of `forbidden_modules` on purpose - a later phase may legitimately want a Pydantic DTO - that ADR-020 chooses frozen dataclasses so nothing imports it today, and that the layer must never see the web framework or the ORM. `grep -c '^\[importlinter:contract:'` is still 3, `grep -c '^name = '` is still 3, no `forbidden_modules` entry moved, and `tests/architecture/test_layer_boundaries.py` passes unmodified with its three-element `EXPECTED_CONTRACT_NAMES`.
- **`CLAUDE.md`'s Project Rules now match the shipped code**, inside the hand-maintained section only. No `<!-- GSD:* -->` block was touched.
- **Roadmap Phase 2 SC-1 stops claiming a proof that does not exist** (see Deviations). It credited the import-linter contract with proving the domain imports no third-party library; plan 02-06 demonstrated that an enumerated `forbidden` contract cannot, by planting an `import greenlet` that the contract reported KEPT. The criterion now names `tests/architecture/test_domain_is_stdlib_only.py` and `sys.stdlib_module_names`, and cites ADR-022.
- **`AI_WORKFLOW.md` carries the Phase 2 record, written while the captures are fresh.** A "What is already true of Phase 2:" block with both sub-headings, one new Verification Practices bullet naming the AST test, and **nine** dated incident entries - the log now holds 13. Every quoted line comes from a committed evidence file: the B042 message and the `AttributeError: 'str' object has no attribute 'value'` false pass, and RUN 2 of `evidence/domain-stdlib-red-green.txt` verbatim with its `Contracts: 3 kept, 0 broken.` / `EXIT=0` against a planted third-party import.
- **The file was appended to, not rewritten.** `git diff -- AI_WORKFLOW.md | grep -c '^-[^-]'` returned **0** before the commit; the four Phase 1 entries, the `_To be completed in Phase 7._` markers and the `## What I Did Not Do` heading are untouched.
- **ARC-02 and ARC-04 ticked after re-verification, not on the plan's say-so.** ARC-02: the three entities are `@dataclass(slots=True)`, the two vocabulary types are `enum.StrEnum`, `CompletionStats` is a frozen slotted dataclass, and the AST test proves the package imports nothing outside the standard library. ARC-04: `grep -rc '(Protocol)'` over `ports/` sums to exactly 8, and `ChangeTaskStatus.__init__(self, uow: UnitOfWork, clock: Clock)` depends on ports and nothing else.
- **The whole gate was observed green in one uninterrupted run**, `make format` first and proven a no-op: black and isort clean over 59 files, flake8 clean, mypy strict clean over 59 source files, three contracts KEPT, **140 passed**, **334 statements / 38 branches / 0 missed / 100%** under `filterwarnings = error` with zero warnings, and `coverage report --include='*/taskmanager/*' --fail-under=100` exiting 0. No `pragma: no cover` anywhere under `src` or `tests`, no `omit` in `pyproject.toml`.

## Task Commits

Each task was committed atomically:

1. **Task 1: reconcile ARC-05, ROADMAP SC-5, the .importlinter comment and the CLAUDE.md rule** - `0aa6ec7` (docs)
2. **Task 2: append the Phase 2 record to AI_WORKFLOW.md and capture the full gate green** - `35434a6` (docs)

**Plan metadata:** see the `docs(02-07)` commit that carries this SUMMARY.

## Files Created/Modified

- `.planning/REQUIREMENTS.md` - ARC-05 reworded; ARC-02 and ARC-04 ticked in both the checklist and the traceability table
- `.planning/ROADMAP.md` - Phase 4 SC-5 reworded, Phase 2 SC-1 reworded, plan 02-07 checked off, the progress row advanced to 7/7 (phase status left open for the verifier)
- `.importlinter` (+7 / -2 comment lines) - the application-layer comment; every contract, name and `forbidden_modules` entry byte-identical
- `CLAUDE.md` (+4 / -2) - the Project Rules application-layer bullet
- `AI_WORKFLOW.md` (+289 / -0) - the Phase 2 human/AI split, one Verification Practices bullet, nine incident entries
- `.planning/phases/02-domain-error-contract/02-07-SUMMARY.md` - this file

## Decisions Made

- **The plan's four amendments became five.** Plan 02-06's handover and its own summary both flagged that roadmap Phase 2 SC-1 is inaccurate in exactly the way ARC-05 was: it names a gate that cannot produce the proof it claims. Leaving it would have closed this phase against a criterion whose evidence is the wrong file. Amending it is the same class of fix as the other four and is documented as a deviation rather than folded in silently.
- **`pydantic` stays out of `forbidden_modules`.** Enforcing D-16 mechanically is out of scope for this phase (02-RESEARCH C-02 says so explicitly, and the contract shape is a locked CONTEXT decision), and a rule nobody has needed yet is a rule that gets deleted under pressure rather than obeyed. What changed is that the comment now records the permissiveness as a decision - the previous version claimed the opposite of the code, which is worse than either option.
- **Nine incident entries, not three.** The plan owes three and forbids padding. The extra six are each traceable to a committed summary, an evidence file or a commit hash: the worktree/hook conflict (`c1c1cae`), the uncommittable TDD red step (five evidence files), the frozen+slots interpreter divergence (`evidence/02-01-frozen-slots-setattr.txt`), the two-flag `coverage --include` trap (`evidence/02-04-tdd-red.txt`), the invariant mutable Protocol member (02-05's deviation 1), and the reconstructed-then-replaced evidence appendix (02-06's deviation 1). Not writing them would have been the mirror-image dishonesty of padding.
- **The TDD compromise is in the evaluator-facing log, with its cost.** The entry states plainly that `git log` alone cannot prove the tests came first in Phase 2, and that two `test` commits land after the `feat` commits they specify. That is the honest version; the alternative was to weaken the `mypy (strict)` hook so the commit graph would look tidier.
- **ARC-02 and ARC-04 were re-verified before the tick.** 02-06's summary warns that an earlier handover was wrong about requirement ownership, so both requirements were checked against the code rather than against a plan header - and ARC-06 and ARC-07, already ticked by 02-06 and 02-04, were confirmed as such rather than re-claimed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] ROADMAP Phase 2 success criterion 1 credits a gate with a proof it cannot produce**

- **Found during:** Task 1
- **Issue:** SC-1 read "...and the import-linter contract proves the `domain` package imports no third-party library." Plan 02-06 demonstrated that it cannot: a `forbidden` contract proves only that the modules it enumerates are absent, and a planted `import greenlet` left all three contracts KEPT while the new AST test went red. Closing this phase against that wording would have signed off a criterion whose named evidence does not support it - the same defect as ARC-05, one artifact over, and 02-06's summary explicitly handed it to this plan.
- **Fix:** SC-1 now names `tests/architecture/test_domain_is_stdlib_only.py`, states that it checks every import root against `sys.stdlib_module_names`, notes that the enumerated contract cannot do this, and cites ADR-022. The numbering and indentation are unchanged.
- **Files modified:** `.planning/ROADMAP.md`
- **Verification:** `grep -q 'test_domain_is_stdlib_only' .planning/ROADMAP.md` matches; the plan's own negative grep for the old SC-5 string still passes, and no other line of the file moved.
- **Committed in:** `0aa6ec7` (Task 1 commit)

**2. [Rule 3 - Blocking] The plan's `<interfaces>` text for `CLAUDE.md` and its own grep gate disagreed**

- **Found during:** Task 1 verification
- **Issue:** The plan's AFTER text for the `CLAUDE.md` bullet spells the rule as `@dataclass(frozen=True, slots=True)`, while its `must_haves` artifact and its automated verify both require the literal string `frozen dataclasses` in that file. Writing the bullet exactly as dictated would have failed the gate the same plan sets.
- **Fix:** the bullet says "application command and result DTOs are frozen dataclasses (`@dataclass(frozen=True, slots=True)`) per ADR-020", which satisfies both the prescribed wording and the grep. This is the same class of collision as 01-04, 02-02, 02-03 and 02-04 hit, and is now routine.
- **Files modified:** `CLAUDE.md`
- **Verification:** `grep -q 'frozen dataclasses' CLAUDE.md` matches and `! grep -q 'application DTOs are$' CLAUDE.md` holds; the full Task 1 grep chain exits 0.
- **Committed in:** `0aa6ec7` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** No scope change. Deviation 1 adds one amended line to a file the plan already edits and closes the last documented gap between this phase's claims and its evidence.

## Issues Encountered

- **The malformed progress row did not recur.** `roadmap update-plan-progress` has written `| n/7 | In Progress|  |` for five consecutive plans (02-02 through 02-06); on the phase's last plan it wrote a well-formed row instead. The bug is presumably in the in-progress branch only, which is worth knowing before anyone reports it.
- **The same handler marked the phase complete, which is not this agent's call.** It ticked the `- [ ] **Phase 2: ...**` line, appended `(completed 2026-09-18)` to it, and set the progress-table row to `Complete | 2026-09-18`. The execution brief reserves phase completion for the orchestrator, after verification. Both were reverted by hand; the row keeps the honest `7/7` and returns to `In Progress | -`, and the plan checkbox for 02-07 stays ticked.
- **`state.update-progress` advanced `completed_phases` from 1 to 2** in the same spirit, because it derives that counter from the SUMMARY files on disk. That one was left as the tool wrote it rather than hand-edited back - the adjacent `status: verifying` and "Phase complete — ready for verification" say plainly that nothing has been verified yet - but it is flagged here because it disagrees with the still-open ROADMAP checkbox until the verifier runs.
- **`state.record-session` flattened `last_activity` to a bare date again**, dropping the descriptive suffix every other entry carries. Restored by hand, as in 02-04, 02-05 and 02-06.
- **`state.update-progress` counts SUMMARY files on disk**, so it was run after this file existed rather than before - the ordering 02-06 discovered.
- Nothing else. Both tasks passed their full `<verify>` chain on the first run after the two fixes above.

## Known Stubs

None. This plan created no code. Every sentence it added to `AI_WORKFLOW.md` points at a commit, a file, a test or a committed capture, and every amendment it made is asserted by a grep in both directions.

## TDD Gate Compliance

Neither task is `tdd="true"` and neither claims to be: both amend prose. The plan's equivalent of a red/green cycle is its negative greps - each amendment is gated on the old string being absent as well as the new string being present - and those were run before each commit.

Worth recording once, since this is the phase-closing plan: **no plan in Phase 2 was able to commit a red test**, because the `mypy (strict)` pre-commit hook rejects a test importing a module that does not exist and `--no-verify` is forbidden by `CLAUDE.md`. Five `evidence/02-0N-tdd-red.txt` files hold the observed red runs instead, and the incident log now states that plainly for an evaluator.

## Threat Flags

None. This plan introduces no network endpoint, no auth path, no file access, no schema and no dependency. Every `mitigate` row of its register is implemented and asserted: T-02-30 (only comment lines changed in `.importlinter`; three contract headers, three `name = ` lines, `pydantic` still absent from the application contract's `forbidden_modules`, `test_layer_boundaries.py` passing unmodified), T-02-32 (all five stale texts amended in one commit, each with a positive and a negative grep), T-02-33 (every incident entry quotes a committed capture; `git diff` showed zero removed lines), T-02-34 (no `pragma: no cover` under `src`/`tests`, no `omit` in `pyproject.toml`, and 100% asserted rather than the 75% floor), T-02-35 (only the hand-maintained `## Project Rules` section of `CLAUDE.md` was touched). T-02-SC stays not-applicable: nothing was installed in this plan or in this phase.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **The phase's documentation and its code now agree.** Phase 4 inherits an ARC-05 it can satisfy and a Phase 4 SC-5 it can be verified against; Phase 2's own SC-1 names the artifact that proves it.
- **Phase 3 inherits one live constraint and one carried-forward fix.** Any non-stdlib import added under `src/taskmanager/domain/` fails the suite immediately, with no `.importlinter` edit required. And `SqlAlchemyUnitOfWork` will meet the mutable-Protocol-member invariance rule that 02-05 hit - the fix is one line of annotation per attribute.
- **Phase 7 owns three things this plan deliberately left alone:** the `## How This Project Was Built` narrative, the `## What I Did Not Do` section, and the per-claim commit/file/test references in the human/AI split. Their `_To be completed in Phase 7._` markers are untouched. It also still owns the refresh of ADR-019, which Phase 1 recorded as stale.
- **`AI_WORKFLOW.md` is appended to at the end of every phase.** That standing rule is now demonstrated twice rather than asserted once; Phase 3 inherits it.
- The phase is **not** marked complete here: the ROADMAP Phase 2 checkbox and the phase status are the verifier's to set.
- No blockers.

## Self-Check: PASSED

`.planning/phases/02-domain-error-contract/02-07-SUMMARY.md` exists on disk, all five modified files exist, and both task commits (`0aa6ec7`, `35434a6`) are present in `git log`.

---
*Phase: 02-domain-error-contract*
*Completed: 2026-09-18*
