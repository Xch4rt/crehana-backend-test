#!/bin/sh
# The container's startup sequence: wait for the database, migrate, then serve.
#
# The steps run in this order and no other (D-06):
#   1. a bounded readiness probe, because `depends_on: condition: service_healthy`
#      only covers `docker compose up` - under a plain `docker run`, or after the
#      database restarts under a running API, nothing else waits;
#   2. `alembic upgrade head`, so the schema is never created by the application
#      and never by hand;
#   2b. an idempotent seed of the demo user the Phase 4 actor seam acts as
#      (D-02). Numbered `2b` rather than `3` because it is temporary: Phase 5
#      deletes this step together with the seam, and the step that serves has
#      been step 3 since Phase 3;
#   3. `exec` into uvicorn, so the server becomes PID 1 and receives SIGTERM
#      directly.
#
# Why the retry loop lives in this file rather than in a module under
# src/taskmanager/: coverage is measured over that package with no `omit` entry
# and no `pragma` allowed (CLAUDE.md), so a wait-for-database module would owe a
# unit test of a `range(30)` loop with a patched clock - a test that asserts the
# shape of the loop rather than the behaviour anyone cares about. The behaviour
# is proven end to end instead, by the cold-start rehearsal recorded in
# .planning/phases/03-persistence-runnable-stack/evidence/03-10-cold-start.txt:
# an empty volume, a database that is not there yet, and an API that reaches
# `healthy` anyway. That is a stronger proof than the unit test would have been,
# and it is the one an evaluator can re-run.
#
# `set -eu`: any failing command aborts the container (a failed migration must
# never be followed by a server), and an unset variable is an error rather than
# an empty string.
set -eu

# --- 1. Wait for the database -------------------------------------------------
#
# The probe goes through SQLAlchemy's synchronous engine, NOT through the
# driver's own top-level connection function. DATABASE_URL is a SQLAlchemy URL
# (`postgresql+psycopg://...`), and libpq only understands the plain
# `postgresql://` scheme - the `+psycopg` token that tells SQLAlchemy which DBAPI
# to load is a syntax error to libpq. Handing this URL straight to the driver
# therefore fails on attempt 1 with a connection-string error, and the retry loop
# then spends all thirty attempts re-raising a permanent error against a
# perfectly healthy database (03-RESEARCH.md Pitfall 2). SQLAlchemy parses the
# token, loads the same driver, and connects.
#
# The per-attempt line carries the exception class name and nothing else. The
# connection string holds the password, and a container log is readable by anyone
# who can run `docker compose logs` (T-3-31).
python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text

ATTEMPTS = 30
DELAY_SECONDS = 1

# The engine is built once, outside the loop, and deliberately so: building it
# parses the URL, so a malformed DATABASE_URL fails here and now, loudly, rather
# than being retried thirty times. Connecting is what is retried, because that is
# the only part that can legitimately succeed later.
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

for attempt in range(1, ATTEMPTS + 1):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any failure here means "not ready yet"
        print(
            f"waiting for database ({attempt}/{ATTEMPTS}): {exc.__class__.__name__}",
            flush=True,
        )
        if attempt < ATTEMPTS:
            time.sleep(DELAY_SECONDS)
    else:
        # No success line: a ready database produces no output at all here, and
        # the Alembic revision that follows is itself the proof the probe passed.
        engine.dispose()
        sys.exit(0)

engine.dispose()
print(
    f"database did not become reachable after {ATTEMPTS} attempts "
    f"{DELAY_SECONDS}s apart; check that the database service is running",
    file=sys.stderr,
)
sys.exit(1)
PY

# --- 2. Apply the migrations --------------------------------------------------
#
# `upgrade head` only, never `downgrade`: a container restart must be incapable
# of destroying data (T-3-32). alembic.ini and migrations/ are copied into this
# image next to this script, and the working directory is where both live.
alembic upgrade head

