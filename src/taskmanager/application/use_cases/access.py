"""One copy of ADR-008's rule: what an actor may not see reads as absent.

Eleven Phase 4 and Phase 5 use cases begin the same way - `get` the resource,
refuse it if it is `None` *or* not the actor's, then proceed. Written out per
use case that is eleven chances to forget the second half of the condition, and
the failure mode of forgetting it is silent: the endpoint works, the tests for
the owner pass, and only an actor who is not the owner discovers that ownership
was never checked. So the rule lives here, once, as three functions every use
case calls: `visible_task_list`, `visible_task` for anyone who may *see* a task,
and `owned_task` for the write paths only its list's owner may take.

**The deliberate asymmetry.** `visible_task_list` refuses with the list-shaped
not-found error - the only place in this module that class is raised, which is
why a grep for it finds one call site. The two task guards refuse with the
task-shaped one on *every* 404 leg, including a missing or foreign parent list,
and that is not an oversight in them. A task
route that answered a foreign parent with `task_list_not_found` would tell the
caller two things they are not entitled to know: that the task itself exists,
because the code differs from the one an absent task returns, and what the
parent list's id is, because the error carries it. ADR-008 requires exactly
those two cases to be indistinguishable, so the task route answers with the
identifier the caller already supplied, and with nothing else. The task is
checked *before* its list for the same reason: a wrong-list request must not
reveal whether the addressed list exists.

**How this module answers 403, and the claim that used to stand here (D-22).**
For the whole of Phase 4 this paragraph said the opposite. It was headed "Why
nothing here can answer 403", and it stated as a grep-checkable property that
the authorization failure class was named nowhere in this file, prose included -
so a reader could settle "this module cannot produce a 403" with a command
rather than with trust. The claim was true, and it was true for a reason worth
keeping in the record: Phase 4 was scoped to the list owner (D-04), the owner
was the only actor who could see a list or a task at all, and a rule with no
visible-but-forbidden case has nothing for a 403 to say. Every refusal was a
`*NotFoundError` because every refused caller was, as far as the system was
concerned, looking at nothing.

Phase 5 retires it. The assignee (D-01) is the first actor who can see a
resource they may not change, so `owned_task` below refuses them with
`AuthorizationError` while refusing everyone else exactly as `visible_task`
does. The replacement property is the same kind of thing, only counted rather
than absent: that class is raised on **one** leg, of **one** function, in this
file, so counting the raise statements that name it settles how many ways this
module can produce a 403 - and the answer is one. The mapping from that class
onto a 403 problem body needs nothing here; it is resolved by MRO walk in
`presentation/api/errors/mapping.py` and proven end to end by
`tests/unit/presentation/test_error_contract.py` (plan 02-04).

The paragraph was rewritten in the commit that falsified it, not afterwards.
A documented property this project asserts with a grep is worth exactly as much
as the discipline of retiring it out loud.

**Why a module of functions rather than a base class.** A `GuardedUseCase`
mixin would put the rule in an inheritance chain, where a subclass can override
it - and an override is invisible at the call site, which is where a reviewer
looks. A function call is grep-able (`grep -rn "visible_task" src/`), and a use
case that forgot to call one shows up in a diff as an absent line rather than as
a missing `if` inside a body nobody re-reads.

All three functions take an already-entered `UnitOfWork`. None opens the block,
none commits, and none reads a clock: the transaction boundary belongs to the
use case (D-17, ARC-08), and these are reads inside it. That holds on the 403
leg too - a refusal this module raises leaves the transaction exactly as it
found it, for the use case to end.

**`for_update` is how a write path says so (ADR-058, Phase 4 review CR-01).** A
use case that is about to `update` or `delete` what it loads passes
`for_update=True`, and the addressed resource then comes from the port's
`get_for_update`: the latest committed state, held against every other writer
until the unit of work ends. Without it, two overlapping requests validated
against the same stale copy, and the second persisted a status transition the
state machine forbids while erasing the first one's write. It is a keyword on
each of the three functions rather than a locking twin of each, because a twin
would be a second copy of the visibility rule - the one thing this module exists
to have exactly one of. (`owned_task` is not such a twin: it differs by which
failures it can produce, not by whether it locks.) The default is `False`, so a
read can never wait on a
writer by accident, and the flag is keyword-only, so a write path names it at the
call site where a reviewer will look for it.

Only the *addressed* resource is held. Both task guards, called with
`for_update=True`, hold the task and, when they consult the parent list at all,
read it plainly:
the list is consulted for ownership, not changed, and a rule of "a task's writer
never holds a list" is what keeps a list deletion, which reaches its tasks
through the cascade, from ever waiting on a writer that is waiting on it. The
assignee's leg does not consult it at all, so on that path there is no second
resource to reason about; see `visible_task` for why.
"""

from uuid import UUID

from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import (
    AuthorizationError,
    TaskListNotFoundError,
    TaskNotFoundError,
)


