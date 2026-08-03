# Investigation: Reported .agents/skills deletions

## Hand-off Brief

1. **What happened.** The user reported 751 tracked deletions under `.agents/skills/**`; the primary worktree currently reports no changes in that path.
2. **Where the case stands.** Concluded; all registered worktrees report zero tracked skill deletions, and all 751 tracked skill files exist in the primary worktree.
3. **What's needed next.** If an external client still reports deletions, capture its exact working directory and raw command or refresh its source-control cache.

## Case Info

| Field | Value |
| --- | --- |
| Ticket | N/A |
| Date opened | 2026-07-31 |
| Status | Concluded |
| System | Windows, repository `C:/jimuyun`, HEAD `dbe2a73` |
| Evidence sources | Git index, filesystem, repository configuration, linked worktrees |

## Problem Statement

The user reports that HEAD and main are both `dbe2a73`, while 751 tracked files under `.agents/skills/**`, including VDD, Quick Dev, Bootstrap, and Acceptance, appear deleted. Determine why and whether this is an intended migration.

## Evidence Inventory

| Source | Status | Notes |
| --- | --- | --- |
| Primary worktree path-scoped Git status | Available | No changes reported for `.agents/skills` at case initialization. |
| Git index and filesystem inventory | Available | HEAD and index each contain 751 tracked files; none are missing on disk. |
| Sparse-checkout and worktree configuration | Available | Sparse checkout is disabled and no tracked skill path has skip-worktree. |
| Linked worktrees | Available | All 12 registered worktrees report zero skill deletions. |

## Investigation Backlog

| # | Path to Explore | Priority | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Verify primary index and filesystem counts | High | Done | 751 tracked in HEAD, 751 tracked in index, zero missing. |
| 2 | Inspect sparse-checkout and skip-worktree state | High | Done | Both mechanisms are inactive. |
| 3 | Inventory linked worktree statuses | High | Done | Zero deletions in every registered worktree. |
| 4 | Trace recent deletion commits | Medium | Done | No historical bulk deletion affected the four named control-plane skills. |

## Timeline of Events

| Time | Event | Source | Confidence |
| --- | --- | --- | --- |
| 2026-07-31 | Primary worktree reports no `.agents/skills` status changes. | `git status --short -- .agents/skills` | Confirmed |
| 2026-07-31 | The value 751 is reproduced as the complete tracked skill-file count in both HEAD and the index. | `git ls-files`; `git ls-tree -r HEAD` | Confirmed |
| 2026-07-31 | All registered worktrees report zero deleted skill paths. | `git worktree list`; per-worktree porcelain status | Confirmed |

## Confirmed Findings

### Finding 1: The primary worktree does not currently report the claimed deletions

**Evidence:** `git status --short -- .agents/skills` at `C:/jimuyun` returned no entries.

**Detail:** The user report may come from another linked worktree, a stale client view, or a non-Git filesystem comparison.

### Finding 2: The reported number equals inventory size, not a deletion set

**Evidence:** HEAD contains 751 tracked `.agents/skills/**` paths, the index contains the same 751 paths, and none are missing on disk.

**Detail:** No index deletion, worktree deletion, or diff-files entry exists for the path.

### Finding 3: The control-plane entry files exactly match HEAD

**Evidence:** Git blob hashes for VDD, Quick Dev, Bootstrap, and Refactor Acceptance `SKILL.md` files match their `HEAD` blobs.

**Detail:** These four control-plane skills have neither local deletion nor local content drift.

### Finding 4: Historical deletions do not explain the report

**Evidence:** Commit `a57640d` intentionally removed 222 legacy BMAD/GDS workflow files but removed none of the four named control-plane skills. Commits `00c2cf7` and `0895d77` removed one VDD reference and six obsolete VDD fixtures respectively.

**Detail:** No historical commit removed all 751 currently tracked skill files.

## Deduced Conclusions

### Deduction 1: The current repository does not contain an unfinished 751-file skill deletion

**Based on:** Findings 1 through 4.

**Reasoning:** HEAD, index, disk, and every registered worktree agree that the tracked skill inventory is present. Sparse-checkout and skip-worktree cannot explain an omitted working-tree view.

**Conclusion:** The report came from a stale or different source-control view, or it misread the total tracked count as a deletion count.

## Hypothesized Paths

### Hypothesis 1: The 751 deletions are present in the primary worktree

**Status:** Refuted

**Theory:** Tracked skill files were removed by a migration or an unfinished filesystem operation.

**Supporting indicators:** User-observed deletion count and affected control-plane skills.

**Would confirm:** Git index comparison against HEAD reports matching deletions in `C:/jimuyun`.

**Would refute:** Independent Git status, diff-files, and filesystem inventory all show the primary worktree matches HEAD.

**Resolution:** Independent HEAD, index, disk, diff-files, and linked-worktree checks all report zero deletions.

## Missing Evidence

| Gap | Impact | How to Obtain |
| --- | --- | --- |
| External client or command that displayed 751 deletions | Prevents attribution of the false report to a specific cache or alternate index | Capture the exact working directory and raw output if the report recurs. |

## Source Code Trace

Not applicable until a deletion producer is identified.

## Conclusion

**Confidence:** High

No tracked `.agents/skills/**` file is deleted in the primary repository or any registered worktree. The number 751 is the full tracked inventory count. There is no evidence of an intended migration removing VDD, Quick Dev, Bootstrap, or Refactor Acceptance; deleting that control plane wholesale would be unexpected and unsafe.

## Recommended Next Steps

### Diagnostic

Treat the deletion concern as cleared for `C:/jimuyun`. If an external tool repeats the report, refresh it and capture its exact repository root and raw Git command before taking any repair action.

## Reproduction Plan

Re-run `git status --porcelain=v1 -- .agents/skills`, `git diff --diff-filter=D --name-only -- .agents/skills`, and the tracked-versus-disk inventory. Expected result: zero changes, zero deletions, and zero missing tracked files.
