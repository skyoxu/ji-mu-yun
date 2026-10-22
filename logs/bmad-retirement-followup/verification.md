# BMAD retirement continuation evidence

## Scope and commits

- Independent Web Work: `/workspace/scratch/6e089e29b8e4/ji-mu-yun-bmad-final`.
- Branch: `refactor/bmad-6-native-wrappers`.
- Starting HEAD, preserved: `1a2684dc42cb63d1a4f575ee5e66047fd26d5670`; initially clean.
- Code commit: `8b5dcec074791f55995340d93d0950c2f5816358`.
- No push, PR, merge, user PC or configured Codex cloud changes.

## Decision and changes

36 files were removed from the index only, with local bytes preserved: 6 unused Stock Quick Dev files and 30 explicitly retired game files (1 alias, 3 GDS entry/validation customizations, 26 GDD compatibility files including 25 data mirrors). Exact ignores, inventory and five current documentation/index files were updated. Code diff: 43 files, 286 insertions, 3282 deletions. `diff-summary.txt` contains every changed path.

The original 178-row inventory now has 165 untracked rows and 13 retained rows. The 165 includes the original 129 source-proven distributions plus 36 retired mixed/custom files; it is not a count of 165 unmodified upstream files. The remaining 13 and upstream-derived repository game guides mean this is not literal removal of every BMAD-derived byte. Repository adapters, VDD, independent Quick Dev TDD, immutable plans/registries/receipts/manifests/hash evidence are preserved.

## 13 launcher files: correction and evidence

All 13 files match official 6.10.0 commit `081e64ee5aab2316b912883f7bee528ee143ce36` after only substituting `python3` with `py -3`. There are no other content changes. `py -3` is Windows Python Launcher selecting Python 3. The files are BMAD Skill instructions, not unrelated Windows code. Describing them as 13 complex business customizations would be wrong. This continuation did not authorize their removal.

Typical exact evidence:

- Local `.agents/skills/bmad-advanced-elicitation/SKILL.md`, upstream `src/core-skills/bmad-advanced-elicitation/SKILL.md`: old `python3 {project-root}/_bmad/scripts/resolve_config.py --project-root {project-root} --key agents`; repository changes only the launcher to `py -3`. Official 6.12.4 uses `uv run` for this call.
- Local `.agents/skills/bmad-code-review/SKILL.md`, old upstream `src/bmm-skills/4-implementation/bmad-code-review/SKILL.md`: `python3 .../resolve_customization.py --skill {skill-root} --key workflow` becomes `py -3 ...`. The 6.12.4 successor is under `src/bmm-skills/ship/`, uses `uv run` and explicit project root.
- PRD `references/validate.md` changes the `python3 -c` webbrowser launcher to `py -3 -c`. This is still launcher-only, not a resolver-only patch.

6.12.4 has changed paths/consolidations/deprecated shims, so retiring all 13 cannot be described as blindly restoring the old paths from the new release. Per-file old source, exact diff and relevant new source evidence are in `classification.json`.

## Quick Dev dependency decision

No active Phase service/runtime/CI or toolchain execution caller was found in the targeted sources (318 Phase/runtime/CI source files plus skills, scripts and current routing documents). The removed Skill invokes its own router and helper; its dedicated test tests that router. The obsolete manual recommendation was removed without redirecting behavior to bmad-build.

`scripts/quick_dev/run.py:12-13` invokes `quick-dev-tdd-adapter/tools/stable_runner.py`, not the retired Stock Skill. `quick-dev-tdd-adapter/tools/tests/test_plan_directory_loop.py:332` passes bmad-quick-dev as a rejected caller to another router. Bootstrap semantic-review names are exclusivity labels, not dispatch. These independent files/tests remain. The scoped installer neither installs nor validates bmad-build, and no former custom routing policy was migrated to it.

## Deliberate game impact and deferred decision

`PhaseA.Platform/Skills/SkillActionCatalog.cs:9` still registers `game-design-master` using bmad-agent-game-designer. `PhaseA.Platform/Runs/GameDesignDocumentService.cs:1376` still requests that Skill. A fresh clone does not provide it. These old entry points must be treated as temporarily unavailable; no service registration was changed and automatic fail-closed behavior is not established.

