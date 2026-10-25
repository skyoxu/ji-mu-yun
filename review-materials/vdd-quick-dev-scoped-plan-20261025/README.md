# VDD / Quick Dev scoped-plan review entry

This branch publishes the current workflow changes and the native plan-ready
12-slice directory for review. It is not implementation-complete, final
Acceptance, independent A/B approval, or permission to merge.

Start with:

1. `publication-manifest.json`: exact SHA256/size/role inventory and explicit gaps.
2. `../../logs/scoped-input-preparation-20261024-v3/SCOPE-SOURCE.md` and
   `DEPENDENCY-APPROVAL.md`: user scope change and four approved relationships.
   The scope has246 retained,59 reduced and25 deployment-side old clauses;
   the new native domain is305 obligations. All330 old IDs remain traceable in
   `old-to-draft-map.json` and the classification ledger.
3. `../../logs/scoped-input-preparation-20261024-v3/inputs/`: seven exact active
   input files. The original requirement and delivered PRD/SPEC/architecture
   documents are historical/provenance inputs, never instructions to run BMAD.
4. `../../execution-plans/2026-10-24-vdd-knowledge-query-scoped-v3-r3/`:
   current canonical plan, coverage, dependencies,12 agent contexts and gates.
5. `../../logs/vdd-scoped-compile-20261025-after-v3/REPORT.md`,
   `native-result.json`, `formal-artifacts.json` and `v4-decisions.jsonl`:
   genuine completion and request-bound V4 evidence, with method limitations.
6. Workflow source/tests: `.agents/skills/vdd-execution-plan/`,
   `.agents/skills/quick-dev-tdd-adapter/`, `scripts/vdd/compile_plan.py`,
   `scripts/quick_dev/run.py`, `scripts/workflow_unit_budget.py`, and the
   retained shared Locator/query infrastructure. Relevant test outputs are
   explicitly listed by the manifest; no old result is represented as fresh
   testing of the entire publication commit.

## Source and commit identity

The original candidate had uncommitted changes. Its old HEAD f57c2998 is only
base provenance, NOT the final publication identity. Use this branch's actual
commit SHA and the manifest's per-file hashes to identify the published bytes.
The original native semantic bundle identity is
`sha256:7aa75d0cfda1125fa9c6dab354032a4fe12f19085a56254256df20b46c5216a7`;
its canonical JSON hash is separate from its file-byte SHA256.
The approved host repair chain is retained in history. Two earlier diagnostic/
review logs are excluded from this branch's current tree; they are not current
review authority. No history was rewritten.

## Explicit test-publication gap

Two mixed business test files still contain historical BMAD-positive/query or
guard scenarios requiring the approved new-scope Q2 reconciliation. Publishing
them as active tests would reactivate excluded expectations. This publication
therefore preserves their exact original bytes only under
`candidate-test-snapshots/<original-path>.txt`; the manifest maps each snapshot
to its original local path and SHA256. They are inert review inputs, not tests
to collect or run. Skill-specific regression tests are published normally.

The native plan-ready result was obtained in the preserved local candidate
where those original paths existed. This review branch does not pretend its
active business-test tree has already been reconciled or recompiled. Clone-only
execution/preflight needs a separate approved test-authoring step. Do not
silently copy these snapshots into active test paths or invoke BMAD to verify
them. This is an explicit review limitation, not a claim that the missing
active test inputs have passed.

## Boundaries

No BMAD installation or BMAD-exclusive wrapper/query-hook/consumer-registration
increment is included. Existing unrelated wrappers remain unchanged. Credentials,
raw caches, full caller transcripts, unrelated logs and the unrelated prestart-40
worktree change are excluded. Original local evidence and unrelated edits remain
preserved. No PR is created, no CI/Actions status is monitored, and no merge is
performed by this publication step.
