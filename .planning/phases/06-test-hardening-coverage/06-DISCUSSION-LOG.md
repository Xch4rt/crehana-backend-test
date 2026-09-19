# Phase 6: Test Hardening & Coverage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-19
**Phase:** 6-Test Hardening & Coverage
**Areas discussed:** Totality proof, Assertion quality audit, Deliberate-break depth, Coverage honesty & suite shape

Baseline measured before the discussion: 1019 passed, 100% line and branch coverage over
`src/taskmanager`, about 10 seconds. Questions were grouped per area in a single turn, in line
with the user's recorded preference for light ceremony.

---

## Totality proof

### How should "every use case and every endpoint has a test" be proven?

| Option | Description | Selected |
|--------|-------------|----------|
| Permanent pytest gate | Architecture-style test enumerates use-case modules and OpenAPI operations; a new route without a test fails a build | ✓ |
| One-time audit matrix | Written table produced once, reused in the README; goes stale silently | |
| Both | Gate is the proof; matrix generated from the same enumeration for Phase 7 | |

**User's choice:** Permanent pytest gate

### How does the gate decide an endpoint "is tested"?

| Option | Description | Selected |
|--------|-------------|----------|
| Observed at runtime | Harness records every (method, route template) requested; final check compares with `app.openapi()` | ✓ |
| Explicit registry | Hand-maintained dict operation → test name, like `REQUIRED_SCANNED_MODULES` | |
| You decide | Research picks | |

**User's choice:** Observed at runtime

### Invalid transitions and auth failure modes: how is "every" established?

| Option | Description | Selected |
|--------|-------------|----------|
| Derived from the source of truth | Parametrize over the complement of `ALLOWED_TRANSITIONS` and a closed list of auth failure modes | ✓ |
| Audit what exists, fill gaps by hand | Checklist, individual additions, no structural guarantee | |

**User's choice:** Derived from the source of truth

---

## Assertion quality audit

### How is "every test asserts on bodies, every mutating test re-reads" enforced?

| Option | Description | Selected |
|--------|-------------|----------|
| Sweep now + AST gate | Fix today's offenders, then an AST test fails status-only tests and mutations without a follow-up GET | ✓ |
| Sweep now, no gate | One-time audit recorded in AI_WORKFLOW.md; nothing stops regressions | |
| Gate for status-only, sweep for re-reads | Gate only the reliably detectable half | |

**User's choice:** Sweep now + AST gate

### What counts as an acceptable re-read after a DELETE or a rejected mutation?

| Option | Description | Selected |
|--------|-------------|----------|
| GET proves the end state | After DELETE a 404 problem body; after a rejection a GET showing the resource unchanged; after success a GET equal to the response | ✓ |
| Success paths only | Rejected mutations covered by the problem+json assertion alone | |

**User's choice:** GET proves the end state

---

## Deliberate-break depth

### How deep does the deliberate-break check go?

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-picked set of ~5 breaks | Mandated completion inversion plus transition table, 404-vs-403, token expiry, `for_update` lock | ✓ |
| Only the mandated break | Literal satisfaction of SC-4 | |
| Hand-picked set + one mutmut run | Adds a scored mutation run; new dev dependency and survivor triage | |

**User's choice:** Hand-picked set of ~5 breaks

### Is the break check a one-off episode or something repeatable?

| Option | Description | Selected |
|--------|-------------|----------|
| Scripted, not gated | `make break-check` applies, asserts red, restores; not in `make test` or CI | ✓ |
| One-off, recorded in prose | AI_WORKFLOW.md entry is the only artifact | |
| Scripted and run in CI | Same script plus a CI job | |

**User's choice:** Scripted, not gated

---

## Coverage honesty & suite shape

### What proves the coverage number is honest?

| Option | Description | Selected |
|--------|-------------|----------|
| Three-way agreement + config pin | Host, Docker and CI totals agree; a test fails on threshold < 75, `omit`, wrong `source`, or a pragma under `src/` | ✓ |
| Three-way agreement only | Numbers recorded; rules stay prose | |
| You decide | Planner picks the lightest proof | |

**User's choice:** Three-way agreement + config pin

### Should this phase reshape the suite for a 5-minute evaluator?

| Option | Description | Selected |
|--------|-------------|----------|
| Light tidy only | Move stray `tests/api/`, complete unit/integration markers, add `make test-unit`; no deletions | ✓ |
| Leave it alone | Any move is risk without requirement value | |
| Tidy + trim redundancy | Also cut overlapping tests | |

**User's choice:** Light tidy only

### If the audit finds a test that passes for the wrong reason (or a real product bug)?

| Option | Description | Selected |
|--------|-------------|----------|
| Fix in-phase + incident entry | Minimal fix inside Phase 6, logged in AI_WORKFLOW.md | ✓ |
| Tests in-phase, product bugs to a gap plan | Keep Phase 6's diff tests-only | |

**User's choice:** Fix in-phase + incident entry

---

## Claude's Discretion

- How the use-case gate maps a module to its unit test
- The runtime recording mechanism for endpoint totality and its behaviour under partial runs
- The new home of `tests/api/test_error_contract.py`
- Substituting breaks 2–5 within the same risk area
- Whether the new gates earn ADR entries and CLAUDE.md rule bullets

## Deferred Ideas

- Mutation testing with mutmut — candidate for Phase 7's "what I'd do next"
- Running the break check in CI
- Trimming redundant tests
- A written use-case/endpoint → test matrix for the README (Phase 7)
