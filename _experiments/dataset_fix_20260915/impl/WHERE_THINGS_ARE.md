# Where things are (STAR-Bench, 2026-09 rerun)

One page to find anything about the audit, the fixes and the rerun. Everything below is in the repository,
so it stays with the code; nothing depends on a web link.

## Start here
| you want | read |
|---|---|
| to run experiments | `COAUTHOR_QUICKSTART.md` |
| to know who runs what | `ASSIGNMENT.md` |
| what we decided and why | `DECISIONS_CHOSEN.md` (+ `DECISIONS_CHOSEN.json`) |
| the full issue list | `../round2/FINAL/register_final.json` (179 issues, severity, fix, workstream) |
| what changed in the code and data | `../../../AUDIT_FIXES_scoring.md`, `WS-*_report.md` in this directory, `../../../../STAR-Bench-Web/AUDIT_FIXES.md` |
| whether everything still passes | `python -m _experiments.scripts.preflight.run --all --report` → `preflight_report.md` |

## The audit trail (read-only history)
- Round 1 registers: `../issues_L1L2_data.json`, `issues_L3_tools.json`, `issues_L4_scoring.json`, `issues_L5_runners.json`, `issues_L6_paper.json`
- Adversarial verification: `../verify_L3L4.json`, `../verify_L5L6.json`, `../verify_parts/`
- Coverage: `../coverage_platform.json`, `../coverage_runners.json`
- Blind re-audit (round 1 of the two extra rounds): `../round1/`
- Verification and coverage close-out (round 2): `../round2/`
- The ICLR revision plan as it stood on 2026-09-15: `../archive/iclr_revision_plan_20260915.html`

## Data and code state
- Frozen at tag `rerun-freeze-20260916` on branch `audit-fixes` in both repositories.
- Single-turn 1,258 cases (143 of them authored in this round, marked `"source": "2026-09 expansion"`),
  multi-turn 50 scenarios / 219 turns, all entities real, all injected results executed.
- Serving configurations: `_experiments/scripts/runner/registry.py`; the table prints with
  `python -m _experiments.scripts.runner.plan --format markdown`.
- Metric definitions as implemented: `_experiments/scripts/scoring/README.md`.

## Still open
- 26 model snapshot revisions in `_experiments/scripts/model_revisions.json` (filled by whoever downloads the model).
- GPU-only checks: per-configuration smoke, the canary, and the batching-agreement run.
- Everything the register marks as post-rerun: the STR quality checker (D04), case-weighted reporting (D20),
  the new blind expert evaluation (D22), and the manuscript itself.
