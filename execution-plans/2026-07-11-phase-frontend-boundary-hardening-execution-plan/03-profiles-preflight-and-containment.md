# Profiles, Preflight, And Containment

## Public Policy Kernel

Common fields:

- identity/scope: profile, actor, task/route/account/project/run
- mode: read-only or workspace-write
- paths: readAllowed, writeAllowed, writeProtected, fullyForbidden
- capabilities: provider network, tool network, child process, environment, git, external tools
- authority inputs, tests, acceptance, rollback
- time, billing, file/byte limits, evidence policy

## Platform Development Profile

- After BH-HANDOFF only, create a task-scoped detached copy or independent clone outside the primary worktree. A linked Git worktree sharing object storage, config or hooks is prohibited for the restricted identity. Codex never receives write access to the primary repository worktree, shared Git state, upstream handoff evidence or live `logs/phase-a-innernet` paths.
- The restricted Platform identity can write only the isolated task workspace and per-run TEMP/HOME/CODEX_HOME. A trusted applier acquires a repository/path fencing lock, validates the Permit, active handoff epoch, base/upstream path manifest, dirty-overlap, SourceChangeManifest and reviewed diff, atomically applies allowed paths, then rechecks fencing/baseline and final hashes before release.
- Reads AGENTS, standards, ADR, execution plan, recovery, dirty tree.
- Protected paths require authorization and Permit.
- Live DB, live hosted workspaces, secret store, signed attestation store, and history evidence are never writable.
- Git defaults to read-only; push/tag/history rewrite require explicit task authority.
- Declares Red/Green/Refactor, smoke, review pipeline, rollback, and change-matrix obligations.
- Binds the exact UpstreamHandoffActiveRegistry handoff/epoch/StateEvent/rowVersion and immutable manifest hash; refuses to start when the final upstream commit is not an ancestor, upstream-owned path hashes drift, an upstream-permitted capability deferral is expired/due, or a requested path belongs to an unfinished/deferral owner.

### Enforcement Scope

- All supported Platform Codex surfaces must call the canonical launcher/preflight provider.
- Direct CLI/IDE sessions that bypass it are unsupported and cannot claim compliant Codex evidence or produce merge-eligible Platform changes.
- After BH-HANDOFF, every diff under the Phase service scope defined by repository AGENTS uses the same canonical Preflight/Postflight path regardless of claimed human/Codex author; `actorType` changes audit attribution, not enforcement. There is no lower-assurance human-only bypass for Phase service diffs.
- A Phase service change cannot bypass the Gate by omitting a Codex declaration, relabeling the author, direct pushing or using an alternate PR workflow. Branch protection requires the complete-diff attestation and test policy for all actor types.
- Supported IDE/GUI integrations must obtain a Permit before enabling file-write tools. An integration without the canonical provider is read-only.
- Human editors may use a protected launcher/UI, but it produces the same scope, base, path, test and Postflight evidence; only actor attribution differs.

## Hosted Project Profile

- One account/project/route/sub-operation/run per job.
- Focused workspace is the only writable root.
- Reads only approved route authority inputs.
- Phase source, runtime, scripts, git metadata, live DB, other accounts, and host secrets are fully forbidden unless a specific read-only tool broker input is declared.
- Source freshness, route completion, and acceptance remain server authority.

## Deterministic Preflight

Before Codex gains write access:

- verify BH-HANDOFF and exact ActiveRegistry handoffId/handoffEpoch/StateEvent hash/rowVersion plus immutable UpstreamHandoffManifest hash
- verify current Permit Authority restoreEpoch and reject a Preflight, Permit or attestation bound to an older epoch
- validate identity, Profile, Gate, Permit authority health, build version
- validate required recovery/authority inputs and upstream runtime preflight result
- canonicalize paths and reject reparse/junction escape
- reject Windows alias/escape forms: ADS, hard links outside scope, UNC/device/extended-device paths, 8.3 aliases, reserved names, trailing dot/space aliases, case collisions, cross-volume targets and path-object replacement after validation
- check dirty overlap and project mutation lease availability
- check protected authorization and actual approvers
- validate tests, rollback, capability, time, billing, and evidence plan
- validate restricted token/tool broker/network controls

Codex Work Declaration is untrusted comprehension evidence only. It lists objective, sources read, expected paths, capabilities, tests, rollback, risks, assumptions, and stop-loss. It never grants authority.

## Canonical Platform Launcher

```powershell
py -3 scripts/python/dev_cli.py codex-preflight --profile platform-development --task-id <id> --plan <path>
```

The launcher:

- talks to protected Permit authority
- produces opaque permitId and asymmetric signed PreflightAttestation
- launches Codex with policy-scoped environment
- invokes the protected Postflight supervisor after work; the supervisor revalidates handoffEpoch/restoreEpoch, computes actual source/host manifest, test and evidence hashes and obtains the asymmetric PostflightAttestation from the remote Authority
- consumes Permit only after Postflight state is durably recorded

Supported IDE/GUI surfaces must integrate the same preflight provider. Until integrated, they are not supported for protected platform changes.

## Provider Network Versus Tool Network

Hosted Codex requires two execution tiers:

1. Networked controller:
   - Codex CLI only.
   - Egress only through configured provider proxy/allowlist.
   - No general shell/tool credentials.
2. No-network worker/tool broker:
   - Starts allowed rg/Python/Godot/dotnet/test commands under a second restricted token.
   - Does not inherit provider credential, proxy secret, browser token, or host environment.
   - Network denied by firewall/token policy.

### Tool Broker Protocol

Tool broker requests use authenticated local IPC bound to permitId/runId and include:

