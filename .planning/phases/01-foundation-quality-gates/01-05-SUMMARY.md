---
phase: 01-foundation-quality-gates
plan: 05
subsystem: delivery
tags: [docker, multistage, non-root, github-actions, ci, postgres-service, evidence]

# Dependency graph
requires:
  - "01-01: `requirements.txt` / `requirements-dev.txt` as the single version source, the `[project]` packaging block, `.dockerignore`, `pytest.ini`, `.flake8`"
  - "01-02: `taskmanager.main:create_app` as a factory with no module-level app, `Settings` with two no-default fields, and the `.env.example` parity test"
  - "01-03: `.importlinter` with three contracts and `lint-imports` as the only sanctioned CLI form"
  - "01-04: the constraint that CI and the image must never drive the local hook framework, and the frozen `make docker-test` contract"
provides:
  - "`Dockerfile` - three genuine stages (builder -> runtime, builder -> test); runtime carries only `/opt/venv` and runs as a non-root system account"
  - "`.github/workflows/ci.yml` - a single `quality-gates` job running six gates as direct steps against a pinned `postgres:18-alpine` service"
  - "`evidence/docker-test-stage.txt` - the research `test` stage observed red, then green, with the runtime observations alongside"
  - "A working `make docker-test`: the target 01-04 could only expand with `-n` now actually builds and runs"
affects: [01-06, 01-07, 01-08, 03-infrastructure]

# Tech tracking
tech-stack:
  added:
    - "Docker multistage build on `python:3.13-slim-trixie` (Docker Engine 29.2.0, BuildKit)"
    - "GitHub Actions: `actions/checkout@v7`, `actions/setup-python@v7`, service image `postgres:18-alpine`"
  patterns:
    - "Dependency layer before source layer, so a code edit never invalidates a `pip install`"
    - "The runtime stage receives an artifact (`/opt/venv`), never a source tree - the package lives in site-packages, `/app` is empty"
    - "The test stage reinstalls the package editable so coverage reports `src/taskmanager/...` and only one copy sits on `sys.path`"
    - "Every gate is a separately named CI step, so a failure names itself in the job log"
    - "Comments describe a forbidden form instead of spelling it, keeping the plan's grep gates strict - the convention 01-03 and 01-04 established"

key-files:
  created:
    - Dockerfile
    - .github/workflows/ci.yml
    - .planning/phases/01-foundation-quality-gates/evidence/docker-test-stage.txt
  modified: []

key-decisions:
  - "The research `test` stage was shipped only after being observed failing. Copied verbatim it is red: 01-02's `.env.example` parity test reads the file from the repository root, and the stage never copied it. `.env.example` was added to the stage's configuration COPY - it is a tracked placeholder, the real `.env` remains excluded by `.dockerignore`, and neither exists in the runtime stage."
  - "Image size recorded as observed (368 MB on linux/arm64 with a BuildKit attestation manifest), not the research's 285 MB. Both are far under the 500 MB ceiling; repeating a number measured on another platform would have been the easier and less honest option."
  - "`--no-logo` added to the CI `lint-imports` step only, as 01-04 handed over. The Makefile keeps the bare invocation: a nine-line banner costs nothing locally and costs log signal in a job."
  - "`permissions: contents: read` declared at workflow level rather than omitting the block. The acceptance criterion only forbids write scopes; an explicit read-only declaration also survives a future change to the repository's default workflow permissions."
  - "The runtime `CMD` was exercised, not just built: the container was started with both no-default settings injected through the environment and served `/openapi.json` with 200. `docker build` succeeding and the image serving are different claims."

patterns-established:
  - "Four evidence captures now exist for plan 01-07; each one is a gate observed red before it was shipped green"
  - "`.dockerignore`, the Dockerfile stages and the CI job form one chain: nothing reaches a layer or a runner that was not deliberately put there"

requirements-completed: [DOCK-01, DOCK-04, FND-10]

# Metrics
duration: 17min
completed: 2026-09-18
---

# Phase 01 Plan 05: Docker Image and CI Workflow Summary

