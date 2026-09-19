---
phase: 05-auth-assignment-notifications
reviewed: 2026-09-19T18:48:29Z
depth: standard
files_reviewed: 47
files_reviewed_list:
  - .env.example
  - docker/entrypoint.sh
  - migrations/versions/0002_full_name_and_assignee_index.py
  - requirements.txt
  - src/taskmanager/application/dto/commands.py
  - src/taskmanager/application/dto/results.py
  - src/taskmanager/application/ports/repositories.py
  - src/taskmanager/application/ports/security.py
  - src/taskmanager/application/use_cases/access.py
  - src/taskmanager/application/use_cases/auth/__init__.py
  - src/taskmanager/application/use_cases/auth/authenticate.py
  - src/taskmanager/application/use_cases/auth/login.py
  - src/taskmanager/application/use_cases/auth/profile.py
  - src/taskmanager/application/use_cases/auth/register.py
  - src/taskmanager/application/use_cases/tasks/assign.py
  - src/taskmanager/application/use_cases/tasks/delete.py
  - src/taskmanager/application/use_cases/tasks/list_assigned.py
  - src/taskmanager/application/use_cases/tasks/update.py
  - src/taskmanager/application/use_cases/users/__init__.py
  - src/taskmanager/application/use_cases/users/list.py
  - src/taskmanager/domain/entities/task.py
  - src/taskmanager/domain/entities/user.py
  - src/taskmanager/domain/exceptions.py
  - src/taskmanager/domain/validation.py
  - src/taskmanager/infrastructure/config/settings.py
  - src/taskmanager/infrastructure/db/constraints.py
  - src/taskmanager/infrastructure/db/mappers.py
  - src/taskmanager/infrastructure/db/models.py
  - src/taskmanager/infrastructure/db/repositories/tasks.py
  - src/taskmanager/infrastructure/logging.py
  - src/taskmanager/infrastructure/notifications/__init__.py
  - src/taskmanager/infrastructure/notifications/logging.py
  - src/taskmanager/infrastructure/security/__init__.py
  - src/taskmanager/infrastructure/security/passwords.py
  - src/taskmanager/infrastructure/security/resources.py
  - src/taskmanager/infrastructure/security/tokens.py
  - src/taskmanager/main.py
  - src/taskmanager/presentation/api/actor.py
  - src/taskmanager/presentation/api/dependencies.py
  - src/taskmanager/presentation/api/routers/assignments.py
  - src/taskmanager/presentation/api/routers/auth.py
  - src/taskmanager/presentation/api/routers/task_lists.py
  - src/taskmanager/presentation/api/routers/tasks.py
  - src/taskmanager/presentation/api/routers/users.py
  - src/taskmanager/presentation/api/schemas/auth.py
  - src/taskmanager/presentation/api/schemas/tasks.py
  - src/taskmanager/presentation/api/schemas/users.py
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-09-19T18:48:29Z
**Depth:** standard
**Files Reviewed:** 47
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

Reviewed the 47 shipped files of Phase 5 (registration, login, the actor seam, assignment,
the assigned-to-me collection, the user directory, the logging notifier, revision 0002 and
the entrypoint). No structural (fallow) findings were supplied, so there is no structural
section.

Findings marked **[verified]** were reproduced by execution: the real application was built
in-process with `create_app(Settings(...))`, driven over `httpx.ASGITransport` against the
migrated `taskmanager_test` database, and the probe rows were deleted afterwards (the table
was confirmed empty again). No source file was modified.

What held up under attack, so it is not re-litigated below:

- **JWT decode policy.** The algorithm is pinned from configuration (`algorithms=[...]`),
  `sub`/`exp`/`iat` are required, expiry and `iat` are verified with zero leeway, a
  non-UUID subject is refused, and `InvalidKeyError` correctly stays outside the catch.
- **404-vs-403 in `access.py`.** The parent-list comparison runs before the assignee
  short-circuit in both guards, so an assignee addressing their task under the wrong list
  gets 404 and never a 403; a former assignee falls back to 404; the 403 is reachable on
  exactly one leg.
- **T-5-12 ordering in `AssignTask`.** `owned_task` runs before the assignee lookup, so
  `user_not_found` is reachable only by an established owner.
