# Start 08-05 Quick Dev from the repaired handoff

Use branch `fix/08-05-real-skill-replay` after a normal fast-forward sync.
The current input is this directory's `current-plan/`, published by the public
canonical compiler. No local VDD rerun is required.

1. Read repository AGENTS, `quick-dev-tdd-adapter/SKILL.md`, its execution guide,
   this plan's semantic bundle, `handoff-repair.v1.json` and each slice context.
2. Start a fresh run under `logs/quick-dev-current-run-20260919/` (choose a fresh
   suffix if it exists). Preserve old runs and do not import old S1/S2 receipts.
3. Resolve Q0's eight runtime snapshot roots from the actual candidate, plan,
   contract, descriptor, fixtures, sources, validator/judge and transition
   inputs. Bind `source_commit` to the synchronized HEAD. Do not reuse a
   historical snapshot or fabricate an execution descriptor to pass Q0.
4. Run the stable CLI's recommendation and preflight, then follow the Skill
   through all 45 current slices. Q2 authors each declared
   `scripts/sc/tests/tc_d1_cer/test_s<n>.py`; these are planned paths, not
   existing tests or proof. Every bound assertion needs its exact marker,
   real production invocation and independent Given/When/Then oracle.
5. Controlled probes decide present/missing/unverifiable. Present work stays
   in regression and terminal coverage; missing executable behavior needs
   real expected RED before production changes. Do not relabel governance,
   constraint or infrastructure failures as expected RED.
6. Keep required regressions, Q7 and whole-plan Q8. Only native current proof
   may publish implementation-complete. Formal Acceptance remains separate.

Quick deterministic entry check from repository root (PowerShell):

```powershell
$plan = "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/quick-dev-ready/current-plan"
py -3 scripts/quick_dev/run.py --plan $plan --slice S1 --profile self-hosted --action preflight
```

This command checks the handoff; it does not run the implementation. Ask local
Codex to use Quick Dev TDD on the complete plan and continue through all slices.

C3's existing product-scope decision is historical and still bound to its
original candidate. This repair creates no new approval. Preserve its allowed
TC-D1 scope, historical validator source, no substitute Trust Approval, and no
Consumer exception. Do not change PhaseA/runtime, Hosted workspaces, account
or sandbox behavior, installed BMAD/GDS, or live shared model entrypoints.
If governance is explicitly enabled, its candidate-specific authorization
checks still apply; plan-ready and this handoff do not bypass them.

Validation and limitations: the online repair ran deterministic compiler checks,
public Quick Dev preflight for all 45 slices, and focused compiler/consumer
regressions on Linux. It did not execute the TC-D1 production assertions,
Windows implementation lifecycle, live model backend, Q8 or formal Acceptance.
Those remain the local implementation workflow's responsibility.
