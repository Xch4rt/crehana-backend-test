"""One copy of ADR-008's rule: what an actor may not see reads as absent.

Eleven Phase 4 and Phase 5 use cases begin the same way - `get` the resource,
refuse it if it is `None` *or* not the actor's, then proceed. Written out per
use case that is eleven chances to forget the second half of the condition, and
the failure mode of forgetting it is silent: the endpoint works, the tests for
the owner pass, and only an actor who is not the owner discovers that ownership
was never checked. So the rule lives here, once, as two functions every use case
calls.

**The deliberate asymmetry.** `visible_task_list` refuses with the list-shaped
not-found error - the only place in this module that class is raised, which is
why a grep for it finds one call site. `visible_task` refuses with the
task-shaped one on *every* leg, including a missing or foreign parent list, and
that is not an oversight in the second function. A task
route that answered a foreign parent with `task_list_not_found` would tell the
caller two things they are not entitled to know: that the task itself exists,
because the code differs from the one an absent task returns, and what the
parent list's id is, because the error carries it. ADR-008 requires exactly
those two cases to be indistinguishable, so the task route answers with the
identifier the caller already supplied, and with nothing else. The task is
checked *before* its list for the same reason: a wrong-list request must not
reveal whether the addressed list exists.

**Why nothing here can answer 403.** Phase 4 is scoped to the owner (D-04), and
the owner is the only actor who can see a list or its tasks at all - so there is
no visible-but-forbidden case left for a 403 to answer, and every refusal here
is a `*NotFoundError`. Phase 5 adds the assignee capabilities, and with them the
first resource an actor can see but may not change; the 403 leg belongs to that
phase, and the mapping from the authorization failure class Phase 2 defined onto
a 403 problem body is already proven end to end by
`tests/api/test_error_contract.py` (plan 02-04). That class is deliberately not
named anywhere in this file, prose included, so "this module cannot produce a
403" is something a grep over it settles rather than something a reader has to
take on trust - the same convention the Makefile follows for the tool
invocations it warns against.

**Why a module of functions rather than a base class.** A `GuardedUseCase`
mixin would put the rule in an inheritance chain, where a subclass can override
it - and an override is invisible at the call site, which is where a reviewer
looks. A function call is grep-able (`grep -rn "visible_task" src/`), and a use
case that forgot to call one shows up in a diff as an absent line rather than as
a missing `if` inside a body nobody re-reads.

Both functions take an already-entered `UnitOfWork`. Neither opens the block,
neither commits, and neither reads a clock: the transaction boundary belongs to
the use case (D-17, ARC-08), and these are reads inside it.

**`for_update` is how a write path says so (ADR-058, Phase 4 review CR-01).** A
use case that is about to `update` or `delete` what it loads passes
`for_update=True`, and the addressed resource then comes from the port's
`get_for_update`: the latest committed state, held against every other writer
until the unit of work ends. Without it, two overlapping requests validated
against the same stale copy, and the second persisted a status transition the
state machine forbids while erasing the first one's write. It is a keyword on the
two existing functions rather than a second pair of them, because a second pair
would be a second copy of the visibility rule - the one thing this module exists
to have exactly one of. The default is `False`, so a read can never wait on a
writer by accident, and the flag is keyword-only, so a write path names it at the
call site where a reviewer will look for it.

Only the *addressed* resource is held. `visible_task(..., for_update=True)` holds
the task and reads its parent list plainly: the list is consulted for ownership,
not changed, and a rule of "a task's writer never holds a list" is what keeps a
list deletion, which reaches its tasks through the cascade, from ever waiting on
a writer that is waiting on it.
"""

from uuid import UUID

from taskmanager.application.ports.unit_of_work import UnitOfWork
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.exceptions import TaskListNotFoundError, TaskNotFoundError


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

    Four refusals, one answer. The task is absent; the task exists under another
    list; the parent list is gone; the parent list belongs to someone else. All
    four raise `TaskNotFoundError(task_id)`, carrying only the identifier the
    caller supplied - see the module docstring for why the third and fourth do
    not get an error of their own.

    `for_update=True` is for a caller about to change or delete the task. It
    holds the task only; the parent list is read plainly on every path.
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
    task_list = await uow.task_lists.get(task_list_id)
    if task_list is None or task_list.owner_id != actor_id:
        raise TaskNotFoundError(task_id)
    return task