- **Post-commit notification.** The send is outside the `async with`, the values it needs
  are captured inside it, the broad `except Exception` does not swallow
  `CancelledError`, and the no-op leg returns before both the write and the send.
- **`for_update`.** All four owner-only write paths and the status path lock the task and
  only the task; the list is read plainly, so the documented lock ordering holds.
- **Revision 0002.** A constant `server_default` makes the `NOT NULL` add metadata-only on
  PostgreSQL 11+, the default is dropped in the same transaction, and the index name
  matches the naming convention. The test database is at `0002`.
- **Entrypoint.** `set -eu`, the heredoc probe's exit status aborts the script, only the
  exception class name is printed, and `exec` hands PID 1 to uvicorn.
- **Login password size.** Measured rather than assumed: a 1,000,000-character password
  costs 32 ms against 26 ms for a 16-character one, and 20 MB is refused with a 400 by the
  form parser. See IN-01 for the residual inconsistency.

The defects that remain are concentrated at two seams the phase's own documentation claims
are closed: what configuration is accepted at boot, and what reaches a log line.

## Critical Issues

### CR-01: The published placeholder is accepted as the JWT signing key, so the documented setup path runs on a public secret

**File:** `src/taskmanager/infrastructure/config/settings.py:51` (with `.env.example:45`)
**Issue:** [verified] `Settings(_env_file=".env.example")` boots: the placeholder
`replace-me-with-a-generated-secret` is 34 characters and the only check is
`min_length=32`. The comment at `settings.py:48-50` shows this was arranged on purpose
("`.env.example` 34 ... clears the new floor"). The module docstring at lines 3-6 promises
the opposite: a misconfigured process must fail at boot "rather than starting up on a
placeholder secret". `docker-compose.yml` documents the evaluator's whole setup as
`cp .env.example .env` once, so the one-command path signs every token with a string that
is published in the repository.

Failure scenario, using nothing but this phase's own endpoints: an attacker registers
(open route), calls `GET /api/v1/users` to read every account's `id`, and mints
`jwt.encode({"sub": "<victim id>", "iat": now, "exp": now + 1800}, "replace-me-with-a-generated-secret", "HS256")`.
`JwtTokenService.decode` accepts it (signature, algorithm and all three required claims
are valid) and `AuthenticateActor` finds the row. That is full impersonation of any user,
including deleting their lists. The user directory (D-13) is what makes the subject
trivially obtainable, so the two decisions compound.

**Fix:** Refuse the known placeholder at boot, which keeps the "one readable
ValidationError" property and costs the evaluator one documented command:
```python
from pydantic import Field, field_validator

_PLACEHOLDER_PREFIX = "replace-me"

    jwt_secret: str = Field(min_length=32)

    @field_validator("jwt_secret")
    @classmethod
    def _refuse_the_published_placeholder(cls, value: str) -> str:
        if value.startswith(_PLACEHOLDER_PREFIX):
            raise ValueError(
                "JWT_SECRET is still the .env.example placeholder; generate one with "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        return value
```
If a zero-edit `docker compose up` must survive, generate the secret in `make`/the
entrypoint when it is absent instead of shipping a fixed one, and record the trade-off in
an ADR. Either way, correct the `settings.py` docstring so it does not claim a guarantee
the code does not give.

## Warnings

### WR-01: A NUL byte in the login `username` is an unauthenticated 500, and the submitted value is written to the log

**File:** `src/taskmanager/presentation/api/routers/auth.py:200` -> `src/taskmanager/application/use_cases/auth/login.py:90`
**Issue:** [verified] `POST /api/v1/auth/login` with `username=a%00b@example.com` answers
`500 internal_error`. `form.username` is passed unvalidated into
`users.get_by_email`, psycopg refuses the NUL (`DataError: PostgreSQL text fields cannot
contain NUL`), nothing translates it, and it becomes the fixed 500. Register is protected
by `EmailStr`; login has no schema at all (by design), so nothing stands in for it. Two
consequences: (1) the one unauthenticated credential endpoint has a deterministic 500 any
fuzzer finds in seconds, and each hit writes a multi-kilobyte traceback, which is free log
amplification; (2) the logged SQLAlchemy message contains `[parameters: (...)]`, so the
attacker-supplied address is echoed into the log - confirmed in the captured output - which
contradicts the "submitted value is never echoed" posture of the 422 handler.
**Fix:** Treat an address that cannot exist as an address that does not exist, and keep the
timing equal. In `Login.execute`:
```python
email = command.email
if "\x00" in email or len(email) > User.EMAIL_MAX_LENGTH:
    await self._hasher.dummy_verify(command.password)
    raise AuthenticationError(_REFUSAL)
```
(or put the same guard in `SqlAlchemyUserRepository.get_by_email`, returning `None`). Add
an API test posting `%00` that asserts 401 and a body identical to the unknown-address one.

