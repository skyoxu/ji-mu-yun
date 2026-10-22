# BMAD wrapper implementation verification

Date: 2026-10-22. Scope: authorized extraction, local commits only; no push,
merge, auto-merge, BMAD7, framework upgrade, Package B, knowledge feature or
Acceptance run. This is not acceptance-passed.

## Baseline and delivered checkout

- GitHub main: `bf78bb43c5583571eab9ec4001fb3c3a913c0708`; checked at start and
  rechecked with `git ls-remote origin refs/heads/main` before finalization.
- Branch: `refactor/bmad-6-native-wrappers`.
- Implementation commit: `e4900e4a` (evidence is appended in a separate commit).
- Delivery checkout: `/workspace/scratch/6e089e29b8e4/ji-mu-yun-bmad-final`.
- Earlier Work checkout and all run evidence remain preserved under
  `/workspace/scratch/6e089e29b8e4/ji-mu-yun-bmad-wrappers`.
- Official v6.10.0: `081e64ee5aab2316b912883f7bee528ee143ce36`.
- SPEC complete tree: `ed1f7c24d848d493ac131064392e8ef7cc86615e` (4 files).
- Architecture complete tree: `402b1adbc4aee309b8fcfe14d56055c5d3990a78` (7 files).
- Both also equal the original trees at import
  `a57640d685e0d3fc4875a42f67a1ba34d62f6555`.
- Environment CLI 6.12.4 is not a Skill version or upgrade instruction.

## Changes and ownership

Two new adapters read and execute original native Skills. The original workflow
method, templates and reviewers remain native; the wrappers do not duplicate the
workflow. SPEC prepare owns the private string-array projection and frozen role
map; native owns private content and append-only memory; publish alone owns the
canonical typed output and selection publication. Existing roles and ordering
survive update/refresh. New roles and removals require explicit caller input.

Architecture injects reviewer lifecycle constraints before native activation and
in initial reviewer messages. Dispatch and waiting use real agent lifecycle APIs.
The complete reviewer set must finish before edits/lint/finalization; a material
fix requires a complete fresh gate. Native altitude/purpose are forwarded when
supplied and otherwise remain native inference, rather than fixed wrapper choices.

The old canonical producer and two existing tests moved byte-for-byte. The
contract reference changes ownership prose only. Three active import sites move
to jimuyun-spec: VDD source_freeze.py, its validator and shared canonical-evidence
migration tests. `parents[4]` and the shared canonical_bytes/domain_hash import
are tested. Existing schema/hash domains, role graph, descriptor ordering,
selection/current authority and VDD content hashes retain their semantics.

The native lock checks complete inventories and bytes, including rejection of
extra files, before and after each run. Three official runtime scripts are
explicitly provisioned offline outside the native Skill trees; no general BMAD
installer ran. Routing and current operation docs identify the new entrypoints.

No historical plans, command registries, receipts, manifests, snapshots or hash
proofs were modified. Historical command paths remain evidence of their frozen
revision and require that checkout for replay. New test manifests are sample
evidence only. No native compatibility shim remains in the delivered checkout.

## Commands and results

All commands below use the delivery repository root unless specified. Test
Python was a temporary Work venv with pytest 9.1.1 and PyYAML 6.0.3; runtime uses
Python 3.12, uv, PYTHONUTF8=1 and PYTHONDONTWRITEBYTECODE=1.

```text
python -B -m scripts.toolchain.bmad_native install-runtime --upstream-root ../bmad-upstream-6.10.0
python -B -m scripts.toolchain.bmad_native verify
```

