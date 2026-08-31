# Architecture Spine Reality / Brownfield Review — 2026-08-31

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

## Verdict

**Needs revision before finalization.** The spine expresses the intended trust
boundaries and lifecycle invariants, but several ownership and schema claims do
not match the repository-owned implementation paths. These are convergent
architecture issues, not requests to widen the product scope.

## Findings

### H1 — Artifact-writer ownership in AD-6 does not match the code

AD-6 states that the coverage gate is the sole writer of runtime coverage,
evidence snapshots, `slice-ready`, and terminal results. In the current
brownfield code those writes are split: `artifact_owners.py` writes
`acceptance-coverage.v1.json` and false-green artifacts; `slice_ready_predicate.py`
writes `slice-ready-result.json`; `terminal_validator.py` writes terminal
observation/replay/lineage artifacts; and `terminal_predicate.py` writes the
implementation-complete result. The coverage gate modules primarily validate
inputs. Two independent implementers could therefore choose incompatible
writers while both claiming AD-6 compliance.

**Required disposition:** amend AD-6 and its graph to name the concrete owner
roles separately (coverage artifact owner, slice-ready predicate writer,
terminal evidence producer, and terminal result predicate), or introduce a
single facade that is explicitly the sole writer and make the existing modules
validators behind it. Keep validator/read-only responsibilities distinct from
write authority.

### H2 — Layered evidence-state vocabulary is inconsistent with emitted artifacts

AD-5 permits `planned-only`, `observed-run`, `recovered-run`, and `invalid-run`.
However, `tools/semantic_oracle.py` emits `evidence_state: "observed"` in its
verification cases (lines 185–188), which is not a legal value in the spine.
The same path still uses the legacy `executions` field, while the canonical
contracts and companions require `process_attempts`, `test_executions`, and
`cases`. This means a conforming judge cannot validate the current semantic
artifact without either silently projecting fields or weakening AD-5.

**Required disposition:** choose one vocabulary and bind it in the spine and
all owner schemas. Prefer the canonical four-state values and the separated
execution counters; add an explicit compatibility projection only if legacy
fixtures must remain readable.

### H3 — Runtime assertion-edge guarantees are stronger than the current gate

AD-8 requires each `runtime_assertion_edge` to carry plan/slice/candidate/run/
observation/result lineage plus selector, target, fixture, case-source,
producer, and validator identities. The plan-local `coverage_gate.py` currently
checks only `acceptance_id`, `case_id`, `observation_id`, and a receipt assertion
(and delegates to a similarly minimal fallback in `semantic_oracle.py`). The
additional lineage is not enforced at this boundary. A hand-authored minimal
edge could therefore pass the existing gate while violating the spine.

**Required disposition:** make the coverage gate (or a named pre-gate validator)
the mechanical enforcer for the full AD-8 edge shape, including hash bindings;
state which module owns this validation so the graph does not imply that
coverage calculation alone proves lineage.

### H4 — Structural seed names do not reflect the repository's executable roots

The spine's Structural Seed lists `scripts/vdd/` and `scripts/quick_dev/`, but
those directories do not exist in the current repository. The executable
implementations are under `.agents/skills/vdd-execution-plan/scripts/`,
`.agents/skills/quick-dev-tdd-adapter/tools/`, and the plan-local
`execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/`.
The current environment is verifiable as Python 3.12.10 with pytest 9.1.1 via
`py -3`; no repository-owned `scripts/vdd` launcher was found.

**Required disposition:** either correct the seed to the existing roots or mark
the paths explicitly as future projections and add a brownfield rule requiring
V0/Q0 to record the resolved launcher and interpreter/test-runner versions.
Do not leave two equally plausible roots.

### M1 — Stage dispatcher bypasses the stated descriptor/executor seam

`tools/stage_command.py` directly invokes pytest selectors (lines 72–74) and
then invokes `artifact_owners.py` (lines 62–80). Only the S3 owner currently
uses `process_executor.execute` to run a descriptor argv. This is compatible
with a plan-local adapter, but it is not the uniform “descriptor → executor →
judge” path implied by the main Mermaid graph. Without an explicit adapter
exception, future slices may run tests directly and bypass descriptor-bound
identity or timeout policy.

**Required disposition:** document `stage_command.py` as a non-authoritative
dispatcher that must delegate every process-bearing stage through the declared
executor/owner, or change the dispatcher so all stages consume the frozen
descriptor. Keep the exception scoped to plan-local diagnostic/test selectors.

### M2 — Declared cwd contract and owner subprocess cwd diverge

The command registry declares repository-relative cwd `.`. In
`stage_command.py`, the owner subprocess is launched with
`cwd=repository_root.parent` (line 79), while the pytest probe uses
`cwd=repository_root` (line 72). This currently works only because several paths
are absolute, but it permits environment-dependent imports and relative path
resolution to diverge from the declared descriptor contract.

**Required disposition:** bind owner execution to the same resolved repository
root/cwd as the descriptor, and add a path-containment check before dispatch.
If the parent cwd is intentional for a platform wrapper, record it as a named
adapter boundary rather than leaving it implicit.

## Brownfield / technology checklist

- Python and pytest are present and executable (`Python 3.12.10`, `pytest 9.1.1`).
- Process execution uses `subprocess.run(..., shell=False)` in the current owner,
  which is consistent with the spine's shell-free rule; timeout/resource and
  concurrency policy remain implementation decisions.
- Run evidence is placed under `logs/tdd-adapter/`, consistent with the
  repository evidence-location convention; generated plan artifacts remain
  append-only only where the owner performs create-if-absent writes.
- Existing Phase service paths (`PhaseA.Platform/**`, `runtime/phase-a/**`) are
  correctly treated as forbidden by the plan contract; no architecture finding
  requires changing those protected trees.

## Gate recommendation

Resolve H1–H4 before setting `status: final`; M1–M2 can be fixed in the same
revision. Re-run the full Reviewer Gate after the ownership/schema/root-path
amendments. No CAP-1…CAP-10 change is required.

