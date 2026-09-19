---
phase: 05-auth-assignment-notifications
plan: 05
subsystem: infrastructure-security
tags: [argon2, pwdlib, pyjwt, jwt, adapters, composition-root, off-loop, tdd]

# Dependency graph
requires:
  - phase: 02-domain-error-contract
    provides: "AuthenticationError with code authentication_failed, and the MRO-walk mapping that already resolves it to 401"
  - phase: 02-domain-error-contract
    provides: "The PasswordHasher, TokenService and Clock Protocol ports, and the no-base-class/no-ABC adapter convention infrastructure/clock.py states"
  - phase: 03-persistence-migrations
    provides: "DatabaseResources and create_database_resources - the frozen typed container and builder shape this plan copies - and dependencies.py::_resources, the single narrowing"
  - phase: 05-auth-assignment-notifications
    provides: "05-01's jwt_secret floor of 32 bytes (D-26) and 05-02's dummy_verify on the PasswordHasher port (D-21)"
provides:
  - "PwdlibPasswordHasher: Argon2id through pwdlib, every call off the event loop via anyio.to_thread.run_sync, a non-Argon2 stored value answered False, one cached throwaway hash per instance"
  - "JwtTokenService: HS256 with the algorithm pinned from configuration, sub/exp/iat required, every token failure one indistinguishable AuthenticationError, InvalidKeyError left outside the catch"
  - "SecurityResources and create_security_resources(settings, clock): the frozen port-typed container plan 05-10 puts on the application's state object"
  - "Two more adapter port bindings in tests/unit/infrastructure/test_adapter_ports.py"