Both exit 0. Complete file inventories also compared directly with the official
checkout; `final-native-inventory.json` records the result. All four semantic
run mirrors (SPEC create/update/refresh and architecture create) passed verification.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 /workspace/scratch/6e089e29b8e4/bmad-test-venv/bin/python -B -m pytest -q .agents/skills/jimuyun-spec/scripts/tests .agents/skills/jimuyun-architecture/scripts/tests .agents/skills/bmad-architecture/scripts/tests scripts/toolchain/canonical_evidence/tests -k 'not test_acceptance_and_bootstrap_use_the_shared_canonical_bytes'
```

Delivery checkout result: **80 passed, 1 deselected in 3.34s**, exit 0.
Coverage includes typed multi-role two-round refresh, an adopted companion inside
its package, renderer reordering with stable hashes and record mtime, real VDD
build/validate, shared import/root discovery, absent/stale pointer or record,
unsafe path and symlink rejection, input/memory drift, missing dependencies and
native missing/changed/extra files. Linux cases include Chinese/space paths and
CRLF input. No native tree was changed by these tests.

The deselected test is the unrelated Bootstrap/Acceptance import test. The earlier
broader invocation produced 45 passed/1 failed because Bootstrap imports require
a valid Codex model configuration absent in Work. That failure remains in
unit-second.log; no model configuration was fabricated and that test was not
edited. The initial fixture memlog failures and their correction also remain in
unit-first.log. These are not hidden successful suite runs.

```text
python -B scripts/sc/validate_skill_quality.py --repository-root . --policy scripts/sc/config/skill-authoring-standard.v1.json --skill-root .agents/skills/jimuyun-spec --mode strict
python -B scripts/sc/validate_skill_quality.py --repository-root . --policy scripts/sc/config/skill-authoring-standard.v1.json --skill-root .agents/skills/jimuyun-architecture --mode strict
```

Both exit 0, status pass, diagnostics empty, authorizes empty. The skill-creator
quick_validate.py also reports both Skills valid. The moved negative fixture:

```text
python -B .agents/skills/jimuyun-spec/tests/fixtures/selection_registry_negative.py
```

Returns **1 as expected** for the intentionally invalid selection. `git diff
--check` passes. Native integrity rejection was not bypassed.

## Actual semantic and consumer evidence

SPEC uses actual native instructions, customization resolver, official memlog
init/append and coherence/preservation passes. It is an LLM workflow, not a
claimed standalone bmad-spec executable. Three actual calls created, updated and
refreshed a local note contract. CAP-1/2/3 and provenance survived; update adds
an explicit 100-character title limit while preserving two unresolved questions.
Final refresh changes no SPEC or source bytes and preserves all 26 prior memlog
entries while appending 6. Its candidate and before-publish evidence exist.

Selection hash remained:
`sha256:c9af0ac0f47e492d688df66b0abd9e63824ee6ca78b183869597bc71f85dd944`.
The immutable selection file SHA-256 remained
`ce0287983e091e986083d9c909ca231f4c2af1b176726f535dfc2fe0b65cebbe`,
and mtime_ns stayed `1792669636593415231`.

The actual final native-derived typed SPEC was then consumed by the real VDD
build_manifest and validate_manifest functions: pass, three source entries,
same selection hash and empty authorizes. No full VDD workflow was invoked.

Architecture executed official resolver, memlog and lint, one independent input
reconciliation and a parallel complete rubric/reality/adversarial gate. Both
lint runs found zero findings. Gate verdicts: PASS / PASS WITH LIMITATION / PASS.
The limitation is lack of implementation source: supplied reality descriptions
are not proof of code conformance. Every gate agent was terminal before final
commands. A real timeout was followed by one agent-state inspection and the
proper lifecycle wait. Review policy was inline at reviewer dispatch; the full
native invocation was supplied by mandatory initial read path. No late audit
was substituted for initial policy.

Five independent controlled scenario responses cover unfinished reviewers,
wrong wait route, timeout, missing reviewer after inspection, and material
post-review changes. They agree with the lifecycle contract. They are explicitly
`controlled_scenario_not_live_fault`, not injected live service faults.

Evidence files copied without rewriting original run records:

- semantic-spec-project/logs/bmad-wrappers/create/execution-evidence.json
- semantic-spec-project/logs/bmad-wrappers/update-title-limit/execution-evidence.json
- semantic-spec-project/logs/bmad-wrappers/final-refresh/execution-evidence.json
- semantic-spec-project/logs/bmad-wrappers/final-refresh/consumer-source-manifest.json
- semantic-architecture-project/logs/bmad-wrappers/create/execution-evidence.json
- lifecycle-scenario-responses.json

Relative paths above are under this verification directory. Large native mirrors,
review files and generated samples remain in the preserved local evidence tree;
the compact proof files and test log are committed alongside this report.

## Limits and environment observations

- No native Windows, junction/reparse or Windows process execution was available.
  POSIX path math, UTF-8 and CRLF tests on Linux do not claim Windows execution.
- No live route-error injection. Timeout recovery was observed; other error
  branches use explicit controlled scenario evaluation and static policy checks.
- Architecture semantic proof covers create/build-substrate. Update workspace
  binding and option forwarding have deterministic tests; native discussion and
  validate-report branches were not semantically run. Required optional native
  editorial/review dependencies must be available or reported blocked.
- Multi-file publication is not an atomic crash transaction. Selection commits
  descriptor membership, not body bytes. Candidate validation, before-publish
  copies and source hashes support explicit recovery; crash recovery was not
  fault-injected or claimed automatically safe.
- FastCtx was unavailable. All work used the isolated Linux Work runtime, not
  the user's PC or configured Codex cloud environment.
- The first Work checkout repeatedly rematerialized four removed legacy files
  between tool calls. The native guard correctly rejected the extra inventory.
  A fresh checkout of the exact local commit avoids the anomaly; repeated checks
  and all 80 tests pass there. The earlier checkout and failures remain preserved.
- A local partial-clone setup initially reported a missing off-cone object; its
  original promisor configuration was restored and sparse checkout reapplied.
  Delivery status, native inventory and tests then passed. No content repair or
  unrelated cleanup was committed.

## Full implementation diff summary

```text
 .agents/skills/bmad-architecture/SKILL.md          |   2 +-
 .../bmad-architecture/references/reviewer-gate.md  |   2 -
 .agents/skills/bmad-spec/SKILL.md                  |  22 +-
 .agents/skills/bmad-spec/assets/spec-template.md   |   5 +-
 .agents/skills/jimuyun-architecture/SKILL.md       |  32 +++
 .../skills/jimuyun-architecture/agents/openai.yaml |   3 +
 .../references/native-version.json                 |   6 +
 .../jimuyun-architecture/references/operation.md   |  54 ++++
 .../references/reviewer-lifecycle.md               |  33 +++
 .../skills/jimuyun-architecture/scripts/invoke.py  |  80 ++++++
 .../scripts/tests/test_invoke.py                   |  61 ++++
 .../jimuyun-architecture/skill-quality.v1.json     | 190 +++++++++++++
 .agents/skills/jimuyun-spec/SKILL.md               |  30 ++
 .agents/skills/jimuyun-spec/agents/openai.yaml     |   3 +
 .../references/canonical-package-contract.md       |   6 +-
 .../jimuyun-spec/references/native-version.json    |   6 +
 .../skills/jimuyun-spec/references/operation.md    |  77 ++++++
 .agents/skills/jimuyun-spec/scripts/bridge.py      | 306 +++++++++++++++++++++
 .../scripts/canonical_package.py                   |   0
 .../jimuyun-spec/scripts/tests/test_bridge.py      | 168 +++++++++++
 .../scripts/tests/test_canonical_package.py        |   0
 .agents/skills/jimuyun-spec/skill-quality.v1.json  | 190 +++++++++++++
 .../tests/fixtures/selection_registry_negative.py  |   0
 .../vdd-execution-plan/scripts/source_freeze.py    |   2 +-
 .../tests/validators/source_freeze.py              |   2 +-
 docs/workflows/README.md                           |   1 +
 docs/workflows/bmad-native-wrappers.md             | 101 +++++++
 knowledge/toolchain-workflow-index.md              |   7 +
 scripts/toolchain/bmad_native/__init__.py          | 127 +++++++++
 scripts/toolchain/bmad_native/__main__.py          |  28 ++
 scripts/toolchain/bmad_native/testing.py           |  35 +++
 scripts/toolchain/bmad_native/v6.10.0.json         |  23 ++
 .../tests/test_consumer_migrations.py              |   2 +-
 33 files changed, 1573 insertions(+), 31 deletions(-)