`PhaseA.Platform/Prototypes/BmadGameTypeDesignCatalog.cs:33-107` loads all present docs/canonical/mirror catalogs and records source provenance. `GameDesignDocumentService.cs:2095-2117` consumes the source entries. The removed mirror was not merely a historical mention or the sole data source: docs guides remain, but the source set changes. No service-level behavior/contract was rewritten.

If the old service entry points must be exposed before sandbox reconstruction, the minimal separate decision is to hide/disable game-design-master and gate the legacy GDD-outline route before dispatch. That registration/contract change was not authorized or implemented here.

`scripts/python/tests/test_game_type_guides_module_matrix.py` retains its canonical installation, mirror and alias assertions. They cannot pass on an unprovisioned fresh clone. They were not deleted, weakened or claimed green. Only the dedicated retired Quick Dev package test was untracked with its package.

## Verification

Executed focused regression:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 UV_OFFLINE=1 /workspace/scratch/6e089e29b8e4/bmad-test-venv/bin/python -B -m pytest -q scripts/toolchain/bmad_native/test_preflight.py .agents/skills/jimuyun-spec/scripts/tests .agents/skills/jimuyun-architecture/scripts/tests .agents/skills/bmad-architecture/scripts/tests scripts/toolchain/canonical_evidence/tests -k 'not test_acceptance_and_bootstrap_use_the_shared_canonical_bytes'
```

Result: **96 passed, 1 deselected in 15.05s** (`wrapper-regression.log`). The existing Acceptance/Bootstrap import integration case needs unavailable Codex model configuration and remains excluded; this is not acceptance-passed. No full VDD, Phase/GDS suite or semantic LLM workflow rerun was performed in this continuation. Previous SPEC/Architecture native workflow evidence remains in `logs/bmad-6124/`.

`python -B -m scripts.toolchain.bmad_native verify` passed: official 6.12.4, 16 locked native/runtime files. SPEC tree `385f63cb1d0e33ea670ca1f6c5bff8e7c80d4166`; Architecture tree `82413aa665685fa3484b7ce36f3c6835bd8661d8`. No native bytes changed in this continuation. `git diff --check` and staged whitespace checks passed.

`local-inventory-check.json` verifies 36 local files retained, exact ignore coverage, historical/Phase code unchanged, custom adapters and GDS tests retained.

`clean-clone.json` records a new local shared-object sparse clone at the code commit: all 36 retired paths absent, all 13 retained launcher files present; missing native verification exits 2 with NATIVE_INSTALLATION_MISSING; explicit install from the verified official 6.12.4 checkout succeeds; verify passes; git status remains clean. This is a targeted sparse checkout, not a full network clone. Its initial setup warned about one unavailable out-of-scope .claude README object in the source partial clone; relevant checkout and status succeeded. No Windows host was available; Linux checks are not Windows execution evidence.

## Installation limits

Use the existing documented explicit install-from-source command against official BMAD-METHOD 6.12.4 commit `bab9082c3e884e0d72c759bcd1a6d90bcc01be84`, then verify. This provisions the two native Skills and four locked runtime dependencies only. It does not restore retired game capabilities or bmad-build.

Shared-runtime risk remains: `--replace-native` backs up and replaces the entire `_bmad/scripts` directory, then installs only four locked files; other helpers move into backup and are not automatically restored. A full official installer may overwrite the 13 retained launcher patches; Git/ignore is not overwrite protection. GDS is separate from the verified BMAD-METHOD 6.12.4 source. No wider runtime fix was made.

## Fresh remote main audit

At 2026-10-22 14:48 UTC, fresh `git fetch origin main`, agreeing `git ls-remote`, and full remote tree inspection returned:

- main: `bf78bb43c5583571eab9ec4001fb3c3a913c0708`
- tree: `e1a48456837237707ad68c39713c355233b7be9e`
- 39,821 tracked tree entries.
- 125 source-confirmed official distribution files still tracked; 49 previously retained mixed/custom files plus 8 legacy SPEC/Architecture customizations also remain there. Their blobs were verified unchanged against the prior source audit. `_bmad/.gdignore` is a repository Godot exclusion marker, not a distribution residual.

The local branch has only 13 retained files from the 178-row cleanup inventory. Remote main has not been cleaned by these local commits. Documentation, historical evidence and custom wrappers are not counted as removable official installation residuals. See `remote-main-audit.json` for exact paths and blobs.