### WR-02: The stored Argon2 hash can reach a log line through SQLAlchemy's parameter dump

**File:** `src/taskmanager/infrastructure/logging.py:95-96` (rendering) and `src/taskmanager/application/use_cases/auth/register.py:95` (the statement); root cause at `src/taskmanager/infrastructure/db/engine.py:69`
**Issue:** [verified mechanism] The engine is created without `hide_parameters=True`, so
every `DBAPIError` stringifies as `... [SQL: INSERT INTO users ...] [parameters: (id,
email, full_name, '$argon2id$...', ...)]`. `handle_unexpected_error` logs `exc_info`, and
`JsonFormatter.format` renders it into the `exception` member. Reproduced by flushing a
`UserRow` that PostgreSQL rejects and formatting the resulting `DataError` with the
project's own `JsonFormatter`: the `$argon2id$` string is present in the JSON line. In
production the trigger is any non-`IntegrityError` failure of the register `INSERT` - a
dropped connection, a statement timeout, a failover. I found no request that forces it on
demand (the duplicate-email race is translated to a 409 and never logged), which is why
this is a Warning and not Critical, but T-5-04's claim that a hash "has no field to travel
in" is false for the log channel, and `docker compose logs` is readable by anyone with the
socket. WR-01 shows the same dump already firing with attacker-chosen input.
**Fix:**
```python
return create_async_engine(
    settings.database_url, pool_pre_ping=True, hide_parameters=True
)
```
and add a unit test that formats a `DBAPIError` raised from a users `INSERT` and asserts
the hash and the address are absent from the rendered line.

### WR-03: `jwt_algorithm` is an unvalidated free string, so a bad value boots cleanly and then fails every login

**File:** `src/taskmanager/infrastructure/config/settings.py:52` (consumed at `src/taskmanager/infrastructure/security/tokens.py:83-94` and `:114-119`)
**Issue:** [verified] `JWT_ALGORITHM=none`, `HS256 ` (trailing space, an easy `.env`
typo) and `RS256` all pass `Settings` validation. The first login then raises
`InvalidKeyError` / `NotImplementedError` from `jwt.encode` and answers 500 forever - the
exact "starts up and fails at the first authenticated request" outcome the settings
docstring says cannot happen. On the decode side the same misconfiguration surfaces as
`InvalidAlgorithmError`, a subclass of `InvalidTokenError`, so it is reported as a 401
that blames the caller - the very misattribution the `tokens.py` docstring (lines 29-35)
says the narrow catch exists to prevent. `HS512` boots too, and with the 32-character floor
PyJWT emits `InsecureKeyLengthWarning` on every encode and decode; the floor in
`settings.py` is correct for HS256 only.
**Fix:** The adapter signs with a shared secret and nothing else, so make the type say so:
```python
from typing import Literal

jwt_algorithm: Literal["HS256"] = "HS256"
```
(or `Literal["HS256", "HS384", "HS512"]` plus a `model_validator` that raises the secret
floor to 48/64 bytes to match). Update the `.env.example` comment accordingly.

### WR-04: A lone surrogate in `full_name` is an unauthenticated 500 on register

