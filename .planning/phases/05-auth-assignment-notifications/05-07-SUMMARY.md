---
phase: 05-auth-assignment-notifications
plan: 07
subsystem: application-auth-use-cases
tags: [auth, use-cases, dto, enumeration, argon2, tdd, d-11, d-12, d-23]

# Dependency graph
requires:
  - phase: 05-auth-assignment-notifications
    provides: "require_password and the PASSWORD_MIN/MAX_LENGTH constants in domain/validation.py (05-01)"
  - phase: 05-auth-assignment-notifications
    provides: "PasswordHasher.dummy_verify on the port and FakePasswordHasher.dummy_verifications (05-02)"
  - phase: 05-auth-assignment-notifications
    provides: "User.full_name, its keyword-only create signature and the 0002 revision (05-03)"
  - phase: 03-persistence
    provides: "SqlAlchemyUserRepository.add's uq_users_email_lower translation into the argument-less EmailAlreadyRegisteredError"
  - phase: 04-task-lists-tasks
    provides: "The use-case shape: uow-first constructor, one async with, one commit on the success path, result mapped outside the block"
provides:
  - "RegisterUserCommand, LoginCommand, AuthenticateActorCommand, GetProfileCommand - the first three commands in the project with no actor_id, each arguing its own exemption"
  - "UserResult (four public fields, no password_hash) and AccessTokenResult (bearer, seconds)"
  - "RegisterUser: policy before hashing, hashing before the transaction, one commit, both duplicate roads"
  - "Login: one refusal constant for both legs, and the throwaway-hash work on the leg that has none of its own"
  - "AuthenticateActor: token -> profile with the row confirmed on every call (D-11)"
  - "GetProfile: AUTH-05's own use case, so ADR-044's UUID actor seam stays unchanged"
  - "AuthenticationError.REFUSAL: the one 401 message, defaulted on the class so no layer spells it"
  - "FakeUserRepository.add refusing a duplicate address like the index does, and FakePasswordHasher recording hash and verify calls"
affects: [05-08, 05-09, 05-10, 05-11, 05-13, 05-16]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A convention gate with an enumerated exemption set, where the set is also derived back off the data the gate runs over - so an exemption is a two-place edit and never an omission"
    - "One error message owned by the exception class as a defaulted argument, so two layers that must answer identically have no string to drift apart"
    - "A test-module repository subclass that overrides the lookup to reproduce a race the fakes cannot otherwise reach (the 04-05/05-04 counting-subclass precedent, inverted: blinded rather than counted)"
    - "Indistinguishability asserted comparatively - two refusals from one fixture, compared on class, code, message and details - never by catching the class twice"
    - "Cost equalisation asserted as a port call count, never as elapsed time"

key-files:
  created:
    - src/taskmanager/application/use_cases/auth/__init__.py
    - src/taskmanager/application/use_cases/auth/register.py
    - src/taskmanager/application/use_cases/auth/authenticate.py
    - src/taskmanager/application/use_cases/auth/profile.py
    - src/taskmanager/application/use_cases/auth/login.py
    - tests/unit/application/test_register_user.py
    - tests/unit/application/test_authenticate_actor.py
    - tests/unit/application/test_profile.py
    - tests/unit/application/test_login.py
    - .planning/phases/05-auth-assignment-notifications/evidence/05-07-tdd-red.txt
  modified:
    - src/taskmanager/application/dto/commands.py
    - src/taskmanager/application/dto/results.py
    - src/taskmanager/domain/exceptions.py
    - src/taskmanager/infrastructure/security/tokens.py
    - tests/unit/application/fakes.py
    - tests/unit/application/test_dtos.py

