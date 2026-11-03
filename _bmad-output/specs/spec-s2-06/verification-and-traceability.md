# Verification, Traceability and Evidence Limits

This is a normative verification contract, not a test execution report. Original S2-06 revision 5, shared scope/dependencies revision 6, frozen PRD and addendum are fully absorbed. All thirteen original FR and nine AC retain their IDs and scope in one package.

## FR preservation matrix

| Requirement | Capability | Normative contract | Original AC mapping |
| --- | --- | --- | --- |
| S2-06-FR01 stable node/roles and endpoint purposes | CAP-1 | identity-and-persistence: protected config and readback | AC01, AC02 |
| S2-06-FR02 unique server home/locality/no request override | CAP-2 | identity-and-persistence: authority and equality chain | AC02 |
| S2-06-FR03 persistent unique test binding | CAP-3 | identity-and-persistence: additive migration/recovery | AC01, AC03 |
| S2-06-FR04 actual-node read/write/run refusal | CAP-4 | consumer-and-role-boundaries: every consumer family | AC02 |
| S2-06-FR05 entry/production duties | CAP-5 | consumer-and-role-boundaries: role operation matrix | AC01, AC04 |
| S2-06-FR06 DI/queue/recovery cannot continue production | CAP-6 | consumer-and-role-boundaries: transition/dispatch | AC04 |
| S2-06-FR07 online/acceptance/readiness validity | CAP-7 | identity-and-persistence: capacity interface | AC06 |
| S2-06-FR08 protected config outside projects | CAP-8 | identity-and-persistence: central vs local capability | AC05 |
| S2-06-FR09 central home/password vs minimal projection | CAP-9 | identity-and-persistence: restricted stores/current central auth | AC05, AC06 |
| S2-06-FR10 additive test usability/future cutover separation | CAP-10 | identity-and-persistence: binding/restart/cutover | AC03, AC06 |
| S2-06-FR11 physical count/instance diagnostics/topology rejection | CAP-11 | consumer-and-role-boundaries: topology gate | AC07 |
| S2-06-FR12 approved shared version vs private user data/cache | CAP-12 | shared-content-and-notifications: source/cache/copy boundary | AC08 |
| S2-06-FR13 central publication vs local audience/read state | CAP-13 | shared-content-and-notifications: notification contract | AC09 |

## Nine required acceptance scenarios

| Scenario | Targeted evidence after implementation | Required failure/recovery observations |
| --- | --- | --- |
| S2-06-AC01 | Temporary existing accounts/projects, one physical node, two co-located logical roles; authenticate, read session/home, use current project | Roles distinct; same IDs and test home before/after normal use. Existing project/Runner behavior remains usable. Evidence labels same-host test only. |
| S2-06-AC02 | Change endpoint/port; submit node/home fields and wrong-home project/run/package/snapshot requests | Same node/account/project IDs; deny before file bytes/process execution; no remote fallback or other-account existence leak. Include ticket/direct artifact/readback paths and server-level invocation. |
| S2-06-AC03 | Temporary pre-upgrade SQLite/workspace with real existing IDs; additive install, interruption/rollback, restart and readback | Null legacy binds once; completed binding unchanged; conflict/orphan registration aborts without overwrite/reset. Projects/runs/history/usable snapshots retained. |
| S2-06-AC04 | Entry-only composition plus all actual queue/service/recovery families; simulate shutdown with waiting and in-flight owned work then entry-only restart | No seeding/create/execute/publish via DI/default/direct/background path; existing cancellation/cleanup bounds honored, no unknown cleanup reuse, no completion-artifact success. Allowed entry/admin and control cleanup work. |
| S2-06-AC05 | Project edits to node/port/config and attempts against central metadata/credential writer; restricted production projection calls | Denial without central change; no password/token hashes in projection, file readback or logs; central authenticated writer still works and current disable/revoke affects dispatch. True Windows Runner/ACL evidence required for OS claims. |
| S2-06-AC06 | Read same-host contract with no real registration/health/remote transport and no S2-03A measurement | scope single_node_test; online/policy separate from invalid measurement/null refs; missing required ownership fails closed. No automatic placement, measured capacity, production split or multi-host claim. |
| S2-06-AC07 | Several actual Runners under one service; alter instance diagnostics; attempt independent scheduler topology | Home/project/node/candidate count unchanged; capacity counted once. Independent services rejected unless real shared budget/lock/fencing/auth/Data Protection proof exists; no fake shared cache proof. |
| S2-06-AC08 | Small approved-source contract fixture with two accounts, shared version query/copy and private-source attack | Shared read-only bytes/version valid; copy edits isolated/provenance honest; project/snapshot/private cache inaccessible to other account. Hash/missing scope/cache hit denial and bounded fallback failure covered. No Phase Locator integration claim. |
| S2-06-AC09 | Small protected same-host publication/projection/read-state contract with eligible/ineligible/newly activated accounts, notice revisions/expiry and forged project/port identity | Central publisher only; node service filters all query/count/read surfaces; read keyed to account/notice/revision; interrupted local update atomic; inert body, no secret leak. Local evidence does not certify cross-host transport/offline recovery or full notification product. |

