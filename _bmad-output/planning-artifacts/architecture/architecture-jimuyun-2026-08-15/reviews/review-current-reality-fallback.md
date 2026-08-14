# Brownfield And Current-Reality Review

Verdict: NEEDS FIXES

The configured reviewer agent could not be observed through the agent lifecycle route, so this lens was completed sequentially against the frozen spine revision.

## P1 - Selection and policy wording must match existing repository custody

The repository already uses an atomically replaceable current pointer that references an immutable content-addressed selection record in `bmad-spec/scripts/canonical_package.py`. Acceptance also binds versioned policy packs through `policyRevision` and `policyHash`. AD-2 currently calls the current pointer itself immutable, while AD-10/AD-12 reference current policy without defining owner-scoped selection custody.

Required fix: preserve immutable content-addressed records, owner-only atomic current pointers, and immutable versioned policy artifacts selected by their existing owner. Do not introduce a central policy or evidence registry.

## P2 - Structural seed overstates unratified filenames

The physical boundary `scripts/toolchain/canonical_evidence/` and stable API are adopted, but `__init__.py`, `canonical_json.py`, `identity.py`, and `repository_path.py` do not yet exist and were not separately ratified. Listing them as a source tree can be read as a required module decomposition despite the following disclaimer.

Required fix: retain the package directory, stable API, vectors/mutations boundary, and dependency direction while removing illustrative internal filenames.

## Confirmed Brownfield Fit

- Existing bmad-spec, VDD source-freeze, and exact-cover domains conform to the adopted `.vN` domain grammar and current `{domain,payload}` envelope.
- Existing private canonical implementations confirm the migration inventory; the spine does not need another adopter class.
- No external framework, service, provider, or version is selected by this spine, so no web version verification is required.