key-decisions:
  - "AuthenticationError now owns its message as a ClassVar REFUSAL defaulted into __init__, and infrastructure/security/tokens.py dropped its private _REFUSAL copy. D-11 requires a junk token and a token whose subject has no row to produce the same body; with a constant in each layer they agreed only until somebody edited one, and neither component now spells the message at all. Two files outside the plan's files_modified were touched to do it"
  - "FakeUserRepository.add compares against `stored` directly rather than calling its own get_by_email. The index is what refuses a duplicate in PostgreSQL, and PostgreSQL does not consult a repository method first - the delegating form was written, observed passing the race-backstop test vacuously, and replaced"
  - "FakePasswordHasher gained `hashed` and `verifications` recorders beside 05-02's dummy_verifications. T-5-07 ('the hasher was never called') and D-12's per-leg call counts are not assertable without them, and the alternative - a stopwatch - is a flake"
  - "COMMAND_CASES now holds all fourteen commands while the actor-first gate runs over a derived subset. The plan asks for all four new commands in the table and three of them break the rule that table's third test asserts; an exemption set named in the test module and re-derived from the table keeps the convention a gate for the other eleven"
  - "Login's refusal is its own constant, not AuthenticationError's default. The two endpoints answer different questions - 'is this token usable?' versus 'are these credentials right?' - and each one's two legs are made identical by a single object in a single module; sharing one string across both would tie two unrelated messages together for no property"
  - "GetProfile exists rather than a widened actor seam, and the cost is named in its docstring: GET /auth/me issues two SELECTs against users. ADR-044 fixes CurrentActor as a UUID and changing it would rewrite every router signature in the project"
  - "Two grep criteria met by rewording prose rather than by changing code - `SecretStr` prints 0 and `require_password` prints 2 - the 01-03 prose-not-literal convention applied to counters the plan itself wrote"
  - "No requirement tick taken. AUTH-01, AUTH-02, AUTH-04 and AUTH-05 are all in this plan's frontmatter and 05-16 is the last claimant; nothing here has a route above it yet, and a tick taken from a use case's existence rather than from an endpoint's behaviour proves nothing. The ninth consecutive Phase 5 plan to make the same call"

patterns-established:
  - "The blinded repository subclass: a fake whose lookup answers None however many rows it holds, which is the state two interleaved transactions produce and the only way a dictionary-backed suite can reach an adapter's constraint-translation leg"
  - "An exemption set that is declared and simultaneously derived, so the declaration cannot silently stop matching the data"

requirements-completed: []

# Metrics
duration: 16min
completed: 2026-09-19
---

# Phase 5 Plan 07: The Auth Use Cases Summary

Registration, login and token resolution exist as behaviour with no HTTP and no database above
them — and the two properties that matter, D-12's indistinguishable refusal and D-11's confirmed
row, are now assertions rather than paragraphs.

## Performance

- **Duration:** ~16 min
- **Started:** 2026-09-19T15:50Z
- **Completed:** 2026-09-19T16:06Z
- **Tasks:** 3 of 3
- **Files modified:** 16 (10 created, 6 modified)

## Accomplishments

- **Four commands and two results, all frozen and slotted (ADR-020).** `RegisterUserCommand` has
  exactly three fields — no `id`, no `created_at`, no role — so the mass-assignment surface
  T-5-09 describes is refused as a *set*, asserted as a whole field list rather than one absent
  name at a time.
- **Three commands carry no `actor_id`, and the convention survived them.** The module docstring
  said every command names the actor first; it now names the three exceptions and says why each
  is an exception to the field and not to the rule. `test_dtos.py` holds the same three in an
  exemption set, runs the gate over everything else, and *derives the set back off the table* —
  so a fourth actor-less command fails the suite instead of quietly joining the exemption.
- **`UserResult` has no field a password hash could travel in**, asserted against
  `dataclasses.fields` rather than `hasattr`: the field list is what a response schema maps from,
  and `hasattr` would pass against a result keeping the hash under another name (T-5-04).
- **`RegisterUser` refuses an over-long password before the hasher exists.** D-10's bound runs
  first and outside the transaction, and the test asserts `hasher.hashed == []` — the port was
  never called, so an unauthenticated request cannot choose how much Argon2 work this server does
  (T-5-07). The lengths come from `PASSWORD_MIN_LENGTH`/`PASSWORD_MAX_LENGTH`, so a policy change
  moves the test with it.
- **Both duplicate roads are driven down.** The pre-check produces the clean 409 in the ordinary
  case; a `_BlindUserRepository` whose lookup answers `None` however many rows it holds reproduces
  the interleaving CLAUDE.md's persistence rule describes, and the repository refuses anyway. An
  implementation that dropped either road passes one of the two tests and fails the other.
- **D-23 is written down as accepted, never as mitigated.** The 409 is an enumeration oracle
  AUTH-01 requires; what is done instead is bounded and stated — the error takes no argument, and
  a test asserts the address appears in neither the message nor `details`.
- **`Login`'s two refusals are one refusal.** A single module constant is referenced by both
  `raise` statements, and the comparative test produces both from one fixture and compares class,
  `code`, `str(error)` **and** `details`. Catching `AuthenticationError` twice — which is what a
  laxer suite would do — passes against exactly the implementation D-12 forbids.
