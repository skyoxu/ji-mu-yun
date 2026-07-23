# Authorization Proof Package

A VDD plan that authorizes work must provide one executable authorization
proof package. It is a role contract, not a fixed list of seven files.

Every participating proof has these dimensions: schema producer authority,
immutable identity, source-of-truth derivation, independent recomputation,
staleness propagation, recovery supersession, and consumer authorization
boundary. Closure members are `PASS` or type-authorized `N/A`; an artifact
outside a closure is classified `OUT-OF-CLOSURE` with machine checks and an
empty authorization set.

`PASS` is not a label alone. Each in-closure proof binds a registered producer
authority, derivation rule, independent validator callable, invalidation
contract, and consumer permission lattice. The runner resolves those entries
from the package semantic contract. Seven dimension mutations separately forge
each dimension's executable reference, and eight source-closure mutations cover
omit, extra, identity drift, role change, predicate unlink, proof unlink,
source_binding replay, and copied source hash.

The package has normative, projection, and execution roles. Normative roles
include the proof schema, artifact/type registry, authority-root registry,
rule registry, permission lattice, and runtime type registry. Projection
roles include required inventory, resolved registry, runtime proof, and a
predicate-specific artifact closure. Execution roles include refresh,
independent closure validation, isolated mutations, and a fresh result
envelope.

Tracked identities bind the Git tree, normalized repository path, tree-entry
mode, and blob identity. Binary data additionally binds raw-byte SHA-256 and
length and is never text-normalized. Generated or external values declare
their canonical byte rule explicitly.

Generated and external text may use `utf8-lf-v1`: raw bytes and decoded UTF-8
text normalized from CRLF/CR to LF are each SHA-256 bound. Invalid UTF-8 or an
undeclared canonicalization rule is rejected.

Each authorizing predicate independently discovers its closure. A shared
superset is allowed only when declared and proved to cover each predicate.
The closure producer and verifier must have independent discovery entrypoints.
The runner executes both registered entrypoints and requires each result to
equal the declared closure; self-reported member lists alone are insufficient.
The producer reads a hash-bound `vdd.plan-link-discovery.v1` document and the
verifier reads a different hash-bound `vdd.validator-read-set-discovery.v1`
document. Package proofs and a package-selected semantic registry are not
discovery sources, and the two discovery references must use distinct IDs,
paths, hashes, and schemas.

Every source inventory member carries the complete frozen context-class set,
a primary source role, and identity/path fields equal to its observed proof.
Its source_binding is a `vdd.plan-source-binding.v1` object, not a label.
The reference requires plan, package, proof, predicate, result, and review
bindings. Bootstrap materializes and revalidates the current review-bound
consumption sidecar; copying that sidecar to another review or input is stale.

External protected roots are repository-declared and supplied in an explicit
handoff envelope. A deterministic package result may not claim protected
handoff, release, fresh-context, or cross-model assurance.

An external validation envelope is accepted only when it names a root and
signer registered in `vdd-artifact-proof-roots.v1.json`, matches package bytes,
and identifies the expected validator. Such evidence remains below protected
handoff and release authority.

The result envelope binds `candidate_hash`, `source_hash`, `validator_root`,
`authority_root`, and `closure_definition_hash`. It emits a rule-level check
for every proof dimension. Downstream consumers freeze and compare these
fields; a process exit code or package path alone is not authorization.

An authorization-closure review is closed when the deterministic package passes, all seven dimension
mutations and eight source-closure mutations are rejected by their expected stable rule IDs, independent closure membership agrees, the
result is fresh against all five bindings, and Bootstrap has no accepted P0/P1. Reopen only when a
stable dimension rule fails, the actual predicate consumer set changes, the authority or threat model
changes, or fresh hash-bound validation fails.
