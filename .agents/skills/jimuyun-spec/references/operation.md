# Operation

## Ownership and round trip

Prepare validates the original typed descriptor/current selection and freezes
input bytes and explicit path/role mappings. Only its private projection uses
native string arrays. Native bmad-spec is the sole author of private SPEC body,
spec-authored companions and append-only memlog. Adopted/provenance files remain
read-only. Publish alone writes the canonical repository SPEC, authored files
and memlog, adapting only the envelope. It preserves body and CAP decisions.
No stage writes either native Skill directory; no concurrent dual writers.

Existing roles survive refresh, even adopted companions inside the package.
Unknown roles, implicit removals, category changes, changed source bytes, changed
memory prefix or native-tree drift block publication. New entries require trusted
--roles assignments; intended removal requires --remove <repository-relative-path>.
Changing an existing role requires a separately approved contract change.
Native relative parent paths may resolve inside the private project; public
wrapper paths cannot traverse. New adopted/provenance files must exist in the
repository and match the private copies. Native memlog remains the decision source.

## Entrypoints

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

Prepare: `python -B .agents/skills/jimuyun-spec/scripts/bridge.py prepare --repo-root . --spec _bmad-output/specs/spec-example/SPEC.md --run logs/bmad-wrappers/<unique-run>`.
For create add --package-id SPEC-example, optionally --roles <JSON-path>.
Roles are an array of {path, role}; source intent uses provenance, upstream
artifacts still needed downstream use adopted_companion.

Read and execute the complete returned invocation with the input/change request.
Preparing a prompt alone is not running BMAD. If delegating, supply the full
invocation initially. Use argv, shell=false, finite timeout, PYTHONUTF8=1 and
PYTHONDONTWRITEBYTECODE=1. Use UV_OFFLINE=1 for the provisioned stdlib runtime.

Publish: `python -B .agents/skills/jimuyun-spec/scripts/bridge.py publish --repo-root . --run logs/bmad-wrappers/<unique-run>`.
Exit 0/JSON indicates publication; exit 2/JSON indicates blocked/invalid input.
The moved canonical_package.py preserves its --repo-root/--spec/--publish CLI
and Python API for existing typed packages. Its --publish entry also requires
the native preflight; read-only canonical/VDD imports work without a native install. Consumers import it here; there is
no native-directory shim. Publishing only calls deterministic producers.

## Authority and failure

Canonical JSON, schema IDs, hash domains, descriptor ordering, selection/current
paths and consumer semantics stay unchanged. Existing entry order is preserved
even if native rendering reorders its strings; new explicit entries append.
Existing content-addressed records are validated and never rewritten. Selection
is written last, but this is not a multi-file crash transaction: selection binds
descriptor membership, not body bytes. VDD separately freezes source hashes.
On interrupted publication stop and recover explicitly from before-publish/ and
candidate/ evidence; do not infer complete writes from a valid selection alone.
Validate current selection before any new run. No plan-ready,
implementation-complete or acceptance-passed. Replay immutable historical
plans/command registries/receipts in their exact historical checkout.

## Routing

[start] -> [typical]
[start] -> [boundary]
[start] -> [error]

Typical creates/refreshes a selected package. Boundary preserves roles across
an explicit scope change. Error blocks dependency, path, selection, source,
role, memory or native-byte drift before publication.

## Verification

Run scripts/tests/test_bridge.py, moved canonical-package tests, the negative
selection fixture and shared canonical-evidence consumer migration tests.
Deterministic fixture rendering proves transport behavior only. Native semantic
proof requires reading the real invocation, running official memlog and native
coherence/preservation passes; report that separately.

Headless calls follow upstream and skip interactive Story Breakdown; this adapter
does not add stories generation, publication or a new dispatch contract.
