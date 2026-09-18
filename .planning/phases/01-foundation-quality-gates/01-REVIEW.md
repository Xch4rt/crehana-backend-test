---
phase: 01-foundation-quality-gates
reviewed: 2026-09-18T03:13:20Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - .dockerignore
  - .env.example
  - .flake8
  - .github/workflows/ci.yml
  - .gitignore
  - .importlinter
  - .pre-commit-config.yaml
  - Dockerfile
  - Makefile
  - pyproject.toml
  - pytest.ini
  - requirements-dev.txt
  - requirements.txt
  - src/taskmanager/__init__.py
  - src/taskmanager/application/__init__.py
  - src/taskmanager/domain/__init__.py
  - src/taskmanager/infrastructure/__init__.py
  - src/taskmanager/infrastructure/config/__init__.py
  - src/taskmanager/infrastructure/config/settings.py
  - src/taskmanager/main.py
  - src/taskmanager/presentation/__init__.py
  - tests/__init__.py
  - tests/architecture/__init__.py
  - tests/architecture/test_layer_boundaries.py
  - tests/unit/__init__.py
  - tests/unit/test_app_factory.py
  - tests/unit/test_settings.py
findings:
  critical: 0
  warning: 7
  info: 6
  total: 13
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-09-18T03:13:20Z
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Phase 1 is foundation only: packaging, a pydantic-settings module, a FastAPI factory, and the
quality-gate plumbing (pre-commit, Makefile, Dockerfile, CI, import-linter contracts). The
reviewed code is small and the gate wiring is mostly sound: CI has a least-privilege token,
`.env` is excluded from both git and the Docker build context, the runtime image drops to a
non-root user and carries no source tree, the import-linter test guards against the
"zero contracts configured" trap, and every tool version is exactly pinned.

No BLOCKER-tier defect was found. Seven WARNING-tier findings were confirmed, three of them
by running the code rather than reading it:

- The coverage gate can be silently weakened: the `exclude_also` pattern `\.\.\.` is unanchored,
  so any `def`/`class`/`if` line containing `...` in a comment, docstring, or string removes
  its whole block from measurement (reproduced: a 4-statement function vanished from the report).
- `test_get_settings_is_cached` reads the developer's real `.env` from the working directory.
  Reproduced two distinct failure modes: an extra key in `.env` raises `ValidationError`
  (because of `extra="forbid"`), and any override in `.env` breaks the equality assertion.
- `test_create_app_uses_settings` cannot detect the bug it is named for: with the env
  monkeypatched, `create_app` would pass even if it ignored its argument.
- Several settings tests depend on `APP_NAME`, `ENVIRONMENT`, `JWT_ALGORITHM`, and
  `JWT_EXPIRE_MINUTES` not being exported in the developer's shell, despite a docstring
  claiming the opposite.
- `jwt_algorithm` accepts any string, so a bad `JWT_ALGORITHM` fails at first request rather
  than at boot, contradicting the settings module's stated fail-fast contract.
- GitHub Actions are tag-pinned rather than SHA-pinned in a public repo.
- `.gitignore` covers `.env` only; `.env.local` / `.env.production` would be committed.

The Info items are correctness-adjacent housekeeping (misleading "pinned exactly" comment in
the Dockerfile, duplicated version string, unconstrained `environment`, missing job timeout,
a `.env.example` placeholder that passes validation, and `or` used for None-coalescing on a
pydantic model).

## Warnings

### WR-01: Unanchored `\.\.\.` in `exclude_also` lets whole functions escape the 75% coverage gate

