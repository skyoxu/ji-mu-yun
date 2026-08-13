# Canonical Spec Package Contract

`canonical-spec-package.v1` is the only producer contract emitted by `bmad-spec`.

## Root Descriptor

The package has exactly one physical descriptor: YAML frontmatter in the root `SPEC.md`.

```yaml
id: SPEC-example
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/specs/spec-example/authority.md
    role: normative_companion
  - path: _bmad-output/planning-artifacts/architecture/example/ARCHITECTURE-SPINE.md
    role: adopted_companion
sources:
  - path: execution-plans/example-requirements.md
    role: provenance
```

Rules:

- `SPEC.md` is the sole implicit `canonical` entry.
- `companions` entries are typed `{path, role}` and roles are closed to `normative_companion` and `adopted_companion`.
- `sources` entries are typed `{path, role: provenance}`.
- Paths are normalized repository-relative POSIX paths. Normative companions remain under the package root; adopted companions and provenance sources may be elsewhere inside repository containment.
- Paths are unique. Unknown roles, duplicate entries, missing listed files, nested competing `SPEC.md` descriptors, and disagreement with the external expected role graph fail closed. An unlisted file gains no authority merely by residing in the package directory.
- `repository_authority` and `unresolved_input` are VDD source-freeze manifest roles, not bmad-spec frontmatter roles.
- Legacy string path arrays are migrated on refresh and are not valid v1 producer output.

## External Selection Record

`bmad-spec` publishes a content-addressed `canonical-spec-package-selection.v1` record outside the package. Its exact payload contains:

```json
{
  "schema": "canonical-spec-package-selection.v1",
  "package_id": "SPEC-example",
  "descriptor_hash": "sha256:<64 lowercase hex>",
  "role_graph": [{"path": "...", "role": "canonical|normative_companion|adopted_companion|provenance"}]
}
```

The descriptor hash projection is exactly `{id, package_schema, companions, sources}` in descriptor order. Encode the envelope `{"domain":"jimuyun.canonical-spec-package.descriptor.v1","payload":<projection>}` with `repository-canonical-json.v1`, then prefix the lowercase SHA-256 digest with `sha256:`. The selection hash uses the same encoding over `{"domain":"jimuyun.canonical-spec-package.selection.v1","payload":<selection-record-without-self-hash>}`. These producer-owned domains are consumer-neutral. Canonical JSON is UTF-8 without BOM or trailing newline, compact separators, arrays preserved in descriptor order, object keys sorted by Unicode scalar sequence, and duplicate keys/floats/lone surrogates rejected.

A maintainer-scoped current pointer has the exact payload `{package_id, schema:"canonical-spec-package-selection-current.v1", selection_hash}` and selects the content-addressed record by hash. The record proves caller-independent package completeness and selection; it does not attest to producer identity. VDD independently resolves the pointer, verifies the record hash, recomputes the descriptor hash, and compares the complete role graph.

## Refresh Procedure

1. Read the existing memlog and all current package files completely.
2. Preserve capability IDs and append decisions; do not hand-edit the derived kernel outside the memlog workflow.
3. Convert legacy path arrays to typed entries and add `package_schema`.
4. Include adopted architecture/UX/design artifacts explicitly with `adopted_companion` when downstream must consume them.
5. Render the package, compute the descriptor and selection hashes, publish the record and current pointer, then run coherence and preservation validation.