- tool ID and pinned executable canonical path/hash/version
- exact arguments after schema validation
- canonical working directory
- read/write path grants
- environment allowlist
- stdin/stdout/stderr byte limits
- total/inactivity timeout
- cancellation token and process-tree identity
- request nonce, monotonic sequence number, protocol version and request/response MAC or authenticated-channel binding

Rules:

- Executable resolution through mutable PATH is prohibited for hosted jobs.
- Python, PowerShell and other general interpreters require script/content hash plus argument/path policy; executable allowlisting alone is insufficient.
- Controller cannot directly spawn shell tools; only broker creates worker processes.
- Controller filesystem is read-only except its private control/output channel; all project mutation is performed by broker workers under Work Policy.
- Broker output is bounded and sanitized before prompt reinjection or evidence persistence.
- IPC replay, wrong permit/run, argument injection, path escape, oversized output and timeout tests are required.
- Windows deployment uses a dedicated Named Pipe or equivalent protected local channel whose ACL admits only the controller identity and broker service identity. The controller verifies broker server identity; the broker verifies the caller token/SID and Permit-bound challenge before accepting a request.
- A request nonce is single-use, sequence numbers are monotonic per run, expired requests are rejected, and broker restart invalidates unfinished channel sessions.
- Broker executable identity, publisher/hash and protocol version are pinned by protected host configuration; reviewed repository code cannot substitute the broker endpoint.

Provider DNS, redirects, IP literals, TLS validation, proxy bypass, IPv4/IPv6, and child-process inheritance require negative tests.

## Containment Feasibility Spike

After BH-HANDOFF and before any Platform or Hosted workspace-write enforcement rollout, prove on the actual Windows host:

- restricted token or dedicated restricted identity
- focused workspace writable ACL only
- Phase repo/runtime/DB/other workspace access denied
- Job Object terminates full process tree
- per-run TEMP/HOME/CODEX_HOME
- environment allowlist
- controller/provider egress and tool/no-network separation
- approved executable broker
- the same or stronger restricted-token, no-network, Job Object, TEMP/HOME, executable and path boundary for every Acceptance runner that may import, build, test, preview or execute generated project content
- Platform primary-worktree/live-log/live-workspace/Git-metadata denial plus trusted reviewed-diff apply from isolated task workspace

### Trusted Acceptance Runner Boundary

- Acceptance executes untrusted generated content under a dedicated restricted identity, never the Phase Web, Permit Authority, signer, journal or administrator identity.
- It has no provider/general network, no host secret, no Phase source/runtime/DB/other-workspace access, and no write access to the formal workspace except through the Mutation transaction.
- It reads a lease-bound immutable snapshot or restricted focused workspace and writes only declared per-run output directories.
- Its input HostEffectiveManifest and SourceChangeManifest hashes must exactly equal the committed candidate recorded by Mutation; testing a different focused workspace, stale snapshot or regenerated candidate fails closed.
- Godot import, C# build, package, preview and diagnostic subprocesses remain inside one Job Object and are terminated on timeout, revoke, cancellation or service restart.
- The protected Acceptance supervisor submits immutable observations to the remote Attestation Authority defined by book 02; neither the runner nor supervisor stores a private attestation key. Assistant text and worker-authored reports are diagnostics only.

If the spike cannot enforce the applicable properties, Platform and Hosted workspace-write remain disabled. Full per-project Windows accounts may be later, but an equivalent tested boundary is mandatory now.

## Acceptance

### Relocated 7-12 R4 Review Envelope Consumption

This plan receives the Phase-facing portion formerly named R4 in the 7-12
review-gate plan. The receiving behavior is an adapter over the repository
Bootstrap owner, not a second review gateway.

- BH-SF2 binds account, project, workspace, route action, current authority
  hash, current live acceptance blocker, and the fresh
  `bootstrap-finalized-run-validation.v3` envelope before projecting any review
  state into a Phase job.
- Missing, stale, non-finalized, cross-account, cross-project, cross-workspace,
  or route-mismatched review evidence fails the review projection closed. It
  cannot be converted into clean, Permit-ready, or route-success state.
- `ILlmRouteEngine`, `CodexHostedProcessCommandFactory`, and
  `scripts/sc/_llm_backend.py::run_llm_exec` remain the shared Phase execution
  entrypoints. The adapter does not construct a second model invocation,
  reviewer lifecycle, finding schema, cost policy, or lineage store.
- Browser-safe output exposes only bounded status and account-safe evidence
  references. It never exposes host paths, prompts, another project's finding
  or disposition memory, or Bootstrap operator details.

This relocation implements the review-specific portion of existing `PBR-026`.
It does not create a new PBR family and does not activate before BH-SF2 entry
and protected-path authorization are satisfied.

- All supported Platform Codex jobs perform preflight before work.
- Hosted tool child cannot access provider egress or host secret.
- Controller cannot use arbitrary child tools outside broker.
- Controller cannot directly mutate project files outside broker-authorized operations.
- Every supported Platform Codex write surface, including IDE/GUI, requires canonical Preflight/Postflight evidence for its full declared diff.
- Platform Codex cannot modify the primary worktree, upstream-owned dirty paths, shared Git metadata, live Phase data/workspaces or protected evidence; trusted apply rejects base/dirty/handoff drift.
- Broker validates executable hash, arguments, paths, environment, output limits and permit/run binding.
- Outside-write, secret-read, network-bypass, orphan-process, cancellation, and timeout tests pass.
- Named Pipe ACL/identity/challenge/replay/restart tests and Windows ADS/hard-link/device/alias/TOCTOU path tests pass.
- Acceptance runner cannot access network, secrets, Phase source/DB or other workspaces and cannot leave an orphan process.
- Missing authority, approval, tests, rollback, trust-store health, or containment proof blocks Permit.
