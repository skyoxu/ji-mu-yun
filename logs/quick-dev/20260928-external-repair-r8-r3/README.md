# R8 probe rerun (diagnostic target binding)

Code under test: the post-`b23bca57` working tree.

The combined S53/S28/S32/S46 run executed 23 tests: 14 passed and 9 failed.
S53 passed with the real `phase-r-a-p` Runner. The nine failures are genuine
missing Credential Manager entries, and now include only the non-secret target
name in the exception. Targets are generated per test account/project, for
example `PhaseA.Runner.<account-id>.s32-project`,
`PhaseA.Runner.<account-id>.project-s28`, and
`PhaseA.Runner.<account-id>.s46-project-<project-id>`.

The exact targets for this run are in the TRX. No credential was substituted
across account or project scope. New evidence is retained in
`../20260928-external-repair-windows/r8-probe-s53-s28-s32-s46-r3.trx`.

Quick Dev successor evidence and Q8 remain blocked until those exact targets
are provisioned with the configured Runner account and rerun successfully.
