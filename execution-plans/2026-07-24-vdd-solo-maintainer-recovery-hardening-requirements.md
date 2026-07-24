# VDD Solo-Maintainer Recovery Hardening Requirements

- Status: approved for Quick Dev planning
- Date: 2026-07-24
- Target: repository routing plus `.agents/skills/vdd-execution-plan/**`
- Authority: explicit maintainer approval on 2026-07-24
- Delivery route: one requirements file implemented by BMAD Quick Dev; do not create a VDD plan directory

## 1. Problem

The solo-maintainer VDD simplification removed controls designed for distributed or adversarial writers. The resulting package is an appropriate baseline, but it still lacks a few low-cost recovery and validation behaviors found while comparing `origin/fixskill1`: explicit input routing, typed material clarification decisions, recoverable stale state, read-only legacy inspection, sanitized handling of sensitive resume data, and CI visibility.

These gaps shall be closed without rebuilding an append-only evidence system or coupling direct implementation back to full VDD planning.

## 2. Operating Model

- One trusted maintainer and one AI assistant own repository changes.
- Git remains the code and baseline authority.
- Clarification resume state is optional, single-writer, and used only when a real cross-session decision must survive.
- A single requirements Markdown file is a direct implementation input. It is not an implicit request to create or repair a complete VDD execution-plan directory.
- VDD directory creation or repair occurs only when the user explicitly requests that outcome.

## 3. Required Behavior

### VDD-REC-001: Input routing

Repository and Skill routing shall distinguish a single requirements Markdown file from an explicitly requested full VDD plan directory. Direct implementation of one requirements file shall not auto-create a VDD directory, lifecycle bundle, 95 report, or Bootstrap review run. The VDD package contract shall contain deterministic route cases, and mutation tests shall reject a changed route outcome.

### VDD-REC-002: Typed clarification decisions

New clarification resume state shall use a new schema version. Every decision shall retain `id`, `summary`, `material`, and `status`, and add:

- `kind`: exactly `fact_gap`, `user_decision`, or `authority_conflict`;
- `depends_on`: a list of decision IDs in the same state.

Decision IDs and dependencies shall be unique. Self-dependencies, missing dependencies, cycles, and unknown kinds shall fail validation. A decision shall not become `resolved` while one of its dependencies is unresolved. Classification shall not impose a minimum question count or confidence score.

### VDD-REC-003: Stale, invalidate, and reopen

Initializing an existing run with changed authority or target hashes shall return `stale` without changing the stored bytes. An explicit invalidate operation may move an active or closed current-schema state to `invalidated`; repeated invalidation is idempotent. An explicit reopen operation may act only on `invalidated`, must receive valid current authority and target hashes, resets stale decisions, and returns the same run to `active`. Invalidated state cannot be recorded or closed before reopening.

### VDD-REC-004: Read-only legacy inspection

Legacy clarification schema versions shall be inspectable only through a dedicated command that requires an expected SHA-256 of the exact input bytes. A match returns minimal non-sensitive metadata; a mismatch fails closed. Inspection shall preserve the file byte-for-byte. Current mutating commands shall reject legacy state and shall never migrate or rewrite it implicitly.

### VDD-REC-005: Lightweight sensitive quarantine

Sensitive keys or credential-shaped values in a decision payload or current-schema state shall never be echoed or retained in decisions. For a current run, detection shall replace the state only after project-root and declared evidence-root containment are verified, using a sanitized terminal `quarantined` envelope that contains a rule ID, payload SHA-256, and timestamp but no original value. A quarantined run cannot resume, record, close, invalidate, or reopen. Legacy inspection remains byte-preserving; if legacy content is sensitive, fail with a digest-only result and do not mutate it.

### VDD-REC-006: Windows CI gate

After Python setup, Windows CI shall run both commands as hard gates and stop on either non-zero exit:

```powershell
py -3 -B .agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py --skill-root .agents/skills/vdd-execution-plan
py -3 -B -m unittest discover -s .agents/skills/vdd-execution-plan/scripts/tests -p "test_*.py" -v
```

No signing key, Bootstrap authorization, or remote service shall be needed.

### VDD-REC-007: Remove contradictory inactive fixtures

Unused generic fixtures that still encode mandatory five-question, numeric-confidence, headless-exit, or second-write-confirmation rules shall be removed or replaced with minimal legacy read-only fixtures. The package must not present those historical controls as current defaults.

## 4. Compatibility And Safety

- Existing `vdd.clarification-resume.v2` and older state remain readable only through the legacy inspection path.
- New state shall not silently add required fields to v2.
- Before any state rewrite, the caller project root, stored project root, declared evidence root, and state path must agree and remain contained.
- Invalid JSON, unknown schemas, invalid identity fields, or ambiguous path ownership fail without mutation.
- Existing lifecycle states and ownership remain unchanged.
- No mutable live execution-plan directory or dated plan identifier may become a VDD package dependency.

## 5. Explicit Exclusions

Do not introduce:

- append-only event or hash chains;
- snapshots, reducers, generations, or committed pointers;
- target registries, cross-process locks, leases, or concurrency stress protocols;
- signed or trusted approvals, reviewer identity, or producer/verifier separation;
- source-proof closure, promotion transactions, or Bootstrap authorization closure;
- mandatory question counts, numeric confidence gates, or repeated write confirmation;
- changes to Quick Dev, Bootstrap Review, implementation acceptance, archive Skills, or historical 7-15 evidence.

## 6. Acceptance

- A single requirements file routes to direct implementation, while explicit full-directory create and repair requests route to VDD.
- Typed decisions accept all three kinds and valid acyclic dependencies, and reject invalid dependency graphs.
- Same-hash init resumes idempotently; drift is byte-preserving stale; invalidate and reopen obey their state boundaries.
- Legacy hash inspection succeeds only on exact bytes and never changes those bytes.
- Sensitive input produces only sanitized quarantine metadata for current state and never exposes the original value.
- Tests prove no event-chain, registry/lock, signature, generation, pointer, or promotion implementation was added.
- The VDD package validator, all VDD unit tests, and the two Windows CI commands pass.

## 7. Delivery Boundary

Implement this as a small self-hosted Quick Dev change. Targeted tests shall stabilize routing and clarification-state behavior before one final package validation and full VDD unit-test discovery. Do not run Bootstrap Review unless the maintainer separately requests it.