**File:** `pyproject.toml:47`
**Issue:** `exclude_also` entries are regexes searched against each source line, and when a
matching line opens a block (`def`, `class`, `if`, `for`, ...), coverage.py excludes the
**entire block**. `"\\.\\.\\."` is unanchored, so it matches any line containing three dots
anywhere: a trailing `# loads...` comment on a `def`, a `"Loading..."` string, an ellipsis
in a docstring's first line. Reproduced in a scratch project with this exact pattern: a
4-statement never-called function whose `def` line ended in `# computes things...` was
removed from the report entirely, and a line `msg = "Loading..."` was also dropped. Because
the brief's 75% threshold is enforced through this configuration, a single stray comment can
inflate coverage without any test being written, which is exactly the "gate silently passes"
class of mistake this phase is supposed to make impossible.
**Fix:** Anchor the pattern so it only matches a line that *is* an Ellipsis body (the
`Protocol` / abstract stub case it was written for):
```toml
[tool.coverage.report]
exclude_also = [
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
    "^\\s*\\.\\.\\.\\s*$",
]
```
If one-line stubs like `def method(self) -> None: ...` must also be excluded, add the
explicit form `":\\s*\\.\\.\\.\\s*$"` rather than relaxing the anchor.

### WR-02: `test_get_settings_is_cached` reads the developer's real `.env` and fails on any customization

**File:** `tests/unit/test_settings.py:56-72` (root cause: `src/taskmanager/infrastructure/config/settings.py:19,22`)
**Issue:** `get_settings()` calls `Settings()` with `env_file=".env"` relative to the CWD.
Every other test passes `_env_file=None`; this one does not, so it is the only test whose
outcome depends on a git-ignored file. Two failure modes were reproduced with a scratch
`.env` and the real `Settings` class:
1. `.env` contains any undeclared key (e.g. `COMPOSE_PROJECT_NAME=taskmanager`, which
   `docker compose` conventionally reads from the same file in Phase 3) ->
   `ValidationError: compose_project_name Extra inputs are not permitted` because of
   `extra="forbid"`.
2. `.env` sets any field the test does not monkeypatch (e.g. `ENVIRONMENT=docker`) ->
   `assert first == Settings(_env_file=None)` is `False` because the cached instance carries
   the dotenv value and the fresh one carries the default.
The file docstring says "no test ever depends on the developer's shell"; this test depends on
the developer's `.env` instead. The suite is green in CI and Docker only because neither has
a `.env`, which hides the flake until an evaluator runs `make test` after `cp .env.example .env`
and edits it.
**Fix:** Isolate the working directory so no `.env` is discoverable:
```python
def test_get_settings_is_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)  # no .env here, so only the process env is read
    get_settings.cache_clear()
    ...
```
Separately, consider whether `extra="forbid"` on the dotenv source is compatible with the
Phase 3 compose setup: compose interpolation variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`,
`COMPOSE_PROJECT_NAME`) placed in the same `.env` will make the host-run app refuse to boot.
If that collision is expected, either scope compose to a different file (`--env-file`) or
document it in `.env.example` now.

### WR-03: `test_create_app_uses_settings` cannot detect the bug it is named for

**File:** `tests/unit/test_app_factory.py:13-22`
**Issue:** The test monkeypatches `DATABASE_URL` and `JWT_SECRET` into the process
environment, then passes `Settings(_env_file=None)` built from that same environment, and
asserts `app.title == "Task Manager API"`, which is the field's default. If `create_app`
silently ignored its `settings` argument and called `get_settings()` instead, the test would
still pass: the environment makes `get_settings()` succeed and the title would still be the
default. The docstring claims the test proves injection; it proves only that `create_app`
returns a `FastAPI`. Since the whole point of the factory (per the `main.py` docstring) is
explicit injection, the property that matters is unverified.
**Fix:** Inject a non-default value and assert on it; no environment is needed at all:
```python
def test_create_app_uses_settings() -> None:
    settings = Settings(
        _env_file=None,
        app_name="Injected Title",
        database_url=DATABASE_URL,
        jwt_secret=JWT_SECRET,
    )
    app = create_app(settings)
    assert app.title == "Injected Title"
