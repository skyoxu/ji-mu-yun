# VDD and Quick Dev regression admission

Authority: ADR-0041. This check approves tested tool content, never a plan,
production write, RED, Q7/Q8 result, review or Acceptance. Both public entries
check it before supervision or task work. S2-06 remains a separate paused task.

## Maintainer commands

From the repository root, use the same Python/pytest environment for the entire
candidate. The following commands use repository-relative paths on Windows and
Linux (`py -3 -B` may replace `python -B` on Windows):

```text
python -B scripts/skill_baseline.py candidate --out logs/baseline-v1/candidate.json
python -B scripts/skill_baseline.py test --candidate logs/baseline-v1/candidate.json --out logs/baseline-v1/regression --bootstrap --defer-admission
# Complete the owner-required review of this exact candidate and evidence.
python -B scripts/skill_baseline.py admit --measurement logs/baseline-v1/regression/measurement.json
python -B scripts/skill_baseline.py check
```

`--defer-admission` retains a complete measurement without activating anything.
The later `admit` command rechecks unchanged content, predecessor, mandatory
case reports/nonces/hashes, successful unit exits and historical coverage before
atomic activation. Missing or modified measurements do not authorize startup.
It does not invent or substitute for independent review authority.

Only the first complete baseline may use `--bootstrap`. It requires both skills,
an empty admission store, and the historical optimization/source/test analysis.
There is no reset or force option. Once bootstrap state exists, deleting the
current pointer does not permit another bootstrap. Restore damaged records from
their byte-exact backup; do not manufacture a replacement approval.

For each later change, create a fresh candidate and run `test` without
`--bootstrap`. `--skill vdd` or `--skill quick-dev` selects one skill; a shared
dependency change invalidates every affected approval until each is tested.
For a bounded diagnosis, `test --diagnostic-target <one-declared-module>` runs
only that module through the same fixture-only channel and can never write an
admission. It cannot be combined with `--bootstrap`; do not call its success a
complete regression result.

Use a fresh output directory. Keep failed results and fix relevant inputs before
retrying. Matching retries share cumulative unit costs and two failures block
another unchanged attempt. Limits are 1800 seconds total and 600 seconds without
genuine output per mandatory module, not per full round.

### One approved disk-resource recovery batch

Two disk interruptions are retained failures, not permission to reset a ledger.
After explicit owner approval and actual free space restoration to at least
512 MiB, `test --resource-recovery <logs/request.json> --defer-admission` may
measure one complete successor batch. It cannot be combined with bootstrap,
diagnosis or a partial Skill selection. The original 192/120 MiB preflight/run
floors and 1800/600 second cumulative unit budgets remain unchanged.

The request schema is `toolchain.skill-resource-recovery.v1`. It binds
`owner_confirmation` (`operation: one-disk-recovery-batch`, actual `message_id`),
the original candidate `path` and raw `sha256`, the successor's canonical
`candidate_sha256`, `output`, `platform`, `target`, original derived `unit_key`,
raw `ledger_sha256`, and exactly two distinct `failures`. Each failure binds its
native `directory` and raw hashes under `files` for `argv.json`, `request.json`,
`exit.json` and `stdout.log`. The native collector command, original candidate,
nonces and explicit `insufficient-disk-during-unit` exit must agree. A completed
case report, assertion failure, ordinary timeout, tampering or missing source
does not qualify. This is a trusted local maintainer record, not cryptographic
authentication against a malicious operator who can rewrite all local files.

The successor is necessary because the repaired runner is fingerprinted. Only
the runner, its permanent regression file, the explicitly approved compiler
watchdog and its exact regression file, this guide, ADR-0041 and the existing
capability registry may differ from the interrupted candidate; suite targets,
policy, platform and tools stay fixed. Old cases remain and substantive new
coverage is mandatory. Original costs and failure counts carry forward under
the **original** unit keys. An exclusive persistent claim allows only one full
batch, including each declared occurrence when both Skills require the stopped
target. Space is checked again at each recovered launch. Any further failure
stops that permit; a crash also consumes it. Do not delete or edit claims.

The output retains the request, original ledger bytes, unit raw results and a
completed recovery receipt. `admit` rechecks their binding in addition to every
ordinary measurement check. Neither recovery nor an owner confirmation grants
formal task execution, changes an oracle or converts old failures into GREEN.

After successful admission, ordinary commands remain unchanged:

```text
python -B scripts/vdd/compile_plan.py --requirements <input.md> --out-dir <plan> --profile standard
python -B scripts/quick_dev/run.py --plan <plan> --slice <slice> --profile standard
```

## Fingerprints and test coverage

`.agents/skill-baselines/policy.v1.json` declares mandatory modules and data/code
roots. The fingerprint uses sorted relative paths and actual file bytes. It
includes Skill instructions/references, execution code, contracts/schemas,
the runner/policy and conservative local Python import closure, including
parent package `__init__.py` files and their imports. Applicable repository
`conftest.py` and pytest configuration files are bound both to the content
fingerprint and test-suite identity; adding or changing them invalidates approval. It does not
sample timestamps, current Git HEAD, machine addresses, credentials, local
`.user.toml`/`.env` settings, run logs or admission records. Protocol constants
already in source (including historical Git pins) remain ordinary source bytes.
Tests have their own content/AST inventory and ordered suite fingerprint. Exact
Python/pytest versions are also bound to the measured admission; changing them
requires another complete measurement, without inventing a source-code change.
Unrelated unimported source modules are not automatically shared dependencies.
Every startup still recomputes the live dependency closure and content hashes.
Import-name resolution is deduplicated only inside that single computation;
there is no retained filesystem or timestamp cache. An admitted immutable suite
record plus identical test-source bytes and pinned tools avoids reparsing the
same test AST at ordinary startup. Full AST/source comparison remains mandatory
when creating, measuring and admitting a candidate. In the test-only channel,
the authenticated actual ancestor broker performs the live requested-Skill
fingerprint check. The child first verifies the existing channel's ancestry,
key and frozen candidate identity and sends its declared fingerprint to that
broker; it does not scan a stale ordinary approval or duplicate the broker's
live scan. The broker still checks current source bytes, exact entry bytes and
fixture paths on every request, with no retained filesystem cache. Invalid
channels still cannot replace an ordinary valid content admission. Shared-
dependency changes still refuse the real child entry. Private
supervisor reentry also verifies admission; no environment skip flag is added.


The first baseline covers optimizations integrated through the actual 8-24 and
8-05 merge ancestry plus later main. The versioned `.agents/skill-baselines/bootstrap-history.v1.json` maps each
optimization family to required test nodes, records the fixed historical bounds
and hashes the retained source analyses under
`logs/toolchain-skill-baseline-20261029/`. Bootstrap refuses missing/changed
analyses and any family without mandatory executable coverage. The immutable
bootstrap record retains that mapping. This validates traceability, not the
semantic completeness of historical analysis. Legally replaced code is not restored.
The original Package B delivery corpus retains all 77 unmodified assertions
and runs against published commit `5197679049e709ea9d22212aacc6c09067b50ec1`.
Its exact old runtime-byte oracle is delivery-scoped, not a prohibition on later
authorized maintenance. The historical regression retains native child reports,
all 77 selected cases and all 231 successful phases. Historical replay never
counts as current-fingerprint behavior proof. All 39 functions without the old
native/child byte oracle also run unmodified on current source. The remaining
38 mixed or byte-only functions retain current instruction, dependency, scope
and source/atomic-binding checks in `test_current_toolchain_quality_contract.py`;
current native suites exercise reuse, RED refusal, real production refactor,
Q7/Q8 and delivered-input integrity separately. The per-case mapping in
`.agents/skill-baselines/package-b-current-coverage.v1.json` records the exact
original predicate, temporal reason and mandatory current witnesses; mapping
alone is not execution evidence or proof of semantic completeness. Full Git history
including the pinned commit and its original baseline is required. No Git
checkout/worktree switch or old-success receipt substitution is used.

Current package unit/fixture modules and declared shared-consumer modules are
mandatory. The Knowledge query module verifies the retained Windows ZIP against
its actual immutable run commit, not current changed runtime bytes. Passing that
archive reader on Linux proves archival integrity only; new current fingerprints
have no new Windows execution evidence. Normal query/permission, source-drift,
UTF-8, cancellation and subprocess tests still run against current code.
Each selected case must have successful setup/call/teardown, with no
skip, xfail/xpass, collection error, ambiguity, timeout or missing report. Tests
which deliberately exercise a failing child must themselves prove that rejection;
a skipped required outer case never counts as success.

