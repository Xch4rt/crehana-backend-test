"""The marker a PATCH command carries where the client sent no field at all.

`None` cannot serve. It is a legal *value* for every nullable PATCH field -
Phase 4 D-05 makes an explicit JSON null the way a client clears `description`
or `due_date` - so a command that used `None` for both meanings could not tell
"leave this alone" from "empty this", and the two produce different rows.

A bare `_UNSET = object()` distinguishes the two at runtime but gives mypy
nothing to narrow on: `str | object` collapses to `object`, so a use case that
forgot its guard and passed the sentinel into `Task.rename` would type-check and
fail in production. A single-member enum is the form the typing ecosystem
settled on precisely because mypy treats `value is not UNSET` as a literal
narrowing - inside the guard `str | Unset` is `str`, and omitting the guard is
an `arg-type` error at the call site rather than a runtime surprise.

A per-field `Patch[T]` wrapper (`provided: bool`, `value: T`) narrows correctly
too, and was rejected for cost rather than for correctness: it makes every read
`command.field.value` behind `command.field.provided`, and it adds a second DTO
vocabulary beside the frozen dataclasses of ADR-020 for no behaviour the enum
does not already give.

The sentinel stops at the application boundary, and that is a decision rather
than an omission. Declaring it in the Pydantic request schemas was executed and
measured (04-RESEARCH Pattern 2): it publishes a `_Unset` component into
`/openapi.json` as part of the field's `anyOf`, and it splits the explicit-null
refusal into two error entries, at `body.title.str` and `body.title.enum[_Unset]`,
neither of which a client can act on. The boundary therefore keeps plain
`X | None = None` fields and the router converts `model_fields_set` into this
marker on the way in.
"""

from enum import Enum
from typing import Final


class Unset(Enum):
    """The single-member enum whose one member means "field not provided"."""

    TOKEN = "unset"


UNSET: Final = Unset.TOKEN