Use the smallest targeted existing service/API/store/browser tests that prove each changed consumer. Temporary SQLite and workspace fixtures only; no live metadata or Hosted projects. Include compatible existing callers and error/no-store behavior. Test successful operations as well as actual mismatch, unauthorized, missing/invalid reference, cancellation and restart cases; do not build a universal gate or blanket test suite for this document.

## Baseline and source interpretation

Bounded current-code observations are recorded in `logs/s2-06-bmad-20261028/spec-author/bounded-source-inventory.json`. AccountSnapshot/ProjectSnapshot/RunSnapshot and RequestContext contain reusable identity but no explicit node/home contract. Program registers production queues/recovery without the proposed role boundary. SQLite already installs additive fields. These observations motivate the minimum changes; they are not claims of implementation or exhaustive endpoint coverage.

Source exports are Library text exports, each one byte shorter than original metadata. Preserve their actual bytes and five provenance roles; do not claim downloaded-original byte identity. The originals' historical code references are rationale only; this design inspects current fixed HEAD `25580d700da91d2702fd234a024a616d55419f90`. Newrouge has not been inspected. External PRD review history is a handoff fact, not source authority for product requirements.

Knowledge activation executed the actual configured callback, with matched request/result and raw pinned-main source bytes saved under `logs/s2-06-bmad-20261028/knowledge-consumption/spec`. Adopt ADR-0035/0061 for existing Runner/storage/restore and cancellation, Phase ADR index for accepted boundaries/change policy, ADR-0044 for derived-cache/lifecycle authority, and hosted-workspace/route-recovery sources for file/readback/recovery. Godot engine/UI standards were read but add no new Godot requirements to this metadata/role package; existing runtime route gates remain inherited.

## Applicable shared claims and exclusions

| Shared source claim | Disposition |
| --- | --- |
| Current .NET/SQLite/node-local storage/identity/Runner and existing snapshots/restoration | Preserved in kernel and identity/consumer companions; no rebuild or second authority. |
| Single physical count, shared budgets vs process cache, minimal approval/copy provenance, protected local notices | Normative contracts above; owner boundaries S2-03A/B, S2-01/02/04A/C/05 and S3-03 stay explicit. |
| Three authority layers, no user install/MCP/tool/network expansion, all writes/backgrounds under same boundary | Preserved in authority and guardrail contracts. No new policy platform. |
| Current credential recheck, output redaction, result binding, active-origin isolation, normal delete and snapshot limits | Existing owner requirements remain release conditions; S2-06 actual-node checks supplement them, never waive them or claim their runtime proof. |
| Formal account password/recovery/minimal soft-delete, HTTPS before opening | Future separate opening conditions; no current Identity/Direct Mail/deployment implementation. |
| All other packages' visual/UI/telemetry/market/governance features and 17-package ordering | Context/non-goal only; no normative implementation expansion. Local UI modularity applies if later consumers touch browser calls; retain current session surface with additive DTO adapter, no new UI or React claim. |
| External framework/product reference links | Upstream rationale; no new dependency/version choice, web research or framework upgrade required by this minimum design. |

## Architecture and delivery handoff

Architecture must freeze central vs node write authority first, then cross-cutting identity/topology/security, runtime dispatch and feature interfaces. This SPEC selects a minimum logical SQLite/projection/readback contract now; architecture must resolve incompatible low-level details before implementation rather than silently defer every storage choice. A change to auth, ownership, persistence or dispatch security requires a new/amended Accepted ADR; this run creates or marks none Accepted. Existing ADR-0035/0036/0038/0061 inheritance remains.

S2-06 may be the first step2 package: it defines capacity interfaces, S2-03A later supplies actual measurement. No implementation cycle or automatic registration is implied. Formal production initialization is separate and cannot reuse test secrets or transfer test accounts/projects. Do not silently broaden same-host source/test evidence into deployment authority.

There is no unresolved product question blocking architecture. The recorded assumption permits signature/order refinement only while preserving these minimum contracts. A real authority contradiction or incompatible API change must be surfaced before implementation; it cannot weaken an FR/AC.

## Honest completion boundary

This run authors SPEC and four normative companions and performs the native author's coherence/preservation sweep. No BMAD reviewer, independent self-review, story breakdown, VDD, Quick Dev, Acceptance, schema/auth/runtime code change or deployment runs. Native publication/typed selection proves package transport, not scenario runtime success.

No Windows Runner, ACL, real process coordination, Godot/runtime or cross-host scenario was executed here. Linux static reads and contract authoring cannot substitute for Windows isolation or later authenticated second-host tests. Future implementation evidence must name exact HEAD/diff, actual consumer paths, raw results and unresolved limits; failures stay append-only. Independent external A/B SPEC review is a later coordinator-owned stage.
