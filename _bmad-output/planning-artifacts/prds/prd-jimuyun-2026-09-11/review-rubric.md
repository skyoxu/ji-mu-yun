# PRD Quality Review — TC-D1 Trustworthy Skill Replay and Evaluation Repair

## Overall verdict

The PRD has a clear thesis, an appropriate capability-oriented shape, and unusually strong protection against the false-success modes found in the current repository. It is not yet decision-ready for Spec and Architecture because several open questions determine the meaning of consumer completeness, rollback equivalence, matrix success, diagnostics, and review approval; leaving those decisions downstream would allow materially different products to satisfy the same PRD.

## Decision-readiness — thin

The document makes the central decisions explicit: TC-D1 repairs the existing capability, preserves evidence, remains non-authorizing, requires real stable/candidate execution, and separates review from Acceptance. The rejected proof shortcuts in `addendum.md` also preserve the important trade-off in favor of stronger evidence despite greater execution and maintenance cost.

The unresolved decisions in §11 are too consequential for a finalized chain-top PRD. The statement that “Questions 1-5 and 7 are phase blockers for Spec or Architecture, not blockers for this PRD's product direction” understates their effect: these questions define which consumers must pass, what rollback success means, what makes each matrix case meaningful, which failures are acceptable, and who can approve the gate. Spec or Architecture could choose incompatible answers while still claiming conformance.

### Findings

- **high** Product acceptance semantics are deferred downstream (§11, questions 1-5 and 7) — The authoritative Consumer set, Prior Route equivalence, minimum stable/candidate difference, case failure taxonomy, diagnostic states, and review approval identity determine whether FR-7 through FR-10 and FR-13 pass. They are product policy, not implementation detail. *Fix:* resolve each as a product decision or state a bounded decision rule and accountable owner before finalizing the PRD; leave only mechanism choices to Spec and Architecture.
- **medium** The PRD does not state the cost accepted for stronger evidence (§1, §8) — The vision rejects shortcuts and SM-C4 rejects speed gained by skipping evidence, but operators cannot tell what operational burden is acceptable before NFR-7 is measured. *Fix:* state the product trade-off explicitly: correctness and reconstructibility take priority within a bounded execution budget, and exceeding that budget yields an unsuccessful diagnostic result rather than reduced coverage.

## Substance over theater — strong

The content is specific to the repository's observed failure modes. Phrases such as “relabeling identical cases,” “changing a rollback flag without restoring prior caller behavior,” and “a route check unreachable on success” correspond to concrete current risks rather than template furniture. The operational users drive distinct decisions and journeys, while the NFRs describe evidence integrity, isolation, immutability, and Windows portability instead of generic reliability claims.

## Strategic coherence — strong

The thesis is consistent from Vision through Features and Success Metrics: prevent false success and make conclusions reconstructible without granting lifecycle authority. The feature order follows that thesis from target and validator trust through probes, comparison, consumers, rollback, coverage, freshness, and Acceptance handoff. The counter-metrics directly prevent passing-test count, evidence volume, category labels, or speed from displacing the stated outcome.

## Done-ness clarity — adequate

Every FR has explicit consequences, and the Success Metrics cover the major false-success families with measurable zero/100% expectations. FR-7 and FR-8 correctly require distinct identities, actual execution, and rejection of reused evidence; FR-10 correctly distinguishes behavior restoration from metadata state; FR-11 rejects aggregate-only coverage.

Some criteria still depend on undefined terms that are currently open questions. “Supported Target Package,” “trusted identity,” “semantic dependencies,” “expected behavior,” “authoritatively declared,” and “same semantic verdict” cannot yet be tested consistently without product-level definitions or decision rules. NFR-7 also has no bound, although it is clearly marked as an assumption.

### Findings

- **high** Several pass/fail predicates depend on undefined product terms (§4 FR-1, FR-3, FR-9, FR-10; §5 NFR-3) — Different implementers can disagree about support, trust, dependency closure, rollback equivalence, and semantic reproduction while satisfying the prose. *Fix:* add concise normative definitions or decision tables for these predicates, linked to the resolved §11 decisions; keep field names and algorithms in the addendum.
- **medium** Historical immutability lacks a declared comparison scope (§4 FR-5; §5 NFR-5; §8 SM-4) — “Historical 08-01 and prior 08-05 tracked evidence remains unchanged” and “no historical evidence loss” do not define the authoritative pre-run inventory, so additions, generated files, ignored files, and renamed paths may be judged inconsistently. *Fix:* define the product-level preservation set and require before/after membership and content identity for that set.

## Scope honesty — adequate

The scope boundary is explicit and useful. §6 and §7 exclude E0, D2-D6, Phase service and user sandbox changes, baseline promotion, autonomous modification, and generalized governance. The addendum distinguishes current evidence gaps from requirements and identifies `docs/fix80501.txt` as informative and non-authorizing.

The assumptions discipline is mechanically incomplete. §0 promises that inferred decisions are marked `[ASSUMPTION]` and indexed, but only NFR-7 carries an inline tag while §12 lists eight assumptions. Several index entries materially affect feasibility and acceptance, especially enumerability of Consumers and reproducibility of the Prior Route.

### Findings

- **medium** Assumptions Index does not round-trip to inline assumptions (§0, §5 NFR-7, §12) — Seven indexed assumptions have no inline marker, so downstream extraction cannot identify where each assumption affects a requirement, metric, or risk. *Fix:* place an `[ASSUMPTION: ...]` marker at every affected location and make each §12 entry point back to it, or convert confirmed statements into explicit decisions and remove them from the index.

## Downstream usability — adequate

The glossary is strong, IDs are contiguous and unique, and features are grouped in a sequence suitable for subsequent Spec and Architecture work. The PRD cleanly separates capabilities from mechanisms; `addendum.md` captures current assets, known gaps, architecture decisions, and deferred technical detail. The brownfield reality is accurately represented: `0dce7806` improved real execution but does not establish semantic stable/candidate comparison, behavioral rollback, full receipt identity, or original-requirement exact cover.

Downstream work is currently blocked by the unresolved product predicates noted above. There is also no explicit mapping from every journey and metric to all affected FRs, although the prose references are sufficient for most extraction and the PRD correctly avoids a full traceability matrix.

### Findings

- **medium** Architecture decision item 5 currently contains an unresolved product ownership decision (`addendum.md`, “Define the authoritative Consumer registry”) — Architecture can design storage and validation, but it should not decide which source is authoritative or who may change the Consumer set. *Fix:* decide authority and change ownership in the PRD, then narrow the addendum item to registry representation, version binding, and closure mechanics.

## Shape fit — strong

This is a high-stakes brownfield internal toolchain capability, and the PRD uses the right capability-spec shape. Four short journeys clarify maintainer, reviewer, operator, and consumer outcomes without persona theater. Technical mechanisms are deferred to the addendum, while repository constraints and current shortcomings remain visible enough to prevent an abstract greenfield design.

## Mechanical notes

- FR, UJ, NFR, and SM identifiers are contiguous and unique.
- Glossary terms are consistently capitalized in normative sections; lowercase “consumer” in risk prose is non-normative and not materially ambiguous.
- The Assumptions Index fails round-trip: eight entries are listed, but only the NFR-7 budget assumption appears inline with `[ASSUMPTION]` syntax.
- No unresolved internal path cross-references were found between `prd.md` and `addendum.md`.
- The absent `.memlog.md` prevents auditing whether every discovery decision and assumption reached the PRD or addendum; this is a Finalize process gap rather than a content dimension verdict.
