# Portable CER fixture repair

Base source: `de6e6a4b0427bc53a8dd9d03b528be075ce0e3d5`.
Owner: Accepted ADR-0058. This is a direct toolchain repair.

The original 340-node scope completed at that source: 36 unittest passes,
333 pytest passes and seven failures, real JUnit, no skips or timeout,
exact original node coverage and stable source/HEAD. The full failed result is
`../observable-verification-20261007T073516Z-52daddd9/summary.json`.

S14/S15/S18 now use standard temporary directories. S14 resolves powershell
or pwsh and still runs the unchanged production base-clean verifier. Every
original frozen-byte, validator and membership control remains. S26 checks the
actual native platform; Windows still requires win32. No platform is spoofed.
No production validator, capability, budget, selector or assertion ID changed.

The two earlier prerequisite-incomplete attempts are preserved separately.
Their operator-interruption notes are observations, not native suite results;
no terminal pytest/JUnit is fabricated for them. Preparation includes real
jsonschema and PowerShell runtimes, immutable Git blobs and historical receipt
inputs. Lossless archives record the original raw identities.

Targeted validation and fixed-new-commit 340-node validation are next steps
at this repair checkpoint. Their later outputs must be new evidence directories.

```powershell
py -3 -u -B scripts/sc/verify_skill_replay.py --scope-file logs/08-05-real-skill-replay/continuation-20261007/targeted-scope.json --expected-count 7
py -3 -u -B scripts/sc/verify_skill_replay.py --expected-count 340
```

C3 stays OPEN; Acceptance remains blocked. authorizes=[]; no VDD, Quick Dev,
formal Acceptance or live backend was invoked. Linux validation does not
replace native local Windows verification. Old Q7/Q8 and Windows failures stay
unchanged. A later README records completed validation without rewriting this
repair checkpoint or native evidence.
