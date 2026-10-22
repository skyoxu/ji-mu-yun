# BMAD 6.12.4 local implementation evidence

Date: 2026-10-22. Environment: independent Linux Web Work at `/workspace/scratch/6e089e29b8e4/ji-mu-yun-bmad-final`.
No user PC or configured Codex cloud environment was used. FastCtx was not
attached; the explicitly authorized Work shell was used. Accepted ADR-0041 and
ADR-0062 govern this bounded adapter change. No full VDD/Quick Dev/Acceptance,
Package B, knowledge-query feature or BMAD7 execution was requested or run.

## Branch and commit boundaries

- Branch: `refactor/bmad-6-native-wrappers`.
- Preserved starting HEAD: `5b3a6067082423348066a7ce760eca44ed880789`; clean initially.
- Implementation commit: `7a8cdaf160355b61ba1087c0147735a3c72aaecc`.
- Earlier wrapper migration/evidence commits remain in ancestry.
- This report and selected new evidence are committed afterward; their commit is
  the delivered HEAD reported in chat. No push, PR, merge or auto-merge occurred.
- Full per-path change summaries for both this continuation and the complete
  branch against fresh remote main are in `diff-summary.txt`.
- Implementation delta: 151 paths, 2,218 inserted / 13,645 removed lines. The bulk
  is 129 index removals (13,470 lines), not local deletion or history rewriting.

## Provenance and inventory

Official BMAD source: https://github.com/bmad-code-org/BMAD-METHOD at v6.12.4,
peeled commit `bab9082c3e884e0d72c759bcd1a6d90bcc01be84`. The annotated tag object is
`eecafe9d4bcad92166bee08623e0526009d862c4`; it is not the commit hash.

| Native source under src/bmm-skills/plan | Complete Git tree | Files |
| --- | --- | --- |
| bmad-spec | 385f63cb1d0e33ea670ca1f6c5bff8e7c80d4166 | 5 |
| bmad-architecture | 82413aa665685fa3484b7ce36f3c6835bd8661d8 | 7 |

Active per-file lock: `scripts/toolchain/bmad_native/v6.12.4.json`, SHA-256
`25eff629efa8dae95c0126247f608250f57182d93d17f8ed80fb3b1961de9f95`. Runtime closure is original memlog.py,
resolve_config.py, resolve_customization.py, config_utils.py. The 6.10.0 lock is
historical provenance only. CLI version is never native Skill version authority.

`distribution-inventory.json` inventories 178 candidates with original bytes,
source commits, source paths and dispositions. Removed from tracking: **129**
(93 BMAD-METHOD, 36 official Game Dev Studio resources). All remain on disk;
old SPEC/architecture originals were preserved in the explicit local replacement
backup. Exact ignores exclude native installs and runtime without hiding custom
entries. No official runtime is copied into tracked code or this evidence bundle.

**49 custom/binding files are retained byte-for-byte:** Windows launcher patches,
Quick Dev router/schema helper/tests/patched entrypoints, game-designer alias,
GDS launch patches and the gds-create-gdd entry/data mirror required by Phase A.
These mixed packages were reported before untracking. They are not blindly
replaced or upgraded. Other historical mixed-package resources need their own
explicit source-pinned installation if used from a clean clone; this installer
only supports the two wrappers and their runtime closure.

The custom jimuyun wrappers, VDD, Quick Dev, adapters, requirements, hash manifests,
installation guide and `_bmad/.gdignore` remain. No existing plan, registry,
receipt, manifest, snapshot, selection, generated output or historical proof was
rewritten. Local inventory and history-scope checks are machine-recorded in
`local-inventory-verification.json`.

## Functional changes

- Removed old runtime-provisioning behavior. A small explicit source installer
  verifies official bytes before installing. Existing installation requires an
  explicit backed-up replacement; no download, upgrade or fallback in preflight.
- Version metadata is project-local (scoped receipt or official manifest).
  Complete native inventory/hash, runtime closure, Python 3.11+, uv and actual
  TOML resolution must pass before any mutating wrapper business action.
- Both original resolvers use explicit project roots. Four TOML layers merge
  through the original resolver. Identity/language propagate; private SPEC uses
  core.output_folder, architecture config uses modules.bmm.planning_artifacts.
  Explicit native doc_workspace remains a supported caller override.
- Repository AGENTS and routing context are explicitly loaded before activation;
  upstream persistent_facts defaults empty. Native source is read in full.
