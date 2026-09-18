---
phase: 01-foundation-quality-gates
plan: 04
subsystem: tooling
tags: [pre-commit, makefile, developer-gate, hook-ordering, evidence, gnu-make-3.81]

# Dependency graph
requires:
  - "01-01: `.venv` with every pinned tool, `requirements-dev.txt` as the single version source, `.flake8` and `pyproject.toml` tool config, editable `taskmanager` install"
  - "01-02: real modules and tests, so the hooks and targets have something to gate"
  - "01-03: `.importlinter` with three contracts and the `lint-imports` console script as the only sanctioned CLI form"
provides:
  - "`.pre-commit-config.yaml` - four pinned mirror repos plus a `repo: local` pair (mypy, import-linter) with `.venv/bin`-qualified entries"
  - "`Makefile` - nine `.PHONY` targets: install, format, lint, typecheck, arch, test, docker-test, up, down"
  - "`evidence/pre-commit-venv-entry.txt` - the RESEARCH recipe observed killing both whole-program gates under a minimal PATH, and the shipped form green under the same"
  - "A hard constraint for plan 01-05: CI must never call `pre-commit run`"
affects: [01-05, 01-06, 01-07, 01-08, 03-infrastructure]

# Tech tracking
tech-stack:
  added:
    - "pre-commit 4.6.2 (pinned in 01-01, first use here) - hook repos pre-commit-hooks v6.0.0, isort 9.0.1, black-pre-commit-mirror 26.5.1, flake8 7.3.0"
  patterns:
    - "Two-tier hook split: file-scoped formatters from isolated mirror repos, whole-program tools as `repo: local` + `language: system`"
    - "Every hook entry and every Makefile tool invocation is `.venv/bin`-qualified; nothing assumes an activated virtualenv"
    - "`lint` never writes; `format` is the only target allowed to rewrite a file"
    - "A gate is shipped only after being observed failing - the venv-qualified entry has its own red/green capture"

key-files:
  created:
    - .pre-commit-config.yaml
    - Makefile
    - .planning/phases/01-foundation-quality-gates/evidence/pre-commit-venv-entry.txt
  modified: []

key-decisions:
  - "The two `repo: local` hook entries are `.venv/bin/mypy` and `.venv/bin/lint-imports`, deviating from the RESEARCH example's bare `entry: mypy` / `entry: lint-imports`. RESEARCH Assumption A1 marks that recipe as reasoned rather than executed; executed here it kills both gates. Consequence accepted and carried: the config only works where `.venv` exists, so CI and the Docker image must never call `pre-commit run`."
  - "Three comments in the Makefile were reworded rather than deleted, because the plan's own grep gates (`ONESHELL`, `python3.13`, `importlinter.cli` must not appear) fire on prose as readily as on code. The comments now describe each forbidden form without spelling it, keeping the greps meaningful as checks on executable content - the same resolution 01-03 reached for its module docstring."
  - "`--no-logo` was deliberately not added to the `arch` recipe or the import-linter hook, despite 01-03's suggestion: the plan specifies the bare invocation and the nine-line banner is harmless in a local run. Plan 01-05 can add it where job-log noise actually costs something."
  - "`git diff --quiet` was scoped with `':(exclude).planning/config.json'` throughout, because that file carries a pre-existing uncommitted orchestrator edit that predates this plan and must stay uncommitted."

patterns-established:
  - "`make <gate>` and the corresponding pre-commit hook run the identical command from the identical `.venv`, so a green hook and a green target can never disagree"
  - "The evidence directory now holds three gate demonstrations (coverage, architecture, pre-commit entry resolution) for plan 01-07 to embed"

requirements-completed: [FND-08, FND-09]

# Metrics
duration: 14min
completed: 2026-09-17
---

# Phase 01 Plan 04: Local Developer Gate Summary

**A pre-commit configuration whose two whole-program hooks were proven to die under a
realistic shell before being fixed, and a nine-target Makefile whose every gate was
executed rather than declared - `make format` left the tree byte-identical, and lint,
typecheck, arch and test all ran green with no activated virtualenv.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-09-18T01:00:34Z
- **Completed:** 2026-09-18T01:14:14Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- `.pre-commit-config.yaml` ships twelve hooks in the order that cannot oscillate:
  seven hygiene/secret hooks from `pre-commit-hooks v6.0.0` (including
  `detect-private-key` and `check-added-large-files`, the T-01-18 controls), then
  isort 9.0.1 → black 26.5.1 (the mirror, not `psf/black`) → flake8 7.3.0 carrying
  `flake8-bugbear==26.9.9`, `flake8-comprehensions==3.17.0` and `pep8-naming==0.15.1`
  at exactly the `requirements-dev.txt` versions. Every `rev` is an exact pinned tag
  (T-01-17).
