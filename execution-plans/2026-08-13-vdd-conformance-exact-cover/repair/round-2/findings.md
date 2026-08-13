# Repair Round 2 Findings

Source: `docs/know20.txt`. This round repairs only the five finalized items:

| ID | Disposition | Repair |
| --- | --- | --- |
| P0-1 | fixed | Every mapping command ID now resolves to the command registry; slice commands are explicit. |
| P0-2 | fixed | Round 1 validation is named `repair-validation`; implementation `terminal-full` is a separate, currently not-ready gate. |
| P0-3 | fixed | Resume state uses S3a/S3b/S3c/S3d and matching dependencies. |
| P1-1 | fixed | Round 2 composition receipt binds producer/consumer paths, hashes, changed paths, and direct consumers. |
| P1-2 | fixed | Validator implementation freshness can never be bypassed by `allow_stale_catalog`; regression guard added. |