- **The unknown-address leg pays the same work.** `dummy_verify` is called there and `verify` is
  not; on the wrong-password leg it is the other way round; on success `verify` runs exactly once
  and nothing else does. Three tests, all reading the fake's recorders, because a timing assertion
  in a unit suite is a flake and the port call is the property (measured 23.4 ms vs 23.6 ms in
  05-RESEARCH; the real cost is paid by one module, `test_passwords.py`).
- **`AuthenticateActor` confirms the row on every call (D-11)**, proved by a counting repository
  asserting `reads == [ACTOR_ID, ACTOR_ID]` across two calls — a value assertion alone passes
  against an implementation that trusted the `sub` claim and never looked. A deleted subject's
  live token is refused with a body indistinguishable from a junk token's (T-5-15), and that is
  now true *by construction*: neither the adapter nor the use case spells the message.
- **Every read path leaves `commits == 0` and `rollbacks == 1`.** `commits == 0` alone is equally
  true of a transaction nobody closed, which is the failure the second half catches.
- Coverage over all four new modules is **100% with no missing lines and no partial branches**
  (`register.py` 25 statements, `authenticate.py` 16, `profile.py` 13, `login.py` 24). The suite
  went from 744 to **785** passing at **100.00%** over 1402 statements, with no `pragma: no cover`
  and no coverage `omit` anywhere under `src/taskmanager/`. `tests/unit` plus `tests/architecture`
  went from 542 to **583**. `make lint`, `make typecheck`, `make arch` (4 contracts kept,
  **0 broken**) and `make test` are all green.

## Task Commits

1. **Task 1: the four auth commands and the two auth results** — `e671f71` (feat)
2. **Task 2: `RegisterUser`, `AuthenticateActor` and `GetProfile`** — `e56da62` (feat)
3. **Task 3: `Login`, and the refusal that says nothing (D-12)** — `4a5c1c0` (feat)

## Files Created/Modified

- `src/taskmanager/application/dto/commands.py` — **modified.** Four commands under an `Auth`
  banner, and a new paragraph in the module docstring naming the three exceptions to its own
  actor-first rule rather than leaving the rule false.
- `src/taskmanager/application/dto/results.py` — **modified.** `UserResult` with its four fields
  and the argument for the fifth it does not have, and `AccessTokenResult` with both wire-format
  obligations commented.
- `src/taskmanager/application/use_cases/auth/__init__.py` — **created**, empty, like
  `use_cases/tasks/__init__.py`.
- `src/taskmanager/application/use_cases/auth/register.py` — **created.** 25 statements. The
  docstring argues five things: why the policy runs first, why hashing is outside the
  transaction, why no validation lives here, why both duplicate roads exist, and D-23.
- `src/taskmanager/application/use_cases/auth/authenticate.py` — **created.** 16 statements.
  States D-11 and its price — one extra indexed `SELECT` per authenticated request, re-measured
  by 05-13.
- `src/taskmanager/application/use_cases/auth/profile.py` — **created.** 13 statements. Names the
  two `SELECT`s `GET /auth/me` costs as the price of leaving ADR-044's seam type alone.
- `src/taskmanager/application/use_cases/auth/login.py` — **created.** 24 statements. One
  `_REFUSAL` constant, one `_TOKEN_TYPE`, the transaction left before any hashing, and T-5-08
  recorded as accepted with the README's future-work list named as its home.
- `src/taskmanager/domain/exceptions.py` — **modified.** `AuthenticationError` gained
  `REFUSAL: ClassVar[str]` and a defaulted `message` parameter, with the D-11 argument in its
  docstring.
- `src/taskmanager/infrastructure/security/tokens.py` — **modified.** Three lines: the private
  `_REFUSAL` is gone, replaced by a comment recording where the message went and why, and
  `decode` raises the argument-less form.
- `tests/unit/application/fakes.py` — **modified.** `FakeUserRepository.add` refuses a duplicate
  address; `FakePasswordHasher` records `hashed` and `verifications`.
- `tests/unit/application/test_dtos.py` — **modified.** Four commands in `COMMAND_CASES`, the
  exemption set and its derivation test, the mass-assignment field-list test, and five tests over
  the two new results.
- `tests/unit/application/test_register_user.py` — **created.** 8 tests, including the blinded
  repository and the parametrized policy pair.