```

```text
M	.agents/skills/bmad-architecture/SKILL.md
M	.agents/skills/bmad-architecture/references/reviewer-gate.md
M	.agents/skills/bmad-spec/SKILL.md
M	.agents/skills/bmad-spec/assets/spec-template.md
A	.agents/skills/jimuyun-architecture/SKILL.md
A	.agents/skills/jimuyun-architecture/agents/openai.yaml
A	.agents/skills/jimuyun-architecture/references/native-version.json
A	.agents/skills/jimuyun-architecture/references/operation.md
A	.agents/skills/jimuyun-architecture/references/reviewer-lifecycle.md
A	.agents/skills/jimuyun-architecture/scripts/invoke.py
A	.agents/skills/jimuyun-architecture/scripts/tests/test_invoke.py
A	.agents/skills/jimuyun-architecture/skill-quality.v1.json
A	.agents/skills/jimuyun-spec/SKILL.md
A	.agents/skills/jimuyun-spec/agents/openai.yaml
R093	.agents/skills/bmad-spec/references/canonical-package-contract.md	.agents/skills/jimuyun-spec/references/canonical-package-contract.md
A	.agents/skills/jimuyun-spec/references/native-version.json
A	.agents/skills/jimuyun-spec/references/operation.md
A	.agents/skills/jimuyun-spec/scripts/bridge.py
R100	.agents/skills/bmad-spec/scripts/canonical_package.py	.agents/skills/jimuyun-spec/scripts/canonical_package.py
A	.agents/skills/jimuyun-spec/scripts/tests/test_bridge.py
R100	.agents/skills/bmad-spec/scripts/tests/test_canonical_package.py	.agents/skills/jimuyun-spec/scripts/tests/test_canonical_package.py
A	.agents/skills/jimuyun-spec/skill-quality.v1.json
R100	.agents/skills/bmad-spec/tests/fixtures/selection_registry_negative.py	.agents/skills/jimuyun-spec/tests/fixtures/selection_registry_negative.py
M	.agents/skills/vdd-execution-plan/scripts/source_freeze.py
M	.agents/skills/vdd-execution-plan/tests/validators/source_freeze.py
M	docs/workflows/README.md
A	docs/workflows/bmad-native-wrappers.md
M	knowledge/toolchain-workflow-index.md
A	scripts/toolchain/bmad_native/__init__.py
A	scripts/toolchain/bmad_native/__main__.py
A	scripts/toolchain/bmad_native/testing.py
A	scripts/toolchain/bmad_native/v6.10.0.json
M	scripts/toolchain/canonical_evidence/tests/test_consumer_migrations.py
```

The evidence-only follow-up commit adds this report, the compact JSON observations,
strict declaration results, native inventory and the clean-checkout test log.
It does not change implementation or any preexisting historical evidence.
