# Operation

## Entrypoints and dependencies

Require Python 3.11+, uv and an explicitly installed project-local BMAD 6.12.4.
Read `docs/workflows/bmad-native-wrappers.md` from the repository root for the
Windows/Linux setup. Run `python -B -m scripts.toolchain.bmad_native verify`
before any write. The complete official Skill trees and four runtime files,
including config_utils.py, must match the current lock. A global CLI version
or a home-installed Skill never substitutes for these project-local bytes.

Explicit offline setup from a verified official source checkout is
`python -B -m scripts.toolchain.bmad_native install-from-source --source-root <official-v6.12.4-source>`.
Existing resources are preserved unless the maintainer explicitly uses
--replace-native, which first moves them into an ignored backup. Wrapper calls
never install, download, upgrade or fall back. Native files/configuration are
local installation state and must not be added to Git.

Exit 2 returns error, message, supported_version and empty authorizes. Missing
or older installs request 6.12.4; newer versions say only 6.12.4 is supported;
modified native bytes request an original reinstall. Invalid project TOML
must be repaired. Every blocked call leaves business artifacts unchanged.

Native Skills resolve exclusively from .agents/skills/bmad-spec and
.agents/skills/bmad-architecture under --repo-root, then verified private copies.
Both official resolvers use explicit --project-root. The official TOML merger
reads config.toml, config.user.toml and both custom/config override layers.
The isolated config preserves merged identity/language but binds core.output_folder
and modules.bmm.planning_artifacts to private output paths. Explicit AGENTS.md
and toolchain routing context are copied and loaded before activation; the new
empty persistent_facts default does not waive repository constraints.

Prepare: `python -B .agents/skills/jimuyun-architecture/scripts/invoke.py prepare --repo-root . --run logs/bmad-wrappers/<unique-run> --input <source-path>`.
Repeat --input for companions. --intent selects create/update/validate. Include
--altitude initiative/feature/epic and --purpose build-substrate/discussion when
the caller selects them; otherwise native inference remains responsible. Include
existing ARCHITECTURE-SPINE.md for update/validate and its .memlog.md for update.
Its isolated parent becomes doc_workspace; create uses native/_bmad-output/architecture.
Inputs must be contained relative paths and cannot replace native resources.

Read and execute the returned invocation, which includes actual verified native
source after the caller policy. Prepare alone does not run BMAD. Use argv,
shell=false, finite timeout, PYTHONDONTWRITEBYTECODE=1, PYTHONUTF8=1, UV_OFFLINE=1.
Native research uses caller-permitted tools; disclose unavailable research.
Optional native branches may require further review/editorial Skills. Resolve
those through the caller's available Skills; report blocked if a required one
is unavailable, never skip it or silently install a full framework.
The caller's real agent APIs own dispatch/cancellation; no new runner exists here.

After all reviewers are terminal, perform required native lint and run
`python -B .agents/skills/jimuyun-architecture/scripts/invoke.py verify --repo-root . --run logs/bmad-wrappers/<unique-run>`.
JSON exit 0 proves native trees unchanged; exit 2 blocks. Neither proves reviewer
success. Keep actual reviewer paths and lifecycle observations with run evidence.

## Responsibility and outputs

Native owns architecture method, spine and memory. Wrapper only binds context
and lifecycle policy before invocation. Return isolated artifacts for review;
adoption into a typed SPEC is explicit and does not happen automatically.
Historical plans/command registries/receipts/hash evidence stay immutable.
ADR-0041/ADR-0062 owners retain their lifecycle authority.

## Routing

[start] -> [typical]
[start] -> [boundary]
[start] -> [error]

Typical invokes the complete native reviewer set. Boundary handles timeout by
one real agent-state inspection then the proper lifecycle wait. Error stops an
invalid route without invented IDs or fallback command polling.

## Verification

scripts/tests/test_invoke.py checks prepare/verify, actual runtime dependencies,
native-tree drift and policy placement. Semantic forward runs use actual agents
and native artifacts; static text checks cannot prove model compliance.
