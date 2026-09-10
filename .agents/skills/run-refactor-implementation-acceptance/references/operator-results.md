# Inspect Results And Review Inputs

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

## Operator And External Reviewer Support

After each public `run-coordinator` invocation, inspect the `Acceptance support`
path printed on stderr. The content-addressed directory under
`logs/acceptance-operator-support/` contains `summary.md`, `report.json`,
`candidate.diff` and `reviewer-prompt.md`. Existing stdout/result contracts and
Acceptance predicates remain authoritative. A support-generation failure is
reported separately and cannot turn a blocked run into success.

The summary shows completion, blockers, action states and the next owner step.
The report scans current tracked source for one-hop literal path and Python
import-name references, with matched lines and source hashes. It suggests
registered checks naming affected files and unregistered pytest candidates.
These are incomplete hints, never a consumer closure or coverage proof; no
suggested check runs automatically. Source/count/size limits are explicit.

For external review, supply the prompt together with its referenced requirements,
Q8/Acceptance evidence and candidate diff. Verify source hashes when transferring
files. References alone do not give an external reviewer repository access.
The diff uses hash-checked frozen snapshot or commit bytes, while consumer hints
reflect explicitly labeled current worktree bytes. Missing inputs, binary diffs
and truncation remain visible limitations. No model is launched, review is not
sent automatically, and reviewer text never grants Acceptance authority.
