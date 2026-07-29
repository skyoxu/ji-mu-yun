# Knowledge Indexes

Generated Locator index generations and current/LKG pointers belong in this
directory. They are derived cache and are not repository fact authority.

`generations/<generation-id>/manifest.json` is immutable and hash-binds its
bundled layers, inputs, and evaluation report. `current.json` is replaced
atomically only after staging passes; `last-known-good.json` is then advanced
to the same generation. A reader must fail closed when either the pointer,
manifest, formal artifact, or source hash does not verify.

The stable three-layer architecture is documented in `knowledge/README.md`.
Source snapshots live under `knowledge/snapshots/`, typed modules under
`knowledge/catalogs/`, and consumer-specific projections under
`knowledge/projections/`. This directory remains reserved for search-engine
generations and current/LKG pointers.

Use `py -3 -B scripts/python/publish_knowledge_catalog.py --check` to validate
staging and add `--publish` only for an intentional local publication.
