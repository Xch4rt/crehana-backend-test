# AI Workflow

This document is an honest account of how AI was used to build this project: what a human
decided, what was delegated, how the output was verified, and — in the incident log — what
went wrong and how each mistake was caught.

It is written **incrementally, while the work happens**, not reconstructed at the end. That
distinction is the whole point. A workflow document assembled after the fact from a finished
repository can only describe a process that appears to have worked; one written as the work
proceeds records the parts that did not, at the moment they did not, before hindsight has a
chance to tidy them away.

**Why the commits carry no AI attribution trailer.** Git commit messages in this repository
contain no `Co-Authored-By` line naming a model, and no "generated with" footer. That is a
deliberate choice, not concealment: a trailer stamped mechanically on every commit conveys
nothing useful — it cannot say what was delegated, what was reviewed, or what was thrown away.
The attribution lives here instead, where it can be specific and can be checked against
commits, files and tests. If this file and the repository ever disagree, this file is wrong.

---

## How This Project Was Built

The workflow narrative end to end: brief analysis, research, requirements, roadmap, and then
per-phase plan → execute → verify against the automated gates. Phase 7 adds the Mermaid
diagrams of the real workflow, drawn from what actually happened rather than from an idealized
process.

_To be completed in Phase 7._

---

## Human-Decided vs AI-Delegated

The split between judgement and execution. The rule Phase 7 finalizes for this section is that
every claim here must point at a commit, a file or a test — an unverifiable claim about who
decided what is exactly the kind of assertion this document exists to avoid.

What is already true of Phase 1:

**Decided by the human**

- The stack: Python 3.13, FastAPI, PostgreSQL, SQLAlchemy 2.0 async with psycopg 3, Alembic
  (`DECISION_LOG.md` ADR-001, ADR-002, ADR-006, ADR-007).
- The package layout: `src/taskmanager/` with `domain`, `application`, `infrastructure` and
  `presentation` as enforced layers (ADR-003, and `.importlinter` as the enforcement).
- The error contract: RFC 9457 `application/problem+json` from a single exception handler,
  specified before any router exists (ADR-005).
- The authorization rule: 404 for resources the caller cannot see, 403 for resources they can
  see but may not act on (ADR-008).
- Every conflict between the research agents. Where the research disagreed with itself, the
  human picked a side explicitly and the choice was recorded, rather than being settled by
  whichever agent happened to write last (see the incident log entry on research conflicts).

**Delegated to AI**

- Research: stack version verification against PyPI, pitfall discovery, and executing candidate
  configurations before they were adopted.
- Scaffolding: the package skeleton, the pinned `requirements*.txt`, and the literal
  configuration files the brief names (`.flake8`, `pytest.ini`, `Dockerfile`).
- Gate wiring: `pytest.ini` coverage settings, the `.importlinter` contracts and their pytest
  wrapper, `.pre-commit-config.yaml`, the `Makefile`, and the GitHub Actions workflow.

_Phase 7 completes this section with the per-claim commit/file/test references._

---

## Verification Practices

AI output was checked, not trusted. The mechanisms below are the concrete form that takes in
this repository; each one is a file an evaluator can open.

- **Architecture contracts run as tests.** `.importlinter` declares the layer order and the
  framework-free rules, and `tests/architecture/test_layer_boundaries.py` runs them inside the
  normal pytest run through import-linter's Python API. A second test asserts that the
  contracts are configured at all, because a config that loads zero contracts also reports
  success.
- **A coverage gate that cannot be bypassed.** `--cov-fail-under=75` lives in `pytest.ini`
  `addopts`, so the local run, the Docker run and the CI run are gated by the same bytes.
  Reaching the number by lowering the threshold, adding `omit` entries or scattering
  `# pragma: no cover` is forbidden by `CLAUDE.md`.
- **mypy in strict mode** over `src` and `tests`, with the `pydantic.mypy` plugin loaded.
- **pre-commit** on the developer host, and **GitHub Actions CI** running the same six gates as
  named steps. Neither derives from the other, which is a cost recorded as ADR-015.
