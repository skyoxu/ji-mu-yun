"""Rebuild Package B input from readable committed requirements, not lost output."""
from pathlib import Path
import json,hashlib,re,subprocess
R=Path('/workspace/ji-mu-yun');B=R/'logs/package-b-rebuild-20261028';p=R/'docs/workflows/skill-control-plane-evolution-requirements.md';original=(B/'requirements-before-rebuild.md').read_text();old_b=original.split('## Package B: Existing Skill Compliance Migration\n',1)[1].split('## Cross-Package Stop Conditions',1)[0];old_outcomes=old_b.split('### Required outcomes\n',1)[1].split('### Acceptance gate',1)[0].strip()
new_b='''## Package B: Existing Skill Compliance Migration

### Objective and current baseline

Migrate the same five existing non-BMAD, non-Chapter-2-7 packages to the
accepted Package A standard. This is a difference migration, preserving the
current public entries, lifecycle owners and runtime gates. Package A is an
accepted prerequisite, not an implementation task in Package B.

The fresh rebuild is pinned to committed main
`fb676bc398f653a2ffa869c95d6c8d632f6f9796`, materialized in the original cloud
workspace on its existing branch. The missing 2026-10-27 temporary candidate
and its success reports are historical investigation clues only. New planning,
implementation and evidence must use readable current sources.

### Six retained requests

'''+old_outcomes+'''

These six requests remain the coverage source. Capability-conditioned controls
come from Package A; they do not grant new permissions. Preserve Context7-first
lookup and official fallback only when a real version-sensitive external API
requires them. Do not invent API lookups, a provider, database or network policy
for a package that does not own those effects.

### Adopted authority and direct reuse

- `docs/standards/skill-authoring-standard.md` and Accepted ADR-0062 own the
  quality standard. `scripts/sc/validate_skill_quality.py` is the existing
  strict/inventory public validator, with its existing policy and schemas.
  Package B must not implement a second validator or edit Package A's oracle.
- Use the existing `skill-quality.v1.json` sidecar shape. Keep only name and
  description in frontmatter. Reuse existing operational references and
  substantive declarations; add a separate guide only when details need to
  leave the main file. Do not create five parallel documentation frameworks.
- The five public workflows, their Q1/Q7/Q8/Acceptance/publisher gates, typed
  errors, caller-session transport and content-bound execution reuse already
  exist. Add quality declarations and focused migration checks, not replacement
  runtimes. A historical pass is not current verification.
- BMAD wrappers, official native installation, administrator read-only consumer
  registration and per-run local configuration forwarding are separate already
  committed work. They are background only, excluded from Package B writes.
  Device configuration and local paths remain ignored.

### Five-package difference map

| Package | Existing capability to reuse | Remaining migration work and observable checks |
| --- | --- | --- |
| VDD | `scripts/vdd/compile_plan.py`; planning, clarification, governance-mode, lifecycle, resume and native semantic validation | Add a valid quality sidecar, dependencies and create/direct-input/invalid-input primary examples. Keep plan-ready distinct from implementation and Acceptance; retain atomic source/contract coverage and native repair. |
| Quick Dev TDD | `scripts/quick_dev/run.py`; observed behavior routing, first-use JSON/Python/TOML, bounded authoring, RED/GREEN/REFACTOR, Q6, Q7/Q8 and execution reuse | Add quality metadata and strict-plan/upgrade-boundary/invalid-contract examples. An upgrade is a typed route to the owning VDD boundary, not automatic approval or BMAD fallback. Keep exact cases, failure IDs, write scopes, and per-unit budgets. |
| Bootstrap Review | `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py`; explicit existing profile/preflight/round and model-route controls | Add quality declarations and clean/later-round/access-failure examples without a new review framework. Replace machine-specific validation commands with actual repository-owned checks. Keep later-round and consumer authority intact; no automatic extra reviewer in this migration. |
| Refactor Acceptance | `.agents/skills/run-refactor-implementation-acceptance/scripts/run_acceptance.py`; existing prepare/coordinator/action and finalization owners | Add quality declarations and deterministic/repair/manual-or-stale examples. Preserve action registry, authority, current proof and finalization requirements; Q8 alone is not acceptance-passed. |
| Knowledge maintenance | `.agents/skills/maintain-knowledge-base/scripts/maintain_knowledge.py`, the request helper and native publisher | Add quality declarations and existing-only/targeted-provisional/publication-failure examples. Preserve main-bound source ownership, failed sidecars, LKG and explicit publication. Do not hard-code an obsolete suite count. Operator-requested needs a real target/main and maintainer confirmation, but no stale-route artifact; catalog-stale-maintenance retains its verified Acceptance route. |

Dependency declarations must identify real prerequisites, authority/version and
missing/mismatch outcomes. The adopted schema resolves package-local JSON
id/version records; a minimal non-authorizing declaration record may be needed.
Such a record documents an adopted contract version, not proof that Python,
Codex, a model, an external dependency or publication was installed or approved.
The native entry still checks actual runtime prerequisites. Preserve legitimate
child dependencies rather than claiming standalone means dependency-free.

### Execution and verification boundary

1. Inspect the five current packages, callers and focused tests; distinguish
   present behavior from missing quality metadata and stale prose.
2. Prepare a Package-B-only canonical requirements input with stable FR anchors
   and source-role/hash mapping. Include applicable global/consumption/drift
   constraints; exclude Package A implementation and unrelated BMAD artifacts.
   Cite existing files as file paths, function names as separate text, and
   directories as explanatory directories rather than malformed file inputs.
3. Use the public VDD compiler with the self-hosted plan-shape profile, because
   these are control-plane packages. Native workers and gates own plan-ready.
   VDD does not execute RED or emit future execution proof.
4. Quick Dev performs controlled probes. Present behavior gets current
   regression/terminal; missing behavior needs a real bound RED before Q4 and
   GREEN/REFACTOR. Absent imports, files or test runtimes are not behavioral RED.
   A genuine host admission defect is repaired narrowly with positive/negative
   tests before final input freezing, never by weakening the failure oracle.
5. Freeze common inputs before final proof. Reuse matching content/coverage/
   environment-bound native originals, not summaries or Git SHA alone. Keep
   failed evidence. Each independent unit retains 1800 seconds total and 600
   seconds without genuine progress; retries share bounded cumulative cost.
6. Run each of the five strict Package A public checks, relevant owning-package
   regressions and a route-boundary check. Preserve under-500-line main files,
   typed dependency failures and capability-aware security controls. Use actual
   supported local test dependencies; do not relabel Linux as Windows.
7. Formal inputs, implementation, plans and native evidence stay in the original
   repository. Save content-hashed stage snapshots and verify restoration;
   preserve an authorized durable copy outside the ephemeral environment.
   A missing old candidate cannot be reconstructed by copying success states.

### Acceptance gate and exclusions

The migrated five packages must pass the existing strict validator; directly
affected existing tests remain green and route checks show no authority,
lifecycle, security or compatibility regression. The complete plan must retain
all six requests and explicit test/case coverage. Native implementation-complete
is only Quick Dev completion. The requested independent A/B review and any
necessary repair come before the separately owned final Acceptance workflow.
Neither a sidecar nor a passing validator grants workflow or publication power.

Do not add a global runtime enforcement platform, daemon, database, MCP service,
new model-selection policy, blanket external-version gate or new approval system.
Do not change Phase services, BMAD/GDS, Chapter 2-7, accepted Package A authority,
private device configuration, existing budgets/security permissions or historical
receipts to make this migration pass. GitHub publication/merge and unrelated
Windows full workflows are not automatic parts of this cloud implementation.

'''
start=original.index('## Package B: Existing Skill Compliance Migration');end=original.index('## Cross-Package Stop Conditions');updated=original[:start]+new_b+original[end:]
updated=updated.replace('| 2 | VDD create/repair Package B | Five Skills migrated and individually validated |','| 2 | VDD create/repair Package B | Native plan-ready covering all five migration targets |\n| 3 | Quick Dev TDD Package B | Current implementation-complete with per-package validation |\n| 4 | Independent review, repair and Acceptance | Separate reviewed and verified final state |')
assert updated[:start]==original[:start]
p.write_text(updated,encoding='utf-8')
common=original.split('## Global Boundaries\n',1)[1].split('## Package A:',1)[0];stops=original.split('## Cross-Package Stop Conditions\n',1)[1].split('## Recommended Execution Order',1)[0]
# Preserve scope text while avoiding automatic interpretation of directory
# annotations as file sources. No source requirement is removed.
common=common.replace('`.agents/skills/`','the .agents/skills directory');common=common.replace('`AGENTS.md`','`AGENTS.md`')
canonical='# Package B canonical requirements (fresh rebuild)\n\n## FR-1 Applicable common constraints\n\n'+common+'\n## FR-2 Six original migration requests\n\n'+old_outcomes+'\n\n## FR-3 Current authority and difference migration\n\n'+new_b.split('### Adopted authority and direct reuse\n',1)[1].split('### Execution and verification boundary',1)[0]+'\n## FR-4 Execution and evidence boundary\n\n'+new_b.split('### Execution and verification boundary\n',1)[1].split('### Acceptance gate and exclusions',1)[0]+'\n## FR-5 Completion and non-goals\n\n'+new_b.split('### Acceptance gate and exclusions\n',1)[1]+'\n## FR-6 Source drift and repair\n\n'+stops+'\nSource provenance: `docs/workflows/skill-control-plane-evolution-requirements.md`, Package B plus applicable shared sections only. Package A implementation text is an accepted prerequisite, not an additional scope.\n'
# Public source discovery accepts paths and optional :: selectors; directory
# names above remain explanatory prose. Examples of future sidecar filenames
# without a slash are not existing source claims.
dir_re=re.compile(r'`([^`\s]+/)`');canonical=dir_re.sub(lambda m:'directory '+m.group(1),canonical)
out=R/'docs/workflows/inputs/package-b-rebuild-20261028';out.mkdir(parents=True,exist_ok=False);(out/'requirements.md').write_text(canonical,encoding='utf-8')
m={'schema':'package-b.input-source-map.v1','authorizes':[],'baseline_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'original_source':str(p.relative_to(R)),'original_source_before_rebuild_sha256':hashlib.sha256(original.encode()).hexdigest(),'revised_source_sha256':hashlib.sha256(updated.encode()).hexdigest(),'canonical_path':str((out/'requirements.md').relative_to(R)),'canonical_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'scope':'Only Package B six retained requests and five existing packages plus applicable common constraints. Package A implementation and BMAD runtime changes excluded.','anchors':{'FR-1':'Global Boundaries and VDD Consumption Contract','FR-2':'All six original Package B required outcomes verbatim','FR-3':'Adopted authority, current code reuse and five-package difference map','FR-4':'Canonical input, public workflows, actual TDD and evidence persistence','FR-5':'Acceptance gate and unchanged non-goals','FR-6':'Cross-Package Stop Conditions'},'normalizations':['Directory annotations are explicit prose, not file inputs. Existing code citations are real file paths. Function names are separate prose. Source map is traceability, not a native compiler receipt.'],'original_six_requests_verbatim':old_outcomes};(out/'source-map.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');print({'document_lines':len(updated.splitlines()),'canonical_bytes':len(canonical.encode()),'anchors':len(m['anchors']),'canonical_sha256':m['canonical_sha256']})