- `mypy` and `import-linter` are `repo: local`, `language: system`, `pass_filenames: false`,
  so they run the same binaries as `make typecheck` and `make arch` — with the pydantic
  plugin present and the editable `taskmanager` install visible (T-01-19, T-01-20).
- **Stability proven, not assumed:** two consecutive `pre-commit run --all-files` both
  reported all twelve hooks `Passed`, and `git diff` was empty after the second (T-01-22).
  The first run modified nothing either — 01-01 through 01-03 had already left the tree
  formatted, and a pre-scan found zero tracked files with trailing whitespace or a missing
  final newline, so no verbatim evidence capture was at risk of being rewritten.
- **The gate was observed failing (T-01-45).** With the RESEARCH recipe's bare entries, under
  `env -i HOME=… PATH=/usr/bin:/bin:/usr/local/bin`, pre-commit reported
  `Executable \`mypy\` not found` and `Executable \`lint-imports\` not found`, both hooks
  `Failed`, exit 1 — while the ten hooks above them still said `Passed`, which is exactly what
  makes the failure mode dangerous in a less careful configuration. Swapping to
  `.venv/bin/`-qualified entries and rerunning the identical command produced twelve `Passed`
  and exit 0. Both captures are committed verbatim.
- `Makefile` exposes nine one-word targets, all `.PHONY`, all `$(VENV)/bin/`-qualified.
  `make format` was run and left the tree byte-identical (ROADMAP criterion 1 exercised, not
  declared); `make lint` (check modes only, T-01-21), `make typecheck`, `make arch`
  (3 contracts kept) and `make test` (8 passed, 100 % over 18 statements) all exit 0 from a
  shell with no activated virtualenv. `make -n docker-test` expands to the two-line
  build/run recipe; `make up` and `make down` print an honest Phase-3 message and exit 0.
- `pre-commit install` ran in this clone: `.git/hooks/pre-commit` exists and both of this
  plan's own commits went through the hooks, which is the first real end-to-end proof that
  the gate fires on a `git commit` and not only on `--all-files`.

## Task Commits

1. **Task 1: pre-commit configuration with the mirror/local hook split** — `4d8fbbe` (build)
2. **Task 2: Makefile with one-word targets** — `4db6f26` (build)

## Files Created/Modified

- `.pre-commit-config.yaml` — hooks plus a header comment explaining *why* the tiers are
  split and why the `.venv/bin/` prefix is load-bearing, so the next person does not
  "simplify" it back to bare entries
- `Makefile` — nine targets with comments naming the constraint behind each shape
  (GNU Make 3.81, no version-suffixed interpreter, check-only `lint`, the forbidden
  import-linter invocation form)
- `.planning/phases/01-foundation-quality-gates/evidence/pre-commit-venv-entry.txt` —
  scenario A (RESEARCH recipe, exit 1, both gates dead) and scenario B (as shipped, exit 0),
  same command, same minimal environment, only the two `entry` values different

## Decisions Made

- **Deviating from RESEARCH deliberately, and proving it.** The plan instructed the
  `.venv/bin/` prefix and flagged the RESEARCH example as unexecuted. Rather than take that
  on faith, both forms were run under the same minimal environment. The bare form fails with
  `Executable \`mypy\` not found` — and it fails *only* for the two hooks that matter most,
  while the mirror hooks keep reporting green, which is precisely the "looks enforced but is
  not" shape this phase exists to eliminate. Evidence committed.
- **The price of the prefix is written down where it will be read.** A `.venv/bin/`-qualified
  entry means the config is developer-host-only. That is not free, and plan 01-05 has to
  honour it: the header comment of `.pre-commit-config.yaml` and the evidence file both state
  that CI and the Docker image must never call `pre-commit run`, and must instead run black,
  isort, flake8, mypy, `lint-imports` and pytest as named steps.
- **Comments reworded, greps left strict.** Three of the plan's acceptance greps
  (`ONESHELL`, `python3.13`, `importlinter.cli`) fired on explanatory comments. Relaxing a
  grep would have turned a mechanical check into one a future contributor could satisfy while
  still calling the forbidden thing; deleting the comments would have thrown away the
  rationale. Both were kept by describing each form instead of spelling it — the resolution
  01-03 already reached for the architecture test's docstring, now an established convention
  in this repository.
- **No `--no-logo`.** 01-03 suggested it for readable logs. The plan specifies the bare
  invocation, and in a local `make arch` the banner costs nothing. Left to plan 01-05, where
  a CI job log is the thing being read.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Three Makefile comments tripped the plan's own grep gates**

