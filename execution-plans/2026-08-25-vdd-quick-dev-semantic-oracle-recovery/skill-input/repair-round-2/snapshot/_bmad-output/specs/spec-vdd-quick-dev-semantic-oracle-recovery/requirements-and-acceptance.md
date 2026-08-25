# Acceptance Coverage Contract

This normative companion defines the active Acceptance ID universe for the
canonical package. It maps the complete, preserved FR/NFR/SM set to the VDD
execution-plan acceptance targets. Cover is sound-and-complete many-to-many;
the rows are not an exclusive partition.

| Acceptance ID | Requirements | Slice | Command family |
| --- | --- | --- | --- |
| A-SEMANTIC | FR-1, FR-2, FR-10, NFR-5, NFR-7, NFR-9, SM-3 | S1 | semantic positive, negative, mutation |
| A-DESCRIPTOR | FR-3, FR-12, FR-14, FR-15, FR-17, NFR-1, NFR-4, NFR-9..NFR-11 | S2 | descriptor positive, negative, mutation |
| A-JUDGE | FR-4, FR-5, FR-7, FR-11, FR-13, NFR-1..NFR-4, NFR-7..NFR-10, SM-4 | S3 | judge positive, negative, mutation |
| A-COVER | FR-6, FR-7, FR-11, FR-14, NFR-2, NFR-6, NFR-8..NFR-11, SM-1, SM-C3 | S4 | coverage positive, negative, mutation |
| A-PROMOTION | FR-8, FR-9, NFR-3, NFR-8, NFR-10, SM-2, SM-C1, SM-C2 | S5 | promotion positive, negative, mutation |
| A-BOUNDARY | FR-16, NFR-3, NFR-5, NFR-6 | S6 | terminal negative |
| A-TERMINAL | FR-1..FR-17, NFR-1..NFR-11, SM-1..SM-4, SM-C1..SM-C3 | S6 | terminal full replay |

Every active acceptance row must resolve through the architecture-defined path:
active acceptance manifest to semantic oracle to descriptor case binding to
receipt case cell to observation assertion to coverage acceptance ID.
