# Phase 6: Test Hardening & Coverage - Context

**Gathered:** 2026-09-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove that the existing test suite demonstrates the API's behaviour rather than merely
exercising it, and that the coverage number is honest (TEST-01..TEST-05).

The starting point matters: at the close of Phase 5 the suite is **1019 passed, 100% line and
branch coverage over `src/taskmanager`, about 10 seconds**, with roughly 25k lines of tests
against 8.7k lines of source. Phase 6 is therefore an **audit-and-hardening phase, not a
test-writing phase**. Its deliverables are: totality gates that make "every use case / every
endpoint / every invalid transition / every auth failure mode" a build failure rather than a
claim; an assertion-quality sweep plus a gate; a scripted deliberate-break check; a coverage
configuration pin with a three-way (host / Docker / CI) agreement; and a light tidy of the
suite layout.

Out of scope: any new API capability, any new endpoint, README / DECISION_LOG prose for
evaluators (Phase 7), trimming or deleting existing tests.

</domain>

<decisions>
## Implementation Decisions

### Totality proof (TEST-01, TEST-02, TEST-04)
- **D-01:** Totality is proven by **permanent pytest gates**, not by a one-time written audit
  matrix. A use case or a route added without its test must fail a build, consistent with the
  repository's "a gate, not a review" rule. The gates live under `tests/architecture/` (or
  beside the harness where they must observe the run) and, being pytest tests, add **no new
  pre-commit hook and no new CI step** (the ADR-015 argument, as already applied to the two
  Phase 4/5 AST gates).
- **D-02:** Use-case totality: a gate enumerates every use-case module under
  `src/taskmanager/application/use_cases/` (today: `auth/{authenticate,login,profile,register}`,
  `task_lists/{create,delete,get,list,update}`,
  `tasks/{assign,change_task_status,create,delete,get,list,list_assigned,update}`, `users/list`,
  plus `access.py`) and fails if one has no unit test that runs against the in-memory fakes. How
  "has a unit test" is decided (module-name convention vs import scan of `tests/unit/application`)
  is the researcher's call, but it must fail on an emptied or renamed package the way
  `REQUIRED_SCANNED_MODULES` does today — never pass silently.
- **D-03:** Endpoint totality is **observed at runtime**, not declared in a registry. The HTTP
  harness records every `(method, route template)` actually requested during the integration
  run, and a final check compares that set against `app.openapi()`. An operation in the OpenAPI
  document that no integration test requested is a failure. This proves the route was really
  hit through HTTP against real PostgreSQL, and leaves no naming convention to maintain. The
  suite runs single-process (no xdist), which is what makes a run-wide recorder sound;
  the researcher must settle how the check behaves when only a subset of tests is selected
  (`-k`, a single file) so that a focused run is not falsely red.
- **D-04:** Negative-path totality is **derived from the source of truth**, not from a
  hand-written checklist:
  - Invalid status transitions are parametrized over the **complement** of
    `ALLOWED_TRANSITIONS` in `src/taskmanager/domain/value_objects/task_status.py` (every
    status pair minus the allowed ones), at the domain level and through HTTP. Adding a fourth
    status must add its negative cases automatically.
  - Authentication failures are parametrized over a **closed list** of modes: missing header,
    non-bearer scheme, malformed token, wrong signature, expired token, unknown subject. Each
    asserts the RFC 9457 `application/problem+json` body, not only the 401.
  - The cross-user 404/403 matrix is already one parametrized test over the real HTTP harness
    (Phase 5 D-04, `tests/integration/api/test_permission_matrix.py`, ADR-083). Phase 6 audits
    it for completeness against the published permission table; it does not rebuild it.
  - The RFC 9457 error contract is audited the same way: every `DomainError` leaf and the
    validation / unexpected-error legs have a test asserting the full body shape.

### Assertion quality (TEST-05, roadmap SC-3)
- **D-05:** **Sweep now, then gate.** One pass fixes today's offenders; then an AST test under
  `tests/architecture/` fails (a) any HTTP test whose only assertion on a response is its status
  code, and (b) any test issuing POST / PATCH / PUT / DELETE with no follow-up read through the
  API. The scout found about 90 bare `assert response.status_code == N` lines under
  `tests/integration/api/`; many are followed by body assertions and are fine, so the real
  offender count is for the sweep to establish. The gate must report `file:line` per offender,
  like the existing AST gates.
- **D-06:** The re-read rule is **"a GET proves the end state"**, on every leg:
  - successful mutation → a GET whose body equals the mutation's response;
  - DELETE → a GET returning the 404 problem body;
  - **rejected** mutation (403 / 404 / 409 / 422) → a GET showing the resource unchanged.
- **D-07:** A heuristic gate that produces false positives is worse than none. If the re-read
  half (D-05 b) cannot be made reliable by AST alone, the researcher may propose a narrow,
  explicit escape hatch (for example a named marker with a required reason) — but never a blanket
  skip, and the status-only half (D-05 a) has no escape hatch.

