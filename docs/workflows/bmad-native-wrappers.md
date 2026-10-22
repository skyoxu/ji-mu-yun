# Repository BMAD adapters

Governed by Accepted ADR-0041 and ADR-0062. The maintainer authorized two thin
repository wrappers and explicit support for official **6.12.4**. No BMAD7,
whole-framework upgrade, knowledge-query feature or Package B migration is implied.

## Ownership and source resolution

| Stage | Owner | Writes |
| --- | --- | --- |
| Repository SPEC create/update/refresh | jimuyun-spec prepare | Private string-array projection and frozen typed roles |
| Native SPEC method | Original bmad-spec | Private SPEC body, authored companions and memlog |
| Typed publication | jimuyun-spec publish | Canonical output and selection/current records |
| Architecture invocation | jimuyun-architecture | Private inputs and initial reviewer lifecycle policy |
| Native architecture method and reviewer gate | Original bmad-architecture | Private spine, memory and reviews |
| Source freeze | Existing VDD producer/validator | Existing manifests and source-content hashes |

Read the selected wrapper SKILL.md and its operation reference. Native resolution
is explicit: only `.agents/skills/bmad-spec/` and `bmad-architecture/` under the
supplied repository root, then exact private copies in the run. A global BMAD CLI,
home Skill directory, PATH discovery or environment CLI version never identifies
these native resources. Preparing invocation.md is not running the native method.
No wrapper modifies native source or copies the native workflow into its own prose.

Architecture policy is supplied before activation and inline in initial reviewer
tasks. The full rubric and every configured lens must be terminal before final
commands. Material fixes require a complete new gate. Verification does not grant
Acceptance or reviewer-completion authority. Headless SPEC follows upstream and
skips interactive Story Breakdown; stories are not a new repository feature.

## Supported official bytes

Official repository: https://github.com/bmad-code-org/BMAD-METHOD/tree/v6.12.4

- Version: 6.12.4, commit `bab9082c3e884e0d72c759bcd1a6d90bcc01be84`.
- `src/bmm-skills/plan/bmad-spec`: Git tree
  `385f63cb1d0e33ea670ca1f6c5bff8e7c80d4166`, 5 files.
- `src/bmm-skills/plan/bmad-architecture`: Git tree
  `82413aa665685fa3484b7ce36f3c6835bd8661d8`, 7 files.
- Required runtime: memlog.py, resolve_config.py, resolve_customization.py and
  config_utils.py from the same official source.
- Active per-file SHA-256 authority: `scripts/toolchain/bmad_native/v6.12.4.json`.
  The old v6.10.0 lock remains provenance only, never fallback authority.

Preflight checks version metadata, complete native inventories, byte hashes,
runtime dependency closure, Python 3.11+, uv and actual TOML resolution. It runs
before every mutating wrapper entry, including canonical_package.py --publish.
Read-only canonical and VDD imports still work without BMAD installed.

## Clean clone and explicit installation

A clean clone intentionally has no original BMAD installation. Install Python
3.11+ and uv on the execution host, then obtain the exact official source in a
separate directory. These commands are shell-independent Git/Python arguments:

```text
git -c core.autocrlf=false clone --branch v6.12.4 --single-branch https://github.com/bmad-code-org/BMAD-METHOD.git ../BMAD-METHOD-6.12.4
python -B -m scripts.toolchain.bmad_native install-from-source --source-root ../BMAD-METHOD-6.12.4
python -B -m scripts.toolchain.bmad_native verify
```

Run the Python commands from the repository root. On Windows the Python launcher
form is `py -3 -B -m scripts.toolchain.bmad_native ...`; use that consistently if
`python` is not the installed interpreter. Paths with spaces must be one quoted
argument. No Linux absolute path is part of the adapter or installation contract.