**File:** `src/taskmanager/domain/validation.py:84-92` (reached from `src/taskmanager/domain/entities/user.py:65`)
**Issue:** [verified] `POST /api/v1/auth/register` with the raw JSON body
`{"email": "...", "full_name": "A\ud800B", "password": "correct-horse"}` answers 500. The
value passes Pydantic's `str`, passes `require_text` (which refuses NUL and nothing else),
and psycopg then raises `UnicodeEncodeError: surrogates not allowed` while binding the
`INSERT`. `_refuse_nul` exists because "PostgreSQL's text types cannot hold NUL"; an
unpaired surrogate is the second value they cannot hold, and this phase put the first
string field guarded only by `require_text` on an unauthenticated route. An Argon2 hash is
computed before the failure, so each such request also costs the full hashing work. The
same root cause affects list names and task titles from Phase 4, but those require a token.
**Fix:** Widen the existing guard rather than adding a second one:
```python
def _refuse_unstorable(text: str, *, field: str) -> None:
    if "\x00" in text:
        raise ValidationError(f"{field} must not contain a NUL character.", details={"field": field})
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValidationError(
            f"{field} must be valid Unicode text.", details={"field": field}
        ) from error
```
and add an API test that posts `\ud800` and asserts the domain's 422.

## Info

### IN-01: Login never applies the password bound that `register.py` calls a DoS control

**File:** `src/taskmanager/application/use_cases/auth/login.py:96-98`
**Issue:** `register.py` justifies `require_password` as the bound that stops "a
128-kilobyte password" reaching the hasher (T-5-07); `Login` hands `command.password` to
`verify`/`dummy_verify` unbounded. Measured, this is not exploitable - Argon2 pre-hashes
the input, 1 MB costs +6 ms, and Starlette refuses the form at 20 MB - so the defect is
the inconsistency between the stated threat model and the code, not a live DoS.
**Fix:** Either short-circuit `len(password) > PASSWORD_MAX_LENGTH` to `dummy_verify` +
refusal, or correct the T-5-07 wording to say the bound is policy, not protection.

### IN-02: Token expiry is judged by the wall clock, not by the injected `Clock`

**File:** `src/taskmanager/infrastructure/security/tokens.py:82-90` vs `:114-119`
**Issue:** [verified] `iat`/`exp` are stamped from `self._clock`, but `jwt.decode`
compares them against PyJWT's own `datetime.now()`. A service built with a clock frozen
one hour ahead issues a token that its own `decode` refuses (`ImmatureSignatureError`);
one frozen an hour behind issues a "30-minute" token that is already expired. Harmless in
production where both are the system clock, but the constructor comment (lines 75-77)
advertises the frozen clock as the way to test time, and it only controls half of it.
**Fix:** Disable PyJWT's `verify_exp`/`verify_iat` and compare `payload["exp"]` and
`payload["iat"]` against `self._clock.now()` inside the same `try`, or document that the
clock governs issuance only.

### IN-03: Stale reference to an entrypoint step this phase deleted

**File:** `src/taskmanager/infrastructure/security/passwords.py:77-79`
**Issue:** The `verify` docstring cites "`docker/entrypoint.sh` step 2b" as the concrete
source of `password_hash = "!"`. Phase 5 removed that step, and the entrypoint header
(lines 20-21) says the old label is deliberately never spelled so that grepping for it
stays a gate; this file spells it. The `UnknownHashError` branch is still correct - rows
written by the old seed survive revision 0002 as "Unnamed", cannot log in, and remain
listed by `GET /users` and assignable.
**Fix:** Reword to "the Phase 4 demo seed, removed in Phase 5 (ADR-045)", and consider
noting in `DECISION_LOG.md` that upgraded volumes keep an un-loginable directory entry.

### IN-04: The first unknown-address login after boot is roughly twice as slow as every later one

**File:** `src/taskmanager/infrastructure/security/passwords.py:112-116`
**Issue:** `dummy_verify` builds its throwaway hash lazily, so the first call per process
pays hash + verify (about 60 ms by the module's own measurements) against about 25 ms for a
wrong-password login. It is a one-shot signal per process start, and concurrent first
calls each compute a hash (benign, last write wins), so the practical exposure is
negligible - but it is a measurable exception to the "indistinguishable in time" claim in
`CREDENTIALS_DESCRIPTION`.
**Fix:** Warm the cache off the request path - for example an `asyncio.create_task` on the
first login of either kind - or state the one-time exception where the claim is made.

---

_Reviewed: 2026-09-19T18:48:29Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
