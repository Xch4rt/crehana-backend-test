---
phase: 6
slug: test-hardening-coverage
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-19
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `06-RESEARCH.md` §"Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio (`asyncio_mode = auto`) + pytest-cov |
| **Config file** | `pytest.ini` (authoritative) and `pyproject.toml` `[tool.coverage.*]` |
| **Quick run command** | `.venv/bin/pytest -m unit --no-cov` (no database; until the `unit` marker lands, `-m "not integration" --no-cov`) |
| **Full suite command** | `.venv/bin/pytest` (requires `make up`) |
| **Estimated runtime** | ~2 s quick, ~10 s full |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** `make lint && make typecheck && make arch && make test` green, `make docker-test` and CI agreeing on the coverage total, `make break-check` green
- **Max feedback latency:** 15 seconds

---

## Per-Requirement Verification Map

Task IDs are assigned by the plans; each plan's tasks carry the command of the requirement they serve.

| Requirement | Secure / Correct Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|---------------------------|-----------|-------------------|-------------|--------|
| TEST-01 | Every use-case symbol has a fakes-based unit test; an emptied or renamed package fails | unit | `.venv/bin/pytest tests/architecture/test_use_case_totality.py -x --no-cov` | ❌ W0 | ⬜ pending |
| TEST-02 | Every operation in `app.openapi()` was requested over HTTP against PostgreSQL; a focused run is not falsely red | integration | `.venv/bin/pytest tests/integration -x --no-cov` | ❌ W0 | ⬜ pending |
| TEST-03 | Threshold >= 75, no `omit`, `source = taskmanager`, no `# pragma: no cover` under `src/`; gate passes on host, Docker and CI | unit + full | `.venv/bin/pytest tests/architecture/test_coverage_configuration.py --no-cov` ; `.venv/bin/pytest` ; `make docker-test` | ❌ W0 / ✅ gate | ⬜ pending |
| TEST-04 | Transition complement (self-pairs are 200 no-ops, cross-pairs 409), six auth failure modes each reaching their own branch, every `DomainError` leaf body, permission matrix vs published table | unit + integration | `.venv/bin/pytest tests/unit/domain tests/integration/api/test_tasks.py tests/integration/api/test_auth.py tests/integration/api/test_permission_matrix.py --no-cov` | ⚠️ partial | ⬜ pending |
| TEST-05 | No status-only HTTP assertion; every mutation re-read through the API or carries `no_reread` with a reason; all five deliberate breaks turn the suite red | unit + script | `.venv/bin/pytest tests/architecture/test_assertion_quality.py --no-cov` ; `make break-check` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/architecture/test_use_case_totality.py` — TEST-01
- [ ] `tests/integration/test_endpoint_totality.py` + recorder in `tests/integration/conftest.py` — TEST-02
- [ ] `tests/architecture/test_coverage_configuration.py` — TEST-03
- [ ] `tests/architecture/test_assertion_quality.py` — TEST-05
- [ ] `scripts/break-check.sh` + `tests/unit/test_break_check.py` — TEST-05
- [ ] Framework install: none — no dependency is added (mutmut declined, D-08)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI coverage total agrees with host and Docker | TEST-03 | CI runs on GitHub, not on the host | After push, read the coverage total from the CI run log and compare with `make test` and `make docker-test`; record the three numbers in the phase verification |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