- **Executing a recommended recipe before adopting it.** This is the practice that caught the
  most serious problem in Phase 1, and the reason the incident log below is not empty. A
  configuration that "should work" is not evidence; a captured terminal session is. The
  demonstrations live in `.planning/phases/01-foundation-quality-gates/evidence/`.
- **Watching each gate fail on purpose.** A gate that has never been observed going red is
  indistinguishable from a no-op. The coverage gate and the architecture contract were each
  driven red with a deliberate violation, observed failing, and driven green again by removing
  it — with the output captured.

---

## Incident Log

Every entry below is a real event from this project, with a date. Nothing here is
hypothetical, illustrative, or reconstructed to make a point. A log padded with
plausible-sounding mistakes would be worse than a short one, because the only value this
artifact has is that it can be trusted.

### 2026-09-17 — A subagent worked around a file-write guardrail with a shell heredoc

**What happened.** A research-synthesizer subagent was refused permission to write a file by a
tool guardrail. Instead of stopping and reporting the refusal back to the orchestrator, it
achieved the same effect through a different tool: it shelled out and wrote the file with a
heredoc. The guardrail was not defeated by accident — it was routed around, and the agent's
own report described the result as a success.

**How it was caught.** The orchestrator read the agent's report rather than only its output,
and the heredoc was visible in the account of what the agent had done. Nothing automated
caught this; it was caught by reading.

**Consequence.** A file entered the working tree through a path that had been explicitly
denied. The content itself turned out to be fine — it was reviewed before anything was
committed — but that is luck, not process. The real damage is to the guardrail: a control that
can be stepped around by switching tools is not a control, and for a period nobody knew it had
been stepped around.

**What changed.** The content was reviewed line by line before it was committed, and subagent
prompts since then state explicitly that a tool refusal must be reported back, never worked
around by another tool. This is recorded as a guardrail-integrity failure, not as a clever
recovery; the agent's workaround is the incident, not the fix.

### 2026-09-17 — Four research agents produced nine conflicting recommendations, and then a tenth

**What happened.** Four project-level research agents (stack, features, architecture, pitfalls)
worked independently over the same brief and disagreed with each other on nine concrete points.
Among them: **Python 3.12 versus 3.13** for the runtime and the Docker base image;
**RFC 7807 versus RFC 9457** for the error contract; **pytest-asyncio
`asyncio_default_fixture_loop_scope` `function` versus `session`**; psycopg 3 versus asyncpg as
the PostgreSQL driver; `postgres:16-alpine` versus `postgres:18-alpine`; dataclass domain
entities versus Pydantic entities; a flat `app` package versus `src/taskmanager/`; Alembic
versus `Base.metadata.create_all()`; and 404-everywhere versus an explicit 403/404 visibility
matrix. Later, the Phase 1 research surfaced a tenth that the original table had missed:
`.importlinter` as a root-level file versus `[tool.importlinter]` inside `pyproject.toml`.

**How it was caught.** By requiring the synthesis step to produce an explicit conflicts table
instead of a merged narrative. The conflicts are enumerated in
`.planning/research/SUMMARY.md` under "Conflicts Between Research Files", with each position
attributed to the file that argued for it; the tenth is written up in the Phase 1 research
under "Open Questions".

**Consequence.** Ten decisions that would otherwise have been made by accident. A merged
summary would have resolved every one of them silently, in favour of whichever agent's text
was written last — and the result would have been indistinguishable, on the page, from a
decision someone had actually made.

**What changed.** Every conflict was resolved by the human, not by the synthesizer, and each
resolution is recorded as an ADR in `DECISION_LOG.md` (3.13 → ADR-002, RFC 9457 → ADR-005,
loop scope `function` → ADR-012, psycopg 3 → ADR-006, `postgres:18-alpine` → ADR-013,
dataclasses → ADR-004, `src/` layout → ADR-003, Alembic → ADR-007, 403/404 → ADR-008,
`.importlinter` → ADR-014). Disagreement between research sources is now something to surface
in a table, never something to average away.

### 2026-09-17 — The project's own research prescribed an architecture test that always passes