### Deliberate-break check (TEST-05, roadmap SC-4)
- **D-08:** A **hand-picked set of about five breaks**, not only the mandated one and not a
  mutation-testing tool. The set is:
  1. invert the completion-percentage formula in
     `src/taskmanager/domain/value_objects/completion.py` (mandated by SC-4);
  2. allow a forbidden transition in `ALLOWED_TRANSITIONS`;
  3. flip a 404-vs-403 visibility decision in `application/use_cases/access.py`;
  4. disable token-expiry enforcement in `infrastructure/security/tokens.py`;
  5. drop `for_update=True` from one write path.
  Each break must turn the suite red; the researcher may swap an item for a better one in the
  same risk area, but the first is fixed. No new dependency: **mutmut is not added**.
- **D-09:** The check is **scripted, not gated**. A script under `scripts/` with a Makefile
  target (working name `make break-check`) applies each break, runs the relevant tests, asserts
  red, and restores the file — an evaluator can rerun it. It is **not** part of `make test`,
  pre-commit or CI, so the normal loop stays at about 10 seconds. The script must restore the
  working tree even when interrupted, and must refuse to run on a dirty tree.
- **D-10:** The episode is recorded in the `AI_WORKFLOW.md` incident log (dated entry, which
  tests went red for each break, and anything a break did **not** turn red). A break that
  survives is a finding handled under D-14.

### Coverage honesty and suite shape (TEST-03, roadmap SC-5)
- **D-11:** Honesty is proven by **three-way agreement plus a configuration pin**. The total is
  recorded from the host (`make test`), Docker (`make docker-test`) and CI, and they must
  agree. A small pytest test reads `pytest.ini` and `pyproject.toml` and fails if the threshold
  drops below 75, an `omit` entry appears, coverage `source` stops being `taskmanager`, or a
  `# pragma: no cover` appears anywhere under `src/`. This turns the existing CLAUDE.md
  coverage rule into a gate.
- **D-12:** Carried forward, not reopened: the threshold stays **75**; 100% is a norm, not a
  requirement (Phase 4 context); the threshold is never reached with pragmas or `omit`; tests
  are outside the denominator because `source = ["taskmanager"]`.
- **D-13:** **Light tidy only.** Move the stray `tests/api/test_error_contract.py` to its right
  home, make sure every test carries the `unit` or `integration` marker so that
  `pytest -m unit` runs with no database, and add a `make test-unit` target. **No deletions and
  no rewrites**: nothing in the brief rewards a smaller suite and a deletion can quietly reduce
  what is proven. Note that `pytest -m unit` alone will not reach 75% by design — the target
  must not trip the coverage gate (researcher to choose how: `--no-cov` or an explicit override).

### Findings policy
- **D-14:** When the audit finds a test that passes for the wrong reason, or a real product
  bug, it is **fixed inside Phase 6** and logged in the `AI_WORKFLOW.md` incident log, as
  earlier phases did. Product fixes stay minimal (a bug fix, not a redesign); anything larger is
  written to Deferred Ideas instead of being built.

### Plan sizing (user preference, binding on the planner)
- **D-15:** **Few, large plans with light ceremony — target 3 to 4 plans for the whole phase.**
  Acceptance criteria are behaviour-based and expressed as test commands, not grep counts over
  prose. No evidence / RED / falsification transcript files, with one exception: the
  deliberate-break episode (D-08..D-10) is itself the evidence SC-4 asks for and belongs in
  `AI_WORKFLOW.md`. The plan checker must not push toward more ceremony. After any `gsd-sdk`
  state handler runs, diff `STATE.md` and repair it by hand (the handlers are known to regress
  it).

### Claude's Discretion
- How the use-case gate maps a module to "its" unit test (D-02).
- The recording mechanism for D-03 (httpx event hook, ASGI middleware in the test app, or a
  wrapper around `api_client` / `authenticated_client`) and its behaviour under partial runs.
- The exact home of `test_error_contract.py` after the move (D-13).
- Substituting breaks 2–5 within the same risk area (D-08).
- Whether new rules earn ADR entries in `DECISION_LOG.md` (next free number is ADR-085) and a
  CLAUDE.md "Project Rules" bullet; the precedent is that every new gate gets both.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 6: Test Hardening & Coverage" — goal and the five success
  criteria
- `.planning/REQUIREMENTS.md` — TEST-01..TEST-05 (lines 88–92) and the traceability notes
  explaining why Phase 6 owns *totality* while FND-06 owns the coverage *configuration*
- `.planning/PROJECT.md` — core value (provable in five minutes) and constraints

### Prior decisions this phase builds on
- `.planning/phases/03-persistence-runnable-stack/03-CONTEXT.md` — D-01..D-05: rollback
  isolation, migration-built test schema, no auto-skip without a database, `taskmanager_test`
