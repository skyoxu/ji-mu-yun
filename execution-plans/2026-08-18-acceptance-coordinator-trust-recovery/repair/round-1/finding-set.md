# Repair Round 1 Finding Set

Predecessor: `868328c827a814f9042fdfa62c52ab574a424b24`

This bounded repair addresses only the current plan-contract defects:

- terminal runner argument and predicate incompatibility;
- missing final receipt bindings;
- requirement/slice and acceptance-ID traceability;
- self-hosted input and authority declarations;
- accidental write access to the immutable 2026-08-17 plan;
- contamination of the new RED baseline by behavior already present at the
  plan creation commit.

It does not modify the 2026-08-17 plan, its authorization, terminal, resume
state, report, or historical evidence.

`repair-closure.json` is intentionally absent until the targeted validation and
the maintainer-owned authority prerequisites are complete.
