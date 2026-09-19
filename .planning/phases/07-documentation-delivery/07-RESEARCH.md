# Phase 7: Documentation & Delivery - Research

**Researched:** 2026-09-19
**Domain:** Documentation inventory, OpenAPI completeness, clean-clone rehearsal, public delivery
**Confidence:** HIGH (this is an inventory phase; almost every claim below was executed or read
out of the repository in this session, not recalled)

## Summary

This is not a technology-research phase. Phase 7 adds no library, no service and no new
architectural idea. Six success criteria are open and five of them are answered by writing or
finishing a document; the sixth (DOCK-05) is answered by a script that proves the documents are
true. So the research below is an **inventory**: for each criterion, what exists in the tree
today, what is missing, and at which path.

The headline findings are that the gap is smaller than it looks in four places and larger than it
looks in one. `DECISION_LOG.md` already holds 96 ADRs and covers three of the brief's five named
ambiguities in dedicated entries — two are decided only in code docstrings and need an ADR each.
`AI_WORKFLOW.md` already holds 51 incident entries (the criterion asks for three) and a
human-vs-AI split for Phases 1-4 — it is missing Phases 5-6, every Mermaid diagram, and the body
of its own "What I Did Not Do" section. The commit history is already 332 atomic,
conventional-commit, phase-scoped commits with **zero** AI attribution trailers, and the GitHub
repository is **already public** — AIW-05 needs a push and a badge, not a visibility flip. The
one criterion that is worse than it looks is DOC-04: all 19 operations already carry tags,
summaries, descriptions and enumerated error codes, but **69 of the 70 non-2xx response legs
publish no schema at all**, so an evaluator reading `/docs` sees that a route can answer 409 and
cannot see the shape of the body they must parse.

`README.md` does not exist. Nothing in the repository reads it, links to it, or gates it, so it
is greenfield — which is an opportunity: the README can be written against a verified quickstart
(captured live in this session against the running container, §Code Examples) and kept honest by
one new pytest gate that reuses this project's existing "observed, not declared" idiom.

**Primary recommendation:** four plans, in this order — (1) OpenAPI error schemas + a totality
gate; (2) the two missing ambiguity ADRs plus the log's stale-reference corrections; (3) README
written against the verified quickstart, with a documentation-honesty gate and the three
`Dockerfile` `COPY` lines that gate needs; (4) `AI_WORKFLOW.md` finalization. Then a fifth,
blocking delivery plan: the rerunnable clean-clone rehearsal, the push, the observed-green badge.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Error-body schema in `/openapi.json` | Presentation (`presentation/api/`) | — | The published document is a presentation artifact; the `problem()` builder already lives there |
| OpenAPI completeness gate | Test tier (`tests/architecture/`) | — | Reads `app.openapi()`; no runtime dependency (ADR-057 precedent) |
| README / DECISION_LOG / AI_WORKFLOW | Repository root | — | The brief names these files literally at the root |
| Documentation-honesty gate | Test tier (`tests/architecture/`) | Dockerfile (`COPY` lines) | Rides inside `pytest`, so CLAUDE.md's two-places rule does not apply — but the test image must contain the files it reads |
| Clean-clone rehearsal | `scripts/` + `Makefile` | Docker (host daemon) | Needs the whole working tree and the Docker socket; cannot run inside the test image |
| Push, badge, email | Human / `gh` CLI | — | Irreversible and account-scoped; must be a checkpoint |

## Project Constraints (from CLAUDE.md)

Directives that bind this phase specifically:

| Directive | Consequence for Phase 7 |
|-----------|------------------------|
| `DECISION_LOG.md` is append-only; a reversal gets a **new** ADR superseding the old by id | The two stale claims (§Gap 2) are corrected by a new ADR, never by editing ADR-019 or line 3025 |
| Everything in English: code, comments, docs, commits, planning artifacts | The README and all diagrams are English; the brief's Spanish headings are quoted as citations only |
| Commit messages carry **no** AI co-author or attribution trailer of any kind | Verified clean across all 332 commits (§Delivery). Phase 7's own commits must stay clean — note the session attribution reminder is **overridden** by this rule |
| `make lint`, `make typecheck`, `make arch`, `make test` green before any commit | Any `src/` change in 07-01 must clear `mypy --strict` and flake8 |
| Coverage gated at 75%, never lowered, never reached with `# pragma: no cover` or `omit` | A new `ProblemResponse` Pydantic model adds statements; they must be covered by a real test |
| A new gate that introduces a **new command** goes in both `.pre-commit-config.yaml` and `.github/workflows/ci.yml` | A gate that rides inside `pytest` adds nothing to either file. Prefer that shape. The rehearsal is a new command but is explicitly a **spot check, not a gate** (the `break-check` precedent, D-09) |
| `.planning/` artifacts are committed and consistent with what shipped | ROADMAP/REQUIREMENTS/PROJECT/STATE ticks are part of the phase, not an afterthought |
| No module under `domain`/`application`/`infrastructure` imports `fastapi` | The `ProblemResponse` schema belongs in `presentation/api/schemas/` or `presentation/api/errors/` |
| FastAPI dependencies as `Annotated[T, Depends(...)]`, never argument defaults | Unchanged; 07-01 touches `responses=` maps only |
| No router raises **or imports** `HTTPException` (whole `presentation/api/` package) | 07-01 adds a schema and `responses=` entries; it must not reach for `HTTPException` |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOC-01 | `README.md` with project description, local setup, running in Docker, running the tests | §Gap 1 (file absent), §README Structure, §Code Examples (verified commands) |
| DOC-02 | README also has endpoint overview, 2-minute quickstart, requirement-to-evidence map, "pending / what I'd do next" | §README Structure, §Endpoint Inventory (19 operations read from `app.openapi()`), §Open Follow-Ups |
| DOC-03 | `DECISION_LOG.md` records each decision as context/options/decision/consequences, including every brief ambiguity | §Gap 2 — 96 ADRs exist, format already correct, **2 of 5 ambiguities have no ADR** |
| DOC-04 | OpenAPI complete: tags, summaries, response models, documented error responses for every route | §Gap 3 — tags/summaries/descriptions 19/19 done; **69/70 error legs publish no schema** |
| DOCK-05 | Clean-clone rehearsal passes before delivery (blocking) | §Clean-Clone Rehearsal — full design, five named traps, all measured |
| AIW-01 | `AI_WORKFLOW.md` shows the real workflow with Mermaid diagrams | §Gap 4 — **zero** mermaid blocks today; §Mermaid Constraints |
| AIW-02 | Human-decided vs AI-delegated, every claim traceable to commit/file/test | §Gap 4 — section exists for Phases 1-4, **missing Phases 5-6** and the per-claim references |
| AIW-05 | Public GitHub repo, atomic phase-scoped commits, green CI badge | §Delivery — repo **already public**, history already clean, 289 commits unpushed, badge absent |

## Gap Inventory (per roadmap success criterion)

### Gap 1 — SC-1/SC-2: `README.md` (DOC-01, DOC-02)

| Item | State | Path |
|------|-------|------|
| `README.md` | **ABSENT** | — (repository root) |
| Any reference to it | None in `tests/`, `scripts/`, `.pre-commit-config.yaml`, `.github/` | verified by `git grep` |
| `docs/` directory | ABSENT | — |
| The challenge brief (PDF or transcription) | **not in the repository** | see §Open Questions Q1 |

The only prose an evaluator currently reads first is the OpenAPI `description` in
`src/taskmanager/main.py` (`DESCRIPTION`), pinned by
`tests/unit/test_app_factory.py::test_the_description_names_the_evaluator_s_path`, whose docstring
says outright: *"This is the copy an evaluator reads first - before the README, because `/docs` is
what `docker compose up` hands them."* The README must not contradict it: both must say
register → Authorize → everything else. [VERIFIED: read in session]

`README.md` is **not** in `.dockerignore`, so adding it to the build context is free.

### Gap 2 — SC-2: `DECISION_LOG.md` (DOC-03)

The file is 4,227 lines, ADR-001..ADR-096, and its header (lines 1-17) already declares exactly
the four-part shape DOC-03 asks for: Context / Options / Decision / Consequences, with the
rejected option named. Spot-checked against ADR-001, ADR-002, ADR-069, ADR-070, ADR-096 — the
shape holds. **The format half of DOC-03 is already satisfied.** [VERIFIED: read in session]

The brief's five named ambiguities (PROJECT.md §Context):

| # | Ambiguity | Covered by | Verdict |
|---|-----------|-----------|---------|
| 1 | Completion-percentage scope (whole list vs filtered subset) | **ADR-009** "completion percentage over the whole list, via one SQL aggregate", refined by **ADR-049** (the two response envelopes) and **ADR-054** (measured, no N+1) | ✅ COVERED, thoroughly |
| 2 | Allowed task status values and transitions | **No ADR.** ADR-048 decides *where the door is* (a dedicated status endpoint) and mentions the matrix in passing as "Phase 2 D-01". The three values and the single forbidden move are decided in the docstring of `src/taskmanager/domain/value_objects/task_status.py` | ❌ **GAP** |
| 3 | Priority values | **No ADR.** `low\|medium\|high` and the `medium` default are decided in `src/taskmanager/domain/value_objects/task_priority.py`; integer priorities are listed in REQUIREMENTS.md "Out of Scope". Only incidental mentions in the log (constraint names at ADR-025/031, the filter DTO at ADR-046) | ❌ **GAP** |
| 4 | Who may be assigned to a task | **ADR-069** (any existing user, self-assignment allowed and emailed, non-existent assignee → 404 `user_not_found` with the check-ordering security property) + **ADR-068** (`GET /users` as the directory) | ✅ COVERED |
| 5 | What triggers the fake invitation | **ADR-070** (attempted after commit, failure swallowed) + **ADR-069** consequences (a repeat `PUT` sends no second email; `DELETE`/unassign notifies nobody) | ✅ COVERED |