- `.planning/phases/04-task-lists-tasks/04-CONTEXT.md` — D-16/D-17: integration-test and
  statement-count conventions; the note that 100% coverage is a norm, not a requirement
- `.planning/phases/05-auth-assignment-notifications/05-CONTEXT.md` — D-04 (permission matrix as
  one parametrized HTTP test), D-20 (`authenticated_client` vs `api_client`)
- `.planning/phases/05-auth-assignment-notifications/05-VERIFICATION.md` and `05-REVIEW.md` —
  the most recent verified state of the suite and any open warnings

### Project rules and decision records
- `CLAUDE.md` §"Project Rules" — quality gates, coverage rules, "a new gate goes in two places"
  and its pytest exemption, error-handling gates
- `DECISION_LOG.md` — ADR-007 (no `create_all`, even in tests), ADR-012 (function-scoped
  asyncio fixture loop), ADR-015 (gates as pytest tests add no CI step), ADR-083 (permission
  model is one table bound to the published document)
- `AI_WORKFLOW.md` §"Verification Practices" and §"Incident Log" — the format the
  deliberate-break entry must follow; see the existing entries "Proving the gates actually
  fire" and "Both new gates were planted red, and the first planting proved the wrong thing"

### Configuration under audit
- `pytest.ini` — `--cov=taskmanager`, `--cov-fail-under=75`, markers, `filterwarnings = error`
- `pyproject.toml` §`[tool.coverage.*]` — `source`, `branch = true`, `exclude_also`, no `omit`
- `.github/workflows/ci.yml`, `Makefile`, `docker-compose.yml` — the three places the suite runs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/integration/conftest.py` — `api_client`, `authenticated_client`, `bearer_header`,
  `seed`, `acting_as`, `statements`, `_require_database`, `migrated_database`. The D-03 recorder
  attaches here.
- `tests/unit/presentation/test_security_scheme.py` — already walks `app.openapi()` operation by
  operation; the enumeration pattern for D-03 exists.
- `tests/architecture/test_routers_raise_no_http_exception.py` and
  `test_no_commit_in_repositories.py` — the house style for an AST gate: `file:line` per
  offender, a `REQUIRED_SCANNED_MODULES`-style guard against a silently empty scan, and a
  companion test that fails if an exemption outlives its reason. D-02, D-05 and D-11 follow it.
- `tests/unit/application/fakes.py` — in-memory repositories, `FakePasswordHasher`,
  `FakeTokenService`, `FakeEmailNotifier`, `FrozenClock`, with conformance assertions in
  `test_ports.py`.
- `tests/integration/api/test_permission_matrix.py` — the 404/403 matrix.
- `tests/integration/api/test_task_lists.py` — builders and `anonymised()` used by the API tests.
- `scripts/init-env.sh` — precedent for a script under `scripts/` with a Makefile target and a
  unit test that runs it in a temporary directory.

### Established Patterns
- Every gate is driven red before it is trusted, and that is recorded in `AI_WORKFLOW.md`.
- New pytest-based gates add no pre-commit or CI step; a gate that introduces a new *command*
  goes in both `.pre-commit-config.yaml` and `.github/workflows/ci.yml`. `make break-check`
  (D-09) is deliberately in neither.
- Requirement ticks are taken once, by the phase's closing plan, against a named passing test.
- `make test` requires a reachable PostgreSQL and never auto-skips (D-03 of Phase 3).

### Integration Points
- `src/taskmanager/domain/value_objects/task_status.py` — `ALLOWED_TRANSITIONS`, the source of
  truth for D-04.
- `src/taskmanager/domain/value_objects/completion.py` — `percentage`, the mandated break.
- `src/taskmanager/application/use_cases/` — the enumeration root for D-02.
- `Makefile` — new `test-unit` and `break-check` targets.
- `tests/api/` — the stray directory to fold in (D-13).

</code_context>

<specifics>
## Specific Ideas

- The measured baseline (1019 passed, 100%, ~10 s, 2026-09-19) should be restated in the phase
  verification so the three-way agreement has a reference number.
- The deliberate-break script is something an **evaluator can rerun**; that is the reason it is
  scripted rather than done once by hand.
- A break that does *not* turn the suite red is the most valuable possible outcome of this
  phase and must be reported as such, not smoothed over.

</specifics>

<deferred>
## Deferred Ideas

- **Mutation testing with mutmut** (a scored run over `domain` + `application`) — considered and
  declined for this phase: new dev dependency and an unbounded survivor triage. Worth a line in
  Phase 7's "what I'd do next".
- **Running the break check in CI** — declined: slower pipeline and one more thing that can
  flake before delivery.
- **Trimming redundant tests** for readability — declined: risk without requirement value.
- **A written use-case → test / endpoint → test matrix** for the README's requirement-to-evidence
  map — belongs to Phase 7 (DOC), which can generate it from the D-02 / D-03 enumerations.

</deferred>

---

*Phase: 6-Test Hardening & Coverage*
*Context gathered: 2026-09-19*