```
Add a second test that `create_app()` with no argument falls back to `get_settings()`
(monkeypatch env, `cache_clear()`, assert `app.title == get_settings().app_name`), which is
the branch uvicorn `--factory` actually exercises in the container.

### WR-04: Settings tests assume undeclared variables are absent from the developer's shell

**File:** `tests/unit/test_settings.py:21-31`, `tests/unit/test_app_factory.py:21`
**Issue:** `test_settings_read_from_environment` asserts `jwt_algorithm == "HS256"` and
`jwt_expire_minutes == 30`, and `test_create_app_uses_settings` asserts the default
`app_name`; none of these tests clears `APP_NAME`, `ENVIRONMENT`, `JWT_ALGORITHM` or
`JWT_EXPIRE_MINUTES`. A developer whose shell profile exports `JWT_EXPIRE_MINUTES=60` (a very
common thing to have lying around from another project) gets a red suite with no obvious
cause. The comment at line 10-11 ("no test ever depends on the developer's shell") is
therefore inaccurate for four of the six fields.
**Fix:** Build a fixture that scrubs every declared field before each test, and use it in
every test that inspects defaults:
```python
@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    return monkeypatch
```
This also makes the `.env.example` parity test and the "defaults apply" test share one
source of truth for the field list.

### WR-05: `jwt_algorithm` is unconstrained, so a misconfigured algorithm fails at first request, not at boot

**File:** `src/taskmanager/infrastructure/config/settings.py:31`
**Issue:** The module docstring commits to "a misconfigured process must fail at boot with a
single readable ValidationError". `jwt_algorithm: str = "HS256"` accepts any value:
`JWT_ALGORITHM=RS256` (asymmetric, needs a key pair the settings do not model),
`JWT_ALGORITHM=hs256` (PyJWT is case-sensitive), or `JWT_ALGORITHM=none`. All of these boot
cleanly and then break at the first `POST /auth/login` in Phase 4, which is the exact
failure mode the docstring promises to prevent. Because a shared-secret `jwt_secret` is the
only key material modeled, only the HMAC family is coherent with the rest of the schema.
**Fix:**
```python
from typing import Literal

jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
```
Update `.env.example` line 26-27 to list the allowed values.

### WR-06: GitHub Actions are pinned to mutable tags, not commit SHAs

**File:** `.github/workflows/ci.yml:57,59`
**Issue:** `actions/checkout@v7` and `actions/setup-python@v7` resolve a floating major tag.
Tags are mutable references; the March 2025 `tj-actions/changed-files` compromise worked by
force-moving existing version tags to a malicious commit, so every workflow pinned to a tag
executed attacker code with the repository's token. This workflow's `permissions:
contents: read` limits the blast radius to reading a public repo and the (fake) job `env`
values, so this is not a secrets-exfiltration risk today, but it is the one item in the
prompt's "CI permissions/pinning" checklist that is not done, and it is the first thing a
security-minded evaluator greps for. The requirements files, pre-commit revs and base image
are all exactly pinned; the workflow is the inconsistency.
**Fix:** Pin to the full commit SHA with the tag as a trailing comment so Dependabot can still
track it (SHAs shown are placeholders; take them from the release page of each action):
```yaml
- uses: actions/checkout@<40-hex-sha-of-v7.0.1>  # v7.0.1
- uses: actions/setup-python@<40-hex-sha-of-v7.0.0>  # v7.0.0
```
Optionally add a `dependabot.yml` with `package-ecosystem: github-actions` so the pins are
maintained automatically.

### WR-07: `.gitignore` excludes `.env` only; `.env.local` / `.env.production` would be committed to a public repo

**File:** `.gitignore:3`
**Issue:** The repository will be public and is meant to be cloned and run by an evaluator.
The only environment file ignored is the literal `.env`. The pydantic-settings, docker
compose and dotenv ecosystems all conventionally use `.env.local`, `.env.test`,
`.env.production`, and the moment a real `JWT_SECRET` or a real DSN lands in one of those it
is one `git add .` away from a public commit. The `detect-private-key` pre-commit hook does
not catch this (it only matches PEM blocks). `.dockerignore:7` has the same single-file
pattern, though the selective `COPY` lines mean no such file would reach an image layer, so
the exposure there is limited to build-context transfer.
**Fix:**
```gitignore
# Environment
.venv/
.env
.env.*
!.env.example
```
Mirror the same three lines in `.dockerignore` for consistency.

## Info

### IN-01: Dockerfile comment claims an exactly pinned base image; the tag is floating

**File:** `Dockerfile:12-14,22,46`
**Issue:** The comment says "The base tag is pinned exactly. A floating tag would make the
build unreproducible", but `python:3.13-slim-trixie` is a floating tag: it moves on every
3.13.x patch release and on every Debian trixie rebuild. The reproducibility argument in the
comment is therefore not delivered by the line below it, and an evaluator who reads the
comment and then the `FROM` line will notice the mismatch.
**Fix:** Either pin the digest (`FROM python:3.13-slim-trixie@sha256:<digest> AS builder`,
same digest in the runtime stage) or soften the comment to say the tag pins the minor
version and distro only. The digest form is the one that matches the comment.

### IN-02: Application version string duplicated between `pyproject.toml` and `main.py`

**File:** `src/taskmanager/main.py:20`, `pyproject.toml:7`
**Issue:** `"0.1.0"` is hard-coded in the FastAPI constructor and again as the package
version. The two will drift the first time one is bumped, and the test at
`tests/unit/test_app_factory.py:22` pins the literal a third time.
**Fix:**
```python
from importlib.metadata import version

