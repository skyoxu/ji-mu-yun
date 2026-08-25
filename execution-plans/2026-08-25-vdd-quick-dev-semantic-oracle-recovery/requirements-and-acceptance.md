# Requirement And Acceptance Map

Source authority is the canonical selection
`sha256:4cf516d611eb0aba633adcebc37df679e6270dd74f231fd98c782a6e754def40`.
`prd.md` is provenance and is not an extraction source.

| Acceptance ID | Requirements | Observable acceptance |
| --- | --- | --- |
| A-SEMANTIC | FR-1, FR-2, FR-10, NFR-5, NFR-7, NFR-9, SM-3 | VDD accepts complete semantic intent and rejects execution fields, missing producer/coverage/fixtures, prose rollback and self-judging. |
| A-DESCRIPTOR | FR-3, FR-12, FR-14, FR-15, FR-17, NFR-1, NFR-4, NFR-9..NFR-11 | Quick Dev alone freezes non-shell descriptor and writes recommendation, reuse, blocker and recovery projection. |
| A-JUDGE | FR-4, FR-5, FR-7, FR-11, FR-13, NFR-1..NFR-4, NFR-7..NFR-10, SM-4 | Independent executor/judge writes non-zero receipt and observation with legal result layers and deterministic IDs. |
| A-COVER | FR-6, FR-7, FR-11, FR-14, NFR-2, NFR-6, NFR-8..NFR-11, SM-1, SM-C3 | Coverage gate accepts only the complete many-to-many manifest-to-oracle-to-descriptor-to-receipt-to-observation path in one closed snapshot. |
| A-PROMOTION | FR-8, FR-9, NFR-3, NFR-8, NFR-10, SM-2, SM-C1, SM-C2 | Frozen independent predecessor judge blocks each of nine `FG-01`..`FG-09` fixtures, corrected fixtures pass, and coverage gate alone writes promotion. |
| A-BOUNDARY | FR-16, NFR-3, NFR-5, NFR-6 | Review, commit, business repository and Chapter 5 authority remain outside Quick Dev; legacy contracts are read-only. |
| A-TERMINAL | FR-1..FR-17, NFR-1..NFR-11, SM-1..SM-4, SM-C1..SM-C3 | Terminal replay verifies every active Acceptance ID through the exact evidence path, all fixture classes, nine false-green regressions and adopted architecture writers. |

An evidence edge is admissible only as: active manifest Acceptance ID ->
semantic oracle `covers_acceptance_ids` -> descriptor selected case binding ->
receipt executed case cell -> observation case assertion -> coverage Acceptance
ID. Cover is sound-and-complete many-to-many; it is not an exclusive partition.