affects: [05-06, 05-07, 05-09, 05-10, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "An off-the-event-loop claim asserted by recording the offload call and its arguments, never by timing - the recorder delegates to the real run_sync, so the round trip still has to work"
    - "A library's stale docstring defended against by asserting the argument ORDER the worker thread received, because the transposed call and the adapter's own except clause cancel into a silently broken application"
    - "A no-I/O promise made falsifiable: socket and open are replaced with objects that raise, and the builder is called between them"
    - "Dataclass field annotations pinned by reading them back with typing.get_type_hints, because nothing at runtime and nothing in mypy distinguishes a port annotation from the adapter that satisfies it"

key-files:
  created:
    - src/taskmanager/infrastructure/security/__init__.py
    - src/taskmanager/infrastructure/security/passwords.py
    - src/taskmanager/infrastructure/security/tokens.py
    - src/taskmanager/infrastructure/security/resources.py
    - tests/unit/infrastructure/test_passwords.py
    - tests/unit/infrastructure/test_tokens.py
    - tests/unit/infrastructure/test_security_resources.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-05-tdd-red.txt
  modified:
    - requirements.txt
    - tests/unit/infrastructure/test_adapter_ports.py

key-decisions:
  - "The plan's own alg=none construction cannot be built: jwt.encode(claims, secret, algorithm='HS256', headers={'alg':'none'}) prepares the key for the HEADER's algorithm and raises InvalidKeyError at encode time in PyJWT 2.14.0. The real forgery - and what an attacker sends - is jwt.encode(claims, None, algorithm='none'), which is what both the test table and the corrected acceptance run use"
  - "The off-loop proof records the callable and the argument tuple run_sync received and delegates to the real implementation, so it doubles as the transposed-argument guard: a green round trip alone cannot distinguish a correct verify(password, hashed) from a transposed call that raises UnknownHashError and is caught into False"
  - "The throwaway password behind the dummy hash is generated with secrets.token_urlsafe(32) rather than written as a literal - one step beyond the plan, which only forbids a hard-coded encoded Argon2 string, so no string in the file looks like a credential at all (T-5-03)"
  - "InvalidKeyError, PyJWTError and leeway=0 are all argued in prose without being spelled, because the plan's own grep criteria require those three literals to appear 1, 0 and 0 times respectively - the 01-03 prose-not-literal convention applied to counters the plan wrote"
  - "The REFUSED table's expired token is forged directly rather than minted through the adapter, because the table is a module-level constant and there is no event loop at import; the adapter's own past-dated mint is a separate test, so the FrozenClock mechanism is still proven"
  - "The two port bindings went to test_adapter_ports.py and not to the behaviour suites, even though Task 1's <behavior> lists the PasswordHasher binding - that module's docstring already argues that asserting one binding twice reads as two problems, and Task 3's <action> owns the file"
  - "SecurityResources' field annotations are pinned with get_type_hints: mypy accepts the adapter types too (they satisfy the ports), so this is the only place the port-not-adapter decision can be asserted rather than merely intended"
  - "Nothing was wired into the composition root. create_app, the application state object and dependencies.py are untouched, and the module docstring names 05-10 as the owner - grep -c 'create_app|app.state' over resources.py prints 0"
  - "No requirement ticks taken. AUTH-02 and AUTH-04 are named in this plan's frontmatter and 05-16 is their last claimant; what ships here is two adapters and a container with no use case and no route above them"

patterns-established:
  - "Recording the offload: an async recorder that appends (callable, args) and awaits the real anyio.to_thread.run_sync, so a concurrency claim is asserted structurally and an argument-order claim comes free"
  - "A refusal table keyed by what is wrong with the input, whose keys become the parametrised ids, plus a separate test asserting every refusal's message is identical - six library exceptions, one answer"

requirements-completed: []

# Metrics
duration: 14min
completed: 2026-09-19
---

# Phase 5 Plan 05: The Two Credential Adapters and Their Container Summary

**The two places this project's security rests on a library rather than on its own code now sit
behind the Phase 2 ports: Argon2id runs off the event loop and answers `False` to a stored value
it did not write, PyJWT verifies with the algorithm pinned from configuration and turns six
different library failures into one indistinguishable `AuthenticationError`, and both travel to a
request inside one frozen, port-typed container built once.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-09-19T15:25Z
- **Completed:** 2026-09-19T15:39Z
- **Tasks:** 3 of 3
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments

- `PwdlibPasswordHasher` implements `PasswordHasher` structurally — no base class, no ABC, mypy
  strict as the gate — over `PasswordHash.recommended()`. The constructor takes an optional
  `PasswordHash` so a test substitutes a cheap Argon2 configuration; the shipped object's cost
  parameters were never lowered, and exactly one test pays the real 37 ms/26 ms round trip.
- Both hashing calls go through `anyio.to_thread.run_sync`, so Argon2's deliberate cost leaves the
  event loop and shares Starlette's own threadpool and `CapacityLimiter` rather than opening a
  second, invisible pool (AUTH-04, T-5-07). **No package was added**: `anyio` is a hard transitive
  of the pinned Starlette, and `requirements.txt` now records that as a comment — `grep -c anyio`
  prints 1 and `grep -cE '^anyio=='` prints 0.
- The off-loop claim is asserted by *recording the offload*, not by timing anything. The recorder
  appends `(callable, args)` and awaits the real `run_sync`, so the round trip still has to work
  and the recorded argument tuple `(PASSWORD, digest)` doubles as the guard against pwdlib's stale
  `recommended()` docstring, which still shows `verify(hash, password)`.
- `verify` catches `UnknownHashError` narrowly and answers `False`.
  `grep -cE 'except (Exception|BaseException)'` prints 0. The case is concrete: the Phase 4 demo
  seed wrote `password_hash = "!"`, so a developer database still holding that row would have
  answered a login attempt with a 500.
- `dummy_verify` (D-12, D-21) builds one throwaway hash per instance, lazily, from
  `secrets.token_urlsafe(32)`. Both rejected alternatives — hashing at import time, and a
  hard-coded encoded Argon2 literal — are named in the method docstring, and the generated seed
  means no string in the file reads as a credential at all (T-5-03).
- `JwtTokenService` pins the accepted algorithm from configuration and never reads it off the
  token (RFC 8725 §2.1), and requires `sub`, `exp` and `iat`. `grep -c 'algorithms='` prints
  exactly 1.
- Its `except` clause catches token failures, `ValueError` and `TypeError` — nothing wider.
  `InvalidKeyError` is named in prose as the one deliberately left outside: a misconfigured server
  must become the fixed 500, never a 401 blaming a caller who did nothing wrong (T-5-02).
- Nine forgeries — unsigned, foreign-signed, expired, missing `iat`, missing `sub`, missing `exp`,
  a non-UUID subject, `""` and `"garbage"` — are one parametrised table, and a tenth test asserts
  every refusal carries the identical message, empty details, and no fragment of any token
  (D-11, T-5-04).
- The expired proof needs no `sleep` and no `freezegun`: a `FrozenClock` two hours in the past
  mints a token whose `exp` is ninety minutes behind the real clock PyJWT compares against. That
  asymmetry — the issuing side reads the injected clock, the verifying side cannot — is why the
  adapter takes a `Clock` at all.
- `SecurityResources` is a frozen slotted dataclass whose two fields are annotated with the
  **ports**, pinned by reading the annotations back with `get_type_hints`, and
  `create_security_resources(settings, clock)` reads `jwt_secret`, `jwt_algorithm` and
  `jwt_expire_minutes` exactly once. `grep -c get_settings` over the module prints 0 (RC-3).
- Building the container performs no I/O, and that is falsifiable rather than decorative: `socket`
  and `open` are replaced with objects that raise and the builder is called between them.
- Coverage over the three new modules is **100% with no missing lines**, and the suite went from
  695 to **725** passing at **100.00%** over 1273 statements, with no `pragma: no cover` and no
  coverage `omit` anywhere under `src/taskmanager/`. `tests/unit` plus `tests/architecture` went
  from 493 to **523**. `make arch` reports **4 kept, 0 broken**, and `jwt`, `pwdlib` and `anyio`
  are imported by exactly two modules, both under `infrastructure/security/`.

## Task Commits

1. **Task 1: `PwdlibPasswordHasher` — Argon2id off the event loop** — `8228d2d` (feat)
2. **Task 2: `JwtTokenService` — HS256 with the algorithm pinned** — `5f3b4d7` (feat)
3. **Task 3: `SecurityResources`, the typed container the composition root builds once** —
   `2889293` (feat)

## Files Created/Modified

- `src/taskmanager/infrastructure/security/__init__.py` — **created**, empty, like
  `infrastructure/db/repositories/__init__.py`.
- `src/taskmanager/infrastructure/security/passwords.py` — **created.** 20 statements. The
  adapter, plus the two library behaviours that produce a quiet wrong application rather than a
  loud one: the argument order pwdlib's own docstring gets wrong, and Argon2's cost being a
  stalled server rather than a slow request under asyncio.
- `src/taskmanager/infrastructure/security/tokens.py` — **created.** 22 statements. The adapter,
  the RFC 8725 argument for pinning, the required-claims argument, and the `_refused`-voiced
  paragraph on why the catch is narrow.
- `src/taskmanager/infrastructure/security/resources.py` — **created.** 10 statements. The frozen
  container, the builder, and the docstring paragraph explaining the divergence from `get_clock`
  so it does not read as an inconsistency (D-27, RC-3).
- `tests/unit/infrastructure/test_passwords.py` — **created.** 10 tests: one real-cost round trip
  bound to `User.PASSWORD_HASH_MAX_LENGTH`, the `$argon2id$` marker, per-hash salting, the two
  `verify` answers, the `"!"` and `""` refusals, `dummy_verify`'s real work, the once-per-instance
  cache asserted by identity, and the offload recording.
- `tests/unit/infrastructure/test_tokens.py` — **created.** 13 collected: the round trip, the
  string-`sub`/`iat`/`exp` shape read off the encoded token, the nine-row refusal table, the
  past-dated mint, and the identical-message test.
- `tests/unit/infrastructure/test_security_resources.py` — **created.** 5 tests: field names and
  port annotations, frozen and slotted, both halves populated from `Settings`, the no-socket and
  no-file proof, and one hasher per application with two builds giving different objects.
- `tests/unit/infrastructure/test_adapter_ports.py` — **modified.** The two credential bindings,
  a docstring paragraph stating that a port binding has one home and the behaviour suites are
  about behaviour only, and "four times" replaced by "once per adapter" so the count cannot drift
  again.
- `requirements.txt` — **modified.** A comment recording `anyio` as directly imported and
  deliberately unpinned, in the "arrives transitively" convention `requirements-dev.txt`'s header
  already states for `coverage` and `grimp`.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-05-tdd-red.txt` — **created.**
  The observed RED for all three tasks.

## Decisions Made

- **The plan's `alg=none` construction cannot be built, and the corrected one is stronger.**
  `jwt.encode(claims, secret, algorithm="HS256", headers={"alg": "none"})` — the form Task 2's
  acceptance snippet uses — raises `InvalidKeyError` at *encode* time in PyJWT 2.14.0, because the
  library prepares the key for the header's algorithm and `alg=none` requires a `None` key. The
  token an attacker actually sends is unsigned, and `jwt.encode(claims, None, algorithm="none")`
  builds exactly that. Both the test table and the acceptance run use the corrected form.
- **The off-loop test is also the transposition test.** pwdlib's `recommended()` docstring has
  shown `verify(hash, password)` since 0.2, and a transposed call raises `UnknownHashError` —
  which this adapter catches and turns into `False`. The two mistakes cancel into an application
  where every login silently fails and nothing reports an error, so a green round trip is not
  evidence. The recorder asserts the pair the worker thread received, in order.
- **The dummy password is generated, not written.** The plan forbids a hard-coded encoded Argon2
  string; generating the plaintext seed from `secrets` as well means there is no literal in the
  file that looks like a credential to anyone grepping the repository, at zero cost, since the
  value is never compared to anything.
- **Three literals are argued in prose without being spelled.** `InvalidKeyError` had to appear at
  least once, `PyJWTError` exactly zero times and `leeway=` exactly zero times, per the plan's own
  criteria — so "widening the catch to the library's own base exception class" and "a leeway of
  zero" are written out longhand. The 01-03 prose-not-literal convention, applied to counters the
  plan itself wrote.
- **The refusal table's expired row is forged, and the adapter's own mint is a separate test.**
  `REFUSED` is a module-level constant, so there is no event loop at import time to `await`
  `issue_access_token` on. The row is a correctly-signed token with past `iat`/`exp`, and
  `test_a_token_minted_two_hours_ago_has_already_expired` is where the adapter itself produces one
  from a `FrozenClock` — so the mechanism the plan asks for is proven, just not inside the table.
- **Both port bindings live in `test_adapter_ports.py`.** Task 1's `<behavior>` lists the
  `PasswordHasher` binding and Task 3's `<action>` assigns the file; the tie goes to Task 3,
  because that module's docstring already argues — about `Clock` — that asserting one binding in
  two places makes a single port change look like two problems.
- **`get_type_hints` is what pins the port annotations.** Both adapters satisfy their ports, so
  annotating the fields with the concrete classes would type-check and run identically. The only
  thing it would break is the reason the container exists, which is a claim no other test could
  make.
- **Nothing was wired in.** `create_app`, the application's state object and `dependencies.py` are
  untouched, and `resources.py`'s docstring names 05-10 as the owner of that step.
- **No requirement ticks taken.** AUTH-02 and AUTH-04 are named in this plan's frontmatter; 05-16
  is their last claimant, and what ships here is two adapters and a container with no use case and
  no route above them. The eighth consecutive plan in this phase to make the same call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 2's acceptance snippet raises before it can assert anything**

- **Found during:** Task 2
- **Issue:** the snippet's third statement,
  `jwt.encode({...}, 'a'*32, algorithm='HS256', headers={'alg':'none'})`, raises
  `jwt.exceptions.InvalidKeyError: When alg = "none", key value must be None.` PyJWT 2.14.0 reads
  the algorithm from the supplied header and prepares the key for *that* algorithm, so the form
  cannot produce a token at all. The plan's `<interfaces>` behaviour table lists the `alg=none`
  row as verified against a decoded token, which it is — the row is right and only the
  construction is wrong.
- **Fix:** built the unsigned token as `jwt.encode(claims, None, algorithm="none")` and ran the
  acceptance snippet in that corrected form, with the resulting token added to the loop of refused
  inputs (the plan's snippet assigned `forged` and then never used it). Verified the decode leg
  raises `InvalidAlgorithmError`, which is a token failure and therefore inside the catch.
- **Files modified:** `tests/unit/infrastructure/test_tokens.py` (the `unsigned()` helper and its
  docstring)
- **Commit:** `5f3b4d7`

### Criteria met in substance rather than literally

- **`grep -rln "jwt\b" src/taskmanager/application src/taskmanager/domain prints nothing`** — it
  prints one path, `application/ports/security.py`. The match is a docstring sentence naming `jwt`
  as one of the modules `.importlinter`'s `application-framework-free` contract forbids in that
  layer; it is prose written by plan 05-02, not an import, and it predates this plan. The property
  the criterion is about is enforced by that contract and is green: `make arch` reports 4 kept, 0
  broken, and `jwt`, `pwdlib` and `anyio` are imported only by the two modules under
  `infrastructure/security/`.
- **`grep -c "to_thread"` and `grep -c "UnknownHashError"` on `passwords.py`** print 4 and 4
  against floors of 3 and 2. The extra matches are the module docstring and the `verify`
  docstring, which argue the two library behaviours; both criteria are "at least", so both are met
  literally as well.

## Threat Flags

None. The two adapters implement the mitigations the plan's threat register assigns them
(T-5-01, T-5-02, T-5-03, T-5-04, T-5-07, T-5-16) and introduce no network endpoint, no file
access and no schema change. T-5-SC's "no package is added" disposition holds: `anyio` was already
installed as a hard transitive of the pinned Starlette and is recorded as a comment rather than a
new pin.

## Quality Gates

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | black 148 files unchanged, isort clean, flake8 clean |
| Types | `make typecheck` | Success: no issues found in 148 source files |
| Architecture | `make arch` | Contracts: 4 kept, 0 broken |
| Tests | `make test` | 725 passed, coverage **100.00%** over 1273 statements (gate 75%) |

## Handoff Notes

- **Plan 05-10 owns the wiring.** `create_security_resources(settings, clock)` is ready to be
  called in the composition root and stored beside the database container; `dependencies.py` then
  narrows it once, in `_resources`' shape, and no provider needs a per-request settings lookup.
  Nothing in this plan touched `main.py` or `dependencies.py`.
- **`JwtTokenService` needs a `Clock` at construction, and the composition root has one.** It must
  be the port, not `SystemClock` spelled inline — `get_clock` already produces the right thing.
- **Plans 05-07 and 05-09 get `dummy_verify` for free**, but only if the hasher they receive is
  the container's. A `PwdlibPasswordHasher()` constructed per request would pay 37 ms on every
  login for the cached hash, which is the exact cost D-21 exists to control (D-27).
- **Do not add a `leeway`.** The expired-token proof is a boundary, not a tolerance; a non-zero
  value would make that test measure the tolerance instead.
- **The 05-06 additions to `test_adapter_ports.py`** should follow the same rule this plan
  applied: one binding, one home, and the behaviour suite stays about behaviour.
- The Phase 6 coverage divergence (host 3.14 vs container 3.13, PEP 649) was not re-measured here;
  `make docker-test` was not run for this plan, and the existing blocker in `STATE.md` still owns
  it.

## Self-Check: PASSED

All four created source modules, all three created test modules, the evidence file and this
summary exist on disk; the three task commits `8228d2d`, `5f3b4d7` and `2889293` are all in
`git log`.