version=version("taskmanager"),
```
This works because both the builder stage and CI install the package (`pip install .` /
`pip install -e .`), and `pytest.ini`'s `pythonpath = src` fallback is a fresh-clone
convenience, not the supported path.

### IN-03: `environment` accepts any string despite `.env.example` documenting four allowed values

**File:** `src/taskmanager/infrastructure/config/settings.py:28`, `.env.example:14`
**Issue:** `.env.example` says "local, ci, staging or production"; the model accepts
`ENVIRONMENT=prodcution` silently. Once later phases branch on this value (e.g. to disable
`/docs` in production), the typo becomes a security-relevant misconfiguration that boots
cleanly.
**Fix:** `environment: Literal["local", "ci", "staging", "production"] = "local"`.

### IN-04: CI job has no `timeout-minutes`

**File:** `.github/workflows/ci.yml:24-25`
**Issue:** A hung Postgres health check or a stuck pip resolution runs for the GitHub default
of 360 minutes. On a public repo this burns shared runner minutes and leaves a red-for-hours
status on the commit the evaluator is looking at.
**Fix:** Add `timeout-minutes: 15` under `quality-gates:`.

### IN-05: `.env.example` ships a placeholder `JWT_SECRET` that passes validation

**File:** `.env.example:24`, `src/taskmanager/infrastructure/config/settings.py:30`
**Issue:** `replace-me-with-a-generated-secret` is 34 characters, so `cp .env.example .env`
followed by `docker compose up` (Phase 3) boots the API on a publicly known signing secret.
The settings docstring frames placeholder secrets as the thing the no-default rule exists to
prevent. This is a deliberate trade-off against the brief's one-command startup, so it is not
flagged higher, but the tension should be resolved explicitly rather than by accident.
**Fix:** Pick one and record it in `DECISION_LOG.md`: (a) keep the working placeholder and add
a `field_validator` that rejects it when `environment != "local"`; or (b) make the
placeholder deliberately invalid (`JWT_SECRET=` with a `# REQUIRED` comment) and have the
compose file inject a generated CI/dev secret instead.

### IN-06: `settings or get_settings()` relies on pydantic model truthiness for None-coalescing

**File:** `src/taskmanager/main.py:17`
**Issue:** `or` treats the argument as absent when it is falsy, not when it is `None`.
`BaseModel` does not define `__bool__` or `__len__` today, so this happens to work, but the
intent is "not provided", and a future `__len__` or `__bool__` on the model (pydantic has
discussed both) would silently reroute every explicitly injected settings object to the
global cache.
**Fix:** `resolved = settings if settings is not None else get_settings()`.

---

_Reviewed: 2026-09-18T03:13:20Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