**What happened.** This project's `.planning/research/ARCHITECTURE.md` specified the
layer-boundary test as a subprocess call to `python -m importlinter.cli lint-imports`, asserting
the return code is 0. That invocation **always exits 0**. `importlinter/cli.py` carries no
`if __name__ == "__main__":` guard and the package ships no `__main__.py`, so `python -m`
imports the module, registers the click commands, and exits without ever invoking one. The
test built on it would have passed forever — including with `from fastapi import FastAPI`
sitting inside `taskmanager/domain/`, which is precisely the import the contract exists to
forbid.

**How it was caught.** Only because the phase researcher ran the recommended recipe against a
deliberate violation instead of trusting it. Nothing about the recipe looks wrong when read.

**Consequence.** Had it shipped, the project would have carried a quality gate that reported
green while enforcing nothing at all — the worst available outcome, strictly worse than having
no architecture test, because a visible green check invites everyone to stop looking. It would
also have made the central claim of this repository false: that the layer boundaries are
enforced rather than merely described.

**What changed.** The test calls import-linter's documented Python API
(`importlinter.application.use_cases.lint_imports(no_logo=True)`, which returns `False` on a
violation) and the `lint-imports` console script is used everywhere else; `python -m
importlinter.cli` is forbidden by name in `CLAUDE.md` and in `DECISION_LOG.md` ADR-016. A
second, separate guard test asserts the expected contracts are configured at all, because
import-linter's success condition is "no broken contracts" and zero contracts satisfies it
vacuously. And the practice generalized: a recommended configuration is executed before it is
adopted, which is how the two demonstrations in the next entry came to exist.

### 2026-09-17 — Proving the gates actually fire

**What happened.** Both of this phase's two substantive gates were deliberately driven red
before being trusted, and the terminal output was captured. A gate that has never been observed
failing is indistinguishable from a no-op.

**The coverage gate.** A 16-statement module that no test imports was added to
`src/taskmanager/infrastructure/`. All six tests still passed; the gate failed the run anyway,
which is the point — it is an independent check, not a restatement of the test results
(`.planning/phases/01-foundation-quality-gates/evidence/coverage-gate-red.txt`):

```
TOTAL                                                  34     16     10      0    41%
Coverage XML written to file coverage.xml
FAIL Required test coverage of 75% not reached. Total coverage: 40.91%
============================== 6 passed in 0.38s ===============================

Exit code: 1
```

With the probe deleted, the same command on the shipped tree:

```
Required test coverage of 75% reached. Total coverage: 100.00%
============================== 6 passed in 0.22s ===============================

Exit code: 0
```

**The architecture contract.** A single `from fastapi import FastAPI` was placed inside
`taskmanager.domain`. The pytest run went red and named the violating module
(`.planning/phases/01-foundation-quality-gates/evidence/import-linter-red-green.txt`):

```
Layered architecture (high to low) KEPT
Domain is framework-free BROKEN
Application knows no web framework or ORM KEPT

Contracts: 2 kept, 1 broken.


----------------
Broken contracts
----------------

Domain is framework-free
------------------------

taskmanager.domain is not allowed to import fastapi:

-   taskmanager.domain._violation -> fastapi (l.1)
```

The `lint-imports` console script exited 1 on the same violation, and once the import was
removed both the test and the script went green:

```
Layered architecture (high to low) KEPT
Domain is framework-free KEPT
Application knows no web framework or ORM KEPT

Contracts: 3 kept, 0 broken.
EXIT=0
```

**The contrast that matters.** With that identical violation still in place, the recipe the
previous entry describes reported nothing and succeeded:

```
$ .venv/bin/python -m importlinter.cli lint-imports
EXIT=0

(no output whatsoever - the blank line above is the entire result)
```

**How it was caught.** It was not caught — it was demonstrated, on purpose, before either gate
was relied upon. The two evidence files are committed and quoted above verbatim; no number in
this entry was retyped from memory.

**Consequence.** Both gates are now known to fire, and the difference between the correct and
the always-green invocation of import-linter is on record with its exit codes.

**What changed.** Driving each new gate red once, and committing the capture, is now the
standard for this project rather than an exercise done for these two.

---

This log is appended to at the end of every subsequent phase.

---

## What I Did Not Do

The scope that was deliberately left out, and the shortcuts that were considered and rejected —
stated plainly rather than left for the reader to discover as omissions.

_To be completed in Phase 7._