**A three-stage image whose runtime carries a virtualenv and nothing else - `whoami` is
`app`, `/app` is empty, and it serves `/openapi.json` on Python 3.13.15 - plus a CI job
that runs all six gates as named steps against a health-checked `postgres:18-alpine`,
and a `test` stage that was caught red before it was allowed to be green.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-09-18T01:19:59Z
- **Completed:** 2026-09-18T01:37:05Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- `Dockerfile` has three real `FROM` lines producing `builder`, `runtime` and `test`,
  both bases the literal tag `python:3.13-slim-trixie`. `requirements.txt` is copied and
  installed before any source, so editing a module reuses the dependency layer; the
  package itself goes in with `pip install --no-deps .`, which is the only reason the
  `[project]` block in `pyproject.toml` is load-bearing rather than decorative.
- The `runtime` stage receives `COPY --from=builder /opt/venv /opt/venv` and nothing
  else. Observed: `whoami` -> `app`, `python --version` -> `Python 3.13.15`,
  `ls -a /app` -> `.` and `..` only, `site-packages` holds `taskmanager` +
  `taskmanager-0.1.0.dist-info`, size 368 MB, `docker history | grep -ci secret` -> 0.
  No `ENV` or `ARG` names a credential (T-01-25); nothing is baked in.
- **The image serves.** Started with `JWT_SECRET` and `DATABASE_URL` injected at run
  time, the exec-form `CMD` produced `Uvicorn running on http://0.0.0.0:8000` and
  `/openapi.json` answered `200`. The factory entrypoint 01-02 chose
  (`uvicorn --factory taskmanager.main:create_app`) works unchanged in the container.
- **The `test` stage runs the whole gated suite with no host interpreter involved:**
  `docker run --rm taskmanager-test` -> `8 passed`, `Required test coverage of 75%
  reached. Total coverage: 100.00%`, exit 0, on `platform linux -- Python 3.13.15`.
  `make docker-test` - the target 01-04 could only expand with `-n` - exits 0 end to end.
- **The container gate was observed failing first.** The research Dockerfile's `test`
  stage, copied verbatim, ends in `FileNotFoundError: '/app/.env.example'` and
  `1 failed, 7 passed` - while still printing `Total coverage: 100.00%` and `Required
  test coverage of 75% reached` two lines above the summary, which is exactly the shape
  that gets skimmed as green. Red and green are committed verbatim in
  `evidence/docker-test-stage.txt`.
