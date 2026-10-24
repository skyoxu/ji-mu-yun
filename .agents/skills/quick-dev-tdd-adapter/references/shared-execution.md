# Shared execution evidence

ADR-0041 permits content-bound reuse of successful controlled Python pytest
executions. This is a Quick Dev execution optimization, not a new lifecycle or
Acceptance authority. VDD continues to own semantic assertion mappings,
validation argv, production owners, execution snapshots and dependency scope.

## Two identities

The slice semantic fingerprint binds the selected slice and frozen semantic
bundle. The execution fingerprint binds the actual ordered argv and cwd,
repository content inventory, declared paths across all slices, target/fixture
bytes, the complete Quick Dev Python engine, OS/architecture/kernel, Python,
installed distribution contents, standard-library Python sources, common child
tool binaries and a digest of the inherited environment. No secret environment
values are written. Only top-level source_commit/baseline_commit provenance is
excluded from semantic hashing; other contract fields remain conservative.
A Git commit alone is not an execution input. Changing an implementation or
helper without changing the slice invalidates reuse.

Dependency discovery includes tracked and untracked/ignored repository files,
with bounded exclusions for logs, execution-plans, Python caches and virtual
environments. Explicit declared paths inside excluded trees are always added.
The semantic bundle is separately bound. Installed Python dependencies are
hashed from their actual distribution inventory, not only version metadata.
The collector also records actual Python-visible file reads and imported module
bytes. Reads/imports outside those inventories, incomplete observation, child
processes and network connections prevent reusable publication with a specific
reason. Tests still execute normally. This deliberately excludes suites that
invoke real external model/tool processes; no declaration can opt them past this
boundary. Pure in-process/mocked consumer tests remain eligible.
The inventory ceiling is 50,000 repository files / 512 MiB and 50,000 environment
files / 2 GiB. Missing inventories, unsafe paths, unsupported interpreters,
unsupported commands or exceeded budgets execute normally with an explicit
non-reuse reason; they never gain a successful reusable proof.

This conservative inventory can invalidate unrelated source edits. It is not a
hermetic sandbox or proof of live service state. Untracked external data,
external services, arbitrary child toolchains and editable dependencies outside
these inventories are outside the supported reuse boundary. Such inputs must
be made repository/environment-bound before reuse is appropriate. Do not claim
that a stable slice declaration alone establishes dependency completeness.

## Originals and uses

The fixed logs/quick-dev-shared-executions/<execution-fingerprint>.json entry
binds the original descriptor, receipt, stdout and stderr by content. Lookup is
an exact key, not glob/mtime/latest-success selection. Only complete nonempty
structured case reports in which every selected setup/call/teardown passed
without xfail may publish an original. Failed, timed-out, skipped, ambiguous,
partial, zero-case or legacy summary-only receipts are not reusable successes.
RED and probe remain actual lifecycle observations; successful GREEN, REFACTOR,
regression and terminal executions may supply shared proof.

A use has execution_kind=reference and process_attempts=0, with an explicit
execution_reference and slice semantic fingerprint. Original report/run/stage
identity and original timing remain unchanged. The consuming descriptor and
candidate identify the new *use*, not a new process. No historical receipt is
rewritten. Exact argv/cwd identity is required; broader/narrower selector
subsumption is deliberately unsupported. CER still proves actual selected case
coverage for each consuming assertion.

Q6 routes compatible Python pytest commands through the same collector and
lookup as terminal. A full shared-module run may cover another slice's Q6 and
terminal with identical argv; narrower primaries do not masquerade as full runs.
Other commands retain existing execution policy without reusable publication.
Q7/Q8 and stage reentry reread original proof and current content through CER,
and reread Q6 references. Missing or changed originals block closure. Current
snapshot, predecessor, RED continuity and exact tuple/terminal coverage gates
remain mandatory. Reentry in the same run preserves immutable stage identity;
use a fresh run to consume successful proof under a different descriptor.

Original and reference request/completion seals are rechecked at Q7/Q8 and recovery.

Sequential duplicate requests return their exact existing receipt after checking
the request/completion seal and outputs. Partial requests block instead of
launching again. Cross-process scheduling/coalescing is not provided.

## Diagnostics and compatibility

Examples: reuse-no-matching-content-key, reuse-dependency-content-changed:<path>,
reuse-contract-changed, reuse-environment-changed:system,
reuse-original-tampered:stdout and reuse-selector-not-covered. A cache miss does
not scan history to infer a cause. Rechecking an explicit reference explains the
changed input class/path. Corrupt matching originals block; do not overwrite them.

Old v2 receipts remain readable through existing lifecycle rules, but have no
shared index/input proof and are not imported as new shared executions. Older
consumers cannot validate cross-run case-report identity; deploy the Quick Dev
producer and readers together. No original task run, receipt or VDD directory
is migrated automatically. Windows/Linux identities cannot share proof. Linux
fixture verification does not establish a real Windows execution result.
