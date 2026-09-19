---
phase: 7
slug: documentation-delivery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-20
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from
> `07-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 + pytest-cov 7.1.0 |
| **Config file** | `pytest.ini` |
| **Quick run command** | `make test-unit` (no database, ~3 s) |
| **Full suite command** | `make test` (1101 tests, 75% gate, needs PostgreSQL) |
| **Container suite** | `make docker-test` (Python 3.13, zero host setup) |
| **Estimated runtime** | ~3 s quick, ~30 s full, ~2 min container |

---

## Sampling Rate

- **After every task commit:** `make test-unit` (every new gate is `unit`-marked and DB-free), plus
  `make lint && make typecheck` when `src/` changes
- **After every plan wave:** `make test`
- **Any plan that touches the `Dockerfile` or adds a file-reading gate:** `make docker-test` as well
- **Before `/gsd:verify-work`:** `make lint typecheck arch test docker-test`, then `make rehearse`
- **Max feedback latency:** 30 seconds (full suite)

---

## Per-Task Verification Map

| Req | Behaviour | Test Type | Automated Command | File Exists | Status |
|-----|-----------|-----------|-------------------|-------------|--------|
| DOC-04 | Every non-2xx leg (except `/health` 503) publishes a `problem+json` schema; every operation has a tag and a summary; tags are described | unit | `pytest tests/architecture/test_openapi_completeness.py --no-cov` | ❌ W0 | ⬜ pending |
| DOC-02 | The README endpoint table equals `app.openapi()["paths"]`, both directions | unit | `pytest tests/architecture/test_documentation_claims.py --no-cov` | ❌ W0 | ⬜ pending |
| DOC-01 | Every `make <target>` the README names exists; rehearsal markers delimit a non-empty block | unit | same file | ❌ W0 | ⬜ pending |
| DOC-03 | The five brief ambiguities each resolve to an ADR heading; every cited `ADR-NNN` resolves | unit | same file | ❌ W0 | ⬜ pending |
| AIW-01 | `AI_WORKFLOW.md` holds ≥ 3 mermaid blocks and no "to be completed" marker | unit | same file | ❌ W0 | ⬜ pending |
| AIW-02 | The human/AI section names every phase 1..7 | unit | same file | ❌ W0 | ⬜ pending |
| DOCK-05 | Fresh clone, `--no-cache` build and the README's own commands reach a healthy API and a green suite | e2e script | `make rehearse` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/architecture/test_openapi_completeness.py` — DOC-04, with a non-vacuity guard
- [ ] `tests/architecture/test_documentation_claims.py` — DOC-01/02/03, AIW-01/02
- [ ] `scripts/clean-clone-rehearsal.sh` + `make rehearse` — DOCK-05
- [ ] `Dockerfile` test stage copies `README.md DECISION_LOG.md AI_WORKFLOW.md Makefile`
- [ ] No framework install and no new dependency

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI green on the delivered commit; badge renders green | AIW-05 | Only observable after a push | `gh run watch`, then open the README on GitHub |
| Mermaid diagrams render | AIW-01 | No local renderer | Open `AI_WORKFLOW.md` on GitHub |
| Repository public, push of the `.planning/` trail confirmed | AIW-05 | Outward-facing and irreversible — the user's call | Checkpoint in the last plan |
| Delivery email to talento@crehana.com | delivery | The user's own action | Final checkpoint states the repo URL and stops |

---

## Validation Sign-Off

- [ ] All tasks have an automated verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
