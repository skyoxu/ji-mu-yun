# Current-Reality / Brownfield Verification Review

## Review Identity

- Lens: current repository reality and brownfield migration safety
- Reviewed file: `ARCHITECTURE-SPINE.md`
- Expected SHA-256: `fabc669a030080efb3f740a5a8093b5fa433c974541ef52dcfd2a61ca1b4d291`
- Observed SHA-256 before review: `fabc669a030080efb3f740a5a8093b5fa433c974541ef52dcfd2a61ca1b4d291`
- Revision status: exact frozen revision matched
- Mutation: none; this review did not edit the spine

## Verdict

**Changes required.** No P0 was found. Four P1 brownfield gaps and one P2 API ambiguity remain. The lifecycle ownership and Acceptance route names in the spine match the current repository contracts.

## Findings

### CR-P1-1 - `current` pointer immutability contradicts both the frozen decision and the current producer

**Severity:** P1

The spine states that a `current` pointer is an "owner-scoped immutable selection artifact" while also requiring all published artifacts to be immutable (`ARCHITECTURE-SPINE.md:56-60`). The current bmad-spec producer publishes a content-addressed selection record and then replaces the stable `current/<package-id>.json` path through `write_json()` and `os.replace()` (`.agents/skills/bmad-spec/scripts/canonical_package.py:192-199`, `:215-220`). This is also inconsistent with the frozen D2 wording that explicitly permits pointer changes without changing immutable artifact truth.

The architecture must distinguish two objects:

- immutable, content-addressed selection records; and
- a mutable owner-scoped selection reference whose replacement is controlled and does not alter the selected artifact's truth.

If the pointer itself must become immutable, the spine must define a successor-pointer/history mechanism and a different stable resolution mechanism. Leaving the current wording will make a conforming implementation reject the repository's only current selection producer or silently exempt it from AD-2.

### CR-P1-2 - The versioned Bootstrap runtime-policy artifact has no physical owner, schema, or cutover rule

**Severity:** P1

AD-10 requires one versioned runtime-policy artifact and recovery from the current published policy (`ARCHITECTURE-SPINE.md:106-110`), but the structural seed names only the shared primitive and the two Skill script directories (`:160-177`). It does not name the policy artifact path, schema owner, publication/selection mechanism, or the rule that removes hardcoded values.

Current Bootstrap production behavior is still compiled into module constants: `CODEX_NO_PROGRESS_TIMEOUT_SECONDS`, segment thresholds, prompt limit, event version, and repeated-failure threshold (`.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py:75-88`). The accepted ownership ADR says the durable semantics belong to `docs/standards/bootstrap-review-control-plane.md` and executable protocol belongs to the repository Skill (`docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md:14-24`); it does not establish a separate policy publisher.

The spine must identify the repository-owned policy location/schema, its publisher/selection owner, and a fail-closed cutover invariant: once a policy-backed field is enabled, the corresponding module constant cannot remain an alternative authority. Without that decision, implementations can create competing "current policy" and hardcoded policy truths.

### CR-P1-3 - `repository-canonical-json.v1` cannot directly encode current Bootstrap identity payloads

**Severity:** P1

AD-5 prohibits floats and accepts only signed int64 numeric values (`ARCHITECTURE-SPINE.md:74-80`). Current Bootstrap schemas intentionally contain numeric fractions: semantic-yield ratios and wall seconds (`.agents/skills/run-phase-bootstrap-review/schemas/bootstrap-review-history-index.v1.schema.json:13-23`, `:48-60`), plus calibration multipliers and observed wall seconds (`.agents/skills/run-phase-bootstrap-review/schemas/bootstrap-review-cost-calibration.v1.schema.json:57-73`). Production code constructs these values as Python floats and includes the generated history in a `value_hash()` identity input (`.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py:11423-11445`, `:11449-11454`). The current `value_hash()` accepts them because it delegates to `json.dumps` (`:512-519`).

Consequently, Bootstrap cannot simply cut over to the shared primitive as required by AD-4/AD-6: valid current identity inputs will be rejected. The artifact owner must ratify an explicit schema/projection migration before mandatory convergence, such as fixed-unit integers or canonical decimal strings, or classify specific hashes as non-canonical raw/presentation identities with a replacement identity contract. The new owner schema/domain and historical verify-only replay must be named; generic "owner schema/domain versions" is insufficient for this known incompatibility.

### CR-P1-4 - Quick Dev still imports durable canonical/path behavior from a historical execution-plan directory

**Severity:** P1

AD-4 makes `scripts/toolchain/canonical_evidence/` the sole shared implementation and AD-6 prohibits new private implementations after it lands (`ARCHITECTURE-SPINE.md:68-86`). However, current Quick Dev production modules explicitly add `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools` to `sys.path` and import `canonical_bytes`, `value_hash`, `safe_relative`, and protocol validators from that plan (`.agents/skills/quick-dev-tdd-adapter/tools/stage_artifact_composer.py:8-20`; `.agents/skills/quick-dev-tdd-adapter/tools/protocol_fixture_support.py:9-14`). The imported canonical/path implementation is physically owned by `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/protocol_artifact_guards.py:17-35`.

This is not just duplicate code: it is a live Skill dependency on a historical plan-owned implementation. The mandatory migration sequence must identify this dependency explicitly, move canonical/path mechanics to the shared primitive, and place remaining Quick Dev protocol validation under a durable Quick Dev owner before the historical plan can be treated as evidence-only or removed. A generic private-implementation removal rule can miss this cross-tree import because the implementation is not inside the consuming Skill.

### CR-P2-1 - `normalize_repository_path(root, path)` is too underspecified to converge current consumers

**Severity:** P2

AD-4 names a stable path API and says it performs lexical identity normalization with root-escape rejection (`ARCHITECTURE-SPINE.md:68-72`), but does not define its returned representation, separator rule, case behavior, dot-segment handling, or how `root` participates in a lexical operation.

Current consumers differ materially:

- bmad-spec resolves against the filesystem, preserves POSIX spelling, and separately rejects case-fold collisions (`.agents/skills/bmad-spec/scripts/canonical_package.py:103-118`, `:148-152`);
- VDD resolves paths and checks containment (`.agents/skills/vdd-execution-plan/scripts/source_freeze.py:44-59`);
- the Quick Dev protocol helper performs only `PurePosixPath` lexical checks (`execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/protocol_artifact_guards.py:31-35`);
- Quick Dev write-set matching normalizes separators and case-folds prefixes (`.agents/skills/quick-dev-tdd-adapter/tools/adapter.py:29-32`).

The shared primitive should specify a repository-relative POSIX output, case-preservation and collision policy, rejection/collapse rules for `.` and `..`, and the exact distinction between lexical identity normalization and owner-level filesystem containment. Otherwise the same Windows path can retain different identities across consumers even after they share one function name.

## Verified Non-Findings

- Lifecycle ownership in AD-1 matches `.agents/skills/vdd-execution-plan/references/lifecycle-state-contract.json` and the current VDD, Quick Dev, Bootstrap, and Acceptance Skill contracts.
- The four route names in AD-12 match current Acceptance routing: `deterministic_only`, `focused_repair_verification`, `full_implementation_conformance`, and `manual_pause`.
- `.agents/skills/run-phase-bootstrap-review/` is the accepted executable protocol owner under ADR-0041; the spine does not incorrectly assign Bootstrap lifecycle authority.

## Recommended Gate Result

`changes_required`: fix CR-P1-1 through CR-P1-4 before adopting the spine as a canonical companion. CR-P2-1 may be fixed in the same architecture revision because it defines a stable public API and is cheap to close now.
