"""Every D-12 constraint name, written down exactly once.

These strings are not documentation: D-13 keys the `IntegrityError` ->
`DomainError` translation on them, matching `psycopg`'s
`diag.constraint_name` against the constants below. A rename applied to the
schema but not here does not fail a type check and does not fail a lint run -
it silently stops matching, so a duplicate list name stops being LIST-06's 409
and becomes a 500 with an unhandled `IntegrityError` behind it.

The rejected alternative is a string literal at each of the three call sites
(model, migration, translation). It is the same argument `problem.py` makes
about hand-assembled error bodies: two copies written a week apart drift in
spelling, and the "one shape" claim quietly stops being true. Here the drift is
worse than cosmetic, because the third reader is an exception handler.

Most of these names are *produced* by `base.NAMING_CONVENTION` rather than
passed to SQLAlchemy; this module is the assertion of what that convention must
render, which `tests/unit/infrastructure/test_models.py` checks against the
compiled DDL. `UQ_USERS_EMAIL_LOWER` is the exception - an expression index has
no column name to interpolate, so `models.py` reads that constant directly.
"""

from typing import Final

PK_USERS: Final[str] = "pk_users"
PK_TASK_LISTS: Final[str] = "pk_task_lists"
PK_TASKS: Final[str] = "pk_tasks"

# Case-sensitive per-owner list-name uniqueness (D-12): `UNIQUE (owner_id, name)`,
# the race-proof backstop behind LIST-06's use-case pre-check.
UQ_TASK_LISTS_OWNER_ID_NAME: Final[str] = "uq_task_lists_owner_id_name"
# The deliberate contrast: a unique index over `lower(email)`, because `User`
# canonicalises the address on construction and the index defends that rule.
UQ_USERS_EMAIL_LOWER: Final[str] = "uq_users_email_lower"

FK_TASK_LISTS_OWNER_ID_USERS: Final[str] = "fk_task_lists_owner_id_users"
FK_TASKS_TASK_LIST_ID_TASK_LISTS: Final[str] = "fk_tasks_task_list_id_task_lists"
FK_TASKS_ASSIGNEE_ID_USERS: Final[str] = "fk_tasks_assignee_id_users"

CK_TASKS_STATUS: Final[str] = "ck_tasks_status"
CK_TASKS_PRIORITY: Final[str] = "ck_tasks_priority"
CK_TASKS_COMPLETED_AT_MATCHES_STATUS: Final[str] = (
    "ck_tasks_completed_at_matches_status"
)

IX_TASKS_TASK_LIST_ID: Final[str] = "ix_tasks_task_list_id"
# D-25, added by revision 0002: the index behind
# `GET /api/v1/tasks/assigned-to-me` and behind every ON DELETE SET NULL the
# `tasks.assignee_id` foreign key performs. `models.py` argues why it exists
# where it refuses two others.
IX_TASKS_ASSIGNEE_ID: Final[str] = "ix_tasks_assignee_id"