Every later content fingerprint requires substantive test growth over its
approved predecessor. Static checks reject deleting existing test bodies,
weakening/replacing their assertions, and rename/copy/comment-only increments.
Declared pytest display `ids`/`id` and CER identity marks do not make an
otherwise copied case new; actual parameter inputs and assertions remain bound.
The supported enhancement form preserves an existing body and appends genuine
assertions, or adds a distinct behavioral case. A changed helper, complex
refactoring of a test, or arbitrary logical equivalence is not mechanically
proved by AST comparison. The maintainer must review oracle/fixture semantics;
passing tests and extra assertion syntax alone are not a semantic proof.
Bug repairs retain pre-fix failing process results and post-fix passing results.

## Candidate-only evaluation

An unadmitted candidate can run only through the regression runner. A temporary
authenticated parent/child channel binds the frozen candidate, live OS-owned
runner ancestry and current disposable fixture root. An arbitrary environment
value or generic skip flag grants nothing. Candidate native commands cannot
target formal task output or production write paths outside that fixture.
Protected path options in this channel must use one exact `--flag value`
occurrence. Equals forms, abbreviations and duplicate protected path options
are rejected before native execution. This does not alter ordinary admitted
CLI syntax.
The channel is not a persistent service, an OS sandbox or protection against a
trusted maintainer deliberately rewriting the gate itself.

The runner reuses the existing structured pytest case observer, preserves raw argv,
output, JUnit and case reports, and verifies unchanged candidate bytes after the
whole required suite. It then writes immutable proof/record files and atomically
activates the pointer. Formal startup rechecks content, suite/runner identity,
proof integrity and predecessor/test-increment lineage. A failed test or a
measurement without all required results produces no admission. Baseline reports
use a distinct schema and do not replace native task execution/dependency proof.
The outer regression observer does not install a second dependency-read auditor
around task tests; the task execution collector remains unchanged.

Pytest removes only each successful case's own `tmp_path` using its supported
`tmp_path_retention_policy=failed` setting. Failed case fixtures and all outer
reports remain. A resource monitor stops the owned process tree before the disk
is exhausted; a resource stop is a failed unit, never a pass.

Only this runner's disposable test scratch may be removed after successful
collection; raw test reports remain. It never cleans another task, old evidence,
device configuration or a business workspace. Keep sufficient space before each
module. On interruption, preserve partial outputs and admission state; do not
reinterpret partial results as approval.

## Platform and trust limits

Admission is platform/Python-family scoped. Linux fixture/native Python tests do
not prove real Windows ACL, Job Object, Runner, process ownership or deployment.
Windows requires its own actual supported-platform execution before approval.
The registry is a single trusted-maintainer integrity mechanism, not external
PKI or an adversarial custody system. Private configuration is not published by
this mechanism. Nothing here authorizes GitHub push, PR, merge or deployment.

## Complete historical capability reconciliation

The first admitted candidate proves its recorded current regression, not by itself every historical optimization. The expanded [capability baseline](toolchain-skill-capability-baseline.md) starts at the first 8-05 seed, includes 8-24 and all reachable changes to the fixed main cutoff, and records explicit retirements, current owners and permanent witnesses. Its full commit ledger distinguishes incidental references from effective capability changes. Keep the original first-bootstrap history immutable; later corrected coverage and changed content use the existing successor/increment path, never a reset bootstrap.

The CH456 fresh CI harness now performs candidate, full guarded test, admission and check before normal metrics. A failed mandatory case exits before admission. The checked-in sequence is also exercised locally by the tiny real runner; that wiring evidence does not claim the Windows job or live model metrics were run. This reconciliation is reviewed in the current work session on the existing branch, not through independent A/B sessions.

## Portable publication regressions

Query regressions must not borrow a device's current Knowledge generation. The
fixture preparer uses immutable main Git objects, the unchanged registered
policy, and the existing native request/producer at a fresh pytest-owned root.
It performs the real evaluation and publication verification there. The real
repository's catalog, projection, index, device configuration and maintainer
request are neither read as fixture inputs nor published by the test. The
explicit preparer CLI is part of both content fingerprints; no copied policy,
forged current pointer or test-only publication bypass is used.

Historical V3 replay retains its original plan/snapshots and oracles, but runs
its real advice lookup in that isolated data fixture with the public source
files that Locator returns. Complete repair input identity is checked after
ordinary read-only admission and before querying; invalid input must not depend
on a running device publication to be rejected. Valid input continues through
the existing query, source, permission and behavior gates. This test setup is
not permission for BMAD or an agent to publish the actual repository Knowledge.