The explicit installer reads a verified source distribution, installs only the
two selected native Skills and four required runtime files, writes a scoped local
receipt and creates TOML defaults only when absent. It performs no download,
package-manager invocation or broad upgrade. Existing resources block unless the
maintainer explicitly adds `--replace-native`; that moves original directories
into a unique `logs/bmad-native-install/` backup before installing. It does not
patch upstream, rewrite an official manifest or overwrite a custom Skill. A
conflicting general installer manifest requires explicit reconciliation first.

`--replace-native` backs up and replaces the entire `_bmad/scripts` directory,
then installs only the four locked dependencies. Other locally installed runtime
helpers move into the backup and are not restored automatically. This is a
scoped installer, not a repair tool for a full BMAD/GDS installation.

An existing official project install can also be verified via its
`_bmad/_config/manifest.yaml` installation.version, provided native sources and
runtime bytes exactly match the lock. If both that manifest and the scoped receipt
exist, their versions must agree. Version labels alone never bypass byte checks.

Before native calls, set `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUTF8=1` and
`UV_OFFLINE=1`. PowerShell uses `$env:NAME='value'`; POSIX shells use
`export NAME=value`. uv and Python must already be installed. Neither wrapper
silently installs a missing dependency. Keep original LF bytes in native files;
user input CRLF and UTF-8 Chinese/space paths are supported.

## 6.12.4 configuration adaptation

Both official resolvers receive explicit `--project-root`. resolve_config.py
merges `_bmad/config.toml`, `_bmad/config.user.toml`, `_bmad/custom/config.toml`
and `_bmad/custom/config.user.toml`. The adapter executes that original resolver;
it does not implement a competing TOML merger. The private configuration retains
merged identity/language while rebinding `core.output_folder` for SPEC and
`modules.bmm.planning_artifacts` for architecture to isolated output paths.

Upstream persistent_facts now defaults to empty. The adapter explicitly copies
and loads AGENTS.md and the toolchain routing index when present, before native
activation. Callers supply approved source/constraint files explicitly. Existing
root policy still governs; no implicit project-context glob or knowledge lookup
is introduced. Native files remain exact before and after runs.

## Failure messages and authority

All native preflight failures return exit 2 with JSON error, message,
supported_version=6.12.4 and authorizes=[]. No business output is modified.

| Error | Required action |
| --- | --- |
| NATIVE_INSTALLATION_MISSING | Install project-local official 6.12.4; a global CLI is insufficient. |
| NATIVE_VERSION_UNKNOWN | Establish a project-local official source/version through explicit installation. |
| NATIVE_VERSION_OLD | Upgrade the project installation to exactly 6.12.4. |
| NATIVE_VERSION_NEWER | Only 6.12.4 is supported; do not blindly upgrade further. Use a separate supported installation or adapt the wrapper. |
| NATIVE_VERSION_CONFLICT | Reconcile conflicting project installation metadata explicitly. |
| NATIVE_TREE_DRIFT | Reinstall the original 6.12.4 Skill trees; do not patch or skip hashes. |
| NATIVE_RUNTIME_MISSING | Install Python 3.11+, uv or the missing official runtime dependency. |
| NATIVE_RUNTIME_DRIFT | Reinstall the original 6.12.4 runtime including config_utils.py. |
| NATIVE_CONFIG_INVALID | Repair the project TOML configuration/override layer. |

Exact English public messages are centralized in bmad_native.MESSAGES and covered
by failure tests. No silent downgrade, install or fallback exists.

Typed roles, descriptor ordering, canonical JSON, schema IDs, hash domains,
selection/current locations and VDD authority remain unchanged. Native string
arrays cannot erase adopted/provenance roles. Existing immutable selection records
are checked without rewriting. Selection hashes bind descriptor membership, not
body content. Publication is not an atomic multi-file crash transaction; candidate
validation and before-publish copies support explicit recovery. Do not infer
complete body writes from a valid selection alone.

## Untracking inventory and retained customization

