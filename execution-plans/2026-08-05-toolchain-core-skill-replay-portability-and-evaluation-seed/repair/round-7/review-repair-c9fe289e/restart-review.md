# Round-7 direct-repair restart review

Reviewed snapshot: `e2f4fb09337a5f298321df39362d363822771f6c`.
Reviewed bundle: `sha256:2eab507d59823997558de9b1c5ac10e3f47d9ccc070f617a0e908a3bff2a3d9a`.

Conclusion: **PASS for the two scoped semantic amendments and their handoff to
fresh VDD compilation**. This is the repairing assistant's follow-up review,
not independent external-review evidence, a full TC-D1 completion verdict,
or authorization to publish `plan-ready`/Acceptance.

## Findings disposition

| Item | Evidence inspected | Disposition |
| --- | --- | --- |
| PhaseA/runtime writes | S14/S19 owners, allowed paths, rollback paths, agent contexts | No protected owner added. S14 now binds actual Toolchain replay rather than knowledge publication. |
| AO-17a empty authorization | O-C1E267D7452D, its new Acceptance, failure intent, S14 proof and context | Closed in the repaired plan: explicit [] positive control; all non-empty grants fail regardless of authenticity; missing/malformed fields fail; foreign lifecycle remains separate. |
| AO-09e reconstruction | O-B9EAA8169232, its new Acceptance, failure intent, S19 proof and context | Closed in the repaired plan: reconstruction from referenced bytes and equality verification precede a real fresh positive replay. Echoed identities, missing/mutated originals, no-launch, and old-output reuse cannot pass. |
| FR-9 Manifest | S25 behavior/terminal/context and unchanged slice comparison | Bidirectional real-call/Manifest coverage retained. No new finding is raised for narrower duplicate wording elsewhere. |
| C3 | Authority companion questions 3-5, Architecture AD-8, repair README | OPEN with affected-decision scope only. No approval/exception is manufactured; unrelated work is not globally blocked. |

Content-derived Acceptance/failure IDs, both coverage projections, assertions,
behavior routing, slice contexts and bundle identity were checked together.
The existing deterministic schema/chain/routing validators pass; all 82 active
obligations remain in the chain. This count is not proof of source completeness
or product execution. Unaffected obligations and slices remain unchanged.

The two identity use cases must remain distinct: a new evaluation may bind new
current inputs, but reproduction of an existing historical binding must first
restore its original identities. A new result cannot silently validate the old
result by rebinding it to modified bytes.

## Execution preparation

The public CLI accepts `--requirements`, repeated `--companion`, `--profile`,
`--out-dir`, `--result-json`, and bounded worker-repair timeout. It alone can
publish canonical readiness. Merely importing validators or running the direct
repair helper cannot do so.

The current V0 extractor rejects duplicate FR/NFR anchors across sources and
does not interpret Spec frontmatter roles automatically. Thus passing only the
atomic table loses contract context; blindly passing every companion can fail
on ambiguous IDs. The local VDD invocation must perform role-aware source
assembly and retain traceability to the complete original canonical package.
This is preparation inside that invocation, not another user repair step.

Old V1/V3/V4 and completed-resume artifacts are not eligible for this repair.
Use a fresh compilation output under the same existing round-7 directory,
retain current-plan and before/ as evidence, and record the new result path.
Do not overwrite historic PASS records or inject them as current worker replies.

Online environment: Linux/Python/Git are available. Codex CLI, OpenAI SDK and
OPENAI_API_KEY are absent. No live model authentication/network check or VDD
compilation was attempted. Local backend presence is checked by
`verify_restart_inputs.py --require-backend`; real authentication is established
only by the real compiler execution. Windows checks remain local.

## Remaining completion condition

Run one local VDD Skill session using VDD-RESTART.md. That session performs input
assembly, a fresh canonical compile, normal bounded repairs, and final semantic
readback. A backend/timeout/semantic failure must remain an explicit failure;
this preparation cannot guarantee that a nondeterministic real-worker run
will succeed on its first process attempt. No additional product decisions or
manual cache cleanup are required from the user for the scoped restart.

`authorizes: []`