**The truth the two missing ADRs must state** (read from the source, not assumed):

```python
# src/taskmanager/domain/value_objects/task_status.py
PENDING = "pending"; IN_PROGRESS = "in_progress"; COMPLETED = "completed"
ALLOWED_TRANSITIONS = {
    PENDING:     {IN_PROGRESS, COMPLETED},
    IN_PROGRESS: {PENDING, COMPLETED},
    COMPLETED:   {IN_PROGRESS},          # completed -> pending is the single forbidden move
}
```
`StrEnum`, not `(str, Enum)`, because since Python 3.11 the latter formats as `TaskStatus.PENDING`.
`ALLOWED_TRANSITIONS` is exhaustive on purpose so a fourth status raises `KeyError` rather than
falling through a permissive default. `TaskPriority` is `low|medium|high` ascending, and the
`medium` default is applied by the `Task` entity, **not** by the enum — deliberately, so the
vocabulary every layer shares does not carry a policy. [VERIFIED: read in session]

Both docstrings already contain the *reasoning* an ADR needs. These two ADRs are transcription
plus the options that were rejected, not new thinking.

**Two stale claims the log itself hands to Phase 7:**

| Claim | Location | Handed over by |
|-------|----------|---------------|
| ADR-019 still says "the workflow has never run on a real runner" — false since run `35301518310` | `DECISION_LOG.md` ADR-019 (line 587) | `.planning/STATE.md` §Blockers |
| A prose reference names `tests/api/test_error_contract.py`, a path that no longer exists (now `tests/unit/presentation/test_error_contract.py`) | `DECISION_LOG.md:3025` (inside ADR-072) | `.planning/phases/06-test-hardening-coverage/06-04-SUMMARY.md` §For Phase 7 |

