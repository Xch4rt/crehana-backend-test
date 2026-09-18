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

# No configuration value is baked in here. Every setting - including the two with
# no default - is injected at run time by the environment (compose, Phase 3).
EXPOSE 8000
CMD ["uvicorn", "--factory", "taskmanager.main:create_app", \
     "--host", "0.0.0.0", "--port", "8000"]

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

RUN useradd --system --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app /opt/venv
USER app

CMD ["pytest"]
