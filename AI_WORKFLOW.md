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
hypothetical, illustrative, or reconstructed to make a point. The log is appended to at the
end of every phase.

_First entries are added in this phase (01-07)._

---

## What I Did Not Do

The scope that was deliberately left out, and the shortcuts that were considered and rejected —
stated plainly rather than left for the reader to discover as omissions.

_To be completed in Phase 7._
