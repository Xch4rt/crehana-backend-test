"""The user directory on the wire: three members, and why they are not four.

`task_lists.py` states the rules this package follows and they are not restated
here. This module adds one model and one argument.
"""

from uuid import UUID

from pydantic import BaseModel

from taskmanager.application.dto.results import UserResult


class UserSummaryResponse(BaseModel):
    """`GET /users`: one entry of the assignment directory (ASGN-03, D-13).

    A second model rather than a reuse of `UserResponse`, on purpose. ASGN-03
    asks for "id, name, email" and nothing else, and the directory has no
    business publishing a `created_at` it was not asked for - a field published
    once is a field that has to keep being published. The two models having
    different member lists is the point: sharing one would make the directory's
    contract move every time the profile's did, and the profile is the shape
    register and `GET /auth/me` both promise.

    Declaration order is serialisation order, so the order below is ASGN-03's
    own wording rather than the profile's. The stored hash is absent here for
    the same reason it is absent from `UserResult`, and the copy below names
    each field explicitly so a later result field cannot arrive by default
    (T-5-08).
    """

    id: UUID
    full_name: str
    email: str

    @classmethod
    def from_result(cls, result: UserResult) -> "UserSummaryResponse":
        """Copy the three published fields, naming each one explicitly."""
        return cls(
            id=result.id,
            full_name=result.full_name,
            email=result.email,
        )