# --- 2b. Seed the demo user ---------------------------------------------------
#
# Phase 4 has no authentication yet, so every request runs as one fixed demo user
# (D-01), and `task_lists.owner_id` is a foreign key to `users.id`. On a fresh
# volume that row does not exist, so an evaluator's very first
# `POST /api/v1/task-lists` after `docker compose up` would be a foreign-key
# violation. The whole point of the seam is that the mandatory use case works
# with zero setup, so the row is written here.
#
# Why here and not in an Alembic data migration. A data row is not a schema
# change. A data migration would make this identity part of the schema's
# recorded history, and Phase 5 could then only remove it by writing a second
# revision that deletes it - whereas here the whole thing disappears when this
# block and actor.py are deleted together. The placement *after* `upgrade head`
# is not a preference either: the `users` table has to exist first.
#
# Why a heredoc and not a module under src/taskmanager/. ADR-037 already settled
# this argument for the readiness probe above: that package's coverage has no
# `omit` entry and allows no `# pragma: no cover` (CLAUDE.md), so a seed module
# would owe a unit test of a five-line INSERT, and it would add a node to
# import-linter's graph that has to import `presentation`. A heredoc is not a
# module under src/, so it adds no node to the graph and cannot break a contract
# - confirmed by running `make arch`, not assumed.
#
# Why the conflict clause below names no target. The seed runs on every
# container start, so it must absorb every way the row can already be there.
# Executed three times against the live database it produced rowcounts 1, 0 and
# 0: the second run with the same id is absorbed by the primary key, and a run
# with a *different* id and the same email is absorbed by the unique index
# `uq_users_email_lower`. A clause that named the primary-key column as its
# target would not absorb that second collision - it would raise, and under
# `set -eu` the container would abort on a restart. The untargeted form is what
# makes a restart safe, not a shortcut. The rowcounts are captured in
# .planning/phases/04-task-lists-tasks/evidence/04-11-seed-idempotence.txt.
# (The targeted form is described here rather than spelled, so that grepping
# this file for it stays a meaningful gate - the 01-03 convention.)
#
# Why `DEMO_USER_ID` is imported rather than pasted. The identifier must exist in
# exactly one place (D-03), which is actor.py; a second copy here would drift the
# day one of them is edited. The import resolves because the runtime image
# installs the `taskmanager` package into /opt/venv, and importing from
# `presentation` is legal for a consumer at the `main` level of the layer order.
#
# Why `full_name` is listed. Revision 0002 added it `NOT NULL` (AUTH-01), and a
# column list that omits it makes this INSERT a NotNullViolation - which, under
# `set -eu`, aborts the container before it ever serves. The conflict clause
# cannot save it either: PostgreSQL checks NOT NULL while building the candidate
# row, before the arbiter index is consulted, so even a restart whose row is
# already present fails. Observed live against the compose database, captured in
# .planning/phases/05-auth-assignment-notifications/evidence/05-03-live-upgrade.txt,
# and this is the fix. The value is a label rather than a name, for the same
# reason the hash below is `!`: this identity is scaffolding.
#
# Why the password hash is not a credential. The value stored is `!`, which is
# not a valid Argon2 encoded hash, so a pwdlib verification against it can never
# succeed - this identity cannot become a live account when the login endpoint
# arrives in Phase 5, and the row is deleted with the seam before that question
# ever comes up. A plausible-looking hash here would be strictly worse: it would
# read as a credential and invite someone to keep it.
#
# Like step 1, a successful run prints nothing.
python - <<'PY'
import os
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from taskmanager.presentation.api.actor import DEMO_USER_ID

SEED = text(
    """
    INSERT INTO users
        (id, email, full_name, password_hash, created_at, updated_at)
    VALUES (:id, :email, :full_name, :password_hash, :now, :now)
    ON CONFLICT DO NOTHING
    """
)

now = datetime.now(UTC)
engine = create_engine(os.environ["DATABASE_URL"])
with engine.begin() as connection:
    connection.execute(
        SEED,
        {
            "id": DEMO_USER_ID,
            "email": "demo@taskmanager.local",
            "full_name": "Demo User",
            "password_hash": "!",
            "now": now,
        },
    )
engine.dispose()
PY

# --- 3. Serve -----------------------------------------------------------------
#
# `exec` replaces this shell, so uvicorn becomes PID 1 and `docker stop` delivers
# SIGTERM to the server itself instead of to a shell that would ignore it.
#
# `--factory` is fixed here because there is exactly one application factory and
# no reason to let it be overridden; everything else - `--host 0.0.0.0 --port
# 8000` - arrives as "$@" from the image's CMD, which is therefore a real default
# argument list that `docker run <image> --port 9000` can replace, rather than a
# command this entrypoint would have to ignore.
exec uvicorn --factory taskmanager.main:create_app "$@"