- `.github/workflows/ci.yml` declares one `quality-gates` job on `ubuntu-latest`,
  triggered on `push` and `pull_request` with no branch filter, with
  `permissions: contents: read` and a `postgres:18-alpine` service whose health command
  is `pg_isready -h 127.0.0.1 -U taskmanager -d taskmanager_test` (the `-h` is the fix
  for the image's init-time Unix-socket-only server) plus interval/timeout/retries/
  start-period. Nine steps: checkout, setup-python 3.13 with `cache: pip` over both
  requirement files, install, then `black --check`, `isort --check-only`, `flake8`,
  `mypy src tests`, `lint-imports --no-logo` and `pytest`, each its own named step.
- **Neither file drives the local hook framework** (T-01-46). Both are grep-clean, and
  so is the cross-file assertion over the two of them together. `secrets.` appears
  nowhere in the workflow; the two job-level values are obviously fake and CI-only.

## Task Commits

1. **Task 1: Multistage Dockerfile with a non-root runtime and a test stage** — `f40b9c1` (build)
2. **Task 2: GitHub Actions workflow running every gate against Postgres** — `4a33cb3` (ci)

## Files Created/Modified

- `Dockerfile` — three stages with a header comment stating what each one is for and
  why the base tag is pinned exactly, plus an inline note on why `.env.example` is in
  the test stage and why nothing is baked into the runtime
- `.github/workflows/ci.yml` — the job, with a header comment explaining why every gate
  is a direct invocation rather than one hook-framework call, and step names aligned to
  the hook ids so `ci.yml` and the hook config can be read side by side
- `.planning/phases/01-foundation-quality-gates/evidence/docker-test-stage.txt` —
  scenario A (research recipe, `1 failed`, exit non-zero), the one-token fix, scenario B
  (as shipped, `8 passed`, exit 0), and the runtime observations including the
  uvicorn/`openapi.json` smoke

## Decisions Made

- **The research's `test` stage was not taken on faith.** RESEARCH states the file was
  built and run, and it was — but against the repository as it stood before 01-02 added
  the `.env.example` parity test. Running it here produced a real red. The lesson is the
  one this phase keeps re-learning: a verified artifact is verified against a snapshot,
  and the snapshot moves. Cost of finding out: one build.
- **The measured size is the one that got written down.** 368 MB here versus 285 MB in
  RESEARCH — same Dockerfile, different platform (linux/arm64, plus a BuildKit
  attestation manifest counted by `docker image ls`). The evidence file says so
  explicitly instead of quietly reusing the research figure.
- **`--no-logo` in CI only.** 01-03 suggested it, 01-04 deliberately left it out of the
  Makefile and handed the decision here. A job log is read once, under pressure, by
  someone looking for the red line; nine lines of ASCII art per run is a real cost there
  and no cost at all in a local `make arch`.
- **An explicit read-only `permissions` block.** Omitting it satisfies the criterion
  today because the repository default is read-only, but that default is a repository
  setting a future maintainer can flip. Declaring `contents: read` makes the job's scope
  a property of the file rather than of an account setting (T-01-28).
- **The runtime `CMD` was smoke-tested.** Every acceptance criterion could be satisfied
  by an image that builds and starts `sh`. Starting the server and fetching a route is
  two extra commands and turns "the image exists" into "the image works".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The `test` stage did not copy `.env.example`, so one test could not pass**

- **Found during:** Task 1
- **Issue:** The plan (following RESEARCH) specifies `COPY pytest.ini .flake8
  .importlinter ./`. `tests/unit/test_settings.py::test_env_example_documents_every_field`
  resolves `.env.example` from the repository root via `Path(__file__).parents[2]`, which
  is `/app` inside the container. The first `docker run --rm taskmanager-test` exited
  non-zero with `FileNotFoundError: [Errno 2] No such file or directory:
  '/app/.env.example'` — `1 failed, 7 passed`. `make docker-test` would have failed for
  an evaluator on the first attempt.
- **Fix:** Added `.env.example` to the `test` stage's configuration COPY. It is a tracked
  placeholder file containing no credential; `.dockerignore` excludes the real `.env`
  (an exact-name pattern, so `.env.example` is unaffected), and the `runtime` stage
  copies neither. Captured the red run, the fix and the green run in
  `evidence/docker-test-stage.txt` rather than silently correcting the line.
- **Files modified:** `Dockerfile`,
  `.planning/phases/01-foundation-quality-gates/evidence/docker-test-stage.txt` (created)
- **Commit:** `f40b9c1`

### Additions Beyond the Plan

**2. [Rule 2 - Missing critical functionality] The deviation from RESEARCH needed a committed observation**

- **Found during:** Task 1
- **Reason:** This phase's stated thesis is that a gate never seen red is
  indistinguishable from a no-op, and 01-02 through 01-04 each committed a red/green
  capture. Fixing the `test` stage without recording the failure would have left the
  fourth gate as the only undocumented one, and would have hidden the most instructive
  detail: the failing run still printed `Total coverage: 100.00%` and `Required test
  coverage of 75% reached`.
- **Impact:** One new evidence file, no shipped file altered beyond the fix itself.
  Plan 01-07 gains a fourth real incident for the honest log.

**3. `--no-logo` and an explicit `permissions` block**

- **Found during:** Task 2
- **Reason:** Both were handed over as open choices (01-04's next-phase notes and the
  plan's own "if a `permissions` block is added at all it must be `contents: read`").
- **Impact:** None on any acceptance criterion; the YAML assertion passes unchanged, and
  `lint-imports --no-logo` was confirmed present in import-linter 2.15's `--help` and run
  locally to `Contracts: 3 kept, 0 broken.`

## Issues Encountered

None blocking. Three observations worth carrying:

- In-container coverage reports **19** statements where the host reports 18. The whole
  difference is `settings.py`: 14 in the container, 13 on the host. Same file, same eight
  modules listed, 100% both ways — the only variable is the interpreter (3.13.15 in the
  container, 3.14.3 in the host venv), which emits a slightly different line table for
  that module. Not investigated further because nothing depends on the absolute number;
  recorded so a future reader does not read the two figures as a regression. If it ever
  matters, the container's 3.13 count is the authoritative one.
- `docker image ls` on this host reports the size of a multi-manifest entry that includes
  a BuildKit attestation manifest. The number is not directly comparable across machines.
- The workflow has still **never executed on a real runner** (RESEARCH assumption A2, no
  repository exists yet). Every component is verified locally — YAML parse, action tags,
  the `postgres:18-alpine` tag, `lint-imports --no-logo`, and all six gate commands run
  on this machine — but the assembled job has not. Plan 01-08's checkpoint is the first
  real run; one fix-up commit is budgeted there.

## Verification Results

| Check | Result |
|-------|--------|
| `grep -c '^FROM ' Dockerfile` | 3 (`builder`, `runtime`, `test`) |
| Both bases are literally `python:3.13-slim-trixie` | pass (2 occurrences) |
| `grep -ciE ':latest\|alpine' Dockerfile` | 0 |
| `grep -ciE '^(ENV\|ARG).*(SECRET\|PASSWORD\|TOKEN)' Dockerfile` | 0 |
| `grep -ci` the local hook framework in `Dockerfile` | 0 |
| `requirements.txt` copied and installed before any `COPY src` | pass |
| `runtime` uses `COPY --from=builder /opt/venv /opt/venv`, `useradd --system`, `USER app` | pass |
| `runtime` copies no `src`, no `tests`, no config | pass (`ls -a /app` -> `.` `..`) |
| `docker build --target runtime -t taskmanager .` | exit 0 |
| `docker run --rm taskmanager whoami` | `app` |
| `docker run --rm taskmanager python --version` | `Python 3.13.15` |
| `docker run --rm taskmanager ls -a /app` lists no `.env` | pass |
| `docker history taskmanager \| grep -ci secret` | 0 |
| `docker image ls taskmanager --format '{{.Size}}'` | `368MB` (< 500 MB) |
| Runtime `CMD` smoke: uvicorn up, `GET /openapi.json` | `200` |
| `docker build --target test -t taskmanager-test . && docker run --rm taskmanager-test` | exit 0, `8 passed`, `Total coverage: 100.00%`, gate reached |
| Same, before the `.env.example` fix | exit non-zero, `1 failed, 7 passed` (captured) |
| `make docker-test` | exit 0 |
| Task 1 full verification chain (single `&&` chain from the plan) | exit 0 |
| `ci.yml` YAML assertion script | `ci.yml OK` |
| `jobs.quality-gates.services.postgres.image` | `postgres:18-alpine` |
| Service `options` contain `pg_isready` and `-h 127.0.0.1` | pass |
| Job `env` defines `DATABASE_URL` and `JWT_SECRET`, both fake | pass |
| `grep -ciE 'secrets\.' .github/workflows/ci.yml` | 0 |
| Gate commands present in step `run`s | `black --check`, `isort --check-only`, `flake8`, `mypy`, `lint-imports`, `pytest` |
| `lint-imports` is its own named step; `importlinter.cli` absent | pass |
| `grep -ci` the local hook framework in `ci.yml` | 0 |
| `actions/checkout@v7` and `actions/setup-python@v7`, `cache: pip`, both requirement files in `cache-dependency-path` | pass |
| `python-version` | `'3.13'` |
| `permissions` | `contents: read` (no write scope) |
| Triggers | `push` and `pull_request`, no branch filter |
| `! grep -qiE 'secrets\.\|:latest' ci.yml Dockerfile` | exit 0 |
| `! grep -qi` the local hook framework over both files | exit 0 |
| `make lint typecheck arch test` after both commits | exit 0 |
| Twelve pre-commit hooks on both commits | Passed / Skipped, no Failed |

## Self-Check: PASSED

All 3 created files verified present on disk (`Dockerfile`, `.github/workflows/ci.yml`,
`evidence/docker-test-stage.txt`); commits `f40b9c1` and `4a33cb3` verified in `git log`.

## Known Stubs

None. Both artifacts are final for Phase 1. Two forward edges, neither a stub:

- The `postgres` service in `ci.yml` is deliberately unused by Phase 1 tests. It is not a
  placeholder — it is a real, health-checked service that Phase 3's integration tests
  consume by adding a pytest marker, not new CI infrastructure.
- Phase 3 replaces `make docker-test`'s body with a compose `run` against a `test`
  service using `target: test`. The stage, the target name and the documented command all
  stay as they are.

## Threat Flags

None. The plan's register (T-01-23 through T-01-31, T-01-46) is fully addressed and each
mitigation was asserted by execution rather than by reading the file:

| Threat | Assertion |
|--------|-----------|
| T-01-23 (root container) | `docker run --rm taskmanager whoami` -> `app` |
| T-01-24 (`.env`/`.git`/`.planning` in a layer) | `ls -a /app` -> empty; nothing at `/` either; `docker history` clean |
| T-01-25 (credential via `ENV`/`ARG`) | grep-asserted 0; both no-default settings injected at run time in the smoke test |
| T-01-26 (unpinned base) | `python:3.13-slim-trixie` x2, `postgres:18-alpine`, `:latest` grep-asserted absent |
| T-01-27 (compromised action) | `@v7` major tags only; SHA pinning remains a Phase 7 option, noted below |
| T-01-28 (job token scope) | explicit `permissions: contents: read` |
| T-01-29 (real credential in `ci.yml`) | `secrets.` grep-asserted 0; values obviously fake |
| T-01-30 (a gate quietly omitted) | the YAML assertion requires all six commands |
| T-01-31 (Postgres not actually ready) | declared `--health-cmd` with `-h 127.0.0.1` and retries |
| T-01-46 (venv-less environment driving the local hooks) | both files grep-clean, individually and together |

## User Setup Required

None. Docker Engine 29.2.0 is present on this machine and both images were built and run
here. An evaluator needs only Docker: `make docker-test` builds the `test` stage and runs
the suite with no Python on the host.

## Next Phase Readiness

Ready for plans 01-06, 01-07 and 01-08. What they must know:

- **Plan 01-06 (`DECISION_LOG.md`) owes three ADRs from this plan**, on top of the two
  still owed by 01-03 and the three by 01-04:
  1. **A dedicated `test` Dockerfile stage rather than a compose profile** — compose does
     not exist until Phase 3, a stage works today, and Phase 3 adds a `test` service with
     `target: test` without renaming `make docker-test`. Consequence: the image carries
     dev tooling and the test suite in a stage an evaluator can build in one command.
  2. **Every CI gate is a direct tool invocation rather than one hook-framework call** —
     the repo-local hooks are `.venv/bin`-qualified (01-04's ADR) and a runner has no
     `.venv`. Consequence: the gate set is pinned in two places (the hook config and
     `ci.yml`) and must be changed in both; the step names are aligned to the hook ids to
     make the drift visible in review. Citation:
     `evidence/pre-commit-venv-entry.txt` and `evidence/docker-test-stage.txt`.
  3. **Actions pinned to major tags (`@v7`), not commit SHAs** — accepted because the job
     references no credential and holds no write scope (`permissions: contents: read`).
     Consequence: a compromised upstream tag would execute in CI; SHA pinning is the
     Phase 7 delivery-hardening option and should be named as such rather than left
     unmentioned.
- **Plan 01-07 (`AI_WORKFLOW.md`) now has four evidence files** in
  `.planning/phases/01-foundation-quality-gates/evidence/`: `coverage-gate-red.txt`,
  `import-linter-red-green.txt`, `pre-commit-venv-entry.txt` and the new
  `docker-test-stage.txt`. The fourth carries a fifth real incident: this project's own
  research published a Dockerfile it had genuinely built and run, and it was red here
  anyway, because the repository grew a test after the research was written — and the red
  run still printed `Total coverage: 100.00%` and `Required test coverage of 75% reached`
  immediately above `1 failed`. Found by running it, not by reading it. Also worth logging
  honestly: the 285 MB figure in RESEARCH was not reproducible on this host (368 MB), and
  the observed number was recorded instead of the cited one.
- **Plan 01-08 (the combined run and the repository checkpoint):** `make docker-test` and
  the whole Task 1 verification chain currently exit 0, so the Docker half of the phase is
  already demonstrable. `ci.yml` has never run on a real runner — the first push is its
  first execution and one fix-up commit is budgeted. The most likely fix-up areas, in
  order: `pip install -e .` on a runner with no build isolation cache, `filterwarnings =
  error` catching a warning that only appears on 3.13 + Ubuntu, and the `cache: pip` key
  on a first run with no cache to restore.
- **Phase 3:** add a `test` service to `docker-compose.yml` with `target: test` and
  `depends_on: db: {condition: service_healthy}`, then swap `make docker-test`'s body —
  do not rename the target. The `postgres` service in `ci.yml` already carries the
  credentials and the health check Phase 3's integration tests need; they should reuse
  `DATABASE_URL` from the job `env` rather than adding a second one.
- **Everything still green:** 8 tests and 100% coverage both on the host and inside the
  container on Python 3.13.15, 3 contracts kept, mypy clean, twelve hooks passing on both
  of this plan's commits, runtime image 368 MB running as `app` and serving `200`.

---
*Phase: 01-foundation-quality-gates*
*Completed: 2026-09-18*
