# Execution prerequisites

The continuation uses Linux, Python 3.12.14, pytest 8.4.2 and jsonschema 4.26.0.
python.json records actual installed versions. S19 runs the real jsonschema CLI.
PowerShell 7.6.6 was downloaded from the official GitHub release, checked
against its published SHA-256 and executed successfully for its version probe.
powershell.json and native version stdout/stderr retain those observations.
The published hashes are archived without newline conversion. The real host
runs the unchanged production PowerShell verifier on isolated CER fixtures.

The initial partial clone required immutable historical blob hydration and
materialization of the 08-01 receipt inputs. Earlier attempts retain their
native diagnostics and preparation output under their original new directories.
No historical Git bytes were normalized. A clone-local exact-path attribute
corrected a spurious mixed-EOL dirty status after byte equality with the Git
blob was established; checkout-byte-preservation.json records that comparison.
No tracked artifact or index bytes were changed by that correction.

FastCtx was unavailable, so repository-local inspection and native execution
were used. These are execution prerequisites, not trust inputs. C3 remains
OPEN and authorizes=[]; this directory grants no Acceptance authority.
