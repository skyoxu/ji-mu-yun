# Windows replay budget repair: remote review handoff

Authority: Accepted ADR-0058 and the maintainer-approved budget separation.
This is a publication of existing implementation and evidence, not a new VDD,
Quick Dev, Q8, Acceptance or Trust Approval run. C3 stays OPEN; authorizes=[].

## Review scope

Review the committed replay runtime, fresh reconstruction, dependency traversal,
budget regressions, CER transport selectors and ADR-0058 amendment. The original
executions record HEAD 00d773a87ae50aaba57b9810f12f6bcf694a33e3 plus source-byte
bindings for the uncommitted candidate. Publishing those bytes in a new commit
does not rewrite or rebind the original evidence to that new commit.

The newest limits are leaf 60s, fresh-child 120s, Matrix aggregate 120s,
fresh orchestration 300s, Matrix harness 150s and parent transport 360s.
The direct verification supervisor still uses a separate 300s per-test limit.
The older measurement README describes earlier limits and is preserved as-is.

## Results and limitations

- Original 20261009 run: 51 unittest passed; 293 pytest passed, 1 failed and
  46 unfinished. S44 checkout evidence was absent in one result; the next
  Consumer test reached the supervisor deadline. The original run remains failed.
- First resume: repeated unittest exceeded its startup/idle deadline; no selected
  pytest nodes ran. This failed resume remains archived.
- Resume r2 used existing --pytest-only: all 47 selected nodes passed, with native
  JUnit, exit 0, no skips and source_stable=true. The selection includes the one
  original failure and all 46 unfinished nodes, not the 293 successful nodes.
- The node audit verifies passing setup/call/teardown for all 340 unique selected
  nodes across original plus resume r2, with no missing or unexpected node.
  This is segmented verification, not a single uninterrupted 340/340 pass.
- Original and resume source bindings agree on shared paths and match the
  currently published candidate bytes. Historical failures are not erased.
- Passing a retry does not establish the root cause of the original transient
  failure or timeout. External review should inspect their native traces and
  assess the remaining budget risk, including the 300s supervisor vs 360s transport.
- No implementation-complete, Acceptance pass or formal lifecycle closeout is
  established by this handoff. Tests and segmented coverage are review inputs.

## Complete native evidence

All relevant 20261008 investigation directories and both 20261008/20261009 budget
verification directories are stored in separate lossless tar.gz archives.
The 20261009 archive includes both failed first resume and successful resume r2.
Original files remain untouched locally. Archives preserve stdout/stderr,
summaries, native process records, event streams, stack snapshots, node lists,
source bindings, diagnostics, RED/GREEN records and every native JUnit that exists.
No missing original JUnit is synthesized.

archives.json lists archive hashes. file-manifest.json records the original
repository-relative path, byte length and SHA-256 of every archived file.
package_evidence.py verified each archived member byte-for-byte before publication.
For convenient GitHub reading, original/resume summaries, bindings, manifests,
event streams and the available native JUnit are also copied alongside the
archives without changing their bytes. node-observations.json selects the actual
passing phase reports with links to their original evidence directories.
review-summary.json is an additive audit, not an authorizing receipt.
