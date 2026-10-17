# Direct Windows binding repair

Base: `080005d24ebae015425a0e61e9f9e89f1366d80f` on
`fix/08-05-real-skill-replay`. The supplied Windows verification and all older
execution evidence remain unchanged in the parent tree.

This is direct repair evidence. It does not publish `acceptance-passed`, replace
Q7/Q8, approve C3, or execute VDD, Quick Dev, Acceptance or a live backend.

## Reproduced causes and repairs

1. Windows Path sorting case-folded owner names, while Git enumerated exact
   case-sensitive paths. Git's quoted non-ASCII output was also mistaken for a
   different owner path. Membership now compares exact path sets read with
   NUL delimiters; identity manifests use literal UTF-8 POSIX path ordering.
   Actual additions, removals, case-only renames and changed dependency bytes
   still fail the independent Trust Approval gate.
2. `git archive` applied checkout/EOL settings to Prior Route bytes. A fresh
   clone could use different autocrlf settings and change the semantic verdict
   despite identical pinned candidate inputs. Reconstruction now reads regular
   immutable Git blobs in bounded batches, without archive conversions.
   Fresh-child semantic verdict, coverage, target identity and snapshot checks
   remain exact. Native stdout/stderr bytes are not normalized.
3. Positive CER controls still expected old label-only v2 Matrix inputs to
   succeed. They now use real v3 Stable/Candidate execution. Duplicate actual
   fixture bytes are checked before execution and name every conflicting case.
   An unexecuted control is never reported as passed. Frozen historical v2
   Matrix files remain unchanged and non-promotable.
4. Target refusals now have structured unsuccessful JSON; obsolete empty-output
   assertions are aligned with that contract. A rename test reads actual path
   and byte bindings rather than calling the removed parent-only witness helper.
5. A real S13 positive integration hit its old 60-second harness deadline.
   Parent lifecycle checks plus fresh-child replay now have a 180-second test
   integration deadline. Production child/Matrix budgets remain 60 seconds and
   8 MiB. No timeout is reclassified as success.

All modified CER assertion marker multisets are preserved, as checked against
the base commit in `selector-identity-final.json`. Validator package, capability,
source declaration, trust baseline, historical plans and Q7/Q8 are unchanged.

## Direct validation

Environment: Linux, Python 3.12.14, pytest 9.1.1. This is not a Windows pass.

- Initial Windows transport RED: six tests, one pass, two failures, three errors.
  The passing case-only rename control confirmed the real C3 boundary.
- Duplicate-byte Matrix RED: one genuine failure with incomplete attribution.
- Existing and added unittest regressions: **32 passed** (25 existing, 7 added).
- Targeted pytest: **30 passed**, plus **2 subtests passed**, zero failures,
  errors or skips. This batch preceded the harness-deadline adjustment.
- Final S13 module: **17 passed**, zero failures, errors or skips, after that
  adjustment. Two tests overlap the targeted batch; counts are not added as
  distinct coverage. Existing custom-marker warnings are retained in raw output.
- Native final repository fresh replay: see `repository-final-validation.json`
  and the lossless `repository-final-stdout.txt.gz`. It records the source hashes,
  command, process outcome and identity comparisons; it grants no authority.

`pytest-initial-*` records an interrupted baseline diagnostic, not a completed
suite. It was stopped without production edits during that attempt after the
complete supplied Windows evidence and bounded fault reproductions were available.
`integration-deadline-red.*` preserves the subsequent real harness timeout.
The intermediate native fresh receipt is retained separately and explicitly
marked as preceding final Matrix/test/ADR edits. No attempt is overwritten or
counted as a final full-suite pass.

## Local Windows re-verification

Synchronize this branch and confirm a clean working tree. Preserve all original
logs. Create a new timestamped evidence directory and record HEAD before/after,
commands, exit codes, native stdout/stderr, JUnit and a summary. Do not repair
code concurrently with the verification.

First run the regression group:

```powershell
python -B -m unittest discover -s scripts/sc/tests -p "test_skill_replay_*regressions.py" -v
```

Then repeat the original pytest scope; use the new evidence directory for JUnit:

```powershell
python -B -m pytest -q scripts/sc/tests/test_skill_package_replay.py scripts/sc/tests/test_skill_package_replay_source_identity.py scripts/sc/tests/tc_d1_cer --junitxml=<new-evidence-directory>/junit.xml
```

Run that complete Windows scope with zero skips or platform exclusions. The
explicit Windows-platform assertion is retained; it was not disguised as a
Linux pass. This repair's online checks are bounded, not a full CER-suite run.

A successful local run provides current direct validation evidence. The
Acceptance lifecycle owner must still assess current snapshot freshness and
all remaining eligibility conditions. Do not reuse an old Q8 or a historical
pass as approval for changed source. C3 remains OPEN for genuine alternative
validator approval, scope approval and Consumer exceptions; unchanged existing
validator membership does not require a new approval merely for enumeration or
Git transport differences.
