# Three V3 draft test-binding corrections

Approval: Sentinel_f0f9db4aab6081919a55b1dd2f5a0aad (2026-10-25 03:04 UTC).
This is a corrected author-draft copy, not a frozen contract, native accepted result, execution permission or receipt.

Original: logs/vdd-scoped-compile-20261024-r3/authoring/v3-caller-candidates.json
Original SHA256: 49da496937898dfdceb01f96f62b94a9da684a7fe6750bd5b62678e4d5fd8965
Corrected copy: v3-caller-candidates.corrected.json
Corrected SHA256: 47cbf5528d6b85617d9198f0f9e4b954fe3a759935419dabb17ff6e2bfd7ed8e

## Reviewed correction scope

The existing report and current AST confirm each assertion decorates both complementary functions below. The previous selector named the specialized function and omitted the original broader function. No test source or oracle was changed.

| Obligation | Assertion | Specialized function retained | Original function added |
| --- | --- | --- | --- |
| `O-8223FCF6C8EC` | `ASSERT_1B2DEF4F4ED8` | `test_planning_attempt_deadline` | `test_contract_1b2def4f4ed8` |
| `O-CDC5AF544B86` | `ASSERT_550968C7B8C5` | `test_planning_closed_episode_does_not_retry` | `test_contract_550968c7b8c5` |
| `O-07E8E988B1EA` | `ASSERT_1907855D27FB` | `test_planning_request_structure` | `test_contract_1907855d27fb` |

For each of the three contracts only:

- Append its own missing function to the existing validation command's OR-only -k expression:195 terms become196, with all existing terms and order retained.
- Include both node selectors in selector_intent, retaining the complete original denial/proof restrictions.
- Add test_functions to the author metadata, retaining the original single test_function hint and all other metadata.

The nine semantic delta paths are recorded in binding-delta.json. binding-only.diff is the complete textual difference. Acceptance/source refs/given/when/then/oracle/assertion IDs, failure family/ID/outcome, owners, write sets, snapshots and all unrelated fields are unchanged. Root status and authorizes=[] are unchanged. All other302 contract objects and binding notes compare equal. The original305-row file remains byte-identical.

## Checks actually performed

- AST-only marker-to-function inspection:each marker binds exactly the two recorded functions.
- Static -k function-name matching:each edit adds exactly its intended original function, retains the specialized function and all previously selected function names. No test module import or collection was performed; dynamic/parametrized case counts are not claimed.
- Current native deterministic group JSON schema, raw source-reference equality, inline projection, schema/domain/execution findings and current-path refresh check:3/3 compatible, no findings and no refresh required.
- The original input/draft identities match the prior inspection. Targeted source/test/Skill/repair files are unchanged; hashes are in validation-results.json.
- Offline audit/profile guards recorded0 forbidden process/network/workflow/write attempts. Validation elapsed 0.447 seconds.

Unchanged302 bodies reuse the prior offline validation; no full305 validation or implementation suite was repeated. This check validates selector structure and current file ownership, not the substantive runtime coverage or success of any test.

## Reuse and real-request limits

The original common test command is repeated by197 contracts (the other test surface has108). To honor the approved preservation of302 contracts, this copy updates only the three affected rows. Thus distinct command sets increase from2 to5:194 unchanged common commands,108 unchanged guard commands, and three distinct extended commands. Do not assume exact-argv execution receipts can be shared across these variants. No execution cache hit was claimed or manufactured.

All305 remain author drafts requiring genuine future request binding. The extra test_binding_intents metadata is not part of the native group wire format. A future genuine request must select the exact requested obligation subset, wrap only obligation_contracts, bind the real current source/domain identity and pass the native validators. This step invented no request or receipt and wrote no accepted state/cache. V4, publication, runtime scenario coverage and current Quick Dev authority remain unverified. The existing scope-reconciliation-before-probe flags are retained.

No pytest collection/execution, real compilation, r3 recovery, model, BMAD skill/reviewer, A/B, push, PR or CI operation ran. Code, Skills, original inputs/contracts and historical evidence were not modified. This approved step is complete and stopped; no next workflow was started.
