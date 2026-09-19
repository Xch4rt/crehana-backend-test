# syntax=docker/dockerfile:1

# Three real stages, not one stage wearing three labels:
#
#   builder  -> installs every runtime dependency into /opt/venv and installs the
#               taskmanager package into it (non-editable).
#   runtime  -> a fresh base that receives only /opt/venv. No source tree, no tests,
#               no tool configuration, no build toolchain. Runs as a non-root account.
#   test     -> extends builder with the dev tooling, the gate configuration and the
#               test suite, so the whole suite runs with no interpreter on the host.
#
# The base tag is pinned exactly. A floating tag would make the build
# unreproducible, and a musl-based image would force source builds of psycopg,
# greenlet and argon2-cffi instead of using the manylinux wheels.
#
# This image never installs or runs the local git-hook framework: its two
# whole-program hooks resolve interpreter paths under a host `.venv/` that does not
# exist here. The container's gate is `pytest`, which already carries the coverage
# threshold and the architecture-contract test.

# ---------- Stage 1: builder ----------
FROM python:3.13-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies are installed before any source is copied, so editing a module
# does not invalidate the dependency layer.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# --no-deps because requirements.txt already resolved everything above; this step
# only installs the taskmanager package itself. It is the reason the [project]
# block in pyproject.toml is mandatory rather than decorative.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps .

# ---------- Stage 2: runtime ----------
FROM python:3.13-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# A dedicated system account with no login shell, rather than loosening
# permissions on the application directory.
RUN useradd --system --create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
USER app

# The only application files this stage receives, and deliberately only these
# three: the package itself still arrives exclusively through /opt/venv, never as
# a source tree. What is copied here is what the *startup sequence* needs and the
# installed package does not carry - the Alembic configuration, the revision
# history, and the entrypoint that applies it.
#
# `--chown=app:app` rather than moving these lines above `USER app`: a COPY made
# after the USER switch still lands as root by default, and the image must keep
# running as the non-root account (T-3-30, ADR-014).
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app docker/entrypoint.sh ./docker/entrypoint.sh

# The executable bit is set in the build rather than inherited from the host file
# mode, which does not survive every build context on every platform - a checkout
# on a filesystem without POSIX permissions would otherwise produce an image that
# fails with "exec: ./docker/entrypoint.sh: permission denied".
RUN chmod +x ./docker/entrypoint.sh

# No configuration value is baked in here. Every setting - including the two with
# no default - is injected at run time by the environment (compose, Phase 3).
EXPOSE 8000

# The entrypoint waits for the database and runs `alembic upgrade head` before
# handing over to uvicorn (D-06). CMD is now the default *argument list* behind
# it - the entrypoint fixes `uvicorn --factory taskmanager.main:create_app` and
# appends these, so `docker run <image> --port 9000` still works instead of being
# silently ignored.
ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]

# Exit 0 only on HTTP 200 from /health, with no curl and no wget - neither is in
# a slim image, and installing one to answer a healthcheck is a package more than
# the job needs (D-09). urlopen raises HTTPError on the 503 that /health returns
# when its database probe fails, so the except branch is what makes an unhealthy
# database an unhealthy container; relying on the traceback's exit code instead
# would be an assumption about every Python build (03-RESEARCH.md assumption A3).
#
# --start-period=30s: the API is not listening until the entrypoint's migration
# finishes. Without it the first failed probe counts against --retries and the
# container flaps to `unhealthy` before it ever had a chance to start.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request\ntry:\n    sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)\nexcept Exception:\n    sys.exit(1)"]

# ---------- Stage 3: test ----------
FROM builder AS test

# The editable reinstall replaces the builder's non-editable copy, so exactly one
# copy of the code sits on sys.path and coverage reports src/taskmanager/... paths.
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt && pip install --no-deps -e .

# .env.example is a tracked placeholder file, not a credential file - the real one
# is excluded from the build context. It is copied because a unit test asserts that
# it documents every declared settings field and nothing else.
COPY pytest.ini .flake8 .importlinter .env.example ./
COPY tests ./tests

# The migration files, because the `migrated_database` fixture builds its Alembic
# Config from alembic.ini and runs the real revisions against taskmanager_test
# (D-02). This stage deliberately does NOT receive docker/entrypoint.sh and keeps
# its own `CMD ["pytest"]`: the entrypoint's `upgrade head` would migrate the
# schema a second time, from outside the fixture that owns it (D-06).
COPY alembic.ini ./
COPY migrations ./migrations

# `scripts/` and git, for two test modules that drive a shell script as a
# program: `tests/unit/test_env_bootstrap.py` runs scripts/init-env.sh through
# `sh` in a temporary directory, and `tests/unit/test_break_check.py` runs
# scripts/break-check.sh inside a throwaway repository it builds with `git init`
# in `tmp_path`. Neither can be answered with a skip - a skipped test here is a
# green container run that exercised none of it, which is the same argument D-03
# makes about the database. Both were collection errors in this stage until plan
# 06-04 ran `make docker-test`.
#
# git is installed in THIS stage only. The runtime image receives nothing from
# here, so the delivered container still carries no version-control tooling.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY scripts ./scripts

RUN useradd --system --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app /opt/venv
USER app

CMD ["pytest"]