- `tests/unit/application/test_authenticate_actor.py` — **created.** 5 tests, including the
  counting repository and the comparative refusal.
- `tests/unit/application/test_profile.py` — **created.** 3 tests.
- `tests/unit/application/test_login.py` — **created.** 9 tests: the eight behaviours the plan
  lists plus a third call-count leg for the success path.
- `.planning/phases/05-auth-assignment-notifications/evidence/05-07-tdd-red.txt` — **created.**
  Three RED runs, appended after each was observed: collection errors and exit status 2, three
  times.

## Decisions Made

1. **The 401 message moved onto the exception class.** `AuthenticationError.REFUSAL`, defaulted
   into `__init__`, and the token adapter's private copy deleted. This is the deviation below,
   and it is also the plan's own requirement made structural: "the **same** message the port
   raises" cannot be a property of two independently typed strings.
2. **`Login` keeps a message of its own.** The two endpoints answer different questions, and
   D-12's requirement is that *login's two legs* match — which one constant in one module
   guarantees. Sharing the token wording would couple two messages that have no reason to move
   together.
3. **The fake refuses duplicates against `stored`, not through its own lookup.** See the
   deviation: the delegating form made the race-backstop test pass vacuously.
4. **Two recorders added to the password fake.** `hashed` for T-5-07, `verifications` for D-12's
   per-leg counts. Both are the same argument 05-02 made for `dummy_verifications`.
5. **The actor-first gate keeps an enumerated exemption**, re-derived from the command table so
   the two cannot drift. The alternative — dropping the three from `COMMAND_CASES` — would have
   left them outside the immutability and slots gates as well, which is a worse trade.
6. **`GetProfile` is a second use case.** Named cost: two `SELECT`s on `/auth/me`. Named benefit:
   eleven router signatures unchanged.
7. **The plan's "`uuid4()` inside `User.create`" is imprecise and was not followed literally.**
   `User.create` takes `user_id` as a keyword argument — Phase 2 D-11/D-12 put identifier
   generation in the application layer — so `RegisterUser` calls `uuid4()` at the call site,
   exactly as `CreateTaskList` does. The property the plan wanted (the id never comes from the
   command) holds, and a test asserts two registrations differ.
8. **No requirement tick.** AUTH-01, AUTH-02, AUTH-04 and AUTH-05 all name 05-16 as last
   claimant. Nothing here is reachable over HTTP until 05-11.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] D-11's "same generic 401 body" had no mechanism, so
one was built — in two files this plan does not list**

- **Found during:** Task 2
- **Issue:** The plan says `AuthenticateActor` must raise `AuthenticationError` "with the **same**
  message the port raises for a bad token". The port's implementation
  (`infrastructure/security/tokens.py`) held that message in a private module constant,
  `_REFUSAL = "Could not validate credentials."`, which the application layer cannot import — the
  layer contract forbids it, and rightly. Retyping the string in `authenticate.py` would have
  produced two constants in two layers that agree only until somebody edits one, and *nothing*
  would have failed at that point: `test_tokens.py` asserts the adapter's refusals share **one**
  message without asserting what it is, and no test compared the two components.
- **Fix:** The message moved onto `AuthenticationError` itself as `REFUSAL: ClassVar[str]`,
  defaulted into `__init__`, with the argument in the class docstring. Both components now write
  `raise AuthenticationError()` and neither spells the message. `tokens.py` lost its constant and
  gained a comment recording where it went.
- **Files modified:** `src/taskmanager/domain/exceptions.py`,
  `src/taskmanager/infrastructure/security/tokens.py` — neither is in this plan's
  `files_modified`, and both are the minimum needed to make the plan's own sentence true.
- **Commit:** `e56da62`

**2. [Rule 1 — Bug] The duplicate-refusing fake delegated to its own lookup, so the race-backstop
test passed against nothing**

- **Found during:** Task 2
- **Issue:** `FakeUserRepository.add` was first written as
  `if await self.get_by_email(user.email) is not None: raise ...`. The test that exercises the
  adapter's constraint leg does so with a subclass that overrides `get_by_email` to answer `None`
  — which is exactly what an interleaved transaction sees. The override therefore disabled the
  refusal too, and the test failed with `DID NOT RAISE`.
- **Fix:** `add` scans `stored` directly for a case-folded match. This is also the more faithful
  model: PostgreSQL does not consult a repository method before enforcing `uq_users_email_lower`.
  The comment in the fake says so.
