# Current Implementation Slices

Current input repair keeps stable slice IDs; no VDD rerun is required.
Use [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md) and the current semantic bundle.
L0-L4 in the source matrix are conceptual lanes, not old runtime slice IDs.

| Order | Slice | Prerequisites | Cases |
| --- | --- | --- | --- |
| 1 | S12 | none | 4 |
| 2 | S47 | S12 | 4 |
| 3 | S69 | S12 | 5 |
| 4 | S66 | S69 | 2 |
| 5 | S29 | S66 | 3 |
| 6 | S79 | S66 | 1 |
| 7 | S11 | S29 | 4 |
| 8 | S15 | S79 | 4 |
| 9 | S18 | S29 | 5 |
| 10 | S39 | S12, S29 | 3 |
| 11 | S55 | S18 | 2 |
| 12 | S38 | S55, S39 | 3 |
| 13 | S58 | S18, S55 | 8 |
| 14 | S76 | S18, S55 | 3 |
| 15 | S9 | S18, S76 | 2 |
| 16 | S10 | S9 | 1 |
| 17 | S23 | S10 | 3 |
| 18 | S2 | S29, S23 | 1 |
| 19 | S54 | S2 | 13 |
| 20 | S43 | S54, S23 | 15 |
| 21 | S68 | S54 | 2 |
| 22 | S78 | S11, S54 | 28 |
| 23 | S3 | S78 | 1 |
| 24 | S22 | S78 | 1 |
| 25 | S33 | S43 | 2 |
| 26 | S57 | S54, S68 | 3 |
| 27 | S67 | S43 | 3 |
| 28 | S21 | S78, S22 | 17 |
| 29 | S63 | S33 | 1 |
| 30 | S35 | S12, S21 | 1 |
| 31 | S50 | S21 | 19 |
| 32 | S56 | S21, S33 | 1 |
| 33 | S61 | S21 | 5 |
| 34 | S73 | S12, S63 | 2 |
| 35 | S80 | S21 | 2 |
| 36 | S20 | S50 | 4 |
| 37 | S30 | S61 | 1 |
| 38 | S48 | S73 | 1 |
| 39 | S59 | S21, S73 | 2 |
| 40 | S75 | S39, S50 | 2 |
| 41 | S6 | S59 | 3 |
| 42 | S8 | S20 | 1 |
| 43 | S60 | S59 | 2 |
| 44 | S74 | S75, S43 | 1 |
| 45 | S40 | S6, S18 | 10 |
| 46 | S4 | S40, S50, S73 | 34 |
| 47 | S19 | S40 | 1 |
| 48 | S24 | S22, S40 | 2 |
| 49 | S26 | S40, S76 | 1 |
| 50 | S31 | S40, S58 | 1 |
| 51 | S34 | S20, S38, S40 | 11 |
| 52 | S37 | S40, S61 | 5 |
| 53 | S52 | S40 | 1 |
| 54 | S65 | S40 | 1 |
| 55 | S14 | S37, S40 | 1 |
| 56 | S16 | S4, S76 | 2 |
| 57 | S17 | S4 | 12 |
| 58 | S28 | S40, S67, S52 | 3 |
| 59 | S44 | S19 | 1 |
| 60 | S49 | S34, S69, S38 | 15 |
| 61 | S51 | S31 | 1 |
| 62 | S62 | S4 | 1 |
| 63 | S1 | S49 | 1 |
| 64 | S13 | S16, S43 | 4 |
| 65 | S25 | S49, S47, S51 | 3 |
| 66 | S32 | S17, S28, S37 | 6 |
| 67 | S42 | S14 | 1 |
| 68 | S45 | S49 | 1 |
| 69 | S64 | S49 | 1 |
| 70 | S5 | S37, S42, S49, S58 | 27 |
| 71 | S27 | S13, S76 | 1 |
| 72 | S53 | S25, S32 | 9 |
| 73 | S46 | S53, S44 | 3 |

All case identities are planned until Q2 authoring and real execution.
No historical S0-S4 runtime or terminal writer is a current completion authority.