- Typed role projection/publication, canonical bytes, domain hashes, selection
  authority and VDD source consumption remain intact. Canonical CLI publication
  now also gates native state; read-only canonical/VDD imports need no native run.
- Architecture lifecycle policy remains effective in initial invocation and each
  reviewer task. Its bytes and the upstream gate/headless/template are unchanged.
- Headless SPEC skips upstream interactive Story Breakdown; no new stories feature.

## Exact public failure prompts

All listed native failures return exit 2, `ok=false`, `supported_version=6.12.4`,
`authorizes=[]`. Preflight failures do not mutate business outputs, selection or
memlog. `UNSAFE_PATH` and existing package errors remain separate path/data errors.

| Code | Exact message |
| --- | --- |
| NATIVE_INSTALLATION_MISSING | Project-local BMAD is missing. Install official BMAD 6.12.4 for these wrappers; a global CLI is not a project installation. |
| NATIVE_VERSION_UNKNOWN | Cannot establish the project installation version. Explicitly install official BMAD 6.12.4 and record its project-local source. |
| NATIVE_VERSION_OLD | Upgrade the project-local native installation to official BMAD 6.12.4, then retry. No automatic upgrade was performed. |
| NATIVE_VERSION_NEWER | These wrappers support only BMAD 6.12.4. Do not upgrade further; use a separate original 6.12.4 project installation or adapt the wrappers first. |
| NATIVE_VERSION_CONFLICT | Project installation metadata disagree. Reconcile the installation explicitly; these wrappers support only official BMAD 6.12.4. |
| NATIVE_TREE_DRIFT | BMAD Skill content does not match the complete official 6.12.4 trees. Reinstall original 6.12.4; do not patch files or bypass hashes. |
| NATIVE_RUNTIME_MISSING | BMAD 6.12.4 requires Python 3.11+, uv and its complete official runtime dependency closure. Install the missing dependency, then retry. |
| NATIVE_RUNTIME_DRIFT | BMAD runtime dependencies do not match official 6.12.4. Reinstall the original 6.12.4 runtime, including config_utils.py. |
| NATIVE_CONFIG_INVALID | Project BMAD TOML configuration is missing or invalid. Repair _bmad/config.toml and its optional override layers for 6.12.4 before retrying. |
| NATIVE_SOURCE_MISMATCH | The supplied source is not the pinned official BMAD 6.12.4 distribution. Obtain that exact official version; no download or fallback was attempted. |
| NATIVE_INSTALL_CONFLICT | Existing installation would be replaced. Preserve it or explicitly select --replace-native for a backed-up local replacement; no automatic upgrade was performed. |

## Commands and results

Run from the repository root with PYTHONDONTWRITEBYTECODE=1, PYTHONUTF8=1,
UV_OFFLINE=1. This Work used Python 3.12 and uv; pytest/PyYAML came from an isolated
test venv, not from a fabricated native runtime.

```text
python -B -m pytest -q scripts/toolchain/bmad_native/test_preflight.py .agents/skills/jimuyun-spec/scripts/tests .agents/skills/jimuyun-architecture/scripts/tests .agents/skills/bmad-architecture/scripts/tests scripts/toolchain/canonical_evidence/tests -k 'not test_acceptance_and_bootstrap_use_the_shared_canonical_bytes'
```

Actual interpreter: `/workspace/scratch/6e089e29b8e4/bmad-test-venv/bin/python`.
**96 passed, 1 deselected**, exit 0; see `regression-final.log`.
The excluded existing Bootstrap/Acceptance import test needs an unavailable
Codex model configuration. It was neither edited nor represented as passing.
Earlier failure history remains in the preceding implementation evidence.

Coverage: typed normative/adopted/provenance two-round round-trip; renderer
reordering; stable descriptor/selection hashes and immutable record mtime;
VDD build_manifest/validate_manifest; canonical_evidence identity and parents[4];
missing/stale selection; unsafe Windows/POSIX lexical paths; Chinese/space paths,
UTF-8/CRLF inputs; actual TOML merge and customization; all mutating entries reject
missing/old/newer/BMAD7/changed/extra-file/wrong-runtime/config failures without
business side effects. Actual original 6.10.0 bytes were additionally rejected by
both wrappers: `actual-610-rejection.json` (not just altered metadata).

```text
python -B scripts/sc/validate_skill_quality.py --repository-root . --policy scripts/sc/config/skill-authoring-standard.v1.json --skill-root .agents/skills/jimuyun-spec --mode strict
python -B scripts/sc/validate_skill_quality.py --repository-root . --policy scripts/sc/config/skill-authoring-standard.v1.json --skill-root .agents/skills/jimuyun-architecture --mode strict
```