- **Files modified:** `tests/unit/application/fakes.py`
- **Commit:** `e56da62`

**3. [Rule 2 — Missing critical functionality] The password fake recorded only `dummy_verify`**

- **Found during:** Task 2
- **Issue:** T-5-07's assertion is "the hasher recorded zero `hash` calls" and D-12's is "one leg
  called `verify` once and `dummy_verify` zero times". `FakePasswordHasher` recorded neither
  `hash` nor `verify`, so both claims were unassertable except by timing — which the plan itself
  forbids.
- **Fix:** `hashed: list[str]` and `verifications: list[tuple[str, str]]`, documented in the
  class docstring beside the existing `dummy_verifications` paragraph.
- **Files modified:** `tests/unit/application/fakes.py`
- **Commit:** `e56da62`

**4. [Rule 3 — Blocking issue] Adding the three actor-less commands to `COMMAND_CASES` would have
broken the actor-first gate**

- **Found during:** Task 1
- **Issue:** The plan requires all four new commands in `COMMAND_CASES`, and that table feeds
  three parametrized tests — one of which asserts `fields[0].name == "actor_id"`. Three of the
  four cannot satisfy it.
- **Fix:** `ACTORLESS_COMMANDS` names the three; the gate runs over `ACTOR_FIRST_CASES`, derived
  by filtering; and `test_only_the_three_unauthenticated_commands_omit_the_actor` computes the
  actor-less set *from the table* and asserts it equals the declaration. The immutability and
  slots gates still run over all fourteen.
- **Files modified:** `tests/unit/application/test_dtos.py`
- **Commit:** `e671f71`

### Criteria met in substance rather than literally

- **`grep -c "SecretStr" commands.py` printed 1 before rewording.** The `RegisterUserCommand`
  docstring explained why the password is *not* that type, which is exactly the passage the
  counter forbids. Reworded to "Pydantic's redacting secret-string type"; the criterion now
  prints `0` literally. The 01-03 prose-not-literal convention.
- **`grep -c "require_password" register.py` printed 3 before rewording**, the third being the
  module docstring's explanation of the call. Reworded to "the domain's password guard"; the
  criterion now prints `2`, the import and the call, exactly as the plan intends.
- **The plan's per-module coverage command cannot be run as written.** `pytest.ini`'s `addopts`
  already carry `--cov=taskmanager --cov-fail-under=75`, so adding `--cov=<one module>` measures
  the whole package while running a subset and the command exits non-zero at ~71%. Run with
  `--cov-fail-under=0` appended; the module rows are what the criterion is about and all four
  show `100%` with no missing lines. The same class of finding as 02-04's `--include` artifact.
- **`-k duplicate` collects 3, not 1.** Both duplicate tests plus the refusal-content one match;
  the criterion asks for at least one.

## Known Stubs

None. Every module shipped here is called by its own tests and by nothing else yet — the routes
that will call them are 05-11's — but nothing is a placeholder, and no value is hard-coded where
a real one belongs.

## Threat Flags

None. Every surface this plan adds was already in the plan's `<threat_model>`: the two
unauthenticated commands (T-5-06, T-5-08, T-5-09), the login lookup (T-5-05) and the token-to-
identity resolution (T-5-15). No new network endpoint, file access or schema change was
introduced — the migration this phase needs shipped in 05-03.

## Issues for Future Phases

- **05-11 owes the seconds/minutes wiring.** `Login` takes `expire_minutes: int` and multiplies;
  `create_app` must pass the same `jwt_expire_minutes` value it builds `JwtTokenService` with, or
  `expires_in` will describe a lifetime the token does not have.
- **05-13 must move the statement counts.** D-11's confirmation read is now implemented, so
  ADR-054's measured 1 and 3 become 2 and 4 for any test going through the real actor path
  (D-20). The invariance is the property; the number moving is this plan being paid for.
- **05-16 owes two ADRs from this plan:** D-23's accepted enumeration oracle (it must say
  *accepted and bounded*, never mitigated), and the `AuthenticationError.REFUSAL` relocation,
  which changed a domain class and an infrastructure adapter to make D-11 structural.
- **Phase 7's README owes T-5-08.** No rate limiting and no lockout on login; Argon2's ~25 ms
  floor is an incidental throttle, not a control.

## Self-Check: PASSED

All ten created files exist on disk; all three task commits (`e671f71`, `e56da62`, `4a5c1c0`)
are in `git log`.