The append-only rule forbids editing either. The established mechanism is a **follow-up ADR that
refines by id** — the precedent is ADR-020 refining ADR-004, and ADR-041 ("follow-up to ADR-017
and ADR-018 — both promises were kept in plan 03-10"). One Phase 7 ADR can carry both
corrections. [VERIFIED: read in session]

**On an index for a 4,227-line log.** The append-only rule governs *entries*, not the header
region: 06-04 recorded that `git diff DECISION_LOG.md | grep -c '^-'` returned 1 for a header
edit alone, i.e. the header has been amended before without anyone treating it as a violation.
No test, hook or CI step reads `DECISION_LOG.md` at all today (`git grep` over `tests/`,
`scripts/`, `.pre-commit-config.yaml`, `.github/` finds only two comment mentions), so nothing
breaks either way. [VERIFIED: read in session]

Three options, with a recommendation:

- **A full 96-row table of contents in the header.** Rejected as primary: a hand-maintained
  96-row list is a second home for the truth and will drift on ADR-097; a *generated* one needs a
  generator, a sync gate and another `Dockerfile COPY` — real cost for a reader who does not want
  96 rows.
- **A curated "start here" block in the header** (~20 lines): a table of the five brief
  ambiguities → the ADR that decides each, and a short list of the decisions an evaluator is most
  likely to question (PostgreSQL, 404-vs-403, whole-list percentage, PyJWT/pwdlib, flake8-not-ruff).
  Small, stable, answers the five-minute question directly. **Recommended.**
- **Put the map in the README instead** and leave the log's header untouched. Recommended
  *as well* — the requirement-to-evidence map (§README Structure) is the natural home, and it is
  the document an evaluator opens first.

Recommendation: do **both** curated forms (header block + README map) and skip the full TOC.

### Gap 3 — SC-3: OpenAPI completeness (DOC-04)

Built the real application and read `app.openapi()` in this session
(`create_app()` with injected `Settings`, no database touched). **19 operations.**

| Property | Result |
|----------|--------|
| Operations with a `tags` entry | **19 / 19** ✅ |
| Operations with a `summary` | **19 / 19** ✅ |
| Operations with a `description` | **19 / 19** ✅ (the handler docstrings) |
| Operations with a success `response_model` | **19 / 19** ✅ (the two 204s correctly carry no content) |
| Non-2xx response legs enumerated | **70** across the 19 operations ✅ |
| Non-2xx legs that publish a **schema** | **1 / 70** ❌ — only `GET /health` 503 (`HealthResponse`) |
| Top-level `tags` array (tag descriptions + ordering) | **absent** (`spec["tags"] is None`) ❌ |
| `servers`, `contact`, `license` in `info` | absent — cosmetic, not required by DOC-04 |
| `HTTPValidationError` in `components.schemas` | absent ✅ — FastAPI skips its default 422 when a route already declares `422`, so the RFC 9457 contract is not contradicted by a stray default |

Error-leg census: `401`×17, `403`×4, `404`×12, `409`×4, `422`×14, `500`×18, `503`×1.
Every one of the 69 problem+json legs looks like this in the document — a description and nothing
a client can parse against:

```json
"409": { "description": "The caller already owns a task list with this name. ..." }
```

Component inventory is otherwise healthy: 17 schemas, `OAuth2PasswordBearer` security scheme with
`tokenUrl: /api/v1/auth/login`, 16 of 19 operations carrying a `security` requirement and the
three open ones (`/health`, register, login) correctly carrying none. There is **no** Pydantic
model for the problem document anywhere — `presentation/api/errors/problem.py` builds a raw dict
into a `JSONResponse` with `media_type="application/problem+json"`. [VERIFIED: executed in session]

**Where the error descriptions live.** Each router module defines module-level constants
(`UNAUTHENTICATED_DESCRIPTION`, `NOT_FOUND_DESCRIPTION`, `DUPLICATE_NAME_DESCRIPTION`,
`VALIDATION_DESCRIPTION`, `UNEXPECTED_DESCRIPTION`, …) and each route spreads them into a
`responses={...}` dict — e.g. `src/taskmanager/presentation/api/routers/task_lists.py:133`. So the
fix is mechanical: a shared helper that turns `{401: DESC}` into
`{401: {"description": DESC, "content": {PROBLEM_JSON: PROBLEM_REF}}}`, applied at 69 sites across
five router modules plus `health.py`. [VERIFIED: read in session]

**How to declare it — measured, because the obvious spelling publishes a lie.** Four variants were
executed against the pinned stack (FastAPI 0.141.1):

| Variant | Result |
|---------|--------|
| `{"model": Problem}` | publishes `application/json` with the schema. **Wrong media type** — the app serves `application/problem+json` |
| `{"model": Problem, "content": {"application/problem+json": {}}}` | publishes `application/problem+json` **with an empty object** *and* `application/json` with the schema. **Worst of both**: says the media type it really serves has no schema |
| `{"model": Problem, "content": {"application/problem+json": {"schema": {"$ref": …}}}}` | publishes **both** media types with the schema. `application/json` is a documented response the API never emits |
| `{"description": …, "content": {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}}}` — **no** `model` key | publishes exactly one media type, correct. ✅ |

The last variant is right, but without a `model` key FastAPI never registers the component, and a
plain `FastAPI()` app has no `components` key at all — so the `$ref` would dangle. Verified fix:
subclass `FastAPI` and inject the component once.

```python
# executed in this session; the `$ref` resolves and the second call is stable
class ProblemAwareFastAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        schema = super().openapi()
        schema.setdefault("components", {}).setdefault("schemas", {}).setdefault(
            "Problem", ProblemResponse.model_json_schema()
        )
        return schema
```
Prefer the subclass over the documented `app.openapi = custom_openapi` assignment: `mypy --strict`
flags the latter as `method-assign` and would need a `type: ignore`. `super().openapi()` caches
into `self.openapi_schema` and returns the same object, so `setdefault` is idempotent — asserted
in the probe. [VERIFIED: executed in session]

**`/health` must be exempt.** Its 503 is `HealthResponse` on `application/json` **by design** —
D-08: `/health` is a status document and never `problem+json`. A gate that demands problem+json on
every non-2xx leg would be wrong, not strict. The exemption list is exactly
`{("get", "/health", "503")}`. [VERIFIED: read `presentation/api/health.py:92` and the ADR]

### Gap 4 — SC-5: `AI_WORKFLOW.md` (AIW-01, AIW-02)

1,914 lines. Inventory against the criterion's four demands:

| Demand | State | Location |
|--------|-------|----------|
| Mermaid diagrams of the real workflow | **ZERO** mermaid fenced blocks in the file. `## How This Project Was Built` (line 22) is a two-paragraph stub ending `_To be completed in Phase 7._` (line 29) | AI_WORKFLOW.md:22-29 |
| Human-decided vs AI-delegated split | Section exists (line 33) with **Phases 1, 2, 3, 4** blocks. **Phases 5 and 6 are absent.** Closes with `_Phase 7 completes this section with the per-claim commit/file/test references._` (line 169) | AI_WORKFLOW.md:33-169 |
| Claims traceable to a commit, file or test | **Already largely true** and better than the criterion demands: existing claims cite ADR ids, `NN-CONTEXT.md` D-numbers, concrete test names (`test_the_seam_says_it_is_not_authentication`), evidence files and source paths. What is missing is **commit hashes** — no claim cites one today | AI_WORKFLOW.md:39-168 |
| Incident log, ≥3 real mistakes, written incrementally | **51 dated entries**, 2026-09-17 → 2026-09-19, appended per phase per the Standing Rule. Vastly exceeds the bar | AI_WORKFLOW.md:209-1908 |
| "What I did not do" section | Heading exists with a three-line preamble, body is `_To be completed in Phase 7._` | AI_WORKFLOW.md:1909-1914 |

**AIW-03 is ticked `[x]` in REQUIREMENTS.md but its second half is not done.** AIW-03 reads
"...plus a 'what I did not do' section", and that section has no body. Phase 7 finishing it is
consistent with the intent (the requirement is owned by Phase 1 so the *log* opens early), but the
planner should know the tick is currently ahead of the file. [VERIFIED: read in session]

Also already true and worth not rewriting: the file opens with an explicit justification for the
absent commit trailers ("If this file and the repository ever disagree, this file is wrong"), and
a `## Verification Practices` section (line 173) with no Phase 7 marker — i.e. done.

**What "finalization" concretely means**, given AIW-03 is (mostly) ticked:
1. Fill `## How This Project Was Built` with the Mermaid diagrams (AIW-01).
2. Append the Phase 5 and Phase 6 human/AI blocks in the existing shape (AIW-02).
3. Replace the line-169 promissory note: add commit references to the claims that have none.
4. Write the `## What I Did Not Do` body (AIW-03's open half).
5. Append the Phase 7 dated incident entry at the end (Standing Rule) — including the two entries
   06-04 explicitly asked for: `make docker-test` having been broken for two phases unnoticed, and
   the CI leg of D-11's three-way coverage agreement.

Three diagrams are enough and each maps to something real:
- `flowchart TD` — brief → research (4 agents) → REQUIREMENTS → ROADMAP (7 phases) → per-phase
  discuss/research/plan/execute/verify/review loop → delivery.
- `flowchart LR` or `stateDiagram-v2` — the gate set: edit → pre-commit (black, isort, flake8,
  mypy, lint-imports) → `make test` (1101 tests, 75% gate, 4 import contracts, 8 architecture
  gates) → `make docker-test` (Python 3.13) → CI. Two honest annotations: `make break-check` sits
  *outside* the loop by D-09, and pre-commit is host-only while CI/Docker run the tools directly.
- `sequenceDiagram` — one real verification round trip, e.g. Phase 5: plan → execute → verify
  (found the forged-token gap) → 05-17 closes it (ADR-084) → re-verify 6/6. This is the diagram
  that proves the process caught something.

### Gap 5 — SC-4: the clean-clone rehearsal (DOCK-05) — **blocking**

Nothing exists: no script, no make target, no prior rehearsal record. Full design in
§Clean-Clone Rehearsal below. This is the largest genuinely new piece of work in the phase.

### Gap 6 — SC-6: public repo, phase-scoped commits, green badge (AIW-05)

Already substantially satisfied — see §Delivery. Remaining: badge markdown, the push, and
observing CI green.

## Endpoint Inventory

Read from `app.openapi()` in this session. This is the source for the README's endpoint table —
and, per §Don't Hand-Roll, the table should be *gated against* this rather than transcribed and
hoped for. [VERIFIED: executed in session]

| Tag | Method | Path | Summary |
|-----|--------|------|---------|
| health | GET | `/health` | Health |
| auth | POST | `/api/v1/auth/register` | Register an account |
| auth | POST | `/api/v1/auth/login` | Log in and get an access token |
| auth | GET | `/api/v1/auth/me` | Read the caller's own profile |
| task lists | GET | `/api/v1/task-lists` | List the caller's task lists |
| task lists | POST | `/api/v1/task-lists` | Create a task list |
| task lists | GET | `/api/v1/task-lists/{list_id}` | Read one task list |
| task lists | PATCH | `/api/v1/task-lists/{list_id}` | Update a task list |
| task lists | DELETE | `/api/v1/task-lists/{list_id}` | Delete a task list |
| tasks | POST | `/api/v1/task-lists/{list_id}/tasks` | Create a task in a list |
| tasks | GET | `/api/v1/task-lists/{list_id}/tasks` | List the tasks in a list, optionally filtered |
| tasks | GET | `/api/v1/task-lists/{list_id}/tasks/{task_id}` | Read one task |
| tasks | PATCH | `/api/v1/task-lists/{list_id}/tasks/{task_id}` | Update a task |
| tasks | DELETE | `/api/v1/task-lists/{list_id}/tasks/{task_id}` | Delete a task |
| tasks | PATCH | `/api/v1/task-lists/{list_id}/tasks/{task_id}/status` | Change a task's status |
| users | GET | `/api/v1/users` | List every user, so an assignee can be named |
| assignments | PUT | `/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee` | Assign a task to a user |
| assignments | DELETE | `/api/v1/task-lists/{list_id}/tasks/{task_id}/assignee` | Take a task back off its assignee |
| assignments | GET | `/api/v1/tasks/assigned-to-me` | List the tasks assigned to the caller, across every list |

Tag counts: health 1, auth 3, task lists 5, tasks 6, users 1, assignments 3.

## README Structure

Written for an evaluator with five minutes, in this order. Rationale for the ordering: the first
screen must answer "can I run this?" and "did they do the work?", not "what is the architecture?".

| # | Section | Content |
|---|---------|---------|
| 1 | Title + one-paragraph description + CI badge | What it is, what it is for, badge immediately (SC-6 asks for the badge *in the README*) |
| 2 | **Run it (2 commands)** | `make env` then `make up`; then `open http://localhost:8000/docs`. Name the prerequisites honestly: Docker and `make`, nothing else |
| 3 | **Run the tests (1 command)** | `make docker-test` as the zero-host-setup path (D-03/DOCK-04); `make install && make test` as the host path, stating that it needs `make up` running (ADR-029) |
| 4 | **2-minute quickstart** | The verified curl walkthrough (§Code Examples). Ends on the filtered listing showing `completion_percentage: 50.0` over 2 tasks while returning 1 item — the single response that demonstrates the brief's trickiest requirement |
| 5 | **Endpoint overview** | The 19-row table above, grouped by tag |
| 6 | **Requirement-to-evidence map** | The table below — the section that answers the brief directly |
| 7 | **Local development** | `make install`, the target list, `.env` via `make env`, `make run` for the host fast loop, `make format` |
| 8 | **Architecture in one screen** | The four layers, the import direction, and *that it is enforced by a test* — link `.importlinter` and `tests/architecture/test_layer_boundaries.py` |
| 9 | **Decisions & AI workflow** | Two links: `DECISION_LOG.md` (96 ADRs, with the five brief ambiguities named) and `AI_WORKFLOW.md` (51 incidents). One sentence each on why they exist |
| 10 | **Pending / what I'd do next** | Honest, itemized — see §Open Follow-Ups |

**The requirement-to-evidence map.** Key it on the brief's own numbering. REQUIREMENTS.md already
carries `[PDF 1.a.i]`-style citations on every requirement, so the keys exist and are consistent
with what shipped; the brief's literal Spanish wording is **not** in the repository (§Open
Questions Q1), so either commit a transcription or key the map on the PDF section numbers plus an
English restatement. Shape:

| Brief | What it asks | Where it is | Proof |
|-------|-------------|-------------|-------|
| 1.a.i | CRUD on task lists | `presentation/api/routers/task_lists.py` | `tests/integration/api/test_task_lists.py`; `curl` step 3 |
| 1.a.iv | Filter tasks, extra completion-% field | `application/use_cases/tasks/list.py`, ADR-009/049/054 | `tests/integration/api/test_tasks.py`; `curl` step 6 |
| 2.a | Layered structure | `src/taskmanager/{domain,application,infrastructure,presentation}` | `make arch` (4 contracts) + `tests/architecture/test_layer_boundaries.py` |
| 2.c | Custom exception error handling | `domain/exceptions.py`, `presentation/api/errors/` | `tests/unit/presentation/test_error_contract.py`; the 409 in `curl` step 5 |
| 3.b | Coverage ≥ 75% | `pytest.ini` `--cov-fail-under=75` | `make test` → 1101 passed, 100.00% over 1659 statements |
| 4.a/4.c | flake8 + `.flake8` file | `.flake8` | `make lint` |
| 5.a | Dockerfile + docker-compose | `Dockerfile`, `docker-compose.yml` | `make up`; `make rehearse` |
| 6 | README | this file | `make rehearse` executes its own commands |

Every row is a *command or a test*, not prose. That is what makes it checkable in five minutes and
is the whole point of the map.

**Keeping the README honest — the recommended gate.** Follow the `ADR-086` / `ADR-057` idiom
(observed from the artifact, never a hand-written list). Split in two, because the two halves need
different amounts of the tree:

*(a) Inside `pytest`* — `tests/architecture/test_documentation_claims.py`, `pytestmark = pytest.mark.unit`,
`ROOT = Path(__file__).resolve().parents[2]` (the existing convention in every sibling):
- Every `ADR-NNN` cited in `README.md` or `AI_WORKFLOW.md` resolves to a `## ADR-NNN:` heading in
  `DECISION_LOG.md`. Catches a typo'd or invented id, which is the highest-value cheap check here.
- Every `make <target>` named in `README.md` appears in the `Makefile`'s `.PHONY` line.
- The README's endpoint table, parsed from its fenced/pipe table, **equals** the set of
  `(method, path)` in `app.openapi()["paths"]` — set equality both ways, so a route added later
  without a README row is a red test.
- A non-vacuity guard (this project adds one to every gate): assert the parser found ≥ 19 rows and
  ≥ 1 ADR citation, so an emptied README passes nothing.

*(b) Inside the rehearsal script* — every filesystem path the README cites exists. This check
needs the **whole** working tree (`docker-compose.yml`, `docker/`, `.github/`, `.planning/`), which
the Docker test image deliberately does not contain; the rehearsal runs in a full clone, so it is
the honest home for it.

**⚠ The `Dockerfile` trap that will bite (a).** The `test` stage copies only
`pytest.ini .flake8 .importlinter .env.example`, `tests`, `alembic.ini`, `migrations`, `scripts`
(plus `pyproject.toml` and `src` from `builder`). It does **not** contain `README.md`,
`DECISION_LOG.md`, `AI_WORKFLOW.md`, `Makefile`, `docker-compose.yml`, `CLAUDE.md`, `.planning/`
or `.github/`. A gate reading those files is green on the host and a **collection/assertion error
in `make docker-test` and in CI's sibling** — which is exactly the failure 06-04 hit and recorded
("Both were collection errors in this stage until plan 06-04 ran `make docker-test`"). The gate's
plan must add `COPY README.md DECISION_LOG.md AI_WORKFLOW.md Makefile ./` to the `test` stage
**in the same task**, and its verification must be `make docker-test`, not `make test`.
[VERIFIED: read `Dockerfile:106-148` in session]

## Clean-Clone Rehearsal (DOCK-05)

Design it as a rerunnable program, not a one-off transcript: `scripts/clean-clone-rehearsal.sh`
behind `make rehearse`. The precedent is `scripts/break-check.sh` + `make break-check` — a spot
check run on demand, deliberately in neither `.pre-commit-config.yaml` nor CI (D-09), which is why
it does **not** trigger CLAUDE.md's two-places rule.

### Making "README followed verbatim" mechanical

Do not re-type the commands into the script — then the script proves the script. Instead:

1. `README.md` marks its evaluator path with HTML comments:
   `<!-- rehearsal:begin -->` … `<!-- rehearsal:end -->` around the fenced blocks of sections 2-4.
2. The script **extracts** the shell lines from those blocks *in the clone* and executes them in
   order. "Verbatim" stops being a claim and becomes the mechanism — if the README changes, the
   rehearsal changes, with nothing to keep in sync.
3. A pytest gate asserts the markers exist, are balanced, and the extracted block is non-empty —
   so deleting the markers is a red test rather than a rehearsal that silently ran zero commands.
   (Same non-vacuity discipline as every gate in `tests/architecture/`.)

### Measured environment, and the five traps

| # | Trap | Measured fact | Handling |
|---|------|--------------|----------|
| 1 | **Host port collision** | The developer stack is **up right now**: `test-api-1` on `0.0.0.0:8000`, `test-db-1` on `0.0.0.0:5432`. Ports are hard-coded in `docker-compose.yml`; there is no override file (D-16 says there deliberately is not) | The rehearsal **must stop the dev stack**: `docker compose down` in the repo (keeps the dev volume) as step 1, and offer to `docker compose up -d` it again at the end. Documented in the script header as a deliberate side effect |
| 2 | **Volume / project-name collision** | Compose derives the project name from the directory basename; the repo dir is `test`, so the dev project is `test` with volume `test_pgdata`. A clone into `/tmp/<something-else>` gets a different project and volume automatically | Still set `COMPOSE_PROJECT_NAME` explicitly (e.g. `crehana-rehearsal`) so the isolation is stated, not inherited from a path. The rehearsal's `docker compose down -v` then cannot touch the dev database |
| 3 | **`.env` bootstrap on a bare machine** | `docker-compose.yml` declares `env_file: .env` on both `api` and `test`, and compose **requires** it — a missing `.env` stops compose with an error naming the file (intentional, D-15). `.env` is git-ignored, so the clone has none. `make env` → `sh scripts/init-env.sh` needs only POSIX sh, awk, cp, mv and `openssl` or `/dev/urandom` — **no Python, no `.venv`, no Docker** | `make env` is necessarily the first extracted command. The script must assert `.env` exists after it and that its `JWT_SECRET` does **not** begin `replace-me` (ADR-084 refuses that value at boot) |
| 4 | **`make` targets that assume `.venv`** | `install format lint typecheck arch test test-unit run` all invoke `$(VENV)/bin/…`. `env up down docker-test break-check` do not | The README's Docker path must name only the second set. A rehearsal on a machine with no `.venv` proves this; if the README's quickstart names `make test`, the rehearsal fails and the README is wrong — which is the gate working |
| 5 | **Uncommitted files the clone would lack** | `git status` is clean today, and `.gitignore` covers only `.venv/`, `.env`, caches, coverage artifacts, `src/*.egg-info/`, `.DS_Store`. Everything `docker compose up` and `make docker-test` need **is tracked**: `Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh`, `docker/initdb/01-create-test-database.sql`, `migrations/*`, `scripts/*`, `.env.example`, `alembic.ini`, `pytest.ini`, `.flake8`, `.importlinter`, `pyproject.toml`, `requirements*.txt`, `Makefile` | The script must **refuse to start on a dirty tree** (`git status --porcelain` non-empty), because a clone proves the committed state and a dirty tree makes the result a lie. Same refusal `break-check.sh` already implements for `src/` |

Additional measured facts the script should rely on rather than guess:
- `api` reaches `healthy` fast — the 03-10 cold-start capture recorded `api healthy` after 3 polls
  at 3s intervals (≈9s) once the image was built. The `--no-cache` build is the long pole.
- A fresh project volume is empty, so `docker/initdb/01-create-test-database.sql` runs and
  `taskmanager_test` exists — which is what makes `make docker-test` work in the clone. (On a
  *reused* volume it would not; hence `down -v`.)
- `make up` runs `docker compose up --build` in the **foreground** by design (so a failed
  migration is visible). The script should run it backgrounded with output tee'd to a log and poll
  `docker compose ps` for `api healthy`, then continue — which is also what an evaluator does when
  they open a second terminal. The README should say "in a second terminal" above the curl block.
- `docker compose logs api | grep task_assigned_email` is the command that shows the simulated
  invitation. Verified live (§Code Examples).
- The unrelated container `nuestracasa-neon-proxy` holds `5433`, not `5432` — no conflict.

### Shape

```sh
# scripts/clean-clone-rehearsal.sh   (POSIX sh, no bashisms — the init-env.sh precedent)
# 0. refuse a dirty tree; refuse if HEAD has no README.md
# 1. record `docker compose ps`; `docker compose down` in the repo   (frees 8000/5432)
# 2. git clone "$PWD" "$WORK/crehana-rehearsal"  (committed state only)
# 3. cd clone; export COMPOSE_PROJECT_NAME=crehana-rehearsal
# 4. docker compose down -v            (idempotent on a re-run)
# 5. docker compose build --no-cache   (the SC-4 "--no-cache build")
# 6. assert every path README.md cites exists in the clone
# 7. extract and run each command between the rehearsal markers, in order,
#    backgrounding `make up` and polling for `api healthy`
# 8. docker compose down -v; report elapsed time per step
# 9. optionally restore the dev stack
```

`git clone "$PWD" <dest>` clones the local repo's current branch and its history — sufficient, and
`break-check.sh`'s `git`-based restore still works inside the clone if anyone runs it there.

**Ordering consequence for the plan:** the rehearsal clones the *committed* tree, so it must run
**after** the README, the ADRs and the AI_WORKFLOW edits are committed, and after the rehearsal
script itself is committed. DOCK-05 is therefore the last plan, and if it finds a gap the fix is a
commit followed by a re-run — which the rerunnable design makes cheap.

## Delivery (AIW-05)

All measured in this session.

| Fact | Value |
|------|-------|
| Remote | `git@github.com:Xch4rt/crehana-backend-test.git` |
| **Visibility** | **`PUBLIC` already** — `gh repo view` returns `"visibility":"PUBLIC"`. No flip needed |
| Default branch | `main` (local and remote agree) |
| Commits total | 332 |
| Commits **unpushed** | 289 (`origin/main` is at `f879894`, Phase 1) |
| Last remote push | 2026-09-18T03:29 |
| CI runs observed | 3, all `success`, all on Phase 1 commits. **Phases 2-6 have never run on a runner** |
| Workflow | one, named `CI`, file `.github/workflows/ci.yml` |
| Commit conventions | 100% conventional-commits. No non-conforming subject in 332 commits |
| Scoping | `docs(NN-NN)` 97, `feat(NN-NN)` 82, `test(NN-NN)` 45, `docs(NN)` 43, `fix(NN)` 20, `docs(phase-NN)` 16, `fix(NN-NN)` 8, `docs(state)` 6, `chore(NN-NN)` 3, `build(NN-NN)` 3, `chore(planning)` 2, `ci(NN-NN)` 1, `test(NN)` 1, plus 5 unscoped bootstrap commits |
| AI attribution trailers | **none.** No `Co-Authored-By`, no "Generated with", no model or vendor name in any commit body. (A case-insensitive grep matches only the literal filename `CLAUDE.md` in message bodies) |

"Atomic, phase-scoped commits" is therefore **already true and demonstrable** — one `git log
--oneline` screenshot in the README's workflow section is stronger evidence than any prose. Note
CLAUDE.md's no-attribution rule **overrides** this session's attribution reminder; Phase 7's own
commits must carry no trailer.

### Badge markdown

```markdown
[![CI](https://github.com/Xch4rt/crehana-backend-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Xch4rt/crehana-backend-test/actions/workflows/ci.yml)
```
Path derived from the workflow filename, which is the form GitHub documents. The badge is
**red-or-stale until the push**, so the README cannot be verified green before the push — hence a
human-verify checkpoint after it. [CITED: docs.github.com/actions badge conventions] [VERIFIED: remote + workflow filename read in session]

### What might fail on the first push — assessed, not guessed

| Risk | Assessment |
|------|-----------|
| `JWT_SECRET` refused at boot | **Safe.** CI sets `ci-only-secret-not-a-real-credential` (41 chars, does not begin `replace-me`) — clears the 32-char floor (ADR-061) and the placeholder refusal (ADR-084) |
| Integration tests can't find the test database | **Safe.** CI's `DATABASE_URL` names `taskmanager_test`; `resolve_test_database_url` falls back to `derive_test_database_url`, which **sets** the database component to the constant `taskmanager_test` (it does not append), so it resolves to the service container's `POSTGRES_DB`. Verified by reading `infrastructure/config/database_url.py` |
| `tests/unit/test_break_check.py` needs `git` and an identity | **Safe.** Ubuntu runners have `git`; the test passes `-c user.name=… -c user.email=…` per invocation (`GIT_ISOLATION`), so the runner's missing global identity cannot bite |
| `scripts/break-check.sh` under `dash` | **Safe.** ADR-094 added HUP/QUIT traps and a dash-run signal test explicitly for Debian-family shells |
| `lint-imports` can't resolve `root_package` | **Safe.** CI runs `pip install -e .` before the gates |
| `filterwarnings = error` divergence (host 3.14 vs CI 3.13) | **Low.** This is the one genuinely unobservable-until-pushed risk and it is the accepted risk ADR-002 records. Mitigated in advance: `make docker-test` runs the same suite on Python **3.13** and is green, which is the same interpreter CI uses |
| Coverage differs from the host number | **Expected and wanted.** 06-04 handed Phase 7: *"The CI leg of D-11's agreement is unrecorded. After the next push, read the coverage total out of the run log."* ⚠ Its prediction of **1796 statements** is **stale** — it predates 06-05; the host now reports **1659**. Record the number CI actually prints, do not repeat the prediction |

### Secret scan — findings, no history rewrite

| Check | Result |
|-------|--------|
| `.env` tracked, ever | **No.** Not in `git ls-files`; `git log -- .env` is empty; `.gitignore` line 3 covers it; `.dockerignore` excludes it from every build context |
| Live `.env` `JWT_SECRET` (64 hex) present anywhere in the repo | **No.** Absent from tracked files and from `git log -S<value>` across all refs |
| `JWT_SECRET=<value>` in tracked files | Three hits, all benign: `.env.example:50` = `replace-me-with-a-generated-secret` (the value ADR-084 **refuses at boot**), and two `awk` patterns in `scripts/init-env.sh` |
| Same string in `.planning/` | 9 files, all discussing the placeholder or the incident — no live value |
| Private keys / certs / keystores | **None.** No `.pem`, `.key`, `.p12`, `.pfx`, `.jks`, `id_rsa`, `id_ed25519` tracked |
| Database credentials in `docker-compose.yml` / `ci.yml` | `taskmanager:taskmanager`, documented in both files as deliberately fake local/CI values (ADR-042). Not a finding |
| Caches / coverage artifacts tracked | **None.** `.coverage`, `coverage.xml`, `.grimp_cache/`, `.import_linter_cache/`, `.mypy_cache/`, `src/taskmanager.egg-info/` are all ignored and untracked |

**Verdict: nothing to remediate, and no history rewrite is warranted.** Worth one sentence in the
README or AI_WORKFLOW: the only signing key ever published in this repository is the placeholder,
and the application refuses to boot with it — which is the Phase 5 incident's fix, stated as a
property rather than a promise.

## Open Follow-Ups (material for the README's "pending" section)

These are recorded, non-blocking, and belong in a "pending / what I'd do next" list — not in a
rewrite. Sourced from `.planning/phases/06-test-hardening-coverage/06-REVIEW.md` and ADR-096.

| Id | One-line | Kind |
|----|----------|------|
| WR-03 | Both halves of the assertion-quality gate are satisfiable by shapes that assert nothing (a re-read whose result is discarded). Closing it is a gate redesign; ADR-096 names it as knowingly open | gate robustness |
| WR-05 | The marker guard enforces "at least one" while documenting "exactly one", and has no test of its own | gate robustness |
| WR-06 | The total half of endpoint totality is *skipped*, not failed, by invocation drift; the invocations that count are unpinned | gate robustness |
| WR-07 | The error-contract gate resolves `raise`s by spelled name only, so a new leaf can arrive unseen | gate robustness |
| WR-08 | The use-case totality gate matches any attribute call by name and accepts a construction in dead code | gate robustness |
| WR-10 | The derived transition test takes its oracle from the code under test, so it cannot see an over-permissive table | test oracle |
| WR-11 | Two of the new D-06 assertions cannot fail | vacuous assertion |
| IN-01..06 | Dockerfile layer ordering, a `.pyc` outliving one restore, small `break-check.sh` behaviours, `test_break_check.py` env inheritance, two `concurrency` edges, minor gate redundancy | info |
| — | v2 scope already agreed: pagination/sorting (API-01, ADR-043), multi-value filters (API-02), an explicit invitation endpoint (API-03), refresh tokens (AUTH-07), password reset (AUTH-08) | product scope |
| — | Conceded security properties, recorded not hidden: register's 409 is an account-enumeration oracle (ADR-066); no rate limiting on login (ADR-067); `GET /users` is an email directory readable by any authenticated caller (ADR-068) | honest limits |

Citing ADR-066/067/068 in the README's pending section is a strength, not a weakness: it shows the
threats were identified and the concession was deliberate.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Keeping the README's endpoint table in step with the API | A hand-maintained list plus a review habit | Set equality against `app.openapi()["paths"]` in a test | ADR-057/ADR-086 already settled this in this repository: never `app.routes`, never a declared list. A second home for the truth drifts |
| Proving the README's commands work | A transcript pasted into a SUMMARY | A script that **extracts and executes** the README's own fenced blocks | A transcript proves one moment; extraction makes the README the source and the run the proof |
| Publishing the error-body shape | Prose in each `description`, or a hand-written JSON example per route | One `ProblemResponse` Pydantic model + `$ref` in 69 `responses` legs | 69 copies of an example drift; a `$ref` cannot |
| Declaring the `problem+json` media type | `responses={401: {"model": Problem}}` | `{"description": …, "content": {"application/problem+json": {"schema": {"$ref": …}}}}` + a `FastAPI` subclass that registers the component | **Measured this session:** `model` publishes `application/json`, a media type this API never emits. Three of four spellings publish something false |
| A table of contents for a 4,227-line log | A hand-typed 96-row TOC | A curated five-ambiguity block in the header + the README's evidence map | 96 rows is churn on every new ADR and serves no five-minute reader |
| Isolating the rehearsal from the dev stack | Editing `docker-compose.yml` ports, or a throwaway override file | `COMPOSE_PROJECT_NAME` + `docker compose down` on the dev stack first | An override file would mean the rehearsal no longer runs the README's commands — it would prove a different stack |
| Validating Mermaid locally | Adding a Node toolchain / `npx` to a Python deliverable | Constrain the syntax (below) and verify by looking at the rendered page after the push | A Node dependency in a Python submission is a cost an evaluator notices |

**Key insight:** every gap in this phase is a *synchronization* problem between a document and the
code. This repository has already solved that class of problem six times (ADR-057, ADR-083,
ADR-085, ADR-086, ADR-087, ADR-090) and the answer was always the same: observe the artifact, do
not restate it, and add a non-vacuity guard so an emptied observation cannot pass.

## Mermaid Constraints (AIW-01)

| Claim | Confidence |
|-------|-----------|
| GitHub renders Mermaid natively in `.md` files from a fenced block with the `mermaid` language identifier; no plugin needed | HIGH [CITED: docs.github.com/.../creating-diagrams] |
| GitHub's own docs state only one limitation explicitly: third-party Mermaid plugins may cause errors. They do **not** pin a version or enumerate unsupported features | HIGH [CITED: same page, fetched in session] |
| Font-Awesome icon syntax (`fa:fa-ban`), and hyperlinks/tooltips inside labels, are unreliable on GitHub | MEDIUM [CITED: github.blog Mermaid announcement + community guides; not in the docs page] |
| Some emoji and extended-ASCII characters break parsing | MEDIUM [CITED: community guides] |
| Newer diagram types / styling may not render, because platforms pin different Mermaid versions | MEDIUM [CITED: community guides] |
| Labels containing `(`, `)`, `[`, `]`, `:` or `,` must be double-quoted (`A["make test (75% gate)"]`), and `end` cannot be a bare node id in a flowchart | ASSUMED (training knowledge; no authoritative source found this session) |

**Practical rules for this phase:** use only `flowchart TD` / `flowchart LR`, `sequenceDiagram`
and `stateDiagram-v2`; double-quote every label; no icons, no click handlers, no emoji, no inline
styling. **Verification is a human look at the rendered file on GitHub after the push** — there is
no local renderer and adding one is the wrong trade (§Don't Hand-Roll). Make it an explicit
checkpoint in the delivery plan.

## Code Examples

### The 2-minute quickstart — executed live against the running container this session

All output below is real, captured from `test-api-1` on `localhost:8000`. The README can use these
commands as written; only the bearer-token plumbing needs a shell idiom. [VERIFIED: executed in session]

```bash
# 0. Is it up?
curl -s localhost:8000/health
# {"status":"ok","checks":{"database":"ok"},"version":"0.1.0"}

# 1. Register (there is no seeded account — by design, ADR-075)
curl -s -X POST localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","full_name":"Ada Lovelace","password":"correct-horse-battery-staple"}'
# 201 {"id":"c96174cc-…","email":"ada@example.com","full_name":"Ada Lovelace","created_at":"…Z"}

# 2. Log in (OAuth2 password form — the username field IS the email)
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=ada@example.com&password=correct-horse-battery-staple' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
# {"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…","token_type":"bearer","expires_in":1800}

AUTH="Authorization: Bearer $TOKEN"

# 3. Create a task list
curl -s -X POST localhost:8000/api/v1/task-lists -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Launch checklist","description":"Everything before the demo"}'
# 201 {"id":"ab5b45a7-…","name":"Launch checklist","total_tasks":0,"completed_tasks":0,"completion_percentage":0.0}

# 4. Two tasks in it
curl -s -X POST localhost:8000/api/v1/task-lists/$LIST/tasks -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"title":"Write the README","priority":"high"}'
# 201 {"id":"5a9c6a16-…","status":"pending","priority":"high","assignee_id":null, …}

# 5. Change a status through the dedicated endpoint
curl -s -X PATCH localhost:8000/api/v1/task-lists/$LIST/tasks/$TASK/status -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"status":"completed"}'
# 200 {"status":"completed","completed_at":"2026-09-19T23:37:27.606759Z", …}

# 6. THE MONEY SHOT — filter the view, keep the whole-list statistics (ADR-009)
curl -s "localhost:8000/api/v1/task-lists/$LIST/tasks?priority=high" -H "$AUTH"
# {"items":[ …1 task… ],"total_tasks":2,"completed_tasks":1,"completion_percentage":50.0}
#            ^ one item returned          ^ counters describe the LIST, not the filtered view

# 7. Assign, and watch the simulated invitation
curl -s -X PUT localhost:8000/api/v1/task-lists/$LIST/tasks/$TASK/assignee -H "$AUTH" \
  -H 'Content-Type: application/json' -d "{\"assignee_id\":\"$USER_ID\"}"
docker compose logs api | grep task_assigned_email
```

The notification line, verbatim from the container log:

```json
{"level": "INFO", "logger": "taskmanager.notifications", "message": "Task assignment invitation",
 "event": "task_assigned_email", "to": "ada@example.com",
 "subject": "You have been assigned a task: Write the README",
 "body": "You have been assigned the task \"Write the README\". Open /api/v1/tasks/assigned-to-me to see every task assigned to you.",
 "task_id": "5a9c6a16-d68d-4455-b5ec-cfa9a9147bde"}
```

### The error contract, also captured live

Two responses worth putting in the README, because together they show the single shape and the
`code`/`errors` extensions:

```bash
curl -i localhost:8000/api/v1/task-lists/00000000-0000-0000-0000-000000000000 -H "$AUTH"
# content-type: application/problem+json
# {"type":"urn:taskmanager:problem:task_list_not_found","title":"Task list not found","status":404,
#  "detail":"No task list exists with identifier 000…0.","instance":"/api/v1/task-lists/000…0",
#  "code":"task_list_not_found","errors":{"task_list_id":"000…0"}}

curl -X PATCH …/tasks/$TASK/status -H "$AUTH" -d '{"status":"pending"}'   # from completed
# {"type":"urn:taskmanager:problem:invalid_status_transition","title":"Invalid status transition",
#  "status":409,"detail":"A task cannot move from completed to pending.","instance":"…",
#  "code":"invalid_status_transition","errors":{"from":"completed","to":"pending"}}
```

`ProblemResponse`'s fields follow directly: `type`, `title`, `status`, `detail`, `instance`,
`code`, and an optional `errors`. Member order is load-bearing (D-06, `errors` last) and
`presentation/api/errors/problem.py` already guarantees it by building a dict literal — the new
Pydantic model must declare the same order so the published schema and the served body agree.

### The DOC-04 fix, measured

```python
# src/taskmanager/presentation/api/errors/problem.py (or a sibling schema module)
PROBLEM_REF: Final[dict[str, Any]] = {"schema": {"$ref": "#/components/schemas/Problem"}}

def problem_response(description: str) -> dict[str, Any]:
    """One error leg, published on the media type this API actually serves."""
    return {"description": description, "content": {PROBLEM_JSON: dict(PROBLEM_REF)}}
```
```python
# src/taskmanager/main.py — the component has to be registered somewhere, and `model=` cannot
# do it without also publishing an `application/json` leg the API never emits.
class ProblemAwareFastAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        schema = super().openapi()
        schema.setdefault("components", {}).setdefault("schemas", {}).setdefault(
            "Problem", ProblemResponse.model_json_schema()
        )
        return schema
```
Both halves executed against FastAPI 0.141.1 in this session: the `$ref` resolves, exactly one
media type is published, and a second `openapi()` call returns the same cached object with the
component still present. Prefer the subclass to `app.openapi = fn`, which `mypy --strict` rejects
as `method-assign`. [VERIFIED: executed in session]

Also in the same plan, for the other half of SC-3 ("`/docs` shows tags"): pass `openapi_tags` to
the constructor so the six tags get descriptions and a deliberate order — today
`app.openapi()["tags"]` is `None`, so `/docs` groups by bare tag name in route-registration order.

## Common Pitfalls

### Pitfall 1: a documentation gate that is green on the host and red in the container
**What goes wrong:** a new test under `tests/` reads `README.md` or `Makefile`; `make test` passes;
`make docker-test` and CI fail with a collection or assertion error.
**Why:** the Dockerfile `test` stage copies a deliberately minimal file set. `README.md`,
`DECISION_LOG.md`, `AI_WORKFLOW.md`, `Makefile`, `docker-compose.yml`, `CLAUDE.md`, `.planning/`
and `.github/` are **not** in the image.
**How to avoid:** add the `COPY` line in the same task as the gate; make `make docker-test` the
task's verification command, not `make test`.
**Warning signs:** the phrase "reads a file from the repository root" in a plan with no Dockerfile
edit beside it. This exact failure happened in 06-04.

### Pitfall 2: publishing an error media type the API never serves
**What goes wrong:** `responses={409: {"model": ProblemResponse}}` looks correct and makes Swagger
show a schema — under `application/json`, which this API never emits for an error.
**Why:** FastAPI attaches the `model` schema to `application/json` regardless of any `content` key
you supply, and merges rather than replaces.
**How to avoid:** the no-`model` + explicit-`$ref` form, plus component registration (§Code Examples).
**Warning signs:** `"application/json"` appearing anywhere in a non-2xx leg of `/openapi.json`
other than `/health` 503.

### Pitfall 3: a rehearsal that "passes" because it collided with the dev stack
**What goes wrong:** the rehearsal reuses the running `test_pgdata` volume or dials the dev API on
:8000 and reports success while having built nothing.
**Why:** hard-coded published ports, and a compose project name derived from a directory basename.
**How to avoid:** `docker compose down` the dev stack, explicit `COMPOSE_PROJECT_NAME`,
`down -v` before and after, and assert the API answering on :8000 is the **rehearsal's** container
(check `docker compose ps` inside the clone, and read `version` from `/health`).
**Warning signs:** a rehearsal that finishes suspiciously fast, or an `api healthy` before the
`--no-cache` build could have completed.

### Pitfall 4: rehearsing a tree that is not the one being delivered
**What goes wrong:** the rehearsal runs from a dirty working tree; the clone silently lacks the
uncommitted README fix; the recorded "pass" describes a repository that does not exist.
**How to avoid:** refuse to start on `git status --porcelain` non-empty — the same refusal
`break-check.sh` already implements.

### Pitfall 5: the README contradicting `/docs`
**What goes wrong:** the README says "log in with the demo account". There **is** no demo account —
ADR-075 deleted the seed and nothing replaced it.
**How to avoid:** both documents must describe register → Authorize → everything else.
`test_the_description_names_the_evaluator_s_path` already pins the `/docs` half; the README half is
covered if its quickstart is the executed one above.

### Pitfall 6: editing `DECISION_LOG.md` to fix a stale sentence
**What goes wrong:** ADR-019's false claim gets corrected in place; the append-only property that
makes the log credible is gone, and the diff shows deletions.
**How to avoid:** a new ADR that supersedes by id. Precedents: ADR-020→ADR-004, ADR-041→ADR-017/018.

### Pitfall 7: reading a stale `coverage.xml` or a stale predicted number
**What goes wrong:** the README or a SUMMARY quotes a coverage figure that is not the current one.
**Two live instances:** (a) 06-04's handover predicts **1796** statements for CI; the host now
reports **1659** after 06-05 — record what CI prints, do not repeat the prediction. (b) **This
research session ran `pytest --collect-only`, which rewrote the untracked `coverage.xml` with a
55% collection-time number.** It is git-ignored so it cannot be committed, but re-run `make test`
before reading that file for any purpose.

## Runtime State Inventory

Not a rename/refactor/migration phase, but three items in this phase's blast radius are state that
lives outside the tree and is worth stating explicitly rather than leaving blank:

| Category | Items found | Action required |
|----------|-------------|------------------|
| Stored data | The dev PostgreSQL volume `test_pgdata` holds records from every prior phase's verification, plus the five rows this research session created (one user `ada1789861038@example.com`, one list, two tasks, one assignment). | None. Throwaway local data; the rehearsal uses a **separate** project volume and never touches it. Worth knowing so `GET /api/v1/users` returning old fixtures in a demo is not mistaken for a bug |
| Live service config | GitHub repository settings: already `PUBLIC`; one workflow (`CI`) active. Nothing else external | Verify visibility is intentional at the delivery checkpoint; no change needed |
| OS-registered state | None — no launchd, no cron, no pm2. Only the two long-running compose containers | The rehearsal stops and restarts them |
| Secrets / env vars | Host `.env` with a real 64-hex `JWT_SECRET` (untracked, never committed, never in history). CI carries two inline fake values in `ci.yml`; **no repository secret is referenced by any workflow** | None. Do not add a repository secret in this phase — the workflow deliberately needs none |
| Build artifacts | `.venv/`, `src/taskmanager.egg-info/`, `.grimp_cache/`, `.import_linter_cache/`, `.mypy_cache/`, `.pytest_cache/`, `.coverage`, `coverage.xml` — all ignored, all untracked | None, and this is what makes the clean-clone rehearsal meaningful: the clone starts with none of them |

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker + compose v2 | `make up`, `make docker-test`, the rehearsal | ✓ | daemon running; two project containers healthy | none — DOCK-05 cannot be done without it |
| `gh` CLI (authenticated) | reading repo visibility, observing the CI run after the push | ✓ | `/opt/homebrew/bin/gh`, `gh repo view` and `gh run list` both succeeded | the GitHub web UI (manual checkpoint) |
| `git` | rehearsal clone, history checks | ✓ | — | none |
| `.venv` with the dev toolchain | `make lint/typecheck/arch/test` | ✓ | CPython 3.14.3; 1101 tests collect in 0.98s | `make docker-test` (Python 3.13) |
| Running PostgreSQL | `make test` integration half (ADR-029, no auto-skip) | ✓ | `postgres:18-alpine`, `test-db-1` healthy on :5432 | `make docker-test` |
| `openssl` | `make env` secret generation | ✓ | present; script falls back to `/dev/urandom` | `/dev/urandom` (in-script) |
| `timeout(1)` | any bounded wait in a new script | ✗ | **absent on this macOS host** | POSIX polling loop with `sleep` + a counter — the idiom `docker/entrypoint.sh` and the 03-10 capture already use. **Do not write `timeout` into the rehearsal script** |
| A Mermaid renderer | validating AIW-01 diagrams locally | ✗ | — | visual check on GitHub after the push (human checkpoint) |
| The challenge brief PDF | keying the requirement-to-evidence map on literal wording | ✗ | not in the repository, no `docs/` directory | REQUIREMENTS.md's `[PDF x.y]` citations + PROJECT.md's Active list. See Q1 |

**Missing with no fallback:** none blocking.
**Missing with fallback:** `timeout(1)`, a Mermaid renderer, the brief PDF.

## Validation Architecture

### Test framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`), pytest-cov 7.1.0 |
| Config file | `pytest.ini` (brief-mandated literal file; `[tool.pytest.ini_options]` in `pyproject.toml` would be silently ignored) |
| Quick run | `make test-unit` → `pytest -m unit --no-cov` (no database, ~1.5s) |
| Full suite | `make test` → `pytest` (1101 tests, 75% gate, requires a reachable PostgreSQL) |
| Container suite | `make docker-test` → `docker compose run --rm --build test` (Python 3.13, zero host setup) |
| Current state | **1101 tests, 100.00% over 1659 statements / 154 branches** [VERIFIED: 1101 collected this session; percentage from 06-VERIFICATION.md] |
| Marker rule | every collected test must carry `unit` or `integration` (ADR-090) — a new test that carries neither fails collection |
| Root convention | `ROOT = Path(__file__).resolve().parents[2]` in `tests/architecture/*` |

### Phase requirements → test map

| Req | Behaviour | Type | Automated command | Exists? |
|-----|-----------|------|-------------------|---------|
| DOC-04 | Every non-2xx leg of every operation (except `/health` 503) publishes a `problem+json` schema; every operation has a tag and a summary; the six tags have descriptions | unit | `pytest tests/architecture/test_openapi_completeness.py -x` | ❌ **Wave 0** |
| DOC-02 | The README's endpoint table equals `app.openapi()["paths"]`, both directions | unit | `pytest tests/architecture/test_documentation_claims.py -x` | ❌ **Wave 0** |
| DOC-02/03 | Every `ADR-NNN` cited in `README.md` / `AI_WORKFLOW.md` resolves to a `## ADR-NNN:` heading | unit | same file | ❌ **Wave 0** |
| DOC-01 | Every `make <target>` the README names exists in the `Makefile` | unit | same file | ❌ **Wave 0** |
| DOC-01/02 | The README's rehearsal markers exist, balance, and delimit a non-empty command block | unit | same file | ❌ **Wave 0** |
| DOC-03 | All five brief ambiguities are answered by an existing ADR heading | unit | same file (assert the five ids resolve) | ❌ **Wave 0** |
| DOCK-05 | A fresh clone, `--no-cache` build and the README's own commands reach a healthy API and a green suite | e2e script | `make rehearse` | ❌ **Wave 0** |
| DOC-01 | Every filesystem path the README cites exists | script | inside `make rehearse` (needs the whole tree) | ❌ **Wave 0** |
| AIW-01 | `AI_WORKFLOW.md` contains ≥ 3 ```mermaid fenced blocks and no `_To be completed in Phase 7._` marker remains | unit | `tests/architecture/test_documentation_claims.py` | ❌ **Wave 0** |
| AIW-02 | The human/AI section names every phase 1..7 | unit | same file | ❌ **Wave 0** |
| AIW-05 | Every commit subject matches conventional-commits and no body contains an AI attribution trailer | manual / one-off | `git log --format=%s` + `git log --format=%B \| grep -i` (both run this session, both clean) | ✅ verified, not gated |
| AIW-05 | Repo public; CI green on the delivered commit; badge renders | **manual** | `gh repo view`, `gh run list`, browser | partially verified (public ✓, green-on-Phase-1 ✓) |
| AIW-01 | Mermaid diagrams render on GitHub | **manual** | browser | ❌ checkpoint |

### Sampling rate

- **Per task commit:** `make test-unit` (the new gates are all `unit`-marked and DB-free, so the
  fast loop covers them) — plus `make lint && make typecheck` for the `src/` change in 07-01.
- **Per plan completion:** `make test` (full suite, 75% gate, 4 import contracts).
- **Any plan that touches the `Dockerfile` or adds a file-reading gate:** `make docker-test` as
  well. This is non-negotiable per Pitfall 1.
- **Phase gate:** `make lint && make typecheck && make arch && make test && make docker-test`, then
  `make rehearse`, then the push and the observed CI run.

### Wave 0 gaps

- [ ] `tests/architecture/test_openapi_completeness.py` — covers DOC-04; exempts `("get","/health","503")` explicitly with the D-08 reason; non-vacuity guard asserting ≥ 19 operations and ≥ 69 problem legs found
- [ ] `tests/architecture/test_documentation_claims.py` — covers DOC-01/02/03 and AIW-01/02; non-vacuity guards on every parse
- [ ] `scripts/clean-clone-rehearsal.sh` + `rehearse` in `.PHONY` and the `Makefile` — covers DOCK-05
- [ ] `Dockerfile` `test` stage: `COPY README.md DECISION_LOG.md AI_WORKFLOW.md Makefile ./`
- [ ] No framework install needed; no new dependency in `requirements*.txt`

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|--------------|------------------|--------------|-------------|
| `responses={code: {"model": M}}` as "the" way to document an error | Explicit `content` per media type, because `model` hard-codes `application/json` | long-standing FastAPI behaviour, unchanged in 0.141.1 | Determines the whole shape of 07-01; measured this session rather than assumed |
| A README with a hand-written endpoint list | The list generated from / gated against `/openapi.json` | this repository's own ADR-057/086 idiom | The README gate design |
| Documenting a workflow in prose after the fact | An incident log appended per phase, then diagrammed | `AI_WORKFLOW.md`'s own thesis, and STATE.md's standing blocker | Phase 7 must **not** reconstruct; only diagram and complete |
| A delivery checklist a human ticks | A rerunnable script that executes the README | the `break-check.sh` precedent (D-09, ADR-091) | The rehearsal design |

**Not deprecated but worth noting:** FastAPI still omits its default `422`/`HTTPValidationError`
when a route declares `422` itself, which is why this API's RFC 9457 contract is not currently
contradicted by a stray default schema. Adding a `content` block to the existing `422` entries
preserves that — removing the `422` key would not.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | Mermaid labels containing `(`, `)`, `[`, `]`, `:` need double-quoting on GitHub, and `end` cannot be a bare flowchart node id | Mermaid Constraints | A diagram fails to render on the delivered README/AI_WORKFLOW. Mitigated by the post-push visual checkpoint |
| A2 | The 5 brief ambiguities listed in PROJECT.md §Context are exactly the ones DOC-03 must cover | Gap 2 | If the PDF names a sixth, an ADR is missing. Resolved by Q1 |
| A3 | An evaluator will read `/docs` before the README (because `docker compose up` hands them the API) | README Structure | Section ordering is suboptimal, nothing breaks. This assumption is already encoded in `test_the_description_names_the_evaluator_s_path` |
| A4 | `docker compose build --no-cache` before running the README's `make up` satisfies SC-4's "`--no-cache` build" even though the README's own command uses the cache | Clean-Clone Rehearsal | A pedantic reading of SC-4 is unmet. Worth confirming with the user |
| A5 | Three Mermaid diagrams are enough for AIW-01 ("brief analysis → research → requirements → roadmap → per-phase plan/execute/verify → quality gates") | Gap 4 | Under-delivers against the criterion's list. Low risk — the three cover all six named stages |
| A6 | Committing a transcription of the brief is acceptable to the user (copyright/confidentiality) | Open Questions Q1 | Legal/etiquette issue. **Must be asked, not assumed** |
| A7 | The five rows this session created in the dev database are acceptable collateral | Runtime State Inventory | None material; it is a local throwaway volume |

## Open Questions / human-gated steps

The planner should turn each of these into a `checkpoint:human-verify` task rather than deciding it.

**Q1 — The brief itself is not in the repository.** No PDF, no transcription, no `docs/`. DOC-02
and roadmap SC-1 ask for "a requirement-to-evidence map **for the PDF**", and the task brief says
the map "must follow its literal wording" — which cannot be verified against anything currently
committed. Three options: (a) commit the PDF under `docs/`; (b) commit an English transcription of
its requirement list; (c) key the map on the `[PDF x.y]` section numbers already in
REQUIREMENTS.md plus an English restatement, and say so in the README. (c) is the lowest-risk
default, but only the user can weigh whether redistributing Crehana's brief in a public repo is
appropriate. **Ask before writing the map.**

**Q2 — Push 289 commits, including the whole `.planning/` trail (227 tracked files).** This is the
project's deliberate differentiator (AIW-04) and is already committed, but pushing is the
irreversible moment it becomes public. Confirm.

**Q3 — The repository is already public.** Confirm that is intentional and should stay so; nothing
in this phase needs to change it.

**Q4 — The CI badge cannot be verified green before the push.** After the push: observe the run
(`gh run watch` / `gh run list`), then confirm the badge renders green in the README on GitHub.
Two human checks, not one.

**Q5 — Mermaid rendering.** Verify the diagrams visually on GitHub after the push; there is no
local renderer and adding one is out of scope.

**Q6 — The delivery email to `talento@crehana.com`.** Entirely the user's action. The plan should
end with a checkpoint that states the repo URL and stops.

**Q7 — The full DECISION_LOG table of contents.** §Gap 2 recommends a curated block over a 96-row
TOC. If the user wants the full TOC, it needs a generator and a sync gate — a fifth plan.

**Q8 — Does the rehearsal restart the developer's compose stack when it finishes?** Restoring it
is friendly; leaving it down is more predictable. Default recommendation: leave it down and print
the one command that brings it back.

## Recommended Plan Shape

Measured against the user's stated preference (phases feel slow; fewer, larger plans; light
ceremony; behaviour-based acceptance criteria and commands rather than grep-counts over prose; no
evidence/transcript files).

| Plan | Scope | Requirements | Acceptance |
|------|-------|-------------|------------|
| **07-01** | `ProblemResponse` schema + `problem_response()` helper + `ProblemAwareFastAPI` + 69 error legs across 5 routers + `openapi_tags` + `tests/architecture/test_openapi_completeness.py` | DOC-04 | `pytest tests/architecture/test_openapi_completeness.py`; `make lint typecheck test`; `/openapi.json` shows `application/problem+json` with a resolving `$ref` on all 69 legs and `application/json` on none of them |
| **07-02** | Two ambiguity ADRs (statuses/transitions; priority values), one follow-up ADR carrying the ADR-019 and line-3025 corrections plus this phase's own decisions, and the curated five-ambiguity block in the log header | DOC-03 | `make test` (the doc gate from 07-03 asserts the five ids resolve); `git diff --stat DECISION_LOG.md` shows additions only in the entry region |
| **07-03** | `README.md` (10 sections, the verified quickstart, the evidence map, the pending list), `tests/architecture/test_documentation_claims.py`, and the `Dockerfile` `COPY` line | DOC-01, DOC-02 | `make test` **and** `make docker-test` both green; the endpoint table equals `app.openapi()` by set equality |
| **07-04** | `AI_WORKFLOW.md`: 3 Mermaid diagrams, Phase 5+6 human/AI blocks, per-claim commit refs, the "What I Did Not Do" body, the Phase 7 incident entry | AIW-01, AIW-02 (+ AIW-03's open half) | `make test` (no `_To be completed in Phase 7._` marker survives; ≥3 mermaid blocks; phases 1-7 all named) |
| **07-05** | `scripts/clean-clone-rehearsal.sh` + `make rehearse`, run it, fix whatever it finds, badge, push, observe CI, record the CI coverage leg, tick ROADMAP/REQUIREMENTS/PROJECT/STATE | DOCK-05, AIW-05 | `make rehearse` exits 0 from a clean tree; `gh run list` shows success on the delivered commit; Q1-Q6 checkpoints answered |

Notes for the planner:
- **07-01 must precede 07-03** — the README's endpoint table and its gate both read the final
  OpenAPI shape.
- **07-05 must be last** and is blocking; it clones the committed tree, so every document must
  already be committed. Its re-run cost is low by design, so a gap found there is a fix-and-rerun,
  not a re-plan.
- 07-02 and 07-04 are independent of each other and of 07-01; they can be ordered for convenience.
- Four plans is achievable by folding 07-02 into 07-03 (both are pure documentation plus one gate).
  Five keeps the delivery checkpoints isolated from the writing, which is worth one extra plan
  boundary.
- Keep acceptance criteria as commands. Avoid "the README mentions X" phrasing — this repository's
  own ADR-060 retires grep-checkable prose claims, and §Don't Hand-Roll gives the mechanical
  alternative for each one.

## Sources

### Primary (HIGH confidence — executed or read in this session)
- `app.openapi()` of the real application, built via `create_app()` with injected `Settings` — 19 operations, 70 non-2xx legs, 69 without content, `tags is None`, 17 components, `OAuth2PasswordBearer`
- Four FastAPI `responses=` spellings probed against FastAPI 0.141.1, plus the `ProblemAwareFastAPI` subclass — the media-type and component-registration findings
- Live HTTP against `test-api-1`: `/health`, register, login, create list, create task ×2, status change, filtered listing (`completion_percentage: 50.0` over 2 tasks), `GET /users`, assign, the `task_assigned_email` log line, a 404 and a 409 problem+json body
- `DECISION_LOG.md` — 96 `## ADR-` headings enumerated; ADR-001/002/069/070/072/096 read in full; header lines 1-17
- `AI_WORKFLOW.md` — heading inventory, 51 dated entries, 0 mermaid blocks, 4 `Phase 7` markers, the Phase 1-4 human/AI blocks
- `src/taskmanager/domain/value_objects/task_status.py`, `task_priority.py` — the transition matrix and the three priorities
- `src/taskmanager/main.py`, `presentation/api/errors/problem.py`, `presentation/api/routers/task_lists.py`, `presentation/api/health.py`
- `Dockerfile` (all three stages), `docker-compose.yml`, `Makefile`, `pytest.ini`, `pyproject.toml`, `.flake8` refs, `.dockerignore`, `.gitignore`, `.env.example`, `scripts/init-env.sh`, `.github/workflows/ci.yml`
- `tests/unit/presentation/test_security_scheme.py`, `tests/integration/test_endpoint_totality.py`, `tests/architecture/*` — the gate idioms and `parents[2]` convention
- `infrastructure/config/database_url.py` — why CI's test DSN resolves correctly
- `git`: 332 commits, 289 unpushed, subject-prefix histogram, zero attribution trailers, `.env` never tracked, no key files, live secret absent from all refs
- `gh repo view Xch4rt/crehana-backend-test` → `"visibility":"PUBLIC"`; `gh run list` → 3 runs, all success, all Phase 1
- `pytest --collect-only` → 1101 tests, 1659 statements
- `docker compose ps` → `test-api-1` :8000 healthy, `test-db-1` :5432 healthy
- `.planning/`: REQUIREMENTS.md, ROADMAP.md (Phase 7 + Standing Rules), PROJECT.md, STATE.md (§Blockers), config.json, 06-REVIEW.md (CR/WR/IN inventory), 06-VERIFICATION.md, 06-04-SUMMARY.md §For Phase 7, 06-05-SUMMARY.md

### Secondary (MEDIUM confidence)
- https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams — fenced `mermaid` block; the only stated limitation is third-party plugin conflicts. Fetched this session
- WebSearch on GitHub Mermaid limitations (github.blog, community guides) — unsupported icon syntax, label hyperlinks/tooltips, emoji/extended-ASCII parsing, version drift. Not corroborated by GitHub's own docs

### Tertiary (LOW confidence — flagged in the Assumptions Log)
- Mermaid label-quoting and reserved-word rules (A1) — training knowledge only

## Metadata

**Confidence breakdown:**
- Gap inventory (all six criteria): **HIGH** — every claim read from or executed against the repository
- OpenAPI diagnosis and fix: **HIGH** — the census was computed and all four candidate spellings were executed
- Verified quickstart: **HIGH** — captured live against the running container
- Delivery / secret scan: **HIGH** — `git`, `gh` and `git grep` output
- Rehearsal design: **MEDIUM-HIGH** — every trap is a measured fact, but the script itself is unwritten and unrun
- Mermaid constraints: **MEDIUM** — GitHub's own docs are thin; the practical rules are community-sourced or assumed
- Brief-literal wording: **LOW** — the brief is not in the repository (Q1)

**Research date:** 2026-09-19
**Valid until:** 2026-10-19 for the stack facts; the inventory is valid until the next commit

## RESEARCH COMPLETE
