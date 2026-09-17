---
phase: 1
slug: foundation-quality-gates
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-17
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `01-RESEARCH.md` → "Validation Architecture" (commands there were executed by the
> researcher against the pinned toolchain).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 + pytest-cov 7.1.0 |
| **Config file** | `pytest.ini` — none yet, Wave 0 creates it |
| **Quick run command** | `pytest tests/unit -q --no-cov` |
| **Full suite command** | `make lint && make typecheck && make arch && make test` |
| **Dockerized suite** | `make docker-test` |
| **Estimated runtime** | ~5 seconds (host gate), ~60 seconds (docker, cached) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit -q --no-cov` (once the test tree exists)
- **After every plan wave:** Run `make lint && make typecheck && make arch && make test`
- **Before `/gsd:verify-work`:** full host gate + `make docker-test` green, and
  `pre-commit run --all-files` twice with no modifications on the second run
- **Max feedback latency:** 10 seconds (host gate)

---

## Per-Task Verification Map

Task IDs are assigned by the planner; the requirement → command mapping below is binding.

| Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|-----------------|-----------|-------------------|-------------|--------|
| FND-01 / ARC-01 | N/A | unit | `python -c "import taskmanager.domain, taskmanager.application, taskmanager.infrastructure, taskmanager.presentation, taskmanager.main"` | ❌ W0 | ⬜ pending |
| FND-02 | Exact pins, no floating versions | smoke | `pip install --dry-run -r requirements-dev.txt` | ❌ W0 | ⬜ pending |
| FND-03 | N/A | smoke | `flake8 src tests` and `! grep -Eq '^[[:space:]]*ignore[[:space:]]*=' .flake8` | ❌ W0 | ⬜ pending |
| FND-04 | N/A | smoke | `black --check src tests && isort --check-only src tests` | ❌ W0 | ⬜ pending |
| FND-05 | N/A | smoke | `pytest --collect-only -q 2>&1 \| grep -q "configfile: pytest.ini"` ; `pytest` warning-free under `filterwarnings = error` | ❌ W0 | ⬜ pending |
| FND-06 | Coverage number is honest (package source, un-imported files counted) | smoke | `pytest` (addopts carry `--cov=taskmanager --cov-fail-under=75`) | ❌ W0 | ⬜ pending |
| FND-07 | N/A | smoke | `mypy src tests` | ❌ W0 | ⬜ pending |
| FND-08 | N/A | smoke | `pre-commit run --all-files && pre-commit run --all-files` | ❌ W0 | ⬜ pending |
| FND-09 | N/A | smoke | `make lint && make typecheck && make arch && make test` | ❌ W0 | ⬜ pending |
| FND-10 | N/A | smoke | YAML parse of `.github/workflows/ci.yml` asserting every gate step is present | ❌ W0 | ⬜ pending |
| FND-11 | Secrets never defaulted; missing/short secret rejected; `.env` never committed | unit | `pytest tests/unit/test_settings.py -q --no-cov` (incl. `.env.example` ↔ `Settings.model_fields` parity test) | ❌ W0 | ⬜ pending |
| ARC-03 | Layer boundaries cannot be bypassed silently | unit | `pytest tests/architecture -q --no-cov` (Python API `lint_imports`, plus guard asserting the expected contract names are configured) and `lint-imports` exit code 0 | ❌ W0 | ⬜ pending |
| DOCK-01 | Non-root user; no `.env` / `.git` in image | smoke | `docker build --target runtime -t taskmanager . && [ "$(docker run --rm taskmanager whoami)" = app ]` | ❌ W0 | ⬜ pending |
| DOCK-04 | N/A | smoke | `make docker-test` | ❌ W0 | ⬜ pending |
| AIW-03 | N/A | smoke | `test -f AI_WORKFLOW.md && grep -Eq '^## Incident Log' AI_WORKFLOW.md && grep -Eq '^### 2026-' AI_WORKFLOW.md` | ❌ W0 | ⬜ pending |
| AIW-04 | N/A | smoke | `grep -q 'HTTPException' CLAUDE.md && grep -q 'domain' CLAUDE.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Known trap (from research, verified by execution):** `python -m importlinter.cli lint-imports`
always exits 0. The architecture test MUST use
`importlinter.application.use_cases.lint_imports(...)` or the `lint-imports` console script.

---

## Wave 0 Requirements

The repository contains no code; everything is Wave 0. Creation order:

- [ ] `pyproject.toml` packaging block + `src/taskmanager/` with the four layer packages
- [ ] `requirements.txt` / `requirements-dev.txt`
- [ ] `pytest.ini`, `.flake8`
- [ ] `src/taskmanager/infrastructure/config/settings.py`, `src/taskmanager/main.py`
- [ ] `tests/unit/test_settings.py`, `tests/unit/test_app_factory.py`
- [ ] `.importlinter`, `tests/architecture/test_layer_boundaries.py`
- [ ] `make install` (creates `.venv`, installs dev requirements, `pip install -e .`, `pre-commit install`)

No `conftest.py` in Phase 1.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Coverage gate actually fires below 75% | FND-06 | One-time demonstration; leaving a failing module in the repo is not an option | Add a temporary uncovered module, run `pytest`, observe `Required test coverage of 75% not reached`, remove it; record the output in `AI_WORKFLOW.md` |
| import-linter contract goes red on a violation | ARC-03 | Same — one-time red/green demonstration | Add `import fastapi` to a `domain` module, run `pytest tests/architecture` and `lint-imports` (both must fail), remove it (both must pass); record output in `AI_WORKFLOW.md` |
| CI is green on a real push | FND-10 | Outward-facing: requires creating the public GitHub repository, which needs explicit user confirmation | After user confirmation: create repo, push, check the Actions run. Fallback if not confirmed in this phase: `ci.yml` committed + local gates green, green-CI evidence carried to Phase 7 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
