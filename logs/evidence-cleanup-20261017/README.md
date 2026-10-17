# 08-05 and 08-24 evidence cleanup

The maintainer requested cleanup on `main` after PR #4 was merged, including
obsolete evidence from the previously merged 08-24 branch. This is an ordinary
forward commit. It does not rewrite Git history or alter recorded test outcomes.

## Archive and scope

The complete pre-cleanup tree is available at commit
`7670748642c046e4858ea6ac8c8b1d4e19e9c6fe`. Use that commit when following a
historical report into a removed intermediate artifact. The deletion diff is
the exact inventory; it is intentionally not duplicated in another large manifest.

| Scope | Removed files | Removed tracked bytes |
| --- | ---: | ---: |
| 08-05 | 2,609 | 77,525,038 |
| 08-24 | 2,039 | 4,511,299 |
| Total | 4,648 | 82,036,337 |

Removed material consists of superseded review/diagnostic logs, duplicate
archives and inventories, obsolete Acceptance inputs and snapshots, old run
outputs, and expired attempt sidecars. Historical failures remain available in
Git at the archive commit. No failure record was edited into a passing result.
Production code, current tests, current plan contracts, upstream requirements,
Accepted ADRs, both current Acceptance pointers and their current packages were
preserved. Compiler records still referenced by retained plan artifacts were
kept. Existing `.gitignore` rules already exclude ordinary logs and ephemeral
Skill-input attempts; no broader ignore or validator exception was introduced.

This reduces the checked-out tree, not the size of existing Git history.

## Retention checks

- Inspected the 39,151-entry Git tree. Traversed literal repository and relative
  artifact references, retaining their transitive dependencies. No retained
  reference found by that scan points to a deleted candidate.
- Kept all 45 current 08-05 predecessor run roots as complete directories,
  including dynamically addressed runtime files and current closeout sidecars.
- Ran the repository's `verify_current_handoff` before and after deletion.
  Both returned pass: 45 predecessors, 228 runtime closure tuples,
  `authorizes=[]`. The entire returned result was equal before and after.
- Rehashed all 89 source entries in the current 08-05 candidate manifest:
  every byte binding still matches.
- Rechecked both current Acceptance final-result and final-wrapper hashes.
  Replayed the native `_completed_receipts` reader: 3 completed 08-05 actions
  and 10 completed 08-24 actions, with all bound stdout/stderr hashes matching.
- Kept the complete 90-file 08-24 terminal run `20260825T072602Z`, identified
  by `terminal-full.json` and `dotnet-shard-diagnostics.json`.
- The staged change contains only the reviewed deletions and this note.
  `git diff --cached --check` passed.

These checks validate retention after cleanup. They are not a new VDD, slice,
full-suite, Windows runtime, or formal Acceptance execution. Existing acceptance
candidate bindings and C3's OPEN disposition are unchanged.

SHA-256 of the sorted UTF-8 deleted-path list, with LF after every path:
`e39d03fed851f6602101f5afda55fa5a828d552b739a4ad7af3632cfdc47a590`.

## Recover an archived artifact

Read original bytes without changing the working tree:

```sh
git show 7670748642c046e4858ea6ac8c8b1d4e19e9c6fe:path/to/artifact
```

Restore a specific file or run directory when its historical replay is needed:

```sh
git restore --source=7670748642c046e4858ea6ac8c8b1d4e19e9c6fe -- path/to/artifact
```

For a complete historical replay, use a separate worktree at the archive commit
so old code and old evidence retain their original bindings.
