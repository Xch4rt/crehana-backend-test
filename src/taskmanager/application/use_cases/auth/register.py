"""Create one account, refusing an address that already has one (AUTH-01).

The body is `use_cases/task_lists/create.py`'s, with one step in front of the
transaction and one deliberate absence.

**The policy runs first, and outside the block.** The domain's password guard
is called before anything expensive happens, because the alternative is letting an
unauthenticated request choose how much Argon2 work this server does: a
128-kilobyte password is a free denial of service if the hasher sees it before
the bound does (T-5-07). The check is the domain's - `domain/validation.py`
owns D-10's 8..128 rule, spelled once - and this module calls it rather than
restating the numbers, so a policy change never has two homes (Phase 2 D-04).

**The hashing happens outside the transaction too.** Argon2id is deliberately
slow - measured at 25-37 ms in `05-RESEARCH.md` - and a connection held across
it is a pool slot spent on arithmetic. Nothing read inside the block depends on
the hash, so there is nothing to gain by moving it in.

**No email or name validation here, and one name guard that is not a second
copy of one.** `User.__post_init__` trims both, lowers the address and applies
every length bound, for the reason `create.py` gives at length: a limit that
exists in two layers is a defect rather than redundancy. The `require_text`
call below calls that same domain helper - it does not restate a rule - and it
is there only to move the question in front of the hashing, exactly as the
password guard is (Phase 5 review WR-04).

**On the duplicate-address pre-check.** It is a convenience, not the guard -
the same argument `create.py` makes about list names, and CLAUDE.md's
persistence rule states the division in so many words: "an `IntegrityError` is
translated inside the adapter into the `DomainError` the use case's pre-check
would have raised". Two registrations can both pass the check below and only
one can pass `uq_users_email_lower`, so the adapter's translation is the
backstop for that race while the pre-check is what produces a clean refusal in
the ordinary case, before anything is written. Both roads lead to one class,
and `test_register_user.py` drives down both.

**D-23, stated rather than glossed.** Answering 409 at all tells an
unauthenticated caller that an address is registered, which is an
account-enumeration oracle. AUTH-01 requires the conflict, so the oracle is
**accepted and bounded**, never described as mitigated: `EmailAlreadyRegisteredError`
takes no argument, so neither the body nor any log line built from it repeats
the address, and `GET /users` already discloses every address in the system to
any authenticated caller - so what remains is a disclosure to callers who have
not registered yet. `Login` concedes nothing of the kind, which is D-12's
separate and much stronger requirement.

The identifier comes from `uuid4()` here and the timestamps from the `Clock`
port. Neither is a field of the command, so a request cannot choose an id, a
creation date, or - since those are the only fields - anything else about the
account beyond the three it supplies (T-5-09).
"""

from uuid import uuid4

from taskmanager.application.dto.commands import RegisterUserCommand
from taskmanager.application.dto.results import UserResult
from taskmanager.application.ports.clock import Clock
from taskmanager.application.ports.security import PasswordHasher
from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import EmailAlreadyRegisteredError
from taskmanager.domain.validation import require_password, require_text


class RegisterUser:
    """Registers one account from an unauthenticated request (AUTH-01)."""

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        # The unit of work first, then the non-transactional ports as separate
        # arguments (D-17) - the constructor of `CreateTaskList`, with the
        # hasher added because this is the one write that needs one.
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def execute(self, command: RegisterUserCommand) -> UserResult:
        """Create the account, or raise the conflict that describes the refusal."""
        # Before anything expensive, and before the transaction: see the module
        # docstring. The returned value is deliberately not bound - the
        # plaintext is already in hand and the call is here for its refusal.
        require_password(command.password, field="password")
        # The same question `User.create` asks below, asked before the work an
        # unauthenticated caller can demand (T-5-07): a name the database
        # cannot hold used to cost a full Argon2 hash before it was refused.
        require_text(
            command.full_name, field="full_name", max_length=User.FULL_NAME_MAX_LENGTH
        )
        hashed = await self._hasher.hash(command.password)
        async with self._uow:
            # Read once and handed down, so `created_at` and `updated_at` are
            # the same instant by construction rather than by coincidence.
            now = self._clock.now()
            # The pre-check. `get_by_email` folds case on both sides, so this
            # asks the question `uq_users_email_lower` will ask - anything else
            # would be an endpoint stricter or laxer than its own database.
            if await self._uow.users.get_by_email(command.email) is not None:
                raise EmailAlreadyRegisteredError()
            user = User.create(
                user_id=uuid4(),
                email=command.email,
                full_name=command.full_name,
                password_hash=hashed,
                now=now,
            )
            await self._uow.users.add(user)
            await self._uow.commit()
        # Mapped outside the block, and mapped to a type with no field a hash
        # could travel in: the result describes a transaction already made
        # durable, and describes it in four fields (T-5-04).
        return UserResult.from_entity(user)
