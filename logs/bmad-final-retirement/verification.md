# Final launcher retirement and PR handoff

Base preserved: fbd94e5145442cfb9490057252f08aaebd9fe855.
Code commit: 0f2c9043a4c120d9533241531fc4528eea660438.
Independent Web Work only; no user PC or configured Codex cloud changes.

All 178 original inventory candidates are now untracked (129 source-proven distributions, 6 retired Stock Quick Dev, 30 game compatibility files, 13 launcher-only patches). The final 13 local files and recovery copies remain; SHA-256 bindings are in launcher-retirement.json. Recovery payloads are intentionally not committed. No frozen history, Phase registrations, native source, wrapper code or existing tests were changed in this final step.

Official future installations must remain unmodified. The repository does not reapply python3-to-py substitutions. Environment dependencies must satisfy upstream requirements; the installer-only Windows launcher example is not a native-file patch. Other Skills require their official installations; the scoped installer supplies only SPEC/Architecture and four locked runtime files. Precise ignores cover audited packages, not every possible future package name.

Validation command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 UV_OFFLINE=1 /workspace/scratch/6e089e29b8e4/bmad-test-venv/bin/python -B -m pytest -q scripts/toolchain/bmad_native/test_preflight.py .agents/skills/jimuyun-spec/scripts/tests .agents/skills/jimuyun-architecture/scripts/tests .agents/skills/bmad-architecture/scripts/tests scripts/toolchain/canonical_evidence/tests -k 'not test_acceptance_and_bootstrap_use_the_shared_canonical_bytes'
```

Result: 96 passed, 1 deselected in 14.49s. The existing Acceptance/Bootstrap integration case remains excluded because its Codex model configuration is unavailable. This is not product Acceptance. Tests cover both wrappers, missing/old/newer/tampered/extra native files, runtime dependencies, no-side-effect rejection, canonical/VDD contracts and reviewer lifecycle constraints.

Fresh local shared-object sparse clone at the code commit: all 178 inventory paths absent before installation; both wrappers reject missing native installation without filesystem changes; documented explicit installation from official 6.12.4 source succeeds; both wrapper prepare calls succeed; complete native inventories/hashes verify in the project and both private native invocation directories; git status stays clean. See clean-clone.json. Initial sparse setup warned about one unavailable out-of-scope .claude README object from the partial source clone; this was not a full network checkout. No ignored installation was copied from the working checkout.

No native Windows execution, full VDD/Acceptance/GDS suite or long semantic reviewer rerun occurred. Existing earlier native semantic evidence remains immutable. No tests were removed to manufacture success.

Known impacts for the Draft PR:
- Old game-design-master registration and GDD outline prompts still refer to the retired designer alias; old game capabilities are temporarily unavailable in fresh clones pending the authorized future sandbox rebuild. Service registration/gates were not refactored.
- Existing GDS installation/mirror/alias assertions remain and cannot pass without their former resources. No waiver or green claim is made.
- Stock bmad-quick-dev is retired; independent quick-dev-tdd-adapter and VDD remain. No routing migration into bmad-build occurred.
- --replace-native backs up/replaces the whole shared _bmad/scripts directory, restoring only four pinned files. Other helpers are not restored automatically. This risk is disclosed, not expanded into an unrelated fix.
- Project installation and global CLI are different. Wrappers support exactly 6.12.4, never BMAD7 or a silent fallback.

The final pre-push main lookup remained bf78bb43c5583571eab9ec4001fb3c3a913c0708; no remote branch or same-head PR existed at initial check. Publication is authorized for this branch as a Draft PR only. Main remains unchanged until merge, which is not authorized. CI and final main audit are reported separately after publication.