- **Found during:** Task 2
- **Issue:** The first Makefile draft explained its constraints by naming them: "silently
  ignores `.ONESHELL`", "never `python3.13`", "never `python -m importlinter.cli`". The
  plan's verification requires `grep -c` to return 0 for all three strings, so the
  verification chain exited 1 three times in a row on prose, not on behaviour.
- **Fix:** Reworded each comment to describe the forbidden form without writing it ("the
  special target that would run a whole recipe in a single shell (added in 3.82)", "never a
  version-suffixed interpreter name", "import-linter's command-line module run through
  `python -m`"). Rationale preserved, gates left strict.
- **Files modified:** `Makefile`
- **Commit:** `4db6f26`

**2. [Rule 2 - Missing critical functionality] The deviation from RESEARCH had no committed observation**

- **Found during:** Task 1
- **Issue:** The plan asks for the `.venv/bin/` prefix and for the SUMMARY to record the
  deviation, but its verification only proves the *shipped* form works. A reader had no way
  to distinguish a necessary deviation from a superstitious one, and this phase's stated
  thesis is that a gate never seen red is indistinguishable from a no-op.
- **Fix:** Ran the RESEARCH recipe verbatim under the same `env -i` command, captured
  `Executable \`mypy\` not found` / `Executable \`lint-imports\` not found` and exit 1,
  restored the shipped config from a backup, reran and captured exit 0. Both in
  `evidence/pre-commit-venv-entry.txt`. `grep -n "entry:"` confirmed the restore, and
  `git diff` was clean before the commit. Cost: about two minutes, no shipped file altered.
- **Files modified:** `.planning/phases/01-foundation-quality-gates/evidence/pre-commit-venv-entry.txt` (created)
- **Commit:** `4d8fbbe`

### Process Deviations

**3. `git diff --quiet` was scoped to exclude `.planning/config.json`**

- **Found during:** Task 1
- **Reason:** `.planning/config.json` carries a pre-existing uncommitted orchestrator edit
  (`_auto_chain_active`) that predates this plan and must remain uncommitted, so a bare
  `git diff --quiet` could never have exited 0 regardless of what the hooks did.
- **Impact:** None on what is being asserted. Every check used
  `git diff --quiet -- . ':(exclude).planning/config.json'`, which still covers every file
  pre-commit could touch. The file was verified byte-identical after both commits: pre-commit
  stashed and restored it around each hook run (`Restored changes from …/patch….`), and
  `git diff -- .planning/config.json` still shows exactly the original one-line change.

## Issues Encountered

None blocking. Two observations:

- `check-yaml` and `check-toml` report `(no files to check) Skipped` on a `--all-files` run
  when the only file of that type is still untracked — pre-commit's `--all-files` means "all
  files git knows about". `check-yaml` first genuinely ran on `.pre-commit-config.yaml` at
  commit time and again on the post-commit `--all-files` sweep, where it passed. Worth
  knowing before reading a Skipped line as a passing one.
- The mirror hook environments cost about 40 s to build on first run and are cached in
  `~/.cache/pre-commit` afterwards. An evaluator's first `git commit` after `make install`
  will pause for that; the README (plan 01-07 / Phase 7) should say so.

## Verification Results

| Check | Result |
|-------|--------|
| `.pre-commit-config.yaml` parses; ids include isort, black, flake8, mypy, import-linter, detect-private-key | pass (12 hooks) |
| Hook order isort < black < flake8 | pass |
| `repo: local` hooks: `language: system`, `pass_filenames: false` | pass (both) |
| Local hook entries are `.venv/bin/mypy` and `.venv/bin/lint-imports` | pass |
| flake8 `additional_dependencies` match `requirements-dev.txt` | pass (3 plugins, exact pins) |
| Every `rev` an exact tag: `v6.0.0`, `9.0.1`, `26.5.1`, `7.3.0` | pass |
| `grep -c 'importlinter.cli' .pre-commit-config.yaml` | 0 |
| `.venv/bin/pre-commit run --all-files` twice | exit 0, exit 0 — all hooks Passed |
| `git diff --quiet` (excluding the pre-existing `config.json` edit) after run 2 | exit 0 |
| `env -i HOME=… PATH=/usr/bin:/bin:/usr/local/bin .venv/bin/pre-commit run --all-files` | exit 0, twelve Passed |
| Same command with bare entries (RESEARCH recipe) | exit 1, both local hooks `Failed`, `Executable ... not found` |
| `.git/hooks/pre-commit` exists | pass (hooks ran on both commits) |
| Nine Makefile targets present and in `.PHONY` | pass |
| `grep -c 'ONESHELL' Makefile` / `'python3\.13'` / `'importlinter.cli'` | 0 / 0 / 0 |
| `make format` then `git diff --quiet` | exit 0, exit 0 — 14 files unchanged |
| `make lint` | exit 0 — black/isort check-only, flake8 silent |
| `make typecheck` | `Success: no issues found in 14 source files` |
| `make arch` | `Contracts: 3 kept, 0 broken.` |
| `make test` | `8 passed`, `Required test coverage of 75% reached. Total coverage: 100.00%` |
| `make -n docker-test` | expands to `docker build --target test …` + `docker run --rm …` |
| `make up` / `make down` | exit 0, one honest line each naming Phase 3 |
| No recipe depends on a `cd` from a previous line | pass (17 recipe lines, each self-contained) |
| `.planning/config.json` still modified and uncommitted, content unchanged | pass |
| `Dockerfile` / `.github/workflows/ci.yml` not created (plan 01-05 owns them) | pass |

## Self-Check: PASSED

All 3 created files verified present on disk (`.pre-commit-config.yaml`, `Makefile`,
`evidence/pre-commit-venv-entry.txt`); commits `4d8fbbe` and `4db6f26` verified in `git log`.

## Known Stubs

`up` and `down` are intentional placeholders, sanctioned by CONTEXT D-12 and RESEARCH Open
Question 2 (RESOLVED). Each prints one accurate line and exits 0; neither claims to start or
stop anything. Phase 3 replaces the bodies with `docker compose up -d` / `docker compose down`
without renaming the targets. `docker-test` is not a stub — its recipe is final — but the
`Dockerfile` it builds arrives in plan 01-05, so only `make -n docker-test` was exercised here;
the real build is plan 01-08's combined run.

## Threat Flags

None. No network surface, auth path, file access pattern or schema was introduced. The plan's
register (T-01-17 through T-01-22, T-01-45) is fully addressed, with T-01-45 strengthened
beyond the plan by the committed red capture of the bare-entry form.

## User Setup Required

None on this machine — `pre-commit install` has already run here, so every subsequent
`git commit` in this clone triggers the twelve hooks. Anyone cloning fresh runs
`make install`, which ends with `pre-commit install`.

## Next Phase Readiness

Ready for plans 01-05, 01-06 and 01-07. What they must know:

- **Plan 01-05 (Dockerfile + `ci.yml`): CI must never call `pre-commit run`.** The two
  repo-local hooks resolve `.venv/bin/mypy` and `.venv/bin/lint-imports`, and a GitHub runner
  has no `.venv`. Run black `--check`, isort `--check-only`, flake8, `mypy src tests`,
  `lint-imports` and `pytest` as named steps instead — the same commands the Makefile already
  encodes, so `make lint typecheck arch test` is the shortest correct CI body if the runner
  builds a `.venv`, and the individual commands are correct if it installs into the system
  interpreter. Plan 01-05's own assertion that `pre-commit` appears nowhere in `ci.yml` is
  therefore load-bearing, not cosmetic.
- **Plan 01-05:** `make docker-test` expects `docker build --target test -t taskmanager-test .`
  to work and the `test` stage's default command to run the suite. The target name is frozen;
  Phase 3 swaps the body only. Add `--no-logo` to the CI `lint-imports` step if job-log noise
  matters — the nine-line banner is deliberately left in the Makefile.
- **Plan 01-06 (`DECISION_LOG.md`) owes three ADRs from this plan:** (1) repo-local
  `language: system` hooks over `pre-commit/mirrors-mypy` + `additional_dependencies`, with
  the developer-host-only consequence; (2) `.venv/bin`-qualified hook entries, with the
  evidence file as its citation; (3) `up`/`down` as honest Phase-1 placeholders
  (RESEARCH Open Question 2). Plus the two still owed by 01-03.
- **Plan 01-07 (`AI_WORKFLOW.md`) now has three evidence files** in
  `.planning/phases/01-foundation-quality-gates/evidence/`: `coverage-gate-red.txt`,
  `import-linter-red-green.txt`, `pre-commit-venv-entry.txt`. The third carries a fourth real
  incident for the honest log: this project's own research published a pre-commit recipe it had
  never executed (and said so, in its Assumptions Log), that recipe silently disables the two
  strongest gates outside an activated venv, and it was caught by running both forms rather
  than by reading either.
- **Phase 3:** when compose lands, convert `up`/`down` in place and leave `docker-test`'s name
  alone. When new tools enter `requirements-dev.txt`, the mirror hook revs in
  `.pre-commit-config.yaml` must be bumped in the same commit — they are a fourth place where
  black, isort and flake8 versions are pinned, and pre-commit's `autoupdate` is the intended
  mechanism.
- **Everything still green:** 8 tests, 100 % coverage over 18 statements, 3 contracts kept,
  mypy clean over 14 files, twelve hooks passing twice in a row and under a minimal PATH.

---
*Phase: 01-foundation-quality-gates*
*Completed: 2026-09-17*
