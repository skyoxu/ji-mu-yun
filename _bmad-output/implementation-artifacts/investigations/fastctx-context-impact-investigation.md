# Investigation: FastCtx Context Impact

## Hand-off Brief

1. **What happened.** Acceptance and Bootstrap work encountered context-window exhaustion after FastCtx became the default inspection plane; causality and impact share remain under investigation.
2. **Where the case stands.** Confirmed evidence shows both historical reviewer over-reading and a current unbounded tool-result return; comparative quantification is pending.
3. **What's needed next.** Inventory comparable pre-FastCtx and FastCtx-era attempts, then measure tool-result volume, read scope, failure class, and session growth.

## Case Info

| Field | Value |
| --- | --- |
| Ticket | N/A |
| Date opened | 2026-08-09 |
| Status | Active |
| System | Windows, Ji Mu Yun repository, Codex CLI |
| Evidence sources | Bootstrap/Acceptance run logs, Codex rollout logs, process results, tool-call records |

## Problem Statement

Determine whether FastCtx materially increased context-window exhaustion during Acceptance and Bootstrap workflows, compared with earlier runs using other local inspection tools, and estimate its contribution without treating correlation as causation.

## Evidence Inventory

| Source | Status | Notes |
| --- | --- | --- |
| `logs/reviews/broh-acceptance-20260809-r4b/**` | Available | Historical context-window failures |
| `logs/reviews/broh-acceptance-20260809-r4c/**` | Available | FastCtx tool calls and segmented reviewer attempts |
| `execution-plans/2026-08-07-bootstrap-review-operability-hardening/bootstrap-runs/**` | Available | Earlier Bootstrap attempts |
| Current Codex rollout | Available | Main-session growth and tool-result evidence |
| Comparable pre-FastCtx successful runs | Partial | Matching review scope and model still need identification |

## Investigation Backlog

| # | Path to Explore | Priority | Status | Notes |
| --- | --- | --- | --- | --- |
| 1 | Inventory attempts and classify tool families | High | In Progress | Compare FastCtx, shell, and other MCP calls |
| 2 | Measure stdout/tool-result bytes per attempt | High | Open | Avoid loading raw output into parent context |
| 3 | Compare failures against artifact size and prompt contract | High | Open | Control for scope and model |
| 4 | Estimate FastCtx contribution and uncertainty | High | Open | Separate trigger, amplifier, and unrelated factors |

## Timeline of Events

| Time | Event | Source | Confidence |
| --- | --- | --- | --- |
| 2026-08-09 | Historical reviewer emitted context-window error | `logs/reviews/broh-acceptance-20260809-r4c/attempts/**/stdout.log` | Confirmed |
| 2026-08-09 | Current r5 completed deterministic validation without launching reviewers | `execution-plans/2026-08-07-bootstrap-review-operability-hardening/acceptance-runs/acceptance-broh-20260809-r5/acceptance-events.jsonl` | Confirmed |
| 2026-08-09 | An unbounded recursive inventory returned more than 10,000 tokens and was truncated | Current Codex tool result | Confirmed |

## Confirmed Findings

### Finding 1: Large tool returns directly consume the parent session

**Evidence:** Current Codex tool result for recursive `project-context.md` discovery exceeded 10,000 tokens and was truncated.

**Detail:** The amplification mechanism is independent of reviewer semantics: any inspection tool that returns a large result directly to Codex can increase parent-context pressure.

## Deduced Conclusions

### Deduction 1: Tool choice alone is not yet isolated

**Based on:** Finding 1 and historical prompt over-reading evidence.

**Reasoning:** FastCtx can return large payloads, but the same failure mode is possible through shell output. A matched comparison must control for requested scope, output cap, model, and retry history.

**Conclusion:** FastCtx impact is plausible and measurable, but no percentage is defensible yet.

## Hypothesized Paths

### Hypothesis 1: FastCtx materially amplified context pressure

**Status:** Open

**Theory:** FastCtx batch reads and structured tool responses caused more raw content to be retained than prior shell-based inspection.

**Supporting indicators:** Historical reviewer logs show full manifest and multi-file reads returned inline; the current unbounded inventory also produced a very large tool result.

**Would confirm:** Matched FastCtx-era attempts show substantially larger retained tool-result bytes or tokens than comparable pre-FastCtx attempts after controlling for scope.

**Would refute:** Comparable runs show no material volume difference, or failures correlate primarily with prompt scope and repeated resume history.

**Resolution:** Pending comparative measurement.

## Missing Evidence

| Gap | Impact | How to Obtain |
| --- | --- | --- |
| Matched pre-FastCtx run set | Prevents causal estimate | Classify historical attempt logs by tool-call family and scope |
| Per-turn retained token counts | Limits exact percentage estimate | Use recorded usage where available; otherwise use byte/character proxies |
| Identical-scope A/B run | Prevents experimental attribution | Design a read-only replay after historical analysis, only with explicit authorization |