Both strict quality results passed with no diagnostics. Skill-creator
quick_validate also passed both wrappers using the isolated test interpreter.
`git diff --check` passed before commit.

Real native workflows (not deterministic fixture substitutes):

- SPEC create and no-scope-change refresh executed the original activation,
  resolvers, memlog and Coherence/Preservation methodology. Both publications
  succeeded; CAP-1..4, typed roles and selection hash remained stable. Memory
  appended from 18 to 23 entries with the original body prefix preserved.
  Actual sample VDD source manifest was built and validated; see
  `native-spec-consumer-manifest.json`. This is consumer verification, not a full
  VDD plan run.
- Architecture executed input reconciliation and the entire independent rubric,
  reality/research and adversarial reviewer set. All terminal before final lint;
  initial/final lint had zero findings. Native result is **partial** because the
  example intentionally supplied no code/interface/durability implementation.
  Document frontmatter final is not implementation approval. All initial task
  lifecycle constraints and actual waits are recorded in execution-evidence.json.
- Six actual project/native copies passed final complete byte verification in
  `post-workflow-native-verification.json`. Upstream source checkout is unchanged.
- Timeout/unknown-agent error recovery is covered by the preserved controlled
  scenario evidence and unchanged initial policy assertions. No live agent fault
  was injected; those scenarios are not falsely labeled live recovery tests.

`clean-clone.json` records a real fresh local Git clone (shared object store,
clean tracked checkout, no native installation copied), both wrappers failing
missing-install before writes, explicit installation from official source,
successful verify, empty git status and no native files in git ls-files. Sharing
Git objects does not supply ignored native installation files.

## Clean clone installation

Install Python 3.11+ and uv first. From a clone of this branch:

```text
git -c core.autocrlf=false clone --branch v6.12.4 --single-branch https://github.com/bmad-code-org/BMAD-METHOD.git ../BMAD-METHOD-6.12.4
python -B -m scripts.toolchain.bmad_native install-from-source --source-root ../BMAD-METHOD-6.12.4
python -B -m scripts.toolchain.bmad_native verify
```

On Windows use `py -3 -B -m ...` if that is the installed Python launcher. Quote
paths containing spaces. PowerShell environment form: `$env:PYTHONUTF8='1'`,
`$env:PYTHONDONTWRITEBYTECODE='1'`, `$env:UV_OFFLINE='1'`; POSIX uses export.
Native source LF bytes must remain intact. Installation is explicit and local;
untracked native resources are intentional dependencies, not omitted delivery code.

## Fresh GitHub main audit after implementation

At `2026-10-22T13:26:17.044166+00:00`, fetched `origin main`, checked live
`git ls-remote origin refs/heads/main`, then read the fetched complete tracked tree.
No local main ref was used.

- Remote main SHA: `bf78bb43c5583571eab9ec4001fb3c3a913c0708`.
- Remote main tree: `e1a48456837237707ad68c39713c355233b7be9e`; 39,821 entries.
- Remote official installation/distribution residuals: **125**.
- Remote custom/binding files: 49; legacy customized SPEC/architecture files: 8
  (four patched native entries plus four repository canonical files).
- Local branch official installation/distribution residuals: **0**.
- The four patched remote entries were restored to official trees by the earlier
  local wrapper split, explaining 125 remote originals versus 129 local removals.

Exact paths, blob IDs and SHA-256 values are in `remote-main-audit.json`.
Documentation, historical references, custom wrappers and repository compatibility
bindings are excluded from deletable official residuals. **Remote main remains
uncleaned because no push/merge was authorized or performed.**

## Limits and diagnostic honesty

Windows was not executed natively. Linux Chinese/space/CRLF and lexical path
checks are not Windows process, NTFS junction or launcher tests. No crash-atomic
multi-file publication guarantee was introduced. Native semantic output remains
LLM workflow evidence, not implementation Acceptance. The Architecture sample's
three implementation questions remain open by design.

Two exploratory old-source lookup commands used incorrect source paths before
correcting SPEC to src/core-skills/bmad-spec; they failed without product changes.
A validator --help probe returned INVALID_ARGUMENTS because that existing CLI has
no help option. The native architecture sample also records its initial module
path failure and explicit-root/PYTHONPATH correction. No such diagnostic was
counted as a successful workflow or dependency substitute.
