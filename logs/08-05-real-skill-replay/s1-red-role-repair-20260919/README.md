# S1 runtime RED role repair

The local operator reported a real S1 assertion failure with
`UNVERIFIED-CANDIDATE-EXTERNAL-TRUST-REJECTED`. The remote plan contained
only `target-binding-failure`, so the generated case-contract had no expected
failure IDs. The earlier automatic handoff repair excluded Governance
requirements, including this executable independent-verification assertion.

The canonical CLI now supports an explicit reviewed runtime-intent selection.
This publication adds a separate expected-red role for FI-6AED86AC07D0 using
the same marker. It preserves the original diagnostic, source meaning,
Governance classification, human approval boundaries and production write set.
S2-S45 slice records and contexts are unchanged. No semantic worker ran.

Validation: 61 targeted tests passed, zero skipped; public S1 preflight passed.
The controlled probe reproduces the missing expected-ID problem and proves
that explicit binding yields missing followed by clean expected RED. Negative
cases reject wrong IDs, setup failures and non-assertion exceptions. Existing
handoff checks verify unchanged scope and canonical publication.

Environment: Linux/Python. The user's unpushed S1 test and failed current-run
were not replayed online. These are mapping/consumer tests, not TC-D1
implementation evidence. No production change, live backend, Q8, Acceptance
or new C3 approval was performed. See s1-red-repair/RESUME-S1.md for local
continuation from a fresh S1 descriptor/probe.