async def visible_task_list(
    uow: UnitOfWork, task_list_id: UUID, actor_id: UUID, *, for_update: bool = False
) -> TaskList:
    """The list, if this actor may see it; otherwise the answer an absent list gets.

    A list owned by someone else and a list that never existed are refused with
    the same class, the same code and the same `details` - the foreign owner's
    identifier never appears in either.

    `for_update=True` is for a caller about to change or delete the list; see the
    module docstring.
    """
    if for_update:
        task_list = await uow.task_lists.get_for_update(task_list_id)
    else:
        task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        raise TaskListNotFoundError(task_list_id)
    return task_list


async def visible_task(
    uow: UnitOfWork,
    task_list_id: UUID,
    task_id: UUID,
    actor_id: UUID,
    *,
    for_update: bool = False,
) -> Task:
    """The task, if it is in this list and this actor may see it (D-14, ADR-008).

    Two answers and four refusals. The owner of the parent list is answered, and
    so is the task's own assignee (D-01) - they are the two actors who may see
    it. The four refusals are unchanged: the task is absent; the task exists
    under another list; the parent list is gone; the parent list belongs to
    someone else and the caller is not the assignee either. All four raise
    `TaskNotFoundError(task_id)`, carrying only the identifier the caller
    supplied - see the module docstring for why the third and fourth do not get
    an error of their own.

    `for_update=True` is for a caller about to change or delete the task. It
    holds the task only; the parent list is read plainly on the owner's path and
    not at all on the assignee's.
    """
    if for_update:
        task = await uow.tasks.get_for_update(task_id)
    else:
        task = await uow.tasks.get(task_id)
    # D-14, and it comes first on purpose: a request naming the wrong list must
    # be refused before anything is looked up under that list, so the answer
    # cannot depend on whether the addressed list exists.
    if task is None or task.task_list_id != task_list_id:
        raise TaskNotFoundError(task_id)
    # D-01, and its placement is the whole design. The assignee sees the task
    # without ever seeing its list, so the list is not read on this leg: the
    # decision is already made, and issuing the statement anyway would put the
    # list's existence - and its owner - on the code path of a caller entitled
    # to know nothing about either. The saving is real (one `SELECT` here where
    # the owner's request costs two), but the reason is the disclosure, not the
    # statement count.
    #
    # It sits *after* the parent comparison above rather than before it, and
    # that ordering is ADR-050 outranking D-01. Placed first, an assignee who
    # addressed their task under the wrong list would be answered anyway, and
    # would thereby learn that the task lives under some other list - the one
    # bit a wrong-list request must not return.
    if task.assignee_id == actor_id:
        return task
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        raise TaskNotFoundError(task_id)
    return task


async def owned_task(
    uow: UnitOfWork,
    task_list_id: UUID,
    task_id: UUID,
    actor_id: UUID,
    *,
    for_update: bool = False,
) -> Task:
    """The task, if this actor owns the list it is in (D-03, ADR-008).

    The owner-only door. `UpdateTask`, `DeleteTask`, `AssignTask` and
    `UnassignTask` come through here; `GetTask` and `ChangeTaskStatus` come
    through `visible_task`, because an assignee may read their task and may
    advance its state machine. This function's whole reason for existing is the
    gap between those two sets: an actor who can see a resource and may not
    change it.

    One 403 and four 404s. The assignee is refused with `AuthorizationError`,
    because they can see this task and are being told only that they may not
    change it. Everyone else - a stranger, an absent task, a task under another
    list (ADR-050), an orphan whose parent is gone - is refused exactly as
    `visible_task` refuses them, with `TaskNotFoundError(task_id)`, so nothing
    about the list or its owner leaks out of the door that says "no".

    The refusal message names the **rule**, never the actor. A 403 tells a
    caller that they may not; who may is a different question, and answering it
    would hand an enumerating caller an identifier their request never
    contained.

    **Why a second function rather than `visible_task(..., require_owner=True)`.**
    A boolean at the call site reads as configuration - something tuned - when
    what is actually being chosen is which set of failures this request can
    produce. The two functions do not differ by a degree of strictness; they
    differ in that one of them can answer 403 and the other cannot, and that is
    worth a name a reviewer can grep for rather than an argument they have to
    trace. **And why not one function returning `(task, is_owner)`:** it would
    change every existing call site, and it would put the ADR-008 decision back
    into the use cases - eleven `if not is_owner:` branches, eleven chances to
    pick the wrong status code - which is the one thing ADR-055 exists to
    prevent.

    `for_update=True` holds the task and only the task, exactly as its sibling
    does; see the module docstring for the lock-ordering rule.
    """
    if for_update:
        task = await uow.tasks.get_for_update(task_id)
    else:
        task = await uow.tasks.get(task_id)
    # First, and for `visible_task`'s reason: a wrong-list request is refused
    # before anything under the addressed list is read, so the answer cannot
    # depend on whether that list exists - and cannot become a 403 for an
    # assignee who addressed their task under the wrong parent (ADR-050).
    if task is None or task.task_list_id != task_list_id:
        raise TaskNotFoundError(task_id)
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        # The one leg in this module that produces a 403, and the whole of the
        # difference between the two functions. The assignee reached a resource
        # they can see, so pretending it is absent would be a lie they can
        # already disprove with a `GET`; everyone else is told nothing.
        if task.assignee_id == actor_id:
            raise AuthorizationError("Only the list owner may change this task.")
        raise TaskNotFoundError(task_id)
    return task
