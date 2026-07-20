# Authorization Proof Package

A VDD plan that authorizes work must provide one executable authorization
proof package. It is a role contract, not a fixed list of seven files.

Every participating proof has these dimensions: schema producer authority,
immutable identity, source-of-truth derivation, independent recomputation,
staleness propagation, recovery supersession, and consumer authorization
boundary. Closure members are `PASS` or type-authorized `N/A`; an artifact
outside a closure is classified `OUT-OF-CLOSURE` with machine checks and an
empty authorization set.

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

Each authorizing predicate independently discovers its closure. A shared
superset is allowed only when declared and proved to cover each predicate.
The closure producer and verifier must have independent discovery entrypoints.

External protected roots are repository-declared and supplied in an explicit
handoff envelope. A deterministic package result may not claim protected
handoff, release, fresh-context, or cross-model assurance.

The result envelope binds `candidate_hash`, `source_hash`, `validator_root`,
`authority_root`, and `closure_definition_hash`. It emits a rule-level check
for every proof dimension. Downstream consumers freeze and compare these
fields; a process exit code or package path alone is not authorization.

An authorization-closure review is closed when the deterministic package passes, all seven isolated
mutations are rejected by their expected stable rule IDs, independent closure membership agrees, the
result is fresh against all five bindings, and Bootstrap has no accepted P0/P1. Reopen only when a
stable dimension rule fails, the actual predicate consumer set changes, the authority or threat model
changes, or fresh hash-bound validation fails.
