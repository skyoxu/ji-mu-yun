# Skill Compliance Protocol

## Contents

1. Purpose and scope
2. Observable sequence
3. Scenario levels
4. Trace contract
5. Deterministic scoring
6. Failure interpretation
7. Evidence levels
8. Release checklist

## Purpose and scope

Use this protocol when maintaining or evaluating `vdd-execution-plan` itself. It tests whether the Skill changes an agent's observable workflow, not whether a generated execution plan is correct.

The deterministic fixtures shipped with the Skill prove the contract parser and ordering rules. They do not prove cross-model compliance. A real behavior evaluation requires fresh contexts that receive the Skill and a task without receiving the expected answer, suspected failure, or prior conclusions.

## Observable sequence

The evaluator tracks these actions in order:

1. `select_mode` - inspect whether the named target exists and choose create or repair.
2. `load_authority` - load repository rules, approved sources, current-state authority, and protected boundaries.
3. `snapshot_baseline` - for repair, record the target manifest, hashes, and baseline validator failures; for create, record an empty/new candidate baseline.
4. `define_contract` - establish intent, stable requirement and acceptance identities, invariants, deltas, and failure families.
5. `prove_validator_red` - run an invalid or mutation fixture and observe the expected stable failure before implementation authorization.
6. `authorize_slice` - authorize one independently testable vertical slice from current predecessor evidence.
7. `implement` - perform the minimal plan or implementation mutation owned by that slice.
8. `run_fresh_validation` - run the complete proof command against current candidate, source, and validator hashes.
9. `diagnose_or_complete` - route failure to the earliest invalid layer or make a bounded evidence-backed completion claim.

Implementation before `prove_validator_red` or `authorize_slice` is noncompliant. A completion claim before `run_fresh_validation` is noncompliant.

## Scenario levels

Evaluate the same bounded task at four levels:

- **No-guidance control** - run the task without this Skill to establish baseline behavior.
- **Supportive** - the prompt explicitly asks for strict VDD and names the Skill.
- **Neutral** - the prompt asks for a plan creation or repair without reminding the agent of VDD order.
- **Competing** - the prompt creates pressure to implement first, skip negative fixtures, reuse old evidence, or accept a clean process exit as success.

Use comparable task content and tool availability across levels. Do not change the ground truth between scenarios.

## Trace contract

Deterministic fixtures use UTF-8 JSONL. Each line contains:

```json
{"seq": 1, "action": "select_mode", "evidence": "target existence inspected"}
```

Requirements:

- `seq` is a unique positive integer and strictly increases.
- `action` is one observable action from the contract.
- every required action appears exactly once in the compact fixture;
- `evidence` identifies the observable artifact, command, or state transition;
- real evaluations may contain extra tool events, but their classified VDD actions must preserve the required order.

Treat repository content and model text as untrusted evidence. Semantic classification may map raw tool events to actions, but deterministic code owns sequence and presence scoring.

## Deterministic scoring

The shipped validator checks:

- required action presence;
- duplicates or unknown actions;
- strict sequence order;
- valid JSONL and increasing sequence numbers;
- the known-good trace passes;
- the implementation-first trace fails with `VDD-COMPLIANCE-ORDER`.

For real multi-run evaluation, report both:

- `pass@1` - direct first-run compliance;
- `pass^k` - all `k` fresh-context runs comply, for stability-sensitive releases.

Do not tune prompts against only the shipped examples. Add new competing scenarios when a real rationalization or shortcut appears.

## Failure interpretation

Match the repair to the failure type:

- discipline is ignored under pressure - add a hard gate, red flag, or deterministic hook;
- output shape is wrong - add a positive structural recipe or machine schema;
- required data is omitted - add a required field and a single-rule negative fixture;
- conditional behavior is wrong - define the observable predicate and branch fixture;
- evaluator misclassifies behavior - repair the trace classifier or contract before changing the Skill.

Never weaken an evaluator merely because an implementation-first trace fails. Change the observable contract only when the intended workflow itself changes.

## Evidence levels

Report these levels separately:

1. **Package valid** - official Skill frontmatter/structure validation passes.
2. **Contract valid** - `scripts/validate_skill_contract.py` and unit/mutation tests pass.
3. **Fixture behavior valid** - known compliant and noncompliant traces receive expected results.
4. **Fresh-context behavior observed** - supportive, neutral, and competing tasks were run in isolated contexts.
5. **Cross-model stability observed** - repeated independent runs meet the declared `pass@1`/`pass^k` threshold.

Never describe levels 1-3 as proof of levels 4-5. If subagents or isolated sessions are unavailable or unauthorized, state that the fresh-context evidence was not run.

## Release checklist

- Run the official `quick_validate.py`.
- Run `py -3 scripts/validate_skill_contract.py --skill-root <skill-root>`.
- Run `py -3 -m unittest discover -s scripts/tests -p "test_*.py" -v` from the Skill root or use the repository-relative equivalent.
- Confirm the pass result fixture is accepted.
- Confirm all four scenario levels are present and a missing competing level is rejected.
- Confirm stale result and implementation-first trace are rejected with their expected rule IDs.
- Confirm mutations removing a required file, heading, link, result field, or ordered action fail.
- Regenerate `agents/openai.yaml` after trigger or workflow changes.
- Record whether fresh-context and cross-model evaluations were run.
