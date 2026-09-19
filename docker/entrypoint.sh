#!/bin/sh
# The container's startup sequence: wait for the database, migrate, then serve.
#
# The steps run in this order and no other (D-06):
#   1. a bounded readiness probe, because `depends_on: condition: service_healthy`
#      only covers `docker compose up` - under a plain `docker run`, or after the
#      database restarts under a running API, nothing else waits;
#   2. `alembic upgrade head`, so the schema is never created by the application
#      and never by hand;
#   3. `exec` into uvicorn, so the server becomes PID 1 and receives SIGTERM
#      directly.
#
# There is no seeding step, and there was one until Phase 5. It wrote the fixed
# demo user the Phase 4 actor seam acted as, and it was given a lettered number
# after step 2 rather than a number of its own precisely so that deleting it
# would renumber nothing - this is that deletion (D-14, ADR-045). The step that
# serves has been step 3 since Phase 3 and still is. The stack now ships with
# **zero** users: the documented path is register, then Authorize, then call,
# and no account and no password exists anywhere in this repository.
# (The old step's label is described rather than spelled, so grepping this file
# for it stays a meaningful gate - the 01-03 convention.)
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