`distribution-inventory.json` records 178 candidates at the original baseline,
their original SHA-256 and current disposition. All 178 are now untracked:
129 source-proven distribution files, 6 retired Stock BMAD Quick Dev files,
30 retired game designer/GDS/GDD compatibility files, and 13 retired Windows
launcher patches. This count includes repository additions and modified upstream
files; it must not be labeled 178 unmodified official files. Local files and
recovery copies remain available, and Git history is preserved. Exact package
ignores cover these installations without hiding repository-owned wrappers.

The 13 launcher patches changed only `python3` to `py -3` relative to official
6.10.0, including the PRD browser-open command. They are retired, not carried
forward. New official BMAD installations stay byte-for-byte original: do not
apply launcher substitutions, compatibility shims or post-install patching.
Official 6.12.4 uses `uv run` in many successors; some old Skills have moved or
been deprecated. Install the interpreter, uv and any other upstream-required
dependencies in the execution environment. The Windows `py -3` example above is
only a way to launch this repository's installer, not an edit to native Skills.
Existing local legacy patched files are recovery material, not evidence of a
clean new installation; explicitly install the official package before using
those other Skills. Only the two pinned wrappers are verified here.

The maintainer no longer uses Stock `bmad-quick-dev` and uses `bmad-build` instead.
The retired package's router, helper and dedicated test are preserved locally and
in Git history. No active Phase/runtime/CI or toolchain execution dependency was
found. Its own calls, the obsolete manual recommendation, Bootstrap exclusivity
labels and an invalid-caller negative test are not external runtime dependencies.
`quick-dev-tdd-adapter`, `scripts/quick_dev/run.py`, VDD, and their tests remain.
No old repository route policy was transferred to `bmad-build`; the scoped native
installer does not install or validate `bmad-build`.

The maintainer accepts temporary unavailability of old game capabilities pending
a future user-sandbox rebuild. A clean clone has no designer alias, GDS workflow
or GDD compatibility mirror. Existing Phase `game-design-master` registration and
the GDD outline prompt still name `bmad-agent-game-designer`; those routes must not
be treated as available from this clone. No service registration, route contract
or game capability was changed or rebuilt by this retirement. A separate decision
is needed to disable the registration/route explicitly if it must be exposed in
that interim state; absence of a Skill is not proof of a fail-closed service gate.

`docs/game-type-guides` and its repository extensions remain tracked. The design
catalog reads every present docs/canonical/mirror catalog, merges entries with docs
preference, and retains source fingerprints. The mirror is not the sole source,
but removing it can change the source set. Existing GDS installation/mirror/alias
assertions in `scripts/python/tests/test_game_type_guides_module_matrix.py` remain
unchanged; they cannot pass in an unprovisioned clean clone and are not waived.
Historical command registries and source hashes must use their frozen checkout.

Only jimuyun-spec and jimuyun-architecture are provisioned and verified by this
installer. It does not restore retired game capabilities or missing resources of
other historical mixed packages. GDS is a separate upstream module, not supplied
by the verified BMAD-METHOD 6.12.4 source. Other BMAD Skills require an explicit
official installation with their own upstream dependencies. New package names
not covered by the audited package ignores need an explicit ignore review before
staging; this inventory is not a guarantee about every future BMAD release.

Repository adapters, requirements, `_bmad/.gdignore`, historical plans, command
registries, receipts, manifests, snapshots, hashes and generated BMAD outputs stay
tracked as before. Historical paths must be replayed in their frozen checkout.
GitHub main remains separate from this branch until the PR is merged; pushing a
branch or opening a Draft PR does not clean main.

## Verification limits

Targeted tests cover real config merging, explicit root resolution, native bytes,
missing/old/newer/modified installations, dependencies, no-side-effect rejection,
typed round trips and real VDD consumption. Native semantic runs use actual agents
and original scripts; deterministic render fixtures are not semantic evidence.
No native Windows run, Windows junction/process verification, full VDD, Quick Dev
or Acceptance execution is implied by Linux checks.
