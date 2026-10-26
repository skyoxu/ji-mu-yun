# Caller-session execution for repository Skills

Authority: ADR-0041. This route is explicitly selected for an online temporary
workspace or another trusted caller that has model reasoning and file tools but
no authenticated Codex CLI. Local Codex CLI and OpenAI API routes remain unchanged.
It is not a Phase runtime provider or a new review/acceptance authority.

## Start and select

From the repository root, with Python 3 available:

```text
python -B scripts/sc/host_session.py init --session logs/host-session-unique --caller chatgpt-work-mode
python -B scripts/workflow_host.py --session logs/host-session-unique vdd -- --requirements <source> --out-dir <plan> --profile self-hosted --resume-from first-failed-stage
python -B scripts/workflow_host.py --session logs/host-session-unique quick-dev -- --plan <plan> --slice <slice> --profile self-hosted
python -B scripts/workflow_host.py --session logs/host-session-unique acceptance -- run-coordinator --request <request> --out <result>
```

Use `py -3` instead of `python` on Windows if that is the installed launcher.
Use a fresh explicit session directory per caller; never auto-select a previous
session. The wrapper only selects `SC_LLM_BACKEND=host-session` and
`JIMUYUN_HOST_SESSION_DIR`, then invokes the same native entry with argv and
shell disabled. Native exit codes and all owner checks remain unchanged.
Invoking native commands without this explicit environment keeps local defaults.
Recommendation-only is still read-only; creating the session is a separate action.

## Complete actual worker requests

Run the native command in a supported background process so the caller can
service it; no nested model API or fake codex executable is needed.

1. `python -B scripts/sc/host_session.py pending --session <session>` discovers
   outstanding request IDs. Read the chosen complete `request.json`, including
   its exact prompt, repository root, requested mode and deadline.
2. Perform that worker task with the current caller's reasoning. Read only the
   requested sources and necessary current authority. For VDD read-only workers,
   return the specified JSON; do not edit source, caches or compiler evidence.
   In a V4 pass, recheck frozen sources against the candidate as a reviewer,
   independently of the author's intended answer. This is a distinct review
   task in the current caller, not a claim of a separate model/process reviewer.
3. For Quick Dev workspace-write requests, edit only the declared test or
   production write set for that stage. The existing worker snapshots and native
   gates check the delta. Never edit selectors/evidence to manufacture GREEN.
4. Save the actual response text to a temporary file. Compute `host_session.digest`
   of the exact request JSON (canonical UTF-8 JSON, sorted keys, compact separators).
   Submit with `host_session.py respond --session <session> --request-id <id>
   --request-sha256 <hash> --output-text-file <file>`.
5. The transport checks session/request identity, hash, deadline, nonempty output
   and `authorizes=[]`. The native consumer then validates schema and semantics;
   only it writes validated caches, process evidence and lifecycle output.

A response is model-authored input, not a trusted verdict or a fixture-cache
injection. The trace records `host-session` and the declared caller; it does not
claim an API model identifier, independent reviewer identity or Codex execution.
Never copy historical success JSON as the answer to a changed live request.

The transport is for a trusted repository maintainer/caller, not adversarial
sandbox isolation. Mode and prompt boundaries remain operating constraints;
Quick Dev additionally enforces its existing before/after write-set checks.
Do not run concurrent unrelated edits in the same workspace during those checks.
The transport does not change Phase credentials, auth, runtime or live workspaces.

## Timeouts, cancellation and recovery

VDD and Quick Dev public entries now default to independent-unit supervision:
1800 seconds total and 600 seconds without genuine progress. A VDD contract
batch before slice generation is a unit; Quick Dev execution/worker stages and
Q6 commands are units. The workflow round is recorded, not globally capped at
1800 seconds. Same-unit retries share the persistent cumulative allowance.
Existing explicit shorter descriptor/host limits still apply. Do not wrap these
entries in a historical aggregate timeout or use 600 as the host total when it
means inactivity. The supervisor terminates the owned native tree, retains
diagnostics and cannot create successful receipts. For an interactive task,
explicitly select a finite per-worker
host budget before launch, for example:

```text
python -B scripts/workflow_host.py --session <session> --host-timeout-seconds 1800 vdd -- --requirements <source> --out-dir <plan> --profile self-hosted
```

The host option accepts 1--3600 seconds. It replaces only the host transport's
per-worker budget and records the native budget, selected budget and selection
source in each request. It does not extend an outer compiler/process deadline,
a session lifetime or any local CLI/API timeout. The wrapper clears an inherited
`JIMUYUN_HOST_TIMEOUT_SECONDS`; only its explicit flag selects the override.
Advanced native invocation may explicitly set that environment variable together
with `SC_LLM_BACKEND=host-session`. No heartbeat or response can renew the budget.
A timeout returns 124; cancel
returns 130; malformed/unbound responses fail closed. To cancel one pending
request use `host_session.py cancel --session <session> --request-id <id>`.
Late/duplicate responses cannot be consumed. A killed parent is not resumed by
submitting old requests: restart the native command through its normal recovery
route, retain the old session for diagnostics, and service only the new request.
No response, timeout or cancellation grants readiness. Keep native failure history.

## Ownership by Skill

- VDD: `scripts/vdd/compile_plan.py` remains sole publisher. All V0--V7/V4
  checks apply. `host-session` changes the worker transport, not plan readiness.
- Quick Dev: Q2/Q4/Q6 use the caller for bounded authoring through the shared
  backend; Q1, controlled probes, RED/GREEN, Q7/Q8 remain real native checks.
  Missing test runtimes and the new-production first-use contract are still
  genuine blockers; an online transport does not solve them implicitly.
- Acceptance: ordinary coordination and its no-launch policy decision are
  deterministic and need neither a Codex executable nor Codex model configuration. The route invokes that same coordinator with current Q8,
  Knowledge/Skill-input and registered-action requirements. Optional Bootstrap
  or policy-gated complex recovery remains a separate explicitly selected route;
  this transport never silently activates it or overrides its capability policy.

Windows-only ACL/Godot/.NET requirements require their actual environment. Do
not report an online Linux test as Windows execution or Package A Acceptance.
