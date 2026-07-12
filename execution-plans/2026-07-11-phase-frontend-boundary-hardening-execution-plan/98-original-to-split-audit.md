# Original-To-Split Audit

## Source

The pre-split top-level plan was approximately 833 lines and contained 19 major sections.

## Mapping

| Original content | Split owner |
| --- | --- |
| Authority/Gates/upstream boundary | top-level, 00, 01 |
| Work package governance/owners | 01, 08 |
| Permit trust/schema/lifecycle/factory | 02 |
| Profiles/Preflight/wrapper/containment | 03 |
| Work Policy/lease/journal/acceptance | 04 |
| React `/ui-v2`/auth/toolchain/contracts/ledger/rollback | 05 |
| Correlation/Endpoint/Data/Workflow/SemVer | 06 |
| Retention/telemetry/performance | 07 |
| Recommended order and phase exits | 08 |
| Risk/DoD/glossary | 09 |

## Post-Split Additions

Second-pass and adversarial-review additions are tracked in `97-post-split-requirements-ledger.md`, including strict upstream BH-HANDOFF, Postflight source/snapshot/host manifest binding, remote isolated signing, trusted Test/Acceptance Attestation, Platform/Hosted containment, Acceptance/Postflight-long fenced lease, complete recovery states, DB handoff/expand-contract/online migration, root key ceremony, Authority DR/SLO/revocation, tool broker IPC, equal-assurance Platform Change Origin Gate, handoff-projected React surfaces, session/bootstrap/proxy/browser policy, npm/release isolation, encrypted quarantine/evidence, supervisor-derived side effects, architecture ratchet, performance fixtures and cross-plan overlap validation.

## Normalization

- The top-level file retains only recovery metadata, authority, Gate summary, book routing, global order and global completion.
- Detailed normative text belongs in exactly one owner book.
- Summaries may link but cannot restate full contract.

## Audit Result

All original requirement families map to at least one owner book. Coverage is finalized by `99-source-coverage.md` and enforced by the split validator.
