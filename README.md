# Task Manager API

[![CI](https://github.com/Xch4rt/crehana-backend-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Xch4rt/crehana-backend-test/actions/workflows/ci.yml)

A REST API for task lists and the tasks inside them, written for Crehana's Backend Technical
Challenge: FastAPI on Python 3.13, PostgreSQL through SQLAlchemy 2.0 async and psycopg 3, Alembic
migrations, JWT authentication, a simulated assignment invitation, and a layered architecture whose
boundaries are enforced by tests rather than by review. Everything below was executed against the
running container before it was written down, and the claims this file makes about the API, the
`make` targets and the decision log are checked by
[`tests/architecture/test_documentation_claims.py`](tests/architecture/test_documentation_claims.py)
on every test run.

<!-- rehearsal:begin -->

## Run it

Prerequisites: **Docker** (with Compose v2) and **make**. No Python, no database, nothing else.

```bash
make env
make up
```

`make env` writes an untracked `.env` with a freshly generated `JWT_SECRET`. Do not copy
`.env.example` by hand instead: the placeholder secret it publishes is refused at boot, on purpose
(ADR-084).

`make up` runs in the **foreground** so a failed migration or a refused connection is visible
rather than hidden. Leave it running and use a second terminal for everything below.

Then open **<http://localhost:8000/docs>**. There is no seeded account (ADR-075), so the first
thing to do there is `POST /api/v1/auth/register`, then click **Authorize** and enter that same
email in the `username` field — OAuth2 fixes the field name; this API's usernames are email
addresses.

## Run the tests

One command, no host Python and no host PostgreSQL:

```bash
make docker-test
```

It builds the test image, runs the whole suite on Python 3.13 against the compose database, and
ends on the coverage line. The gate is `--cov-fail-under=75` in `pytest.ini`; the suite currently
sits well above it, and the number it prints is the one to believe.

There is also a host path — `make install` then `make test` — described under
[Local development](#local-development). It needs a reachable PostgreSQL (`make up`) and it does
**not** skip the integration half when one is missing: it fails, once, with the URL and the remedy
(ADR-029). That is deliberate — a run that silently skipped every database test would report green
having exercised none of the persistence layer.

## 2-minute quickstart

With `make up` running in the other terminal. Needs `curl` and a POSIX shell.

```bash
API=http://localhost:8000

# 0. Is it up? The version field tells you which process answered.
curl -s $API/health
# {"status":"ok","checks":{"database":"ok"},"version":"0.1.0"}

# 1. Register. There is no seeded account - that is by design (ADR-075).
curl -s -X POST $API/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","full_name":"Ada Lovelace","password":"correct-horse-battery-staple"}'
# 201 {"id":"a3e833d0-...","email":"ada@example.com","full_name":"Ada Lovelace","created_at":"...Z"}

# 2. Log in. OAuth2 password form - the username field IS the email.
TOKEN=$(curl -s -X POST $API/api/v1/auth/login \
  -d 'username=ada@example.com&password=correct-horse-battery-staple' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
AUTH="Authorization: Bearer $TOKEN"
# {"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...","token_type":"bearer","expires_in":1800}

# 3. Create a task list.
LIST=$(curl -s -X POST $API/api/v1/task-lists -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Launch checklist","description":"Everything before the demo"}' \
  | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
# 201 {"id":"24f0c966-...","name":"Launch checklist","total_tasks":0,"completed_tasks":0,"completion_percentage":0.0}

# 4. Two tasks in it, one high and one medium.
TASK=$(curl -s -X POST $API/api/v1/task-lists/$LIST/tasks -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Write the README","priority":"high"}' \
  | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
curl -s -X POST $API/api/v1/task-lists/$LIST/tasks -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Record the decisions","priority":"medium"}' > /dev/null
# 201 {"id":"b0b95a64-...","status":"pending","priority":"high","assignee_id":null, ...}

# 5. Move one to completed, through the dedicated status endpoint.
curl -s -X PATCH $API/api/v1/task-lists/$LIST/tasks/$TASK/status -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"status":"completed"}'
# 200 {"status":"completed","completed_at":"2026-09-20T01:01:52.007236Z", ...}

# 6. The one worth reading: filter the view, keep the whole-list statistics.
curl -s "$API/api/v1/task-lists/$LIST/tasks?priority=high" -H "$AUTH"
# {"items":[ ...1 task... ],"total_tasks":2,"completed_tasks":1,"completion_percentage":50.0}
```

Step 6 is the interesting response. One item comes back, because the filter asked for the high
task only — and the counters still say `total_tasks: 2`, `completed_tasks: 1`,
`completion_percentage: 50.0`, because the percentage describes the **list**, never the filtered
view. The brief does not say which it should be; ADR-009 decides it, ADR-049 and ADR-054 refine it,
and one SQL aggregate computes it without an N+1.

Two refusals, to show the error contract. Every route answers errors as RFC 9457
`application/problem+json` documents with one shape — `type`, `title`, `status`, `detail`,
`instance`, `code`, and an optional `errors` — and no handler builds a body by hand:

```bash
# A list that does not exist, or that belongs to somebody else: both are 404 (ADR-008).
curl -s $API/api/v1/task-lists/00000000-0000-0000-0000-000000000000 -H "$AUTH"
# 404 application/problem+json
# {"type":"urn:taskmanager:problem:task_list_not_found","title":"Task list not found","status":404,
#  "detail":"No task list exists with identifier 000...0.","instance":"/api/v1/task-lists/000...0",
#  "code":"task_list_not_found","errors":{"task_list_id":"000...0"}}

# completed -> pending is the one forbidden move in the transition table (ADR-097).
curl -s -X PATCH $API/api/v1/task-lists/$LIST/tasks/$TASK/status -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"status":"pending"}'
# 409 {"type":"urn:taskmanager:problem:invalid_status_transition","title":"Invalid status transition",
#  "status":409,"detail":"A task cannot move from completed to pending.","instance":"...",
#  "code":"invalid_status_transition","errors":{"from":"completed","to":"pending"}}
```

And the simulated invitation, which is what the brief asks for instead of real email delivery. It
is sent through an `EmailNotifier` port **after** the transaction commits (ADR-070), and the
runtime adapter logs it structurally and sends nothing:

```bash
# Register a second account and hand it the task.
GRACE=$(curl -s -X POST $API/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"grace@example.com","full_name":"Grace Hopper","password":"correct-horse-battery-staple"}' \
  | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
curl -s -X PUT $API/api/v1/task-lists/$LIST/tasks/$TASK/assignee -H "$AUTH" \
  -H 'Content-Type: application/json' -d "{\"assignee_id\":\"$GRACE\"}"
docker compose logs api | grep task_assigned_email
# {"level": "INFO", "logger": "taskmanager.notifications", "message": "Task assignment invitation",
#  "event": "task_assigned_email", "to": "grace@example.com",
#  "subject": "You have been assigned a task: Write the README", "body": "...", "task_id": "b0b95a64-..."}
```

<!-- rehearsal:end -->

## Endpoint overview

Nineteen operations, grouped the way `/docs` groups them. This table is compared by **set
equality**, in both directions, against the operations the application publishes — a route added
without a row here, or a row here for a route that does not exist, fails a test.

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

`status` is not writable through the generic `PATCH` on a task. The dedicated
`PATCH .../status` endpoint is the only door, so the transition table cannot be bypassed (ADR-097).

## Requirement-to-evidence map

Keyed on the brief's own section numbers. **The brief itself is not redistributed in this
repository**, so the keys are the `[PDF x.y]` citations carried on every requirement in
[`.planning/REQUIREMENTS.md`](.planning/REQUIREMENTS.md), plus an English restatement of each line.
Every cell in the last column is a command or a test path — never prose.

| Brief | What it asks | Where it is | Proof |
|-------|--------------|-------------|-------|
| 1.a.i | CRUD on task lists | `src/taskmanager/presentation/api/routers/task_lists.py` | `tests/integration/api/test_task_lists.py`; quickstart step 3 |
| 1.a.ii | CRUD on the tasks inside a list | `src/taskmanager/presentation/api/routers/tasks.py` | `tests/integration/api/test_tasks.py`; quickstart step 4 |
| 1.a.iii | Change a task's status, valid transitions only | `src/taskmanager/domain/value_objects/task_status.py` | `tests/unit/domain/test_task_status.py`; quickstart step 5 |
| 1.a.iv | Filter tasks, and report a completion percentage | `src/taskmanager/application/use_cases/tasks/list.py` (ADR-009, ADR-049, ADR-054) | `tests/integration/api/test_tasks.py`; quickstart step 6 |
| 1.b.ii | JWT authentication: register, log in, protect every route | `src/taskmanager/presentation/api/routers/auth.py` | `tests/integration/api/test_auth.py` |
| 1.b.iii | Assign a task to a user, and expose the assignee | `src/taskmanager/presentation/api/routers/assignments.py` | `tests/integration/api/test_assignment.py`; `tests/integration/api/test_permission_matrix.py` |
| 1.b.iv | Send a simulated invitation email on assignment | `src/taskmanager/infrastructure/notifications/`, `application/use_cases/tasks/assign.py` | `tests/unit/infrastructure/test_notifier.py`; `tests/unit/application/test_assign_task.py`; quickstart step 7 |
| 2.a | Layered structure, use cases separated from the framework | `src/taskmanager/{domain,application,infrastructure,presentation}` | `make arch` (4 contracts); `tests/architecture/test_layer_boundaries.py` |
| 2.b | Strong typing with Pydantic at every boundary | `src/taskmanager/presentation/api/schemas/`, `infrastructure/config/settings.py` | `make typecheck`; `tests/unit/presentation/test_schemas.py` |
| 2.c | Custom exceptions and proper error handling | `src/taskmanager/domain/exceptions.py`, `presentation/api/errors/` | `tests/unit/presentation/test_error_contract.py`; `tests/architecture/test_error_contract_totality.py` |
| 2.d | Business validations | `src/taskmanager/domain/validation.py`, `application/use_cases/access.py` | `tests/unit/domain/test_validation.py`; `tests/integration/api/test_permission_matrix.py` |
| 2.e | Unit and integration tests | `tests/unit/`, `tests/integration/` | `make docker-test` |
| 2.f | Code formatted with black and isort | `pyproject.toml` | `make lint` |
| 2.g | Containerised with Docker | `Dockerfile`, `docker-compose.yml` | `make up`; `make docker-test` |
| 2.h | A record of the technical decisions | [`DECISION_LOG.md`](DECISION_LOG.md) | `tests/architecture/test_documentation_claims.py` |
| 3.a | Tests with pytest | `pytest.ini`, `tests/` | `make docker-test` |
| 3.b | Coverage of at least 75% | `pytest.ini` (`--cov-fail-under=75`) | `make docker-test`; `tests/architecture/test_coverage_configuration.py` |
| 3.c | A `pytest.ini` file holding the configuration | `pytest.ini` | `make docker-test`; `tests/architecture/test_coverage_configuration.py` |
| 4.a | flake8 passes with no errors | `.flake8` | `make lint` |
| 4.b | black and isort configured | `pyproject.toml`, `.pre-commit-config.yaml` | `make lint` |
| 4.c | A literal `.flake8` file | `.flake8` | `make lint` |
| 5.a | A `Dockerfile` and a `docker-compose.yml` | `Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh` | `make up` |
| 6 | A README covering setup, Docker and the tests | this file | `tests/architecture/test_documentation_claims.py` |

## Local development

The container is the source of truth; this is the fast edit loop beside it.

```bash
make install           # a .venv, the pinned dev requirements, an editable install, pre-commit
make env               # an untracked .env with a real JWT_SECRET - never copy .env.example by hand
make up                # the stack, including PostgreSQL on localhost:5432
make run               # uvicorn --reload on the host, against the compose database
```

The gates, each one word:

| Command | What it does |
|---------|--------------|
| `make lint` | black and isort in check mode, then flake8. Never rewrites a file |
| `make format` | isort then black, in that order. The only target that rewrites |
| `make typecheck` | mypy, strict, over `src` and `tests` |
| `make arch` | the import-linter contracts |
| `make test` | the whole suite with the coverage gate. Needs `make up` (ADR-029) |
| `make test-unit` | the no-database slice, in about a second and a half. A convenience, not a gate |
| `make docker-test` | the whole suite in the container. No host Python, no host database |
| `make break-check` | breaks `src/` five times on purpose and asserts the suite notices. A spot check run on demand, deliberately outside every gate path |
| `make down` | stops the stack, keeps the data volume |

`make install` also installs the pre-commit hooks, which run the formatters, flake8, mypy and
import-linter on every commit. They do **not** run pytest — `make test` before a commit is a rule
this project keeps by hand, and the Docker test stage and CI are what enforce it mechanically.

## Architecture in one screen

```
presentation  ->  infrastructure  ->  application  ->  domain
```

Four layers under `src/taskmanager/`, with imports pointing only downward. `domain` holds the
entities, the value objects and the error hierarchy, and imports **no third-party library at all** —
not even Pydantic. `application` holds one class per use case, depending only on `typing.Protocol`
ports, and names no web framework and no ORM. `infrastructure` implements those ports with
SQLAlchemy, psycopg, PyJWT and Argon2. `presentation` is the only layer that knows what HTTP is,
and the only one that may raise `HTTPException` — which, in practice, it never does either, because
every refusal travels as a `DomainError` to a single RFC 9457 handler.

None of that is a convention. [`.importlinter`](.importlinter) declares 4 contracts and
[`tests/architecture/test_layer_boundaries.py`](tests/architecture/test_layer_boundaries.py) runs
them inside pytest, so a violating import fails a test rather than a review. The other modules in
that directory gate the rest: that the domain is stdlib-only, that no repository ends a
transaction, that no router names `HTTPException`, that every use case and every endpoint is
reached by the suite, that every error leaf is published, that the coverage configuration has not
been softened, and that this README still agrees with the API.

## Decisions and AI workflow

[**`DECISION_LOG.md`**](DECISION_LOG.md) — 102 ADRs, each with context, the options that were
really on the table, the decision and its consequences. It is append-only: a later reversal is a
new entry naming the old one by id, never an edit. Its first screen is the shortcut — the brief's
five genuine ambiguities and where each is resolved (the completion percentage's scope, ADR-009;
the status values and the moves between them, ADR-097; the priority values and the default,
ADR-098; who may be assigned, ADR-069; what triggers the invitation, ADR-070), and then the five
decisions a reviewer is most likely to want an argument for.

[**`AI_WORKFLOW.md`**](AI_WORKFLOW.md) — how this was really built with AI assistance: three
diagrams of the actual loop, a phase-by-phase account of what the human decided versus what was
delegated, and an incident log of every mistake the AI made and what caught it, written as the work
happened rather than reconstructed afterwards. It ends with what was deliberately not done,
including the places where this project's own gates are weaker than they look.

## Pending, and what I would do next

**Scope agreed out of v1**, with requirement ids so you can tell it was decided rather than
forgotten: pagination and sorting on the list endpoints (API-01, ADR-043); multi-value filters such
as `?status=pending&status=in_progress` (API-02); an explicit invitation endpoint independent of
assignment (API-03); refresh tokens and revocation (AUTH-07); password reset and email verification
(AUTH-08).

**Three security properties conceded on purpose**, each with its own ADR, because a concession that
appears only in the code is indistinguishable from an oversight:

- Registration's 409 on a duplicate email **is** an account-enumeration oracle (ADR-066). The brief
  requires that 409 literally, so the requirement was chosen over the property. What bounds it: the
  error body carries no address in any spelling, and the login door stays indistinguishable.
- There is **no rate limiting, lockout or CAPTCHA on login** (ADR-067). Argon2's cost is an
  incidental throttle, not a control — and it is a denial-of-service surface in the other
  direction. The answer is a per-address or per-IP counter and a 429 taught to the single handler.
- `GET /api/v1/users` is **an email directory readable by any authenticated caller** (ADR-068).
  ASGN-03 asks literally for a way to discover an assignee id. The answer is to scope the directory
  to a team or tenancy, a concept this brief does not have.

**Seven gate-robustness warnings left open.** A code review after Phase 6 was asked to find where
this project's own gates can still pass for the wrong reason. It found two criticals and eleven
warnings; both criticals and four warnings were fixed, and seven are open and recorded as open in
`.planning/phases/06-test-hardening-coverage/06-REVIEW.md`, with WR-03 additionally named in
ADR-096: both halves of the assertion-quality gate are satisfiable by a re-read whose result is
discarded (WR-03); a marker guard that documents "exactly one" while enforcing "at least one"
(WR-05); the total half of endpoint totality skipping rather than failing under invocation drift
(WR-06); the error-contract gate resolving `raise`s by spelled name only (WR-07); the use-case
totality gate accepting a construction in dead code (WR-08); the derived transition test taking its
oracle from the code under test (WR-10); and two D-06 assertions that cannot fail (WR-11).

Publishing that list is the point. A project that names the ways its own gates can lie is making a
different claim than one that does not.