## Source Code Trace

| Element | Detail |
| --- | --- |
| Error origin | Codex model context limit |
| Trigger | Oversized accumulated prompt, tool results, or reviewer reads |
| Condition | Raw evidence is returned inline faster than history can be compacted |
| Related files | Bootstrap reviewer prompts, attempt stdout logs, Codex rollout logs |

## Conclusion

**Confidence:** Low

FastCtx is a confirmed context-volume amplifier in unbounded calls, but its share of the historical failures has not yet been quantified against comparable earlier runs.

## Recommended Next Steps

### Fix direction

Defer until comparative evidence is complete.

### Diagnostic

Build a compact per-attempt dataset containing tool family, returned bytes, artifact scope, model, failure class, and retry history.

## Reproduction Plan

Not yet authorized. Historical evidence analysis comes first.

## Side Findings

- Broad recursive discovery can itself recreate the context-pressure condition being investigated.

## Follow-up: 2026-08-09

### New Evidence

- Historical sample under `logs/reviews/broh-acceptance-20260809-r4b`, `logs/reviews/broh-acceptance-20260809-r4c`, and the 8-07 `bootstrap-runs` contains 69 attempts with FastCtx calls: 6 contained the exact context-window error (`8.7%`); median stdout size was 24,998 bytes and maximum 1,561,387 bytes.
- The same sample contains 8 attempts classified as other/shell tooling: 2 contained the exact error (`25%`); median stdout size was 421,397.5 bytes.
- Five attempts contained no tool call before the error: all 5 failed immediately (`100%`), with stdout sizes from 403 to 2,340 bytes.
- The current r5 Acceptance run has no reviewer attempt and no child process launch; its lifecycle evidence ends after deterministic validation and Bootstrap decision.

### Additional Findings

#### Finding 2: FastCtx is a volume amplifier, not a confirmed primary trigger

**Evidence:** The grouped counts above; exact error lines in the historical stdout logs.

**Detail:** FastCtx calls can produce large inline results, including attempts with hundreds of reads/greps, but context failures also occur before any tool call. The data therefore supports amplification, not sole causation.

#### Finding 3: The available sample cannot establish a true pre-FastCtx baseline

**Evidence:** The identified 8-07 and r4b/r4c records are already from the FastCtx-routed control plane; no matched same-scope pre-FastCtx attempt was identified in the inspected set.

**Detail:** The observed error-rate comparison is within a mixed attempt sample, not a controlled before/after experiment. It must not be reported as FastCtx's causal percentage.

### Updated Hypotheses

- **FastCtx materially amplified context pressure:** remains Open, medium support.
- **Prompt/contract and retry-history dominate the trigger:** upgraded to Strongly Supported by immediate no-tool failures and oversized non-FastCtx outputs.
- **Current r5 failure is a reviewer-child regression:** Refuted for the observed incident; r5 launched no reviewer child.

### Updated Conclusion

**Confidence:** Medium

The evidence shows FastCtx can materially increase the amount of text retained by a Codex session, especially for unbounded reads. It does not show that FastCtx caused the historical failures by itself, and it does not provide a valid percentage contribution. The primary confirmed control defect remains unbounded accumulated context plus prompt/retry state; FastCtx should be treated as an amplifier that requires output-budget enforcement.

### Backlog Changes

- Matched pre-FastCtx baseline: remains Open and is required before any causal percentage is claimed.
- Per-tool output budgeting and summary-only parent protocol: High priority design follow-up.

## Follow-up: 2026-08-09 #2

### New Evidence

- Controlled A/B payload test used the same 1,382-byte, 25-line schema file repeated 10 times.
- Native PowerShell content payload: 13,820 bytes total, approximately 3,455 tokens using a coarse four-characters-per-token proxy.
- FastCtx-formatted payload (line numbers, path header, completion footer): approximately 1,649 bytes and 413 proxy tokens per group, or 16,490 bytes and 4,130 proxy tokens for 10 groups.
- FastCtx formatting overhead for this small file was approximately 267 bytes per group, about 19.3% over the raw content payload.

### Additional Findings

#### Finding 4: FastCtx has measurable envelope overhead

**Evidence:** Controlled payload comparison above.

**Detail:** For small reads, FastCtx's path, line-number, and completion metadata increase the context payload. With larger files, raw content dominates and the percentage overhead should fall; with many independent calls, repeated envelopes increase it again.

**Limitation:** The platform did not expose billable/API token usage for these tool calls. The figures are serialized-byte and coarse token proxies, and native shell command/tool envelope overhead was not included.

### Updated Conclusion

**Confidence:** Medium

FastCtx occupies more context than the raw native-content payload in this controlled sample, by roughly 19%. That is a real transport/envelope cost, but it is far smaller than the multi-hundred-kilobyte or megabyte increases caused by unbounded file reads, repeated retries, and reviewer prompt behavior. FastCtx should be budgeted and summarized, but the A/B result does not make it the primary historical root cause.
